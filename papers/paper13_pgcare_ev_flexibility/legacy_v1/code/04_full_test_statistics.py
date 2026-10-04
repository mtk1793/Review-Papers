from pathlib import Path
import json, numpy as np, pandas as pd
from sklearn.metrics import f1_score,matthews_corrcoef
from xgboost import XGBClassifier
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data'; R=ROOT/'results'
SEED=1793; SPD=96; H=4; L=8; DT=.25; IDLE,G2V,V2G=0,1,2
z=np.load(D/'digital_twin_arrays.npz'); agg=pd.read_csv(D/'aggregate_timeseries.csv'); sp=np.load(R/'split_indices.npz')
soc,state,conn,ttd,req=z['soc'],z['state'],z['conn'],z['ttd'],z['req']; cap,charger,min_soc,policy=z['cap'],z['charger'],z['min_soc'],z['policy']; T,N=soc.shape; DAYS=T//SPD
native=agg.native_kw.to_numpy('f4'); price=agg.price.to_numpy('f4'); hour=agg.hour.to_numpy('f4'); q25=agg.q25_kw.to_numpy('f4'); q75=agg.q75_kw.to_numpy('f4'); tr_end=int(.6*DAYS)*SPD
lmu,ls=native[:tr_end].mean(),native[:tr_end].std(); pmu,ps=price[:tr_end].mean(),price[:tr_end].std()
ts,es=sp['test_t'],sp['test_ev']; M=len(ts); X=np.empty((M,L,16),'f4')
for j in range(L):
    tj=ts-(L-1-j); st=state[tj,es]
    X[:,j,0]=soc[tj,es]; X[:,j,1]=conn[tj,es]; X[:,j,2]=(st==0); X[:,j,3]=(st==1); X[:,j,4]=(st==2); X[:,j,5]=np.minimum(ttd[tj,es],24)/24; X[:,j,6]=req[tj,es]
    X[:,j,7]=(native[tj]-lmu)/ls; X[:,j,8]=(price[tj]-pmu)/ps; X[:,j,9]=np.sin(2*np.pi*hour[tj]/24); X[:,j,10]=np.cos(2*np.pi*hour[tj]/24); X[:,j,11]=(native[tj]-q25[tj])/np.maximum(q75[tj]-q25[tj],1e-3); X[:,j,12]=cap[es]/100; X[:,j,13]=charger[es]/11; X[:,j,14]=min_soc[es]; X[:,j,15]=policy[es]/2
y=state[ts+H,es].astype(int)
xgb=XGBClassifier(); xgb.load_model(R/'xgb_classifier.json'); P=xgb.predict_proba(X.reshape(M,-1)); px=P.argmax(1)
# physics mask
p=P.copy(); tf=ts+H; fc=conn[tf,es].astype(bool); p[~fc,1:]=0; p[policy[es]!=2,2]=0; maxgain=charger[es]*H*DT*.93/cap[es]; p[soc[ts,es]+maxgain<=min_soc[es]+.06,2]=0; s=p.sum(1,keepdims=True); s[s==0]=1; p=p/s
summ=json.load(open(R/'study_summary.json')); thr=float(summ['conformal_threshold']); safe=p.argmax(1); amb=(p>=thr).sum(1)!=1
if amb.any():
    ta,ea=ts[amb],es[amb]; need=np.maximum(0,(req[ta,ea]-soc[ta,ea])*cap[ea]); urg=need/np.maximum(ttd[ta,ea],DT)>.72*charger[ea]; safe[amb]=np.where(conn[ta,ea].astype(bool)&urg,G2V,IDLE)
pd.DataFrame({'t':ts,'ev':es,'true':y,'xgb':px,'proposed':safe,'p_idle':p[:,0],'p_g2v':p[:,1],'p_v2g':p[:,2]}).to_csv(R/'prediction_audit_full_test.csv',index=False)
rng=np.random.default_rng(SEED+2000); B=1000; rec=[]; diffs=[]
def metrics(yy,pp):
    return f1_score(yy,pp,average='macro'),matthews_corrcoef(yy,pp),f1_score(yy,pp,labels=[2],average='macro',zero_division=0)
for name,pred in [('XGBoost',px),('PG-CARE full',safe)]:
    vals=np.empty((B,3))
    for b in range(B):
        ii=rng.integers(0,M,M); vals[b]=metrics(y[ii],pred[ii])
    est=metrics(y,pred)
    for k,metric in enumerate(['macro_f1','mcc','v2g_f1']): rec.append({'model':name,'metric':metric,'estimate':est[k],'ci_low':np.quantile(vals[:,k],.025),'ci_high':np.quantile(vals[:,k],.975)})
# paired bootstrap PG-CARE minus XGB
vals=np.empty((B,3))
for b in range(B):
    ii=rng.integers(0,M,M); a=metrics(y[ii],safe[ii]); x=metrics(y[ii],px[ii]); vals[b]=np.array(a)-np.array(x)
for k,metric in enumerate(['macro_f1','mcc','v2g_f1']): diffs.append({'metric':metric,'delta_estimate':metrics(y,safe)[k]-metrics(y,px)[k],'ci_low':np.quantile(vals[:,k],.025),'ci_high':np.quantile(vals[:,k],.975)})
pd.DataFrame(rec).to_csv(R/'bootstrap_ci.csv',index=False); pd.DataFrame(diffs).to_csv(R/'paired_bootstrap_deltas.csv',index=False)
print(pd.DataFrame(rec).to_string(index=False)); print(pd.DataFrame(diffs).to_string(index=False))
