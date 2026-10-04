import json,time,math
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import accuracy_score,balanced_accuracy_score,f1_score,matthews_corrcoef,precision_recall_fscore_support,mean_absolute_error
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier,XGBRegressor
import torch, torch.nn as nn
from torch.utils.data import TensorDataset,DataLoader
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data'; R=ROOT/'results'; R.mkdir(exist_ok=True)
z=np.load(D/'digital_twin_arrays.npz'); agg=pd.read_csv(D/'aggregate_timeseries.csv')
soc,state,conn,ttd,req=z['soc'],z['state'],z['conn'],z['ttd'],z['req']; cap,charger,min_soc,policy=z['cap'],z['charger'],z['min_soc'],z['policy']
T,N=soc.shape; SPD=96; DAYS=T//SPD; H=4; L=8; SEED=1793
native=agg.native_kw.to_numpy('f4'); price=agg.price.to_numpy('f4'); hour=agg.hour.to_numpy('f4'); day=agg.day.to_numpy('i4'); q25=agg.q25_kw.to_numpy('f4'); q75=agg.q75_kw.to_numpy('f4')
tr_end=int(.6*DAYS)*SPD; va_end=int(.8*DAYS)*SPD; lmu,ls=native[:tr_end].mean(),native[:tr_end].std(); pmu,ps=price[:tr_end].mean(),price[:tr_end].std()
def sample(lo,hi,n,seed):
 r=np.random.default_rng(seed); return r.integers(max(lo,L-1),min(hi-H,T-H),n),r.integers(0,N,n)
def make(ts,es):
 M=len(ts); X=np.empty((M,L,16),'f4')
 for j in range(L):
  tj=ts-(L-1-j); st=state[tj,es]
  X[:,j,0]=soc[tj,es]; X[:,j,1]=conn[tj,es]; X[:,j,2]=(st==0); X[:,j,3]=(st==1); X[:,j,4]=(st==2); X[:,j,5]=np.minimum(ttd[tj,es],24)/24; X[:,j,6]=req[tj,es]; X[:,j,7]=(native[tj]-lmu)/ls; X[:,j,8]=(price[tj]-pmu)/ps; X[:,j,9]=np.sin(2*np.pi*hour[tj]/24); X[:,j,10]=np.cos(2*np.pi*hour[tj]/24); X[:,j,11]=(native[tj]-q25[tj])/np.maximum(q75[tj]-q25[tj],1e-3); X[:,j,12]=cap[es]/100; X[:,j,13]=charger[es]/11; X[:,j,14]=min_soc[es]; X[:,j,15]=policy[es]/2
 tf=ts+H; y=state[tf,es].astype('i8'); ys=soc[tf,es].astype('f4'); c=conn[tf,es].astype(bool); up=(c&(policy[es]==2)&(ys>min_soc[es]+.06))*charger[es]; dn=(c&(ys<req[tf,es]-.01))*charger[es]
 return X,y,ys,up.astype('f4'),dn.astype('f4')
sizes={'train':30000,'val':10000,'test':20000}; periods={'train':(0,tr_end),'val':(tr_end,va_end),'test':(va_end,T)}; S={}
for k,(a,b) in periods.items():
 ts,es=sample(a,b,sizes[k],SEED+len(k)); S[k]=(ts,es,*make(ts,es)); print(k,np.bincount(S[k][3],minlength=3))
Xtr=S['train'][2].reshape(sizes['train'],-1); Xv=S['val'][2].reshape(sizes['val'],-1); Xt=S['test'][2].reshape(sizes['test'],-1); ytr,yv,yt=S['train'][3],S['val'][3],S['test'][3]
def met(y,p):
 _,_,f,_=precision_recall_fscore_support(y,p,labels=[0,1,2],zero_division=0); return dict(accuracy=accuracy_score(y,p),balanced_accuracy=balanced_accuracy_score(y,p),macro_f1=f1_score(y,p,average='macro'),mcc=matthews_corrcoef(y,p),idle_f1=f[0],g2v_f1=f[1],v2g_f1=f[2])
