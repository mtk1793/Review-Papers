from pathlib import Path
import json,numpy as np,pandas as pd
from sklearn.metrics import accuracy_score,balanced_accuracy_score,f1_score,matthews_corrcoef,precision_recall_fscore_support
from lightgbm import Booster
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'data';R=ROOT/'results';SEED=1793;SPD=96;H=4;L=8;DT=.25;IDLE,G2V,V2G=0,1,2
z=np.load(D/'digital_twin_arrays.npz');agg=pd.read_csv(D/'aggregate_timeseries.csv');sp=np.load(R/'split_indices.npz')
soc,state,conn,ttd,req=z['soc'],z['state'],z['conn'],z['ttd'],z['req'];cap,charger,min_soc,policy=z['cap'],z['charger'],z['min_soc'],z['policy'];T,N=soc.shape;DAYS=T//SPD
native=agg.native_kw.to_numpy('f4');price=agg.price.to_numpy('f4');hour=agg.hour.to_numpy('f4');q25=agg.q25_kw.to_numpy('f4');q75=agg.q75_kw.to_numpy('f4');tr_end=int(.6*DAYS)*SPD
lmu,ls=native[:tr_end].mean(),native[:tr_end].std();pmu,ps=price[:tr_end].mean(),price[:tr_end].std()
def build(ts,es):
 M=len(ts);X=np.empty((M,L,16),'f4')
 for j in range(L):
  tj=ts-(L-1-j);st=state[tj,es];X[:,j,0]=soc[tj,es];X[:,j,1]=conn[tj,es];X[:,j,2]=(st==0);X[:,j,3]=(st==1);X[:,j,4]=(st==2);X[:,j,5]=np.minimum(ttd[tj,es],24)/24;X[:,j,6]=req[tj,es];X[:,j,7]=(native[tj]-lmu)/ls;X[:,j,8]=(price[tj]-pmu)/ps;X[:,j,9]=np.sin(2*np.pi*hour[tj]/24);X[:,j,10]=np.cos(2*np.pi*hour[tj]/24);X[:,j,11]=(native[tj]-q25[tj])/np.maximum(q75[tj]-q25[tj],1e-3);X[:,j,12]=cap[es]/100;X[:,j,13]=charger[es]/11;X[:,j,14]=min_soc[es];X[:,j,15]=policy[es]/2
 return X.reshape(M,-1),state[ts+H,es].astype(int)
def mask(P,ts,es):
 p=P.copy();tf=ts+H;fc=conn[tf,es].astype(bool);p[~fc,1:]=0;p[policy[es]!=2,2]=0;maxgain=charger[es]*H*DT*.93/cap[es];p[soc[ts,es]+maxgain<=min_soc[es]+.06,2]=0;s=p.sum(1,keepdims=True);s[s==0]=1;return p/s
def met(y,p):
 _,_,f,_=precision_recall_fscore_support(y,p,labels=[0,1,2],zero_division=0);return dict(accuracy=accuracy_score(y,p),balanced_accuracy=balanced_accuracy_score(y,p),macro_f1=f1_score(y,p,average='macro'),mcc=matthews_corrcoef(y,p),idle_f1=f[0],g2v_f1=f[1],v2g_f1=f[2])
b=Booster(model_file=str(R/'lightgbm_classifier.txt'))
Xv,yv=build(sp['val_t'],sp['val_ev']);Xt,yt=build(sp['test_t'],sp['test_ev']);Pv=b.predict(Xv);Pt=b.predict(Xt);Pvm=mask(Pv,sp['val_t'],sp['val_ev']);Ptm=mask(Pt,sp['test_t'],sp['test_ev']);nc=1-Pvm[np.arange(len(yv)),yv];q=np.quantile(nc,.90,method='higher');thr=1-q;phy=Ptm.argmax(1);safe=phy.copy();amb=(Ptm>=thr).sum(1)!=1
if amb.any():
 ts,es=sp['test_t'][amb],sp['test_ev'][amb];need=np.maximum(0,(req[ts,es]-soc[ts,es])*cap[es]);urg=need/np.maximum(ttd[ts,es],DT)>.72*charger[es];safe[amb]=np.where(conn[ts,es].astype(bool)&urg,G2V,IDLE)
rows=pd.DataFrame([{'model':'LightGBM',**met(yt,Pt.argmax(1))},{'model':'LightGBM + physics',**met(yt,phy)},{'model':'PG-CARE (LightGBM+physics+conformal)',**met(yt,safe)}]);rows.to_csv(R/'pgcare_lgbm_metrics.csv',index=False)
upd=json.load(open(R/'study_summary.json'));upd['lgbm_conformal_threshold']=float(thr);upd['lgbm_conformal_coverage']=float(np.mean(Ptm[np.arange(len(yt)),yt]>=thr));upd['lgbm_ambiguous_fraction']=float(amb.mean());json.dump(upd,open(R/'study_summary.json','w'),indent=2)
pd.DataFrame({'t':sp['test_t'],'ev':sp['test_ev'],'true':yt,'lgbm':Pt.argmax(1),'pgcare_lgbm':safe,'p_idle':Ptm[:,0],'p_g2v':Ptm[:,1],'p_v2g':Ptm[:,2]}).to_csv(R/'prediction_audit_lgbm_full_test.csv',index=False)
print(rows.to_string(index=False));print('threshold',thr,'coverage',upd['lgbm_conformal_coverage'],'amb',upd['lgbm_ambiguous_fraction'])
