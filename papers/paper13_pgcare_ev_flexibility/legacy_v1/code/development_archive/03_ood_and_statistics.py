from pathlib import Path
import json, time, platform, sys
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, matthews_corrcoef, precision_recall_fscore_support
from xgboost import XGBClassifier, XGBRegressor
from lightgbm import Booster

ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data'; R=ROOT/'results'; R.mkdir(exist_ok=True)
SEED=1793; IDLE,G2V,V2G=0,1,2; DT=.25; SPD=96; H=4; L=8
z=np.load(D/'digital_twin_arrays.npz'); agg=pd.read_csv(D/'aggregate_timeseries.csv')
soc0,state0,conn0,pev0,ttd0,req0=z['soc'],z['state'],z['conn'],z['pev'],z['ttd'],z['req']
cap,charger,min_soc,target,policy=z['cap'],z['charger'],z['min_soc'],z['target'],z['policy']
T0,N=soc0.shape; DAYS0=T0//SPD; tr_end=int(.60*DAYS0)*SPD
native0=agg.native_kw.to_numpy('f4'); price0=agg.price.to_numpy('f4')
lmu,ls=native0[:tr_end].mean(),native0[:tr_end].std(); pmu,ps=price0[:tr_end].mean(),price0[:tr_end].std()

# ---------- Shifted 90-day OOD digital twin ----------
rng=np.random.default_rng(SEED+1000); DAYS=90; T=DAYS*SPD
idx=np.arange(T); day=idx//SPD; hour=(idx%SPD)*DT; dow=day%7; doy=(275+day)%365
mor=np.exp(-.5*((hour-7.0)/1.6)**2); eve=np.exp(-.5*((hour-20.2)/2.0)**2); mid=.30*np.exp(-.5*((hour-13)/3.0)**2)
season=1.10+.13*np.cos(2*np.pi*(doy-10)/365); weekend=np.where(dow>=5,.95+.10*mid,1.)
eps=rng.normal(0,.07,T); ar=np.zeros(T)
for k in range(1,T): ar[k]=.90*ar[k-1]+eps[k]
event=np.ones(T)
for d in rng.choice(DAYS,size=16,replace=False):
    s=d*SPD+rng.integers(66,84); event[s:min(T,s+rng.integers(6,18))]*=rng.uniform(1.18,1.45)
base=N*(.62+.42*mor+1.08*eve+mid)*season*weekend*np.clip(1+ar,.70,1.40)*event
solar=np.maximum(0,np.sin(np.pi*(hour-6)/12))**1.7; pvseason=.45+.40*np.sin(np.pi*(doy+40)/365)**2
pv=.95*N*solar*pvseason*np.repeat(rng.beta(4,2.5,DAYS),SPD); native=np.maximum(base-pv,-.20*N)
price=np.clip(.11+.045*((hour>=7)&(hour<16))+.17*((hour>=16)&(hour<22))+.025*np.sin(2*np.pi*doy/365)+rng.normal(0,.007,T),.06,None)
# Shifted mobility: later arrival, earlier departure, longer trips, more day-to-day variance.
arr=np.zeros((DAYS,N),'f4'); dep=np.zeros((DAYS,N),'f4'); trip=np.zeros((DAYS,N),'f4'); reqd=np.zeros((DAYS,N),'f4')
for d in range(DAYS):
    wk=d%7>=5
    arr[d]=np.clip(rng.normal(19.2 if wk else 18.8,2.0,N),13,23.75)
    dep[d]=np.clip(rng.normal(8.0 if wk else 6.7,1.25,N),4.0,11.5)
    trip[d]=np.clip(rng.lognormal(np.log(13 if wk else 18),.52,N),2,55)
    reqd[d]=np.clip(target+rng.normal(.015,.035,N),.72,.97)
q25=np.zeros(DAYS,'f4'); q75=np.zeros(DAYS,'f4')
for d in range(DAYS):
    sl=slice(d*SPD,(d+1)*SPD); hist=slice((d-1)*SPD,d*SPD) if d>0 else sl
    q25[d],q75[d]=np.quantile(native[hist],[.25,.75])
