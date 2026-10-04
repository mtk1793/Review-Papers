from pathlib import Path
import json, time, math
import numpy as np, pandas as pd
from lightgbm import LGBMClassifier,LGBMRegressor, Booster
from sklearn.metrics import (accuracy_score,balanced_accuracy_score,f1_score,matthews_corrcoef,
 precision_recall_fscore_support,roc_auc_score,brier_score_loss,mean_absolute_error,mean_squared_error)
from scipy.stats import binomtest
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data_v2'; R=ROOT/'results_v2'; R.mkdir(exist_ok=True)
SEED=1793; rng=np.random.default_rng(SEED); SPD=96; H=4; L=8; DT=.25; IDLE,G2V,V2G=0,1,2
z=np.load(D/'digital_twin_v2.npz'); agg=pd.read_csv(D/'aggregate_timeseries_v2.csv')
soc,state,conn,ttd,dec_ttd,dec_conn_h1,req=[z[k] for k in ['soc','state','conn','ttd','dec_ttd','dec_conn_h1','req']]
cap,charger,min_soc,policy=[z[k] for k in ['cap','charger','min_soc','policy']]
T,N=soc.shape; DAYS=T//SPD
native=agg.native_kw.to_numpy('f4'); price=agg.price.to_numpy('f4'); hour=agg.hour.to_numpy('f4'); q25=agg.q25_kw.to_numpy('f4'); q75=agg.q75_kw.to_numpy('f4')
# Chronology: model training 0-199 d, calibration 200-239, validation 240-279, test 280-364.
bounds={'train':(0,200*SPD),'cal':(200*SPD,240*SPD),'val':(240*SPD,280*SPD),'test':(280*SPD,T)}
lmu,ls=native[:bounds['train'][1]].mean(),native[:bounds['train'][1]].std(); pmu,ps=price[:bounds['train'][1]].mean(),price[:bounds['train'][1]].std()
F=17
feature_names=['soc','connected_now','idle','g2v','v2g','declared_ttd','req_soc','native_z','price_z','sin_hour','cos_hour','load_quantile_pos','capacity','charger','min_soc','policy','declared_conn_h1']

def build(ts,es,labels=True):
    ts=np.asarray(ts,dtype=np.int32); es=np.asarray(es,dtype=np.int16); M=len(ts); X=np.empty((M,L,F),'f4')
    for j in range(L):
        tj=ts-(L-1-j); st=state[tj,es]
        X[:,j,0]=soc[tj,es]; X[:,j,1]=conn[tj,es]; X[:,j,2]=(st==0); X[:,j,3]=(st==1); X[:,j,4]=(st==2)
        X[:,j,5]=np.minimum(dec_ttd[tj,es],24)/24; X[:,j,6]=req[tj,es]; X[:,j,7]=(native[tj]-lmu)/ls; X[:,j,8]=(price[tj]-pmu)/ps
        X[:,j,9]=np.sin(2*np.pi*hour[tj]/24); X[:,j,10]=np.cos(2*np.pi*hour[tj]/24); X[:,j,11]=(native[tj]-q25[tj])/np.maximum(q75[tj]-q25[tj],1e-3)
        X[:,j,12]=cap[es]/100; X[:,j,13]=charger[es]/11; X[:,j,14]=min_soc[es]; X[:,j,15]=policy[es]/2; X[:,j,16]=dec_conn_h1[tj,es]
    if not labels: return X.reshape(M,-1)
    tf=ts+H; y=state[tf,es].astype('i8'); yc=conn[tf,es].astype('i8'); ys=soc[tf,es].astype('f4')
    up=(yc.astype(bool)&(policy[es]==2)&(ys>min_soc[es]+.06))*charger[es]
    down=(yc.astype(bool)&(ys<req[tf,es]-.01))*charger[es]
    return X.reshape(M,-1),y,yc,ys,up.astype('f4'),down.astype('f4')

