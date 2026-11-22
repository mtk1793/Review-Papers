#!/usr/bin/env python3
"""SYNTHETIC SOFTWARE SMOKE TEST ONLY. NEVER CITABLE SCIENTIFIC RESULTS."""
import json,sys
from pathlib import Path
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'src'))
from h2bench.physics import Plant,HydrogenEnv,wind_to_power
from h2bench.evaluate import evaluate_controller,metrics,paired_block_bootstrap
from h2bench.forecast import fit_quantile_lstm,predict_quantiles,make_windows,conformal_radius,score_forecast
from h2bench.train import train_hierarchy

def main():
    rng=np.random.default_rng(177);n=1000
    # Deliberately simulated oscillatory winds, NOT historical Guyborough.
    v=np.maximum(0,9+3*np.sin(np.arange(n)/25)+rng.normal(0,1.5,n))
    wind=np.asarray([wind_to_power(x) for x in v])
    model=fit_quantile_lstm(wind[:550],epochs=1,hidden=12,lookback=12,horizon=2)
    q=predict_quantiles(model,wind[550:800],lookback=12,horizon=2)
    _,target=make_windows(wind[550:800]/700.,lookback=12,horizon=2)
    radius=conformal_radius(target*700.,q[:,0],q[:,2])
    fscore=score_forecast(target*700.,q,radius)
    sac,qr=train_hierarchy(wind[:650],steps=240,seed=11)
    p=Plant()
    a=evaluate_controller(wind[650:],'curtailment_only')
    b=evaluate_controller(wind[650:],'hierarchical',sac=sac,qr=qr)
    ma=metrics(a,p);mb=metrics(b,p)
    comp=paired_block_bootstrap(b.reward_usd.values-a.reward_usd.values,block_size=24,reps=200)
    report={'dataset_kind':'SYNTHETIC_TEST_FIXTURE','not_scientific_validation':True,
      'forecast_calibration_software_test':fscore,'baseline':ma,'hierarchy':mb,
      'paired_bootstrap_software_test':comp,'algorithms':'LSTM quantile, double-critic SAC, 51-quantile QR-DQN',
      'RL_training_steps':240,'RL_training_step_count_is_insufficient_for_claiming_convergence':True}
    out=root/'results'/'smoke_results.json';out.write_text(json.dumps(report,indent=2))
    print('SMOKE PASS. Generated',out)
if __name__=='__main__':main()