rows=[{'model':'Persistence',**met(yt,S['test'][2][:,-1,2:5].argmax(1))}]; timing={}
lr=LogisticRegression(max_iter=160,class_weight='balanced',solver='lbfgs'); t=time.perf_counter(); lr.fit(Xtr[:18000],ytr[:18000]); timing['logistic_train_s']=time.perf_counter()-t; rows.append({'model':'Logistic Regression',**met(yt,lr.predict(Xt))})
rf=RandomForestClassifier(n_estimators=35,max_depth=12,min_samples_leaf=2,class_weight='balanced_subsample',n_jobs=-1,random_state=SEED); t=time.perf_counter(); rf.fit(Xtr[:25000],ytr[:25000]); timing['rf_train_s']=time.perf_counter()-t; rows.append({'model':'Random Forest',**met(yt,rf.predict(Xt))})
cnt=np.bincount(ytr,minlength=3); cw=len(ytr)/(3*np.maximum(cnt,1)); sw=cw[ytr]
xgb=XGBClassifier(n_estimators=65,max_depth=5,learning_rate=.10,subsample=.85,colsample_bytree=.8,objective='multi:softprob',num_class=3,eval_metric='mlogloss',tree_method='hist',n_jobs=8,random_state=SEED); t=time.perf_counter(); xgb.fit(Xtr,ytr,sample_weight=sw); timing['xgb_train_s']=time.perf_counter()-t; px=xgb.predict(Xt); rows.append({'model':'XGBoost',**met(yt,px)})
# lightweight temporal convolutional mixture-of-experts with multi-task heads
class TCMoE(nn.Module):
 def __init__(self):
  super().__init__(); self.conv=nn.Sequential(nn.Conv1d(16,32,3,padding=1),nn.GELU(),nn.Conv1d(32,32,3,padding=1),nn.GELU()); self.gate=nn.Sequential(nn.Linear(32,24),nn.GELU(),nn.Linear(24,3)); self.experts=nn.ModuleList([nn.Sequential(nn.Linear(32,32),nn.GELU(),nn.Linear(32,6)) for _ in range(3)])
 def forward(self,x):
  h=self.conv(x.transpose(1,2)).mean(-1); w=torch.softmax(self.gate(h),-1); o=torch.stack([e(h) for e in self.experts],1); o=(w[:,:,None]*o).sum(1); return o[:,:3],o[:,3:],w
device='cuda' if torch.cuda.is_available() else 'cpu'; torch.manual_seed(SEED); m=TCMoE().to(device); opt=torch.optim.AdamW(m.parameters(),lr=.0025,weight_decay=1e-4); CE=nn.CrossEntropyLoss(weight=torch.tensor(cw,dtype=torch.float32,device=device)); hub=nn.SmoothL1Loss()
Rtr=np.c_[S['train'][4],S['train'][5]/11,S['train'][6]/11].astype('f4'); Rv=np.c_[S['val'][4],S['val'][5]/11,S['val'][6]/11].astype('f4'); Rt=np.c_[S['test'][4],S['test'][5]/11,S['test'][6]/11].astype('f4')
dl=DataLoader(TensorDataset(torch.from_numpy(S['train'][2]),torch.from_numpy(ytr),torch.from_numpy(Rtr)),batch_size=2048,shuffle=True)
t=time.perf_counter()
for ep in range(12):
 m.train(); tot=0
 for xb,yb,rb in dl:
  xb,yb,rb=xb.to(device),yb.to(device),rb.to(device); opt.zero_grad(); lo,re,_=m(xb); loss=CE(lo,yb)+.45*hub(re[:,0],rb[:,0])+.20*hub(re[:,1:],rb[:,1:]); loss.backward(); opt.step(); tot+=loss.item()*len(xb)
 print('epoch',ep,'loss',tot/len(dl.dataset))
timing['tcmoe_train_s']=time.perf_counter()-t
def npred(X):
 P=[];RR=[];G=[]; xx=torch.from_numpy(X); m.eval(); t=time.perf_counter()
 with torch.no_grad():
  for s in range(0,len(xx),4096):
   lo,re,g=m(xx[s:s+4096].to(device)); P.append(torch.softmax(lo,-1).cpu().numpy()); RR.append(re.cpu().numpy()); G.append(g.cpu().numpy())
 return np.vstack(P),np.vstack(RR),np.vstack(G),time.perf_counter()-t