def sample(period,n,seed,ev_hi=N,ev_lo=0):
    lo,hi=bounds[period]; rr=np.random.default_rng(seed); ts=rr.integers(max(lo,L-1),min(hi-H,T-H),n,dtype=np.int32); es=rr.integers(ev_lo,ev_hi,n,dtype=np.int16); return ts,es
sizes={'train':60000,'cal':20000,'val':20000}
S={}
for i,k in enumerate(['train','cal','val']):
    ts,es=sample(k,sizes[k],SEED+10+i); S[k]=(ts,es,*build(ts,es)); print(k,np.bincount(S[k][3],minlength=3), 'conn',S[k][4].mean())
Xtr,ytr,yctr=S['train'][2],S['train'][3],S['train'][4]; Xcal,ycal,yccal=S['cal'][2],S['cal'][3],S['cal'][4]; Xv,yv,ycv=S['val'][2],S['val'][3],S['val'][4]
# Class weights.
cnt=np.bincount(ytr,minlength=3); cw=len(ytr)/(3*np.maximum(cnt,1)); sw=cw[ytr]
# Future connectivity model: actual t+H connectivity is a prediction target; declared schedule is only an input.
conn_model=LGBMClassifier(n_estimators=120,num_leaves=31,learning_rate=.05,subsample=.85,colsample_bytree=.85,random_state=SEED,n_jobs=-1,verbosity=-1)
t=time.perf_counter(); conn_model.fit(Xtr,yctr); conn_train_s=time.perf_counter()-t
# State forecaster.
state_model=LGBMClassifier(n_estimators=180,num_leaves=47,max_depth=-1,learning_rate=.035,subsample=.88,colsample_bytree=.82,min_child_samples=30,reg_lambda=.2,random_state=SEED,n_jobs=-1,verbosity=-1)
t=time.perf_counter(); state_model.fit(Xtr,ytr,sample_weight=sw); state_train_s=time.perf_counter()-t
# Flexibility point + quantile regressors. CQR is calibrated later.
up_mean=LGBMRegressor(n_estimators=160,num_leaves=39,learning_rate=.04,subsample=.9,colsample_bytree=.85,objective='regression_l1',random_state=SEED,n_jobs=-1,verbosity=-1)
up_lo=LGBMRegressor(n_estimators=160,num_leaves=39,learning_rate=.04,subsample=.9,colsample_bytree=.85,objective='quantile',alpha=.10,random_state=SEED,n_jobs=-1,verbosity=-1)
up_hi=LGBMRegressor(n_estimators=160,num_leaves=39,learning_rate=.04,subsample=.9,colsample_bytree=.85,objective='quantile',alpha=.90,random_state=SEED,n_jobs=-1,verbosity=-1)
for m in [up_mean,up_lo,up_hi]: m.fit(Xtr,S['train'][6])
# Save frozen models.
conn_model.booster_.save_model(str(R/'connectivity_lgbm.txt')); state_model.booster_.save_model(str(R/'state_lgbm.txt')); up_mean.booster_.save_model(str(R/'upflex_mean_lgbm.txt')); up_lo.booster_.save_model(str(R/'upflex_q10_lgbm.txt')); up_hi.booster_.save_model(str(R/'upflex_q90_lgbm.txt'))
# Leak-free physical projection. Structurally accepts only forecasts/current metadata, not raw future arrays.
def physics_project(P,p_conn,ts,es):
    p=P.copy(); p[:,1:]*=p_conn[:,None]
    # User participation is declared/static and current SOC is measured at forecast issue time.
    p[policy[es]!=2,2]=0.0
    max_gain=charger[es]*H*DT*.96/cap[es]
    p[soc[ts,es]+max_gain<=min_soc[es]+.06,2]=0.0
    # If currently essentially full, G2V is physically unattractive over a 1-h horizon.
    p[soc[ts,es]>=.985,1]*=.1
    s=p.sum(1,keepdims=True); bad=s[:,0]<=1e-12; p[bad]=[1,0,0]; s=p.sum(1,keepdims=True); return p/s
