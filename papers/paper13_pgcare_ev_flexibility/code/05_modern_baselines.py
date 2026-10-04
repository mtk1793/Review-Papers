from pathlib import Path
import time,json,numpy as np,pandas as pd
from sklearn.metrics import accuracy_score,balanced_accuracy_score,f1_score,matthews_corrcoef,precision_recall_fscore_support
from lightgbm import LGBMClassifier
from catboost import CatBoostClassifier
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data'; R=ROOT/'results'; SEED=1793; SPD=96; H=4; L=8
z=np.load(D/'digital_twin_arrays.npz'); agg=pd.read_csv(D/'aggregate_timeseries.csv'); sp=np.load(R/'split_indices.npz')
soc,state,conn,ttd,req=z['soc'],z['state'],z['conn'],z['ttd'],z['req']; cap,charger,min_soc,policy=z['cap'],z['charger'],z['min_soc'],z['policy']; T,N=soc.shape; DAYS=T//SPD
native=agg.native_kw.to_numpy('f4'); price=agg.price.to_numpy('f4'); hour=agg.hour.to_numpy('f4'); q25=agg.q25_kw.to_numpy('f4'); q75=agg.q75_kw.to_numpy('f4'); tr_end=int(.6*DAYS)*SPD
lmu,ls=native[:tr_end].mean(),native[:tr_end].std(); pmu,ps=price[:tr_end].mean(),price[:tr_end].std()
def build(ts,es):
 M=len(ts); X=np.empty((M,L,16),'f4')
 for j in range(L):
  tj=ts-(L-1-j); st=state[tj,es]
  X[:,j,0]=soc[tj,es]; X[:,j,1]=conn[tj,es]; X[:,j,2]=(st==0); X[:,j,3]=(st==1); X[:,j,4]=(st==2); X[:,j,5]=np.minimum(ttd[tj,es],24)/24; X[:,j,6]=req[tj,es]; X[:,j,7]=(native[tj]-lmu)/ls; X[:,j,8]=(price[tj]-pmu)/ps; X[:,j,9]=np.sin(2*np.pi*hour[tj]/24); X[:,j,10]=np.cos(2*np.pi*hour[tj]/24); X[:,j,11]=(native[tj]-q25[tj])/np.maximum(q75[tj]-q25[tj],1e-3); X[:,j,12]=cap[es]/100; X[:,j,13]=charger[es]/11; X[:,j,14]=min_soc[es]; X[:,j,15]=policy[es]/2
 return X.reshape(M,-1),state[ts+H,es].astype(int)
def met(y,p):
 _,_,f,_=precision_recall_fscore_support(y,p,labels=[0,1,2],zero_division=0); return dict(accuracy=accuracy_score(y,p),balanced_accuracy=balanced_accuracy_score(y,p),macro_f1=f1_score(y,p,average='macro'),mcc=matthews_corrcoef(y,p),idle_f1=f[0],g2v_f1=f[1],v2g_f1=f[2])
Xtr,ytr=build(sp['train_t'],sp['train_ev']); Xt,yt=build(sp['test_t'],sp['test_ev']); cnt=np.bincount(ytr,minlength=3); cw=len(ytr)/(3*np.maximum(cnt,1)); sw=cw[ytr]
rows=[]
t=time.perf_counter(); lgb=LGBMClassifier(n_estimators=160,num_leaves=31,max_depth=-1,learning_rate=.05,subsample=.85,colsample_bytree=.8,random_state=SEED,n_jobs=8,verbosity=-1); lgb.fit(Xtr,ytr,sample_weight=sw); rows.append({'model':'LightGBM','train_s':time.perf_counter()-t,**met(yt,lgb.predict(Xt))}); lgb.booster_.save_model(str(R/'lightgbm_classifier.txt'))
t=time.perf_counter(); cat=CatBoostClassifier(iterations=180,depth=7,learning_rate=.07,loss_function='MultiClass',random_seed=SEED,verbose=False,thread_count=8); cat.fit(Xtr,ytr,sample_weight=sw); rows.append({'model':'CatBoost','train_s':time.perf_counter()-t,**met(yt,cat.predict(Xt).ravel().astype(int))}); cat.save_model(str(R/'catboost_classifier.cbm'))
pd.DataFrame(rows).to_csv(R/'modern_baselines.csv',index=False); print(pd.DataFrame(rows).to_string(index=False))