Pv,Rvh,Gv,_=npred(S['val'][2]); Pt,Rth,Gt,inf=npred(S['test'][2]); timing['tcmoe_infer_ms_per_sample']=1000*inf/len(Pt); Xvp=xgb.predict_proba(Xv); Xtp=xgb.predict_proba(Xt)
bw,bf=0,-1
for w in np.linspace(0,1,11):
 f=f1_score(yv,(w*Pv+(1-w)*Xvp).argmax(1),average='macro')
 if f>bf: bf,bw=f,float(w)
Pve=bw*Pv+(1-bw)*Xvp; Pte=bw*Pt+(1-bw)*Xtp
def mask(P,ts,es):
 p=P.copy(); tf=ts+H; fc=conn[tf,es].astype(bool); p[~fc,1:]=0; p[policy[es]!=2,2]=0; maxgain=charger[es]*H*.25*.93/cap[es]; p[soc[ts,es]+maxgain<=min_soc[es]+.06,2]=0; s=p.sum(1,keepdims=True); s[s==0]=1; return p/s
Pvm=mask(Pve,S['val'][0],S['val'][1]); Ptm=mask(Pte,S['test'][0],S['test'][1]); raw=Pte.argmax(1); phy=Ptm.argmax(1)
nc=1-Pvm[np.arange(len(yv)),yv]; q=np.quantile(nc,.90,method='higher'); thr=1-q; ss=(Ptm>=thr).sum(1); safe=phy.copy(); amb=ss!=1
if amb.any():
 ts,es=S['test'][0][amb],S['test'][1][amb]; need=np.maximum(0,(req[ts,es]-soc[ts,es])*cap[es]); urg=need/np.maximum(ttd[ts,es],.25)>.72*charger[es]; safe[amb]=np.where(conn[ts,es].astype(bool)&urg,1,0)
rows += [{'model':'TC-MoE alone',**met(yt,Pt.argmax(1))},{'model':'PG-CARE expert fusion',**met(yt,raw)},{'model':'PG-CARE + physics',**met(yt,phy)},{'model':'PG-CARE (full)',**met(yt,safe)}]
# regressors and operational value
xu=XGBRegressor(n_estimators=50,max_depth=5,learning_rate=.10,tree_method='hist',n_jobs=8,random_state=SEED); xd=XGBRegressor(n_estimators=50,max_depth=5,learning_rate=.10,tree_method='hist',n_jobs=8,random_state=SEED+1); xs=XGBRegressor(n_estimators=45,max_depth=5,learning_rate=.10,tree_method='hist',n_jobs=8,random_state=SEED+2)
xu.fit(Xtr,S['train'][5]); xd.fit(Xtr,S['train'][6]); xs.fit(Xtr,S['train'][4]); pu=np.maximum(0,xu.predict(Xt)); pdn=np.maximum(0,xd.predict(Xt)); psoc=xs.predict(Xt)
reg=pd.DataFrame([['XGB','SOC',mean_absolute_error(S['test'][4],psoc)],['TC-MoE','SOC',mean_absolute_error(S['test'][4],Rth[:,0])],['XGB','UpFlex_kW',mean_absolute_error(S['test'][5],pu)],['TC-MoE','UpFlex_kW',mean_absolute_error(S['test'][5],Rth[:,1]*11)],['XGB','DownFlex_kW',mean_absolute_error(S['test'][6],pdn)],['TC-MoE','DownFlex_kW',mean_absolute_error(S['test'][6],Rth[:,2]*11)]],columns=['model','target','mae'])
# Decision-aware risk calibration for flexibility. The scaling factor is selected only on validation data
# to maximize reserve value under asymmetric shortfall penalties; it is then frozen for test.
uv=np.maximum(0,xu.predict(Xv)); ftv=S['val'][0]+H; tv=pd.DataFrame({'t':ftv,'true':S['val'][5],'xgb':uv}).groupby('t').mean()*N; tv_t=tv.index.to_numpy(); reqv=np.where(native[tv_t]>q75[tv_t],.12*N*np.mean(charger),0.0); av=tv.true.to_numpy()
def economic_value(pred, actual, request):
    c=np.minimum(pred,request); d=np.minimum(c,actual); sh=np.maximum(0,c-actual); return float((d*.25*.18-sh*.25*.55).sum())