# Classification conformal calibration after leak-free projection.
Pcal=state_model.predict_proba(Xcal); pccal=conn_model.predict_proba(Xcal)[:,1]; Pcalm=physics_project(Pcal,pccal,S['cal'][0],S['cal'][1])
alpha=.10; scores=1-Pcalm[np.arange(len(ycal)),ycal]; rank=min(1.0, math.ceil((len(scores)+1)*(1-alpha))/len(scores)); qhat=float(np.quantile(scores,rank,method='higher')); class_thr=1-qhat
# CQR calibration for upward flexibility.
lo=np.maximum(0,up_lo.predict(Xcal)); hi=np.maximum(lo,up_hi.predict(Xcal)); yuf=S['cal'][6]; cqr_scores=np.maximum(lo-yuf,yuf-hi); cqr_rank=min(1.0,math.ceil((len(yuf)+1)*(1-alpha))/len(yuf)); cqr_q=float(np.quantile(cqr_scores,cqr_rank,method='higher'))
# Validation threshold for connectivity only affects physical projection; select by macro-F1, no target leakage.
conn_thresholds=np.arange(.30,.76,.05); best_ct=.50; best_f=-1
Pv=state_model.predict_proba(Xv); pcv=conn_model.predict_proba(Xv)[:,1]
for ct in conn_thresholds:
    # Smooth probability but attenuate active states harder below ct.
    adj=np.where(pcv>=ct,pcv,pcv*.35); pp=physics_project(Pv,adj,S['val'][0],S['val'][1]); pred=pp.argmax(1); f=f1_score(yv,pred,average='macro')
    if f>best_f: best_f=f; best_ct=float(ct)
# Validation-selected reliability-budgeted recovery (RBR) coefficient.
# RBR recovers some headroom above the CQR lower bound while constraining validation shortfall
# to at most 5% of committed flexibility. It is selected before the test set is touched.
vlo=np.maximum(0,up_lo.predict(Xv)-cqr_q); vhi=np.maximum(vlo,up_hi.predict(Xv)+cqr_q); vmu=np.maximum(0,up_mean.predict(Xv)); vy=S['val'][6]
vsets=physics_project(Pv,np.where(pcv>=best_ct,pcv,pcv*.35),S['val'][0],S['val'][1])>=class_thr
vrel=np.clip(1-(vhi-vlo)/np.maximum(charger[S['val'][1]],1e-3),0,1); vgate=(vsets.sum(1)==1)&(pcv>=.70)
best_beta=0.0; best_commit=-1.0
for beta in np.linspace(0,1,21):
    vc=np.maximum(0,vlo+beta*vrel*vgate*np.maximum(0,vmu-vlo)); short=np.maximum(0,vc-vy).sum(); denom=max(vc.sum(),1e-9); rate=short/denom
    if rate<=.05 and vc.sum()>best_commit: best_beta=float(beta); best_commit=float(vc.sum())
# Metrics helpers.
def cls_metrics(y,p):
    _,_,f,_=precision_recall_fscore_support(y,p,labels=[0,1,2],zero_division=0)
    return {'accuracy':accuracy_score(y,p),'balanced_accuracy':balanced_accuracy_score(y,p),'macro_f1':f1_score(y,p,average='macro'),'mcc':matthews_corrcoef(y,p),'idle_f1':f[0],'g2v_f1':f[1],'v2g_f1':f[2]}
def ece(y,P,bins=15):
    conf=P.max(1); pred=P.argmax(1); ok=(pred==y).astype(float); edges=np.linspace(0,1,bins+1); z=0
    for a,b in zip(edges[:-1],edges[1:]):
        m=(conf>a)&(conf<=b)
        if m.any(): z += m.mean()*abs(ok[m].mean()-conf[m].mean())
    return float(z)
def multiclass_brier(y,P):
    Y=np.eye(3)[y]; return float(np.mean(np.sum((P-Y)**2,axis=1)))
