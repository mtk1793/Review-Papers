import os, json, math, time, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, matthews_corrcoef, precision_recall_fscore_support, mean_absolute_error
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from xgboost import XGBClassifier, XGBRegressor
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; RES=ROOT/'results'
DATA.mkdir(exist_ok=True); RES.mkdir(exist_ok=True)
SEED=1793; rng=np.random.default_rng(SEED)
IDLE,G2V,V2G=0,1,2; names=['Idle','G2V','V2G']
N=100; DAYS=365; DT=0.25; SPD=96; T=DAYS*SPD; H=4; L=8
# ---------- Digital twin ----------
idx=np.arange(T); day=idx//SPD; hour=(idx%SPD)*DT; dow=day%7; doy=day%365
mor=np.exp(-.5*((hour-7.5)/1.8)**2); eve=np.exp(-.5*((hour-19)/2.4)**2); mid=.35*np.exp(-.5*((hour-13)/3.2)**2)
season=1+.16*np.cos(2*np.pi*(doy-10)/365)+.05*np.sin(4*np.pi*doy/365); weekend=np.where(dow>=5,.92+.10*mid,1.)
eps=rng.normal(0,.05,T); ar=np.zeros(T)
for k in range(1,T): ar[k]=.92*ar[k-1]+eps[k]
event=np.ones(T)
for d in rng.choice(DAYS,size=36,replace=False):
    s=d*SPD+rng.integers(64,80); event[s:min(T,s+rng.integers(4,16))]*=rng.uniform(1.10,1.35)
base=N*(.55+.45*mor+.95*eve+mid)*season*weekend*np.clip(1+ar,.75,1.30)*event
solar=np.maximum(0,np.sin(np.pi*(hour-6)/12))**1.7; pvseason=.55+.45*np.sin(np.pi*(doy+40)/365)**2
pv=1.2*N*solar*pvseason*np.repeat(rng.beta(5,2,DAYS),SPD); native=np.maximum(base-pv,-.25*N)
price=np.clip(.10+.04*((hour>=7)&(hour<16))+.13*((hour>=16)&(hour<21))+.02*np.sin(2*np.pi*doy/365)+rng.normal(0,.004,T),.06,None)
cap=np.clip(rng.normal(72,16,N),40,120).astype('f4'); charger=rng.choice([7.2,9.6,11.0],N,p=[.45,.25,.30]).astype('f4')
eta_c=rng.uniform(.90,.96,N).astype('f4'); eta_d=rng.uniform(.90,.96,N).astype('f4'); min_soc=rng.uniform(.30,.55,N).astype('f4'); target=rng.uniform(.78,.92,N).astype('f4')
policy=rng.choice([0,1,2],N,p=[.08,.32,.60]).astype('i1')
arr=np.zeros((DAYS,N),'f4'); dep=np.zeros((DAYS,N),'f4'); trip=np.zeros((DAYS,N),'f4'); reqd=np.zeros((DAYS,N),'f4')
for d in range(DAYS):
    wk=d%7>=5; arr[d]=np.clip(rng.normal(18.2 if wk else 17.4,1.7,N),13,23.75); dep[d]=np.clip(rng.normal(8.7 if wk else 7.4,1.1,N),4.5,12)
    trip[d]=np.clip(rng.lognormal(np.log(10 if wk else 14),.48,N),2,45); reqd[d]=np.clip(target+rng.normal(0,.025,N),.72,.95)
q25=np.zeros(DAYS,'f4'); q75=np.zeros(DAYS,'f4')
for d in range(DAYS):
    sl=slice(d*SPD,(d+1)*SPD); hist=slice((d-1)*SPD,d*SPD) if d>0 else sl; q25[d],q75[d]=np.quantile(native[hist],[.25,.75])
