"""Benchmark software-side inference cost for the frozen final models.
These are CPU software timings, not embedded-controller or HIL latency claims.
"""
from pathlib import Path
import time
import numpy as np
import pandas as pd
from lightgbm import Booster
from xgboost import XGBRegressor
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data'; R=ROOT/'results'
z=np.load(D/'digital_twin_arrays.npz'); agg=pd.read_csv(D/'aggregate_timeseries.csv'); sp=np.load(R/'split_indices.npz')
soc,state,conn,ttd,req=z['soc'],z['state'],z['conn'],z['ttd'],z['req']; cap,charger,min_soc,policy=z['cap'],z['charger'],z['min_soc'],z['policy']
T,N=soc.shape; DAYS=T//96; H=4; L=8
native=agg.native_kw.to_numpy('f4'); price=agg.price.to_numpy('f4'); hour=agg.hour.to_numpy('f4'); q25=agg.q25_kw.to_numpy('f4'); q75=agg.q75_kw.to_numpy('f4'); tr_end=int(.6*DAYS)*96
lmu,ls=native[:tr_end].mean(),native[:tr_end].std(); pmu,ps=price[:tr_end].mean(),price[:tr_end].std()
def build(ts,es):
    M=len(ts); X=np.empty((M,L,16),'f4')
    for j in range(L):
        tj=ts-(L-1-j); st=state[tj,es]
        X[:,j,0]=soc[tj,es]; X[:,j,1]=conn[tj,es]; X[:,j,2]=(st==0); X[:,j,3]=(st==1); X[:,j,4]=(st==2)
        X[:,j,5]=np.minimum(ttd[tj,es],24)/24; X[:,j,6]=req[tj,es]; X[:,j,7]=(native[tj]-lmu)/ls; X[:,j,8]=(price[tj]-pmu)/ps
        X[:,j,9]=np.sin(2*np.pi*hour[tj]/24); X[:,j,10]=np.cos(2*np.pi*hour[tj]/24); X[:,j,11]=(native[tj]-q25[tj])/np.maximum(q75[tj]-q25[tj],1e-3)
        X[:,j,12]=cap[es]/100; X[:,j,13]=charger[es]/11; X[:,j,14]=min_soc[es]; X[:,j,15]=policy[es]/2
    return X.reshape(M,-1)
X=build(sp['test_t'],sp['test_ev'])
lgb=Booster(model_file=str(R/'lightgbm_classifier.txt')); xu=XGBRegressor(); xu.load_model(R/'xgb_upflex.json')
lgb.predict(X[:100]); xu.predict(X[:100])
rows=[]
for name,fn in [('LightGBM classifier',lambda:lgb.predict(X)),('XGBoost flexibility',lambda:xu.predict(X))]:
    vals=[]
    for _ in range(10):
        t=time.perf_counter(); fn(); vals.append(time.perf_counter()-t)
    med=float(np.median(vals))
    rows.append({'component':name,'samples':len(X),'median_total_ms':med*1000,'median_us_per_sample':med/len(X)*1e6})
pd.DataFrame(rows).to_csv(R/'inference_timing.csv',index=False)
print(pd.DataFrame(rows).to_string(index=False))