# Evaluate the entire contiguous test period in chunks.
lo_t=max(bounds['test'][0],L-1); hi_t=min(bounds['test'][1]-H,T-H); issue_times=np.arange(lo_t,hi_t,4,dtype=np.int32); all_t=np.repeat(issue_times,N); all_e=np.tile(np.arange(N,dtype=np.int16),len(issue_times))
chunk=100000; rec=[]; full={'y':[],'raw':[],'phy':[],'safe':[],'Praw':[],'Pm':[],'pc':[],'up':[],'upmean':[],'upl':[],'upu':[],'ts':[],'es':[]}
for s0 in range(0,len(all_t),chunk):
    ts=all_t[s0:s0+chunk]; es=all_e[s0:s0+chunk]; X,y,yc,ys,up,down=build(ts,es)
    P=state_model.predict_proba(X); pc=conn_model.predict_proba(X)[:,1]; pc_adj=np.where(pc>=best_ct,pc,pc*.35); Pm=physics_project(P,pc_adj,ts,es); raw=P.argmax(1); phy=Pm.argmax(1)
    sets=Pm>=class_thr; safe=phy.copy(); amb=sets.sum(1)!=1
    if amb.any():
        need=np.maximum(0,(req[ts[amb],es[amb]]-soc[ts[amb],es[amb]])*cap[es[amb]]); urg=need/np.maximum(dec_ttd[ts[amb],es[amb]],DT)>.72*charger[es[amb]]
        safe[amb]=np.where(conn[ts[amb],es[amb]].astype(bool)&urg,G2V,IDLE)
    mu=np.maximum(0,up_mean.predict(X)); ql=np.maximum(0,up_lo.predict(X)-cqr_q); qu=np.maximum(ql,up_hi.predict(X)+cqr_q)
    for k,v in [('y',y),('raw',raw),('phy',phy),('safe',safe),('Praw',P),('Pm',Pm),('pc',pc),('up',up),('upmean',mu),('upl',ql),('upu',qu),('ts',ts),('es',es)]: full[k].append(v)
for k in full: full[k]=np.concatenate(full[k],axis=0)
y=full['y']; raw=full['raw']; phy=full['phy']; safe=full['safe']; Praw=full['Praw']; Pm=full['Pm']; pc=full['pc']; up=full['up']; mu=full['upmean']; ql=full['upl']; qu=full['upu']; ts=full['ts']; es=full['es']
rows=pd.DataFrame([{'model':'LightGBM raw',**cls_metrics(y,raw)},{'model':'Leak-free physics projection',**cls_metrics(y,phy)},{'model':'PG-CARE v2 conformal+abstention',**cls_metrics(y,safe)}]); rows.to_csv(R/'v2_classification_metrics.csv',index=False)
# Calibration and coverage.
sets=Pm>=class_thr; coverage=(sets[np.arange(len(y)),y]); setsize=sets.sum(1)
cal_rows=[{'stage':'raw','ece':ece(y,Praw),'brier':multiclass_brier(y,Praw),'coverage':np.nan,'mean_set_size':np.nan,'singleton_fraction':np.nan},{'stage':'projected+conformal','ece':ece(y,Pm),'brier':multiclass_brier(y,Pm),'coverage':coverage.mean(),'mean_set_size':setsize.mean(),'singleton_fraction':(setsize==1).mean()}]
pd.DataFrame(cal_rows).to_csv(R/'v2_calibration_metrics.csv',index=False)
# Conditional coverage by class and 4-hour hour-block.
cond=[]
for c in range(3):
    m=y==c; cond.append({'group':'class','value':c,'n':int(m.sum()),'coverage':float(coverage[m].mean()),'mean_set_size':float(setsize[m].mean())})
for hb in range(6):
    h=hour[ts]; m=(h>=4*hb)&(h<4*(hb+1)); cond.append({'group':'hour_block','value':f'{4*hb:02d}-{4*(hb+1):02d}','n':int(m.sum()),'coverage':float(coverage[m].mean()),'mean_set_size':float(setsize[m].mean())})
