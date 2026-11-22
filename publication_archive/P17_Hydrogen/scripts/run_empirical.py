#!/usr/bin/env python3
"""Real-data experiment. Fails closed if source data/provenance are absent.

Outcomes are conditional on price/export/turbine assumptions; cannot be
presented as true NS historical curtailment, market-clearing or NPV outcomes.
"""
import json,sys,hashlib,argparse
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
from h2bench.ingest import validate_coverage,enforce_temporal_splits
from h2bench.physics import Plant,Market,technical_upper_bound_annual_mwh
from h2bench.forecast import fit_quantile_lstm,make_windows,predict_quantiles,conformal_radius,score_forecast
from h2bench.train import train_hierarchy,train_single_sac
from h2bench.evaluate import evaluate_controller,metrics,paired_block_bootstrap

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',default='config/experiment.json');ap.add_argument('--run-lp-mpc',action='store_true');args=ap.parse_args()
    cfg=json.loads((root/args.config).read_text())
    path=root/cfg['data_paths']['wind_csv'];provenance=root/cfg['data_paths']['provenance']
    if not path.exists() or not provenance.exists():
        raise SystemExit('BLOCKED: real source CSV and provenance absent. Run matching dataset downloader first; no synthetic data accepted.')
    meta=json.loads(provenance.read_text())
    if meta.get('provider')!=cfg['dataset']['provider']:
        raise SystemExit('DATASET CONFIG MISMATCH: expected '+cfg['dataset']['provider']+'; found '+str(meta.get('provider')))
    df=pd.read_csv(path,parse_dates=['timestamp_utc'])
    df['year']=df.timestamp_utc.dt.year
    if df.timestamp_utc.dt.tz is None:raise ValueError('timestamps must include UTC offset')
    qc=validate_coverage(df,cfg['dataset']['interval_minutes'])
    if qc['nonconsecutive_steps'] or qc['missing_values'] or qc['duplicate_timestamps']:
        raise ValueError('Dataset QC failed: '+str(qc))
    train,cal,test=enforce_temporal_splits(df,cfg['dataset']['train_years'],cfg['dataset']['calibration_year'],cfg['dataset']['test_year'])
    p=Plant(**cfg['plant']);m=Market(**{k:v for k,v in cfg['market'].items() if k in Market.__dataclass_fields__})
    L=cfg['learning']['lookback_steps'];H=cfg['learning']['forecast_horizon_steps']
    model=fit_quantile_lstm(train.wind_mw.values,epochs=cfg['learning']['lstm_epochs'],lookback=L,horizon=H,hidden=cfg['learning']['lstm_hidden'])
    calq=predict_quantiles(model,cal.wind_mw.values,lookback=L,horizon=H)
    _,cy=make_windows(cal.wind_mw.values/700.,L,H);cy=cy*700.
    radius=conformal_radius(cy,calq[:,0],calq[:,2])
    tq=predict_quantiles(model,test.wind_mw.values,L,H)
    _,ty=make_windows(test.wind_mw.values/700.,L,H);ty=ty*700.
    score=score_forecast(ty,tq,radius)
    pred=np.column_stack([test.wind_mw.values]*3).astype(float)
    trpred=np.column_stack([train.wind_mw.values]*3).astype(float)
    trainq=predict_quantiles(model,train.wind_mw.values,L,H)
    trpred[L:L+len(trainq),:]=trainq
    trpred[:,0]=np.maximum(0,trpred[:,0]-radius)
    trpred[:,2]=np.minimum(p.wind_capacity_mw,trpred[:,2]+radius)
    # For decisions at t>=L, most recent forecast is a horizon-H forecast.
    # Arrays align at decision time, not target time, and do NOT include test future observations.
    pred[L:L+len(tq),:]=tq
    pred[:,0]=np.maximum(0,pred[:,0]-radius)
    pred[:,2]=np.minimum(p.wind_capacity_mw,pred[:,2]+radius)
    methods={'curtailment_only':evaluate_controller(test.wind_mw.values,'curtailment_only',plant=p,market=m,dt_hours=cfg['dataset']['interval_minutes']/60),
             'fixed_50pct':evaluate_controller(test.wind_mw.values,'fixed_50pct',plant=p,market=m,dt_hours=cfg['dataset']['interval_minutes']/60),
             'no_electrolysis':evaluate_controller(test.wind_mw.values,'no_electrolysis',plant=p,market=m,dt_hours=cfg['dataset']['interval_minutes']/60)}
    main_results={name:metrics(dfm,p,cfg['dataset']['interval_minutes']/60) for name,dfm in methods.items()}
    by_seed={}
    for seed in cfg['learning']['rl_seeds']:
        sac,qr=train_hierarchy(train.wind_mw.values,steps=cfg['learning']['rl_train_steps'],seed=seed,plant=p,market=m,dt_hours=cfg['dataset']['interval_minutes']/60,forecast=trpred)
        hierarchical=evaluate_controller(test.wind_mw.values,'hierarchical',sac=sac,qr=qr,prediction=pred,plant=p,market=m,dt_hours=cfg['dataset']['interval_minutes']/60)
        single_agent=train_single_sac(train.wind_mw.values,steps=cfg['learning']['rl_train_steps']//2,seed=seed,plant=p,market=m,dt_hours=cfg['dataset']['interval_minutes']/60,forecast=trpred)
        single=evaluate_controller(test.wind_mw.values,'single_sac',sac=single_agent,prediction=pred,plant=p,market=m,dt_hours=cfg['dataset']['interval_minutes']/60)
        by_seed[seed]={'hierarchical':metrics(hierarchical,p,cfg['dataset']['interval_minutes']/60),'single_sac':metrics(single,p,cfg['dataset']['interval_minutes']/60)}
        hierarchical.to_csv(root/'results'/f'holdout_hierarchy_seed_{seed}.csv',index=False)
        if seed==cfg['learning']['rl_seeds'][0]:
            comparison=paired_block_bootstrap(hierarchical.reward_usd.values-methods['curtailment_only'].reward_usd.values,
                block_size=cfg['learning']['bootstrap_block_steps'],reps=cfg['learning']['bootstrap_reps'])
    if args.run_lp_mpc:
        from h2bench.mpc import evaluate_lp_mpc
        mpc=evaluate_lp_mpc(test.wind_mw.values,horizon=8,plant=p,market=m,dt_hours=cfg['dataset']['interval_minutes']/60)
        methods['lp_mpc_persistence_forecast']=mpc
        main_results['lp_mpc_persistence_forecast']=metrics(mpc,p,cfg['dataset']['interval_minutes']/60)
    for name,dfm in methods.items():dfm.to_csv(root/'results'/f'holdout_{name}.csv',index=False)
    all_h=np.asarray([by_seed[s]['hierarchical']['scenario_net_usd'] for s in cfg['learning']['rl_seeds']])
    if len(all_h)<2:raise ValueError('at least 2 random seeds required')
    seed_t_ci=stats.t.interval(.95,len(all_h)-1,loc=all_h.mean(),scale=stats.sem(all_h))
    report={'data':'REAL source meteorological reanalysis, wind output derived via assumed generic power curve',
       'dataset_provider':meta,'data_file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
       'time_split':{'train':cfg['dataset']['train_years'],'calibration':cfg['dataset']['calibration_year'],'test':cfg['dataset']['test_year']},
       'quality':qc,'forecast':score,'calibration_radius_mw':radius,'baselines':main_results,
       'trained_by_seed':by_seed,'seed_mean_net_usd':float(all_h.mean()),'seed_t_ci95_net_usd':list(map(float,seed_t_ci)),
       'paired_block_bootstrap_hierarchy_vs_curtailment_only':comparison,
       'technical_electrolyzer_max_mwh_366d':technical_upper_bound_annual_mwh(p.electrolyzer_capacity_mw,8784),
       'not_historical_hydrogen_market_or_AC_powerflow':True,
       'not_full_technoeconomic_NPV':True,
       'deployment_ready':False}
    (root/'results'/'empirical_results.json').write_text(json.dumps(report,indent=2))
    print('EMPIRICAL EXPERIMENT COMPLETE: actual dataset validated; check results/empirical_results.json')
if __name__=='__main__':main()