soc=np.zeros((T,N),'f4'); state=np.zeros((T,N),'i1'); conn=np.zeros((T,N),'u1'); pev=np.zeros((T,N),'f4'); ttd=np.zeros((T,N),'f4'); req=np.zeros((T,N),'f4')
prev=np.clip(rng.beta(4.5,3.3,N)*.65+.18,.16,.95).astype('f4'); last=np.zeros(N,bool)
eta_c=np.full(N,.93,dtype='f4'); eta_d=np.full(N,.93,dtype='f4')
for t in range(T):
    d=int(day[t]); h=hour[t]; c=((h>=arr[d])|(h<dep[d]))&(policy!=0); conn[t]=c
    arriving=c&(~last)&(h>=arr[d]); prev[arriving]=np.maximum(.10,prev[arriving]-trip[d,arriving]/cap[arriving])
    tt=np.where(h<dep[d],dep[d]-h,(24-h)+dep[d]); ttd[t]=tt; req[t]=reqd[d]
    need=np.maximum(0,(reqd[d]-prev)*cap); urgkw=need/np.maximum(tt,DT); urgent=c&(urgkw>.72*charger)
    low=native[t]<q25[d]; high=native[t]>q75[d]; charge_only=c&(policy==1); bi=c&(policy==2)
    must=c&(prev<reqd[d])&(urgent|low|(prev<min_soc+.04)); can=bi&(~urgent)&(prev>min_soc+.08)&(need<.55*charger*np.maximum(tt,DT))
    dv=can&high; dc=(charge_only&(prev<reqd[d])&(urgent|low|((h>=0)&(h<6))))|(bi&must); dc&=~dv
    st=np.zeros(N,'i1'); p=np.zeros(N,'f4'); st[dc]=G2V; st[dv]=V2G; p[dc]=charger[dc]; p[dv]=-charger[dv]
    p[(prev>=.985)&(p>0)]=0; p[(prev<=min_soc)&(p<0)]=0; st[p==0]=IDLE
    prev=np.clip(prev+np.where(p>=0,eta_c*p*DT/cap,(p/eta_d)*DT/cap),.10,.99); soc[t]=prev; state[t]=st; pev[t]=p; last=c

np.savez_compressed(D/'ood_shift_arrays.npz', soc=soc, state=state, conn=conn, pev=pev, ttd=ttd, req=req, arr=arr, dep=dep, trip=trip, native=native, price=price, q25=q25, q75=q75)
pd.DataFrame({'step':idx,'day':day,'dow':dow,'doy':doy,'hour':hour,'native_kw':native,'price':price,'q25_kw':q25[day],'q75_kw':q75[day],'connected':conn.sum(1),'idle':(state==0).sum(1),'g2v':(state==1).sum(1),'v2g':(state==2).sum(1),'mean_soc':soc.mean(1),'ev_kw':pev.sum(1),'feeder_kw':native+pev.sum(1)}).to_csv(D/'ood_aggregate_timeseries.csv',index=False)

# ---------- Build OOD 1-hour-ahead samples with frozen in-domain normalization ----------
def make(ts,es):
    M=len(ts); X=np.empty((M,L,16),'f4')
    for j in range(L):
        tj=ts-(L-1-j); st=state[tj,es]
        X[:,j,0]=soc[tj,es]; X[:,j,1]=conn[tj,es]; X[:,j,2]=(st==0); X[:,j,3]=(st==1); X[:,j,4]=(st==2)
        X[:,j,5]=np.minimum(ttd[tj,es],24)/24; X[:,j,6]=req[tj,es]; X[:,j,7]=(native[tj]-lmu)/ls; X[:,j,8]=(price[tj]-pmu)/ps
        X[:,j,9]=np.sin(2*np.pi*hour[tj]/24); X[:,j,10]=np.cos(2*np.pi*hour[tj]/24)
        X[:,j,11]=(native[tj]-q25[day[tj]])/np.maximum(q75[day[tj]]-q25[day[tj]],1e-3)
        X[:,j,12]=cap[es]/100; X[:,j,13]=charger[es]/11; X[:,j,14]=min_soc[es]; X[:,j,15]=policy[es]/2
    tf=ts+H; y=state[tf,es].astype('i8'); ys=soc[tf,es]; c=conn[tf,es].astype(bool)
    up=(c&(policy[es]==2)&(ys>min_soc[es]+.06))*charger[es]
    return X,y,up.astype('f4')