soc=np.zeros((T,N),'f4'); state=np.zeros((T,N),'i1'); conn=np.zeros((T,N),'u1'); pev=np.zeros((T,N),'f4'); ttd=np.zeros((T,N),'f4'); req=np.zeros((T,N),'f4')
prev=np.clip(rng.beta(5,3,N)*.65+.20,.20,.95).astype('f4'); last=np.zeros(N,bool)
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
agg=pd.DataFrame({'step':idx,'day':day,'dow':dow,'doy':doy,'hour':hour,'base_load_kw':base,'pv_kw':pv,'native_kw':native,'ev_kw':pev.sum(1),'feeder_kw':native+pev.sum(1),'price':price,'q25_kw':q25[day],'q75_kw':q75[day],'connected':conn.sum(1),'idle':(state==0).sum(1),'g2v':(state==1).sum(1),'v2g':(state==2).sum(1),'mean_soc':soc.mean(1)})
agg.to_csv(DATA/'aggregate_timeseries.csv',index=False)
pd.DataFrame({'ev_id':np.arange(N),'capacity_kwh':cap,'charger_kw':charger,'min_soc':min_soc,'target_soc':target,'policy':policy}).to_csv(DATA/'fleet_parameters.csv',index=False)
np.savez_compressed(DATA/'digital_twin_arrays.npz',soc=soc,state=state,conn=conn,pev=pev,ttd=ttd,req=req,cap=cap,charger=charger,min_soc=min_soc,target=target,policy=policy,arr=arr,dep=dep)
# ---------- ML dataset ----------
train_end=int(.60*DAYS)*SPD; val_end=int(.80*DAYS)*SPD; load_mu=native[:train_end].mean(); load_sd=native[:train_end].std(); pmu=price[:train_end].mean(); psd=price[:train_end].std()
def build(ts,es):
    M=len(ts); X=np.empty((M,L,16),'f4')
    for j in range(L):
        tj=ts-(L-1-j); st=state[tj,es]
        X[:,j,0]=soc[tj,es]; X[:,j,1]=conn[tj,es]; X[:,j,2]=(st==0); X[:,j,3]=(st==1); X[:,j,4]=(st==2); X[:,j,5]=np.minimum(ttd[tj,es],24)/24; X[:,j,6]=req[tj,es]
        X[:,j,7]=(native[tj]-load_mu)/load_sd; X[:,j,8]=(price[tj]-pmu)/psd; X[:,j,9]=np.sin(2*np.pi*hour[tj]/24); X[:,j,10]=np.cos(2*np.pi*hour[tj]/24); X[:,j,11]=(native[tj]-q25[day[tj]])/np.maximum(q75[day[tj]]-q25[day[tj]],1e-3)
        X[:,j,12]=cap[es]/100; X[:,j,13]=charger[es]/11; X[:,j,14]=min_soc[es]; X[:,j,15]=policy[es]/2
    tf=ts+H; y=state[tf,es].astype('i8'); ys=soc[tf,es]; c=conn[tf,es].astype(bool); up=(c&(policy[es]==2)&(ys>min_soc[es]+.06))*charger[es]; dn=(c&(ys<req[tf,es]-.01))*charger[es]
    return X,y,ys,up.astype('f4'),dn.astype('f4')
def sample(lo,hi,n,seed):
    rr=np.random.default_rng(seed); ts=rr.integers(max(lo,L-1),min(hi-H,T-H),n); es=rr.integers(0,N,n); return ts,es
sizes={'train':70000,'val':20000,'test':35000}; periods={'train':(0,train_end),'val':(train_end,val_end),'test':(val_end,T)}; S={}
for k,(lo,hi) in periods.items():
    ts,es=sample(lo,hi,sizes[k],SEED+len(k)); X,y,ys,up,dn=build(ts,es); S[k]=(ts,es,X,y,ys,up,dn); print(k,np.bincount(y,minlength=3))
Xtr=S['train'][2].reshape(sizes['train'],-1); Xv=S['val'][2].reshape(sizes['val'],-1); Xt=S['test'][2].reshape(sizes['test'],-1); ytr=S['train'][3]; yv=S['val'][3]; yt=S['test'][3]
def metr(y,p):
    _,_,f,_=precision_recall_fscore_support(y,p,labels=[0,1,2],zero_division=0)
    return {'accuracy':accuracy_score(y,p),'balanced_accuracy':balanced_accuracy_score(y,p),'macro_f1':f1_score(y,p,average='macro'),'mcc':matthews_corrcoef(y,p),'idle_f1':f[0],'g2v_f1':f[1],'v2g_f1':f[2]}