risk_grid=np.linspace(.10,1.00,19); risk_factor=max(risk_grid,key=lambda f:economic_value(f*tv.xgb.to_numpy(),av,reqv));
# sampled aggregate by target time
ft=S['test'][0]+H; tmp=pd.DataFrame({'t':ft,'true':S['test'][5],'xgb':pu}).groupby('t').mean()*N; tmp['proposed']=risk_factor*tmp['xgb']; tids=tmp.index.to_numpy(); request=np.where(native[tids]>q75[tids],.12*N*np.mean(charger),0.0); actual=tmp.true.to_numpy()
def op(pred,label):
 commit=np.minimum(pred,request); delivered=np.minimum(commit,actual); short=np.maximum(0,commit-actual); h=.25; before=native[tids]; after=before-delivered; return {'strategy':label,'reserve_revenue_$':float((delivered*h*.18).sum()),'shortfall_penalty_$':float((short*h*.55).sum()),'net_value_$':float((delivered*h*.18-short*h*.55).sum()),'delivered_mwh':float((delivered*h).sum()/1000),'shortfall_mwh':float((short*h).sum()/1000),'peak_reduction_kw':float(before.max()-after.max()),'flex_rmse_kw':float(np.sqrt(np.mean((pred-actual)**2)))}
ops=pd.DataFrame([op(np.zeros_like(actual),'No forecast'),op(np.roll(actual,4),'Persistence'),op(tmp.xgb.to_numpy(),'XGBoost'),op(tmp.proposed.to_numpy(),'PG-CARE risk-calibrated'),op(actual,'Oracle')])
summary={'simulated_days':DAYS,'ev_count':N,'ev_time_states':int(T*N),'idle_fraction':float((state==0).mean()),'g2v_fraction':float((state==1).mean()),'v2g_fraction':float((state==2).mean()),'annual_g2v_mwh':float(np.maximum(z['pev'],0).sum()*.25/1000),'annual_v2g_mwh':float((-np.minimum(z['pev'],0)).sum()*.25/1000),'native_peak_kw':float(native.max()),'controller_peak_kw':float((native+z['pev'].sum(1)).max()),'transformer_like_temporal_weight':bw,'risk_calibration_factor':float(risk_factor),'conformal_threshold':float(thr),'conformal_coverage':float(np.mean(Ptm[np.arange(len(yt)),yt]>=thr)),'ambiguous_fraction':float(amb.mean()),**timing}
pd.DataFrame(rows).to_csv(R/'classification_metrics.csv',index=False); reg.to_csv(R/'regression_metrics.csv',index=False); ops.to_csv(R/'closed_loop_metrics.csv',index=False); json.dump(summary,open(R/'study_summary.json','w'),indent=2)
pd.DataFrame({'t':S['test'][0][:10000],'ev':S['test'][1][:10000],'true':yt[:10000],'xgb':px[:10000],'proposed':safe[:10000],'p_idle':Ptm[:10000,0],'p_g2v':Ptm[:10000,1],'p_v2g':Ptm[:10000,2]}).to_csv(R/'prediction_audit_sample.csv',index=False)
np.savez_compressed(R/'split_indices.npz',train_t=S['train'][0],train_ev=S['train'][1],val_t=S['val'][0],val_ev=S['val'][1],test_t=S['test'][0],test_ev=S['test'][1]); torch.save({'state_dict':m.state_dict(),'H':H,'L':L},R/'tcmoe.pt'); xgb.save_model(R/'xgb_classifier.json'); xu.save_model(R/'xgb_upflex.json'); xd.save_model(R/'xgb_downflex.json')
print('\n',pd.DataFrame(rows).to_string(index=False)); print('\n',reg.to_string(index=False)); print('\n',ops.to_string(index=False)); print('\n',json.dumps(summary,indent=2))