rr=np.random.default_rng(SEED+1001); M=30000
ts=rr.integers(L-1,T-H,M); es=rr.integers(0,N,M); X,y,up=make(ts,es); Xf=X.reshape(M,-1)
xgb=XGBClassifier(); xgb.load_model(R/'xgb_classifier.json'); probs=xgb.predict_proba(Xf); raw=probs.argmax(1)
summary=json.load(open(R/'study_summary.json')); thr=float(summary['conformal_threshold']); risk=float(summary['risk_calibration_factor'])

def physics_mask(P):
    p=P.copy(); tf=ts+H; fc=conn[tf,es].astype(bool); p[~fc,1:]=0; p[policy[es]!=2,2]=0
    maxgain=charger[es]*H*DT*.93/cap[es]; p[soc[ts,es]+maxgain<=min_soc[es]+.06,2]=0
    s=p.sum(1,keepdims=True); s[s==0]=1; return p/s
pm=physics_mask(probs); phy=pm.argmax(1); ss=(pm>=thr).sum(1); safe=phy.copy(); amb=ss!=1
if amb.any():
    ta,ea=ts[amb],es[amb]; need=np.maximum(0,(req[ta,ea]-soc[ta,ea])*cap[ea]); urg=need/np.maximum(ttd[ta,ea],DT)>.72*charger[ea]
    safe[amb]=np.where(conn[ta,ea].astype(bool)&urg,G2V,IDLE)

def met(lbl,p):
    _,_,f,_=precision_recall_fscore_support(lbl,p,labels=[0,1,2],zero_division=0)
    return dict(accuracy=accuracy_score(lbl,p),balanced_accuracy=balanced_accuracy_score(lbl,p),macro_f1=f1_score(lbl,p,average='macro'),mcc=matthews_corrcoef(lbl,p),idle_f1=f[0],g2v_f1=f[1],v2g_f1=f[2])
ood_rows=[{'model':'XGBoost',**met(y,raw)},{'model':'XGB + physics',**met(y,phy)},{'model':'PG-CARE (XGB)',**met(y,safe)}]
# Frozen LightGBM model and its validation-calibrated conformal threshold.
lgb=Booster(model_file=str(R/'lightgbm_classifier.txt')); Pl=lgb.predict(Xf); Plm=physics_mask(Pl); lraw=Pl.argmax(1); lphy=Plm.argmax(1); lthr=float(summary.get('lgbm_conformal_threshold',thr)); lsafe=lphy.copy(); lamb=(Plm>=lthr).sum(1)!=1
if lamb.any():
    ta,ea=ts[lamb],es[lamb]; need=np.maximum(0,(req[ta,ea]-soc[ta,ea])*cap[ea]); urg=need/np.maximum(ttd[ta,ea],DT)>.72*charger[ea]; lsafe[lamb]=np.where(conn[ta,ea].astype(bool)&urg,G2V,IDLE)
ood_rows += [{'model':'LightGBM',**met(y,lraw)},{'model':'LightGBM + physics',**met(y,lphy)},{'model':'PG-CARE (LightGBM)',**met(y,lsafe)}]
ood=pd.DataFrame(ood_rows); ood.to_csv(R/'ood_shift_metrics.csv',index=False)

# OOD reserve-value check using frozen XGB flexibility model and frozen risk factor.
xu=XGBRegressor(); xu.load_model(R/'xgb_upflex.json'); pred=np.maximum(0,xu.predict(Xf)); ft=ts+H
tmp=pd.DataFrame({'t':ft,'true':up,'xgb':pred}).groupby('t').mean()*N; tmp['proposed']=risk*tmp.xgb
tids=tmp.index.to_numpy(); request=np.where(native[tids]>q75[day[tids]],.12*N*np.mean(charger),0.0); actual=tmp.true.to_numpy()
def op(pred,label):
    commit=np.minimum(pred,request); delivered=np.minimum(commit,actual); short=np.maximum(0,commit-actual); h=DT
    return {'strategy':label,'reserve_revenue_$':float((delivered*h*.18).sum()),'shortfall_penalty_$':float((short*h*.55).sum()),'net_value_$':float((delivered*h*.18-short*h*.55).sum()),'delivered_mwh':float((delivered*h).sum()/1000),'shortfall_mwh':float((short*h).sum()/1000),'flex_rmse_kw':float(np.sqrt(np.mean((pred-actual)**2)))}