rows=[{'model':'Persistence',**metr(yt,S['test'][2][:,-1,2:5].argmax(1))}]; timings={}
# logistic
lr=LogisticRegression(max_iter=250,class_weight='balanced',C=1.0); t0=time.perf_counter(); lr.fit(Xtr[:40000],ytr[:40000]); timings['logistic_train_s']=time.perf_counter()-t0; rows.append({'model':'Logistic Regression',**metr(yt,lr.predict(Xt))})
# RF
rf=RandomForestClassifier(n_estimators=45,max_depth=14,min_samples_leaf=2,class_weight='balanced_subsample',n_jobs=-1,random_state=SEED,max_features='sqrt'); t0=time.perf_counter(); rf.fit(Xtr[:50000],ytr[:50000]); timings['rf_train_s']=time.perf_counter()-t0; rows.append({'model':'Random Forest',**metr(yt,rf.predict(Xt))})
# XGB
cnt=np.bincount(ytr,minlength=3); cw=len(ytr)/(3*np.maximum(cnt,1)); sw=cw[ytr]
xgb=XGBClassifier(n_estimators=110,max_depth=6,learning_rate=.08,subsample=.85,colsample_bytree=.8,objective='multi:softprob',num_class=3,eval_metric='mlogloss',tree_method='hist',n_jobs=8,random_state=SEED); t0=time.perf_counter(); xgb.fit(Xtr,ytr,sample_weight=sw,verbose=False); timings['xgb_train_s']=time.perf_counter()-t0; xgbp=xgb.predict(Xt); rows.append({'model':'XGBoost',**metr(yt,xgbp)})
# ---------- PG-TMoE ----------
class Model(nn.Module):
    def __init__(self):
        super().__init__(); dm=24; self.p=nn.Linear(16,dm); self.pos=nn.Parameter(torch.randn(1,L,dm)*.02); layer=nn.TransformerEncoderLayer(dm,4,64,.10,batch_first=True,activation='gelu'); self.e=nn.TransformerEncoder(layer,1); self.g=nn.Sequential(nn.Linear(dm,24),nn.GELU(),nn.Linear(24,3)); self.x=nn.ModuleList([nn.Sequential(nn.Linear(dm,32),nn.GELU(),nn.Linear(32,6)) for _ in range(3)])
    def forward(self,x):
        h=self.e(self.p(x)+self.pos).mean(1); w=torch.softmax(self.g(h),-1); o=torch.stack([e(h) for e in self.x],1); o=(w.unsqueeze(-1)*o).sum(1); return o[:,:3],o[:,3:],w
device='cuda' if torch.cuda.is_available() else 'cpu'; torch.manual_seed(SEED); m=Model().to(device); opt=torch.optim.AdamW(m.parameters(),lr=.002,weight_decay=1e-4); CE=nn.CrossEntropyLoss(weight=torch.tensor(cw,dtype=torch.float32,device=device)); hub=nn.SmoothL1Loss()
Rtr=np.c_[S['train'][4],S['train'][5]/11,S['train'][6]/11].astype('f4'); Rv=np.c_[S['val'][4],S['val'][5]/11,S['val'][6]/11].astype('f4'); Rt=np.c_[S['test'][4],S['test'][5]/11,S['test'][6]/11].astype('f4')
dl=DataLoader(TensorDataset(torch.from_numpy(S['train'][2]),torch.from_numpy(ytr),torch.from_numpy(Rtr)),batch_size=4096,shuffle=True,num_workers=0)
best=None; bestv=9e9; t0=time.perf_counter()
for ep in range(3):
    m.train()
    for xb,yb,rb in dl:
        xb=xb.to(device); yb=yb.to(device); rb=rb.to(device); opt.zero_grad(); lo,re,_=m(xb); loss=CE(lo,yb)+.5*hub(re[:,0],rb[:,0])+.25*hub(re[:,1:],rb[:,1:]); loss.backward(); opt.step()
    m.eval(); vs=0
    with torch.no_grad():
        xv=torch.from_numpy(S['val'][2]); yvt=torch.from_numpy(yv); rvt=torch.from_numpy(Rv)
        for s in range(0,len(xv),8192):
            lo,re,_=m(xv[s:s+8192].to(device)); loss=CE(lo,yvt[s:s+8192].to(device))+.5*hub(re[:,0],rvt[s:s+8192,0].to(device))+.25*hub(re[:,1:],rvt[s:s+8192,1:].to(device)); vs+=loss.item()*len(lo)
    vs/=len(xv); print('epoch',ep,'val',vs)
    if vs<bestv: bestv=vs; best={k:v.detach().cpu().clone() for k,v in m.state_dict().items()}
