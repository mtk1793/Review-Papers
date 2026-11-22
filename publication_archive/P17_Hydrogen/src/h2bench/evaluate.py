"""Controlled dispatch baselines, statistical uncertainty, and auditable metrics."""
import numpy as np
import pandas as pd
from .physics import HydrogenEnv

def feature_vec(wind_mw,predicted_mw,env,price_usd_mwh=42.,low=None,high=None):
    p=env.p
    if low is None:low=predicted_mw
    if high is None:high=predicted_mw
    return np.asarray([wind_mw/p.wind_capacity_mw,predicted_mw/p.wind_capacity_mw,
        low/p.wind_capacity_mw,high/p.wind_capacity_mw,price_usd_mwh/200.,env.soc_mwh/max(p.bess_energy_mwh,1e-9),
        env.h2_kg/max(p.h2_tank_capacity_kg,1e-9),
        env.previous_mw/p.electrolyzer_capacity_mw],dtype=np.float32)

def battery_request(action,env,wind):
    if action==1: return env.p.bess_power_mw # store priority
    if action==0:return -env.p.bess_power_mw # hydrogen priority, discharge buffer if required
    return 0. # export priority

def target_mw(action,elec_fraction,env):
    if action==2:return 0. # export
    if action==1:return .2*env.p.electrolyzer_capacity_mw*elec_fraction
    return env.p.electrolyzer_capacity_mw*elec_fraction

def evaluate_controller(wind_mw,policy='curtailment_only',sac=None,qr=None,prediction=None,plant=None,market=None,dt_hours=.25):
    env=HydrogenEnv(plant=plant,market=market,dt_hours=dt_hours)
    n=len(wind_mw);rows=[]
    for i,w in enumerate(wind_mw):
        if prediction is None:lo=pred=hi=float(w)
        else:
            item=np.asarray(prediction[i])
            if item.ndim==0:lo=pred=hi=float(item)
            else:lo,pred,hi=map(float,item)
        s=feature_vec(w,pred,env,low=lo,high=hi)
        action=0
        if policy=='no_electrolysis':action=2;fraction=0.
        elif policy=='curtailment_only':fraction=1. if w>env.p.export_limit_mw else 0.
        elif policy=='fixed_50pct':fraction=.5
        elif policy=='single_sac':fraction=sac.choose(np.r_[s,[0.]],deterministic=True)
        elif policy=='hierarchical':
            action=qr.choose(s,epsilon=0.,risk_frac=.25)
            fraction=sac.choose(np.r_[s,[action/2.]],deterministic=True)
        else:raise ValueError('unknown controller '+policy)
        # no 'perfect forecast' labels for operations using current observed wind
        target=target_mw(action,fraction,env)
        rec=env.step(float(w),target,battery_request(action,env,w))
        rec['step']=i;rec['market_action']=action;rec['forecast_mw']=pred;rec['forecast_low_mw']=lo;rec['forecast_high_mw']=hi
        rows.append(rec)
    return pd.DataFrame(rows)

def metrics(df,plant,dt_hours=.25):
    wind_mwh=float(df.wind_mw.sum()*dt_hours)
    utilized_mwh=float(df.electrolyzer_mw.sum()*dt_hours)
    # Direct electrolyzer supplied from wind or BESS: energy routed from wind is
    # not simply all electrolyzer draw if BESS discharges; report separately.
    sold_kg=float(df.delivered_kg.sum());produced_kg=float(df.produced_kg.sum())
    curtail_mwh=float(df.curtail_mw.sum()*dt_hours)
    return {'n_steps':int(len(df)),'wind_mwh':wind_mwh,
      'electrolyzer_input_mwh':utilized_mwh,
      'electrolyzer_capacity_factor':utilized_mwh/(plant.electrolyzer_capacity_mw*dt_hours*len(df)),
      'curtailment_mwh':curtail_mwh,
      'production_kg':produced_kg,'delivery_kg':sold_kg,
      'gross_cash_usd':float(df.cash_usd.sum()),'wear_charge_usd':float(df.wear_charge_usd.sum()),
      'scenario_net_usd':float(df.reward_usd.sum()),
      'equivalent_aging_hours':float(df.wear_eq_hours.sum()),
      'num_starts':int(df.started.sum()),
      'max_balance_error_mw':float(df.balance_error_mw.abs().max()),
      'note':'scenario net is NOT NPV; does not include full CAPEX, financing, maintenance, transport or tax'}

def paired_block_bootstrap(diff,block_size=96,reps=2000,seed=42):
    """Paired circular-block resampling, CI of mean difference.
    Blocks reduce but cannot eliminate dependence bias; test sensitivity to block length.
    """
    x=np.asarray(diff,dtype=float)
    if x.ndim!=1 or len(x)<max(2*block_size,20):
        raise ValueError('not enough paired held-out observations for block bootstrap')
    rng=np.random.default_rng(seed);n=len(x)
    b=np.empty(reps)
    blocks=int(np.ceil(n/block_size))
    for j in range(reps):
        start=rng.integers(0,n,size=blocks)
        idx=(start[:,None]+np.arange(block_size)[None,:])%n
        b[j]=x[idx.ravel()[:n]].mean()
    lo,hi=np.quantile(b,[.025,.975]);observed=float(x.mean())
    # two-sided bootstrap sign probability (descriptive, not a gold-standard hypothesis test)
    p=min(1.,2*min(float((b<=0).mean()),float((b>=0).mean())))
    return {'mean_difference':observed,'ci95_low':float(lo),'ci95_high':float(hi),
            'bootstrap_sign_p_approx':p,'block_size_steps':block_size,'reps':reps}