oodop=pd.DataFrame([op(tmp.xgb.to_numpy(),'XGBoost raw'),op(tmp.proposed.to_numpy(),'PG-CARE risk-calibrated'),op(actual,'Oracle')]); oodop.to_csv(R/'ood_closed_loop_metrics.csv',index=False)
json.dump({'ood_days':DAYS,'ood_samples':M,'idle_fraction':float((state==0).mean()),'g2v_fraction':float((state==1).mean()),'v2g_fraction':float((state==2).mean()),'xgb_conformal_coverage':float(np.mean(pm[np.arange(M),y]>=thr)),'xgb_ambiguous_fraction':float(amb.mean()),'lgbm_conformal_coverage':float(np.mean(Plm[np.arange(M),y]>=lthr)),'lgbm_ambiguous_fraction':float(lamb.mean())},open(R/'ood_summary.json','w'),indent=2)

# ---------- Bootstrap CIs on original test audit sample ----------
a=pd.read_csv(R/'prediction_audit_sample.csv'); yy=a.true.to_numpy(int); bx=a.xgb.to_numpy(int); bp=a.proposed.to_numpy(int)
br=np.random.default_rng(SEED+2000); B=1000; rec=[]
for name,pred in [('XGBoost',bx),('PG-CARE full',bp)]:
    mf=[]; mc=[]; vf=[]
    for _ in range(B):
        ii=br.integers(0,len(yy),len(yy)); mf.append(f1_score(yy[ii],pred[ii],average='macro')); mc.append(matthews_corrcoef(yy[ii],pred[ii])); vf.append(f1_score(yy[ii],pred[ii],labels=[2],average='macro',zero_division=0))
    rec.append({'model':name,'metric':'macro_f1','estimate':f1_score(yy,pred,average='macro'),'ci_low':np.quantile(mf,.025),'ci_high':np.quantile(mf,.975)})
    rec.append({'model':name,'metric':'mcc','estimate':matthews_corrcoef(yy,pred),'ci_low':np.quantile(mc,.025),'ci_high':np.quantile(mc,.975)})
    rec.append({'model':name,'metric':'v2g_f1','estimate':f1_score(yy,pred,labels=[2],average='macro',zero_division=0),'ci_low':np.quantile(vf,.025),'ci_high':np.quantile(vf,.975)})
pd.DataFrame(rec).to_csv(R/'bootstrap_ci.csv',index=False)

# ---------- Battery-throughput cost sensitivity ----------
ops=pd.read_csv(R/'closed_loop_metrics.csv'); costs=[]
for c in [0.00,.03,.06,.10]:
    for _,row in ops[ops.strategy.isin(['XGBoost','PG-CARE risk-calibrated','Oracle'])].iterrows():
        degradation=row.delivered_mwh*1000*c
        costs.append({'strategy':row.strategy,'throughput_cost_$/kWh':c,'gross_net_value_$':row['net_value_$'],'throughput_cost_$':degradation,'net_after_throughput_$':row['net_value_$']-degradation})
pd.DataFrame(costs).to_csv(R/'throughput_cost_sensitivity.csv',index=False)

with open(R/'system_info.txt','w') as f:
    f.write(f'Python: {sys.version}\nPlatform: {platform.platform()}\nProcessor: {platform.processor()}\n')
    try:
        import sklearn,xgboost,torch,pandas,numpy
        f.write(f'numpy: {numpy.__version__}\npandas: {pandas.__version__}\nscikit-learn: {sklearn.__version__}\nxgboost: {xgboost.__version__}\ntorch: {torch.__version__}\n')
    except Exception as e: f.write(str(e))
print('OOD metrics\n',ood.to_string(index=False)); print('\nOOD operation\n',oodop.to_string(index=False)); print('\nBootstrap\n',pd.DataFrame(rec).to_string(index=False))