m.load_state_dict(best); timings['pgtmoe_train_s']=time.perf_counter()-t0
def pred(X):
    P=[];R=[];G=[]; m.eval(); xx=torch.from_numpy(X); t0=time.perf_counter()
    with torch.no_grad():
        for s in range(0,len(xx),8192):
            lo,re,g=m(xx[s:s+8192].to(device)); P.append(torch.softmax(lo,-1).cpu().numpy()); R.append(re.cpu().numpy()); G.append(g.cpu().numpy())
    return np.vstack(P),np.vstack(R),np.vstack(G),time.perf_counter()-t0
Pv,Rvhat,Gv,_=pred(S['val'][2]); Pt,Rthat,Gt,te=pred(S['test'][2]); timings['pgtmoe_infer_ms_per_sample']=1000*te/len(Pt)
# ensemble with XGB probability to stabilize low-data deep model; weight chosen on validation grid.
Xvprob=xgb.predict_proba(Xv); Xtprob=xgb.predict_proba(Xt); bestw=0; bestf=-1
for w in np.linspace(0,1,11):
    pp=w*Pv+(1-w)*Xvprob; ff=f1_score(yv,pp.argmax(1),average='macro')
    if ff>bestf: bestf=ff; bestw=float(w)
Pve=bestw*Pv+(1-bestw)*Xvprob; Pte=bestw*Pt+(1-bestw)*Xtprob
# physics mask

def mask(P,ts,es):
    p=P.copy(); tf=ts+H; future_conn=conn[tf,es].astype(bool); pol=policy[es]; p[~future_conn,1:]=0; p[pol!=2,2]=0; maxgain=charger[es]*H*DT*.93/cap[es]; p[soc[ts,es]+maxgain<=min_soc[es]+.06,2]=0; sm=p.sum(1,keepdims=True); sm[sm==0]=1; return p/sm
Pvm=mask(Pve,S['val'][0],S['val'][1]); Ptm=mask(Pte,S['test'][0],S['test'][1]); raw=Pte.argmax(1); phy=Ptm.argmax(1)
# conformal safety wrapper, alpha=0.1
nc=1-Pvm[np.arange(len(yv)),yv]; q=np.quantile(nc,.90,method='higher'); thr=1-q; setsize=(Ptm>=thr).sum(1); safe=phy.copy(); amb=setsize!=1
if amb.any():
    ts=S['test'][0][amb]; es=S['test'][1][amb]; need=np.maximum(0,(req[ts,es]-soc[ts,es])*cap[es]); urg=need/np.maximum(ttd[ts,es],DT)>.72*charger[es]; safe[amb]=np.where(conn[ts,es].astype(bool)&urg,G2V,IDLE)
rows += [{'model':'PG-TMoE ensemble',**metr(yt,raw)},{'model':'PG-TMoE + physics',**metr(yt,phy)},{'model':'PG-TMoE + physics + conformal',**metr(yt,safe)}]
# regression heads and XGB baselines
xup=XGBRegressor(n_estimators=80,max_depth=5,learning_rate=.08,subsample=.85,colsample_bytree=.8,tree_method='hist',n_jobs=8,random_state=SEED); xdn=XGBRegressor(n_estimators=80,max_depth=5,learning_rate=.08,subsample=.85,colsample_bytree=.8,tree_method='hist',n_jobs=8,random_state=SEED+1); xs=XGBRegressor(n_estimators=70,max_depth=5,learning_rate=.08,tree_method='hist',n_jobs=8,random_state=SEED+2)
xup.fit(Xtr,S['train'][5]); xdn.fit(Xtr,S['train'][6]); xs.fit(Xtr,S['train'][4])
reg=pd.DataFrame([
 {'model':'XGB','target':'SOC','mae':mean_absolute_error(S['test'][4],xs.predict(Xt))}, {'model':'PG-TMoE','target':'SOC','mae':mean_absolute_error(S['test'][4],Rthat[:,0])},
 {'model':'XGB','target':'UpFlex_kW','mae':mean_absolute_error(S['test'][5],xup.predict(Xt))}, {'model':'PG-TMoE','target':'UpFlex_kW','mae':mean_absolute_error(S['test'][5],Rthat[:,1]*11)},
 {'model':'XGB','target':'DownFlex_kW','mae':mean_absolute_error(S['test'][6],xdn.predict(Xt))}, {'model':'PG-TMoE','target':'DownFlex_kW','mae':mean_absolute_error(S['test'][6],Rthat[:,2]*11)}])
