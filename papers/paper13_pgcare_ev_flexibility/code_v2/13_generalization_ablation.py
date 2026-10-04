from pathlib import Path
import json, numpy as np, pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import accuracy_score,balanced_accuracy_score,f1_score,matthews_corrcoef,precision_recall_fscore_support
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data_v2'; R=ROOT/'results_v2'; SEED=1793; SPD=96; H=4; L=8; F=17
z=np.load(D/'digital_twin_v2.npz'); agg=pd.read_csv(D/'aggregate_timeseries_v2.csv')
soc,state,conn,dec_ttd,dec_conn_h1,req=[z[k] for k in ['soc','state','conn','dec_ttd','dec_conn_h1','req']]; cap,charger,min_soc,policy=[z[k] for k in ['cap','charger','min_soc','policy']]
native=agg.native_kw.to_numpy('f4'); price=agg.price.to_numpy('f4'); hour=agg.hour.to_numpy('f4'); q25=agg.q25_kw.to_numpy('f4'); q75=agg.q75_kw.to_numpy('f4'); T,N=soc.shape
lmu,ls=native[:200*SPD].mean(),native[:200*SPD].std(); pmu,ps=price[:200*SPD].mean(),price[:200*SPD].std()
def build(ts,es):
 M=len(ts); X=np.empty((M,L,F),'f4')
 for j in range(L):
  tj=ts-(L-1-j); st=state[tj,es]
  X[:,j,0]=soc[tj,es];X[:,j,1]=conn[tj,es];X[:,j,2]=(st==0);X[:,j,3]=(st==1);X[:,j,4]=(st==2);X[:,j,5]=np.minimum(dec_ttd[tj,es],24)/24;X[:,j,6]=req[tj,es];X[:,j,7]=(native[tj]-lmu)/ls;X[:,j,8]=(price[tj]-pmu)/ps;X[:,j,9]=np.sin(2*np.pi*hour[tj]/24);X[:,j,10]=np.cos(2*np.pi*hour[tj]/24);X[:,j,11]=(native[tj]-q25[tj])/np.maximum(q75[tj]-q25[tj],1e-3);X[:,j,12]=cap[es]/100;X[:,j,13]=charger[es]/11;X[:,j,14]=min_soc[es];X[:,j,15]=policy[es]/2;X[:,j,16]=dec_conn_h1[tj,es]
 return X.reshape(M,-1),state[ts+H,es].astype(int)
def met(y,p):
 _,_,f,_=precision_recall_fscore_support(y,p,labels=[0,1,2],zero_division=0);return {'accuracy':accuracy_score(y,p),'balanced_accuracy':balanced_accuracy_score(y,p),'macro_f1':f1_score(y,p,average='macro'),'mcc':matthews_corrcoef(y,p),'idle_f1':f[0],'g2v_f1':f[1],'v2g_f1':f[2]}
def cols(chans): return np.array([j*F+c for j in range(L) for c in chans],int)
r=np.random.default_rng(SEED+50); tr_t=r.integers(L-1,200*SPD-H,50000); tr_e=r.integers(0,80,50000); Xtr,ytr=build(tr_t,tr_e); cnt=np.bincount(ytr,minlength=3); sw=(len(ytr)/(3*np.maximum(cnt,1)))[ytr]
issue=np.arange(280*SPD,T-H,4,dtype=int); te_t=np.repeat(issue,20); te_e=np.tile(np.arange(80,100),len(issue)); Xte,yte=build(te_t,te_e)
# Frozen unseen-EV training/evaluation: no EV identity is used, but all training examples are from EVs 0-79.
m=LGBMClassifier(n_estimators=180,num_leaves=47,learning_rate=.035,subsample=.88,colsample_bytree=.82,min_child_samples=30,random_state=SEED,n_jobs=-1,verbosity=-1);m.fit(Xtr,ytr,sample_weight=sw); unseen=met(yte,m.predict(Xte)); pd.DataFrame([{'test':'unseen EVs 80-99',**unseen}]).to_csv(R/'v2_unseen_ev_metrics.csv',index=False)
# Feature group ablation on same unseen-EV protocol.
groups={'full':list(range(17)),'no_static_identity':[0,1,2,3,4,5,6,7,8,9,10,11,15,16],'no_declared_schedule':[0,1,2,3,4,6,7,8,9,10,11,12,13,14,15],'dynamic_only':[0,1,2,3,4,7,8,9,10,11]}
rows=[]
for name,ch in groups.items():
 c=cols(ch); mm=LGBMClassifier(n_estimators=135,num_leaves=39,learning_rate=.04,random_state=SEED,n_jobs=-1,verbosity=-1);mm.fit(Xtr[:,c],ytr,sample_weight=sw);rows.append({'feature_set':name,'n_channels':len(ch),**met(yte,mm.predict(Xte[:,c]))})
pd.DataFrame(rows).to_csv(R/'v2_feature_group_ablation.csv',index=False)
# Schedule-declaration corruption stress applied to frozen full model: flip declared_conn_h1 and jitter declared_ttd feature in test X.
Xs=Xte.copy(); rr=np.random.default_rng(SEED+51); # flattened channel locations
for j in range(L):
 flip=rr.random(len(Xs))<.12; k=j*F+16; Xs[flip,k]=1-Xs[flip,k]; kt=j*F+5; Xs[:,kt]=np.clip(Xs[:,kt]+rr.normal(0,.06,len(Xs)),0,1)
stress=met(yte,m.predict(Xs)); pd.DataFrame([{'test':'clean unseen-EV','schedule_flip_rate':0,**unseen},{'test':'12% declaration corruption','schedule_flip_rate':.12,**stress}]).to_csv(R/'v2_schedule_stress.csv',index=False)
print('Unseen EV',unseen);print(pd.DataFrame(rows).to_string(index=False));print('Stress',stress)