pd.DataFrame(cond).to_csv(R/'v2_conditional_coverage.csv',index=False)
# Connectivity prediction performance on full test.
yconn=conn[ts+H,es].astype(int); conn_pred=(pc>=best_ct).astype(int); conn_metrics={'accuracy':float(accuracy_score(yconn,conn_pred)),'f1':float(f1_score(yconn,conn_pred)),'auc':float(roc_auc_score(yconn,pc)),'threshold':best_ct}
# CQR flexibility coverage/width and point accuracy.
cqr_cov=((up>=ql)&(up<=qu)); cqr=pd.DataFrame([{'metric':'MAE point upflex kW','value':mean_absolute_error(up,mu)},{'metric':'RMSE point upflex kW','value':mean_squared_error(up,mu)**.5},{'metric':'CQR empirical coverage','value':cqr_cov.mean()},{'metric':'CQR mean width kW','value':np.mean(qu-ql)},{'metric':'CQR zero-safe fraction','value':np.mean(ql<=1e-9)}]); cqr.to_csv(R/'v2_cqr_metrics.csv',index=False)
# McNemar exact test raw vs PG-CARE correctness.
a=(raw==y); b=(safe==y); n01=int((~a&b).sum()); n10=int((a&~b).sum()); pval=float(binomtest(min(n01,n10),n01+n10,.5).pvalue) if n01+n10 else 1.0
pd.DataFrame([{'comparison':'raw_vs_pgcare','raw_wrong_pgcare_right':n01,'raw_right_pgcare_wrong':n10,'exact_p':pval}]).to_csv(R/'v2_mcnemar.csv',index=False)
# Rolling 14-day windows across test.
roll=[]; tday=ts//SPD
for d0 in range(280,365,14):
    m=(tday>=d0)&(tday<min(d0+14,365));
    if m.sum():
        for name,p in [('raw',raw),('pgcare',safe)]: roll.append({'start_day':d0,'end_day':min(d0+14,365)-1,'model':name,'n':int(m.sum()),**cls_metrics(y[m],p[m])})
pd.DataFrame(roll).to_csv(R/'v2_rolling_origin_metrics.csv',index=False)
# Store compact prediction arrays for grid study/bootstrap.
np.savez_compressed(R/'v2_full_test_predictions.npz',y=y,raw=raw,phy=phy,safe=safe,pc=pc,up_true=up,up_mean=mu,up_lower=ql,up_upper=qu,ts=ts,es=es,setsize=setsize)
# Audit sample.
ix=np.linspace(0,len(y)-1,50000,dtype=int); pd.DataFrame({'t':ts[ix],'ev':es[ix],'true_state':y[ix],'raw':raw[ix],'pgcare':safe[ix],'p_conn':pc[ix],'set_size':setsize[ix],'up_true_kw':up[ix],'up_mean_kw':mu[ix],'up_lower_kw':ql[ix],'up_upper_kw':qu[ix]}).to_csv(R/'v2_prediction_audit_sample.csv',index=False)
summary={'version':'PG-CARE v2 leak-free','train_days':200,'cal_days':40,'val_days':40,'test_days':85,'full_test_examples':int(len(y)),'class_alpha':alpha,'class_probability_threshold':class_thr,'cqr_qhat':cqr_q,'connectivity':conn_metrics,'train_seconds':{'connectivity':conn_train_s,'state':state_train_s},'mcnemar_p':pval,'rbr_beta':best_beta,'future_information_mask':'PROHIBITED: physics_project receives no target-time state/connectivity arrays'}
json.dump(summary,open(R/'v2_summary.json','w'),indent=2)
print('RBR beta',best_beta); print(rows.to_string(index=False)); print('\nCalibration\n',pd.DataFrame(cal_rows).to_string(index=False)); print('\nConnectivity',conn_metrics); print('\nCQR\n',cqr.to_string(index=False)); print('McNemar',n01,n10,pval,'test n',len(y))