# ---------- Closed-loop reserve/peak shaving value on the sampled chronological test set ----------
# Aggregate test samples by forecast target time; use unbiased sampled EV mean * N for actual/predicted up-flex.
target_t=S['test'][0]+H; dfc=pd.DataFrame({'target_t':target_t,'true_up':S['test'][5],'xgb_up':np.maximum(0,xup.predict(Xt)),'pgt_up':np.maximum(0,Rthat[:,1]*11)})
g=dfc.groupby('target_t').mean()*N
# reserve request occurs only during upper-quartile native load; request 12% of fleet nameplate.
req_res=np.where(native[g.index.to_numpy()] > q75[day[g.index.to_numpy()]], .12*N*np.mean(charger), 0.0)
actual=g.true_up.to_numpy(); predx=g.xgb_up.to_numpy(); predp=g.pgt_up.to_numpy()
def dispatch_metrics(pred,name):
    commit=np.minimum(pred,req_res); delivered=np.minimum(commit,actual); short=np.maximum(0,commit-actual); h=DT
    rev=(delivered*h*.18).sum(); penalty=(short*h*.55).sum(); throughput=(delivered*h).sum();
    before=native[g.index.to_numpy()]; after=before-delivered; peak_red=before.max()-after.max(); rmse=np.sqrt(np.mean((pred-actual)**2));
    return {'strategy':name,'reserve_revenue_$':rev,'shortfall_penalty_$':penalty,'net_value_$':rev-penalty,'delivered_mwh':throughput/1000,'shortfall_mwh':(short*h).sum()/1000,'peak_reduction_kw':peak_red,'flex_rmse_kw':rmse}
ops=pd.DataFrame([dispatch_metrics(np.zeros_like(actual),'No forecast commitment'),dispatch_metrics(np.roll(actual,4),'Persistence flexibility'),dispatch_metrics(predx,'XGB flexibility'),dispatch_metrics(predp,'PG-TMoE flexibility'),dispatch_metrics(actual,'Oracle flexibility')])
# Rule-controller fleet energy outcomes from full year.
full={'simulated_days':DAYS,'ev_count':N,'ev_time_states':int(T*N),'idle_fraction':float((state==0).mean()),'g2v_fraction':float((state==1).mean()),'v2g_fraction':float((state==2).mean()),'annual_ev_charge_mwh':float(np.maximum(pev,0).sum()*DT/1000),'annual_v2g_mwh':float((-np.minimum(pev,0)).sum()*DT/1000),'native_peak_kw':float(native.max()),'controlled_peak_kw':float((native+pev.sum(1)).max()),'mean_soc':float(soc.mean()),'train_days':int(.60*DAYS),'validation_days':int(.20*DAYS),'test_days':DAYS-int(.80*DAYS),'transformer_weight':bestw,'conformal_probability_threshold':float(thr),'conformal_empirical_coverage':float(np.mean(Ptm[np.arange(len(yt)),yt]>=thr)),'ambiguous_fraction':float(amb.mean()),'soc_mae':float(mean_absolute_error(S['test'][4],Rthat[:,0]))}
pd.DataFrame(rows).to_csv(RES/'classification_metrics.csv',index=False); reg.to_csv(RES/'regression_metrics.csv',index=False); ops.to_csv(RES/'closed_loop_metrics.csv',index=False); json.dump({**full,**timings},open(RES/'study_summary.json','w'),indent=2)
pd.DataFrame({'t':S['test'][0][:20000],'ev':S['test'][1][:20000],'true':yt[:20000],'xgb':xgbp[:20000],'pgt_raw':raw[:20000],'pgt_physics':phy[:20000],'pgt_safe':safe[:20000],'p_idle':Ptm[:20000,0],'p_g2v':Ptm[:20000,1],'p_v2g':Ptm[:20000,2]}).to_csv(RES/'prediction_audit_sample.csv',index=False)
np.savez_compressed(RES/'split_indices.npz',train_t=S['train'][0],train_ev=S['train'][1],val_t=S['val'][0],val_ev=S['val'][1],test_t=S['test'][0],test_ev=S['test'][1])
torch.save({'state_dict':m.state_dict(),'L':L,'H':H},RES/'pgtmoe.pt'); xgb.save_model(RES/'xgb_classifier.json'); xup.save_model(RES/'xgb_upflex.json'); xdn.save_model(RES/'xgb_downflex.json')
print('\nCLASSIFICATION\n',pd.DataFrame(rows).to_string(index=False)); print('\nREGRESSION\n',reg.to_string(index=False)); print('\nOPS\n',ops.to_string(index=False)); print('\nSUMMARY\n',json.dumps(full,indent=2))
