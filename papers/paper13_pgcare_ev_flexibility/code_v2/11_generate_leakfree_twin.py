"""Leak-free supervisory EV-fleet digital twin for PG-CARE v2.

Key change from v1: actual plug-in times and owner-declared schedules are distinct.
Any future feasibility logic may use only present measurements and declared schedules;
realized future connectivity is reserved exclusively for labels/evaluation.
"""
from pathlib import Path
import numpy as np, pandas as pd
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data_v2'; D.mkdir(exist_ok=True)
SEED=1793; rng=np.random.default_rng(SEED)
IDLE,G2V,V2G=0,1,2; N=100; DAYS=365; DT=.25; SPD=96; T=DAYS*SPD
idx=np.arange(T); day=idx//SPD; hour=(idx%SPD)*DT; dow=day%7; doy=day%365
# Stochastic exogenous system demand and PV. Kept as a controlled simulation arm.
mor=np.exp(-.5*((hour-7.5)/1.8)**2); eve=np.exp(-.5*((hour-19)/2.3)**2); mid=.32*np.exp(-.5*((hour-13)/3.1)**2)
season=1+.15*np.cos(2*np.pi*(doy-10)/365)+.05*np.sin(4*np.pi*doy/365); weekend=np.where(dow>=5,.93+.08*mid,1.)
eps=rng.normal(0,.05,T); ar=np.zeros(T)
for k in range(1,T): ar[k]=.92*ar[k-1]+eps[k]
event=np.ones(T)
for d in rng.choice(DAYS,size=34,replace=False):
    s=d*SPD+rng.integers(64,82); event[s:min(T,s+rng.integers(5,18))]*=rng.uniform(1.10,1.34)
base=N*(.56+.44*mor+.96*eve+mid)*season*weekend*np.clip(1+ar,.74,1.31)*event
solar=np.maximum(0,np.sin(np.pi*(hour-6)/12))**1.7; pvseason=.55+.44*np.sin(np.pi*(doy+40)/365)**2
pv=1.15*N*solar*pvseason*np.repeat(rng.beta(5,2,DAYS),SPD); native=np.maximum(base-pv,-.22*N)
price=np.clip(.10+.04*((hour>=7)&(hour<16))+.13*((hour>=16)&(hour<21))+.02*np.sin(2*np.pi*doy/365)+rng.normal(0,.004,T),.06,None)
# Fleet heterogeneity.
cap=np.clip(rng.normal(72,16,N),40,120).astype('f4'); charger=rng.choice([7.2,9.6,11.0],N,p=[.45,.25,.30]).astype('f4')
eta_c=rng.uniform(.90,.96,N).astype('f4'); eta_d=rng.uniform(.90,.96,N).astype('f4'); min_soc=rng.uniform(.30,.55,N).astype('f4'); target=rng.uniform(.78,.92,N).astype('f4')
policy=rng.choice([0,1,2],N,p=[.08,.32,.60]).astype('i1')
# Owner-declared schedule vs realized schedule. Deviations emulate late/early arrivals,
# early unplugging and schedule uncertainty. The declared schedule is available to forecasting.
dec_arr=np.zeros((DAYS,N),'f4'); dec_dep=np.zeros((DAYS,N),'f4'); act_arr=np.zeros((DAYS,N),'f4'); act_dep=np.zeros((DAYS,N),'f4'); trip=np.zeros((DAYS,N),'f4'); reqd=np.zeros((DAYS,N),'f4')
for d in range(DAYS):
    wk=d%7>=5
    da=np.clip(rng.normal(18.2 if wk else 17.4,1.65,N),13,23.5); dd=np.clip(rng.normal(8.7 if wk else 7.4,1.05,N),4.5,12)
    dec_arr[d],dec_dep[d]=da,dd
    act_arr[d]=np.clip(da+rng.normal(0,.50,N),12.5,23.75)
    act_dep[d]=np.clip(dd+rng.normal(0,.42,N),4.0,12.5)
    # ~6% of sessions experience material early departure; ~4% arrive much later.
    early=rng.random(N)<.06; act_dep[d,early]=np.maximum(4.0,act_dep[d,early]-rng.uniform(.5,2.0,early.sum()))
    late=rng.random(N)<.04; act_arr[d,late]=np.minimum(23.75,act_arr[d,late]+rng.uniform(.5,2.0,late.sum()))
    trip[d]=np.clip(rng.lognormal(np.log(10 if wk else 14),.48,N),2,45)
    reqd[d]=np.clip(target+rng.normal(0,.025,N),.72,.95)
q25=np.zeros(DAYS,'f4'); q75=np.zeros(DAYS,'f4')
for d in range(DAYS):
    sl=slice(d*SPD,(d+1)*SPD); hist=slice((d-1)*SPD,d*SPD) if d>0 else sl; q25[d],q75[d]=np.quantile(native[hist],[.25,.75])
# Dynamic arrays.
soc=np.zeros((T,N),'f4'); state=np.zeros((T,N),'i1'); conn=np.zeros((T,N),'u1'); pev=np.zeros((T,N),'f4'); ttd=np.zeros((T,N),'f4'); dec_ttd=np.zeros((T,N),'f4'); req=np.zeros((T,N),'f4'); dec_conn_h1=np.zeros((T,N),'u1')
prev=np.clip(rng.beta(5,3,N)*.65+.20,.20,.95).astype('f4'); last=np.zeros(N,bool)
for t in range(T):
    d=int(day[t]); h=hour[t]
    c=((h>=act_arr[d])|(h<act_dep[d]))&(policy!=0); conn[t]=c
    arriving=c&(~last)&(h>=act_arr[d]); prev[arriving]=np.maximum(.10,prev[arriving]-trip[d,arriving]/cap[arriving])
    tt=np.where(h<act_dep[d],act_dep[d]-h,(24-h)+act_dep[d]); ttd[t]=tt
    dtt=np.where(h<dec_dep[d],dec_dep[d]-h,(24-h)+dec_dep[d]); dec_ttd[t]=dtt; req[t]=reqd[d]
    h1=(h+1.0)%24; dd=d + (h+1.0>=24); dd=np.minimum(dd,DAYS-1)
    dec_conn_h1[t]=(((h1>=dec_arr[dd])|(h1<dec_dep[dd]))&(policy!=0)).astype('u1')
    need=np.maximum(0,(reqd[d]-prev)*cap); urgkw=need/np.maximum(tt,DT); urgent=c&(urgkw>.72*charger)
    low=native[t]<q25[d]; high=native[t]>q75[d]; charge_only=c&(policy==1); bi=c&(policy==2)
    must=c&(prev<reqd[d])&(urgent|low|(prev<min_soc+.04)); can=bi&(~urgent)&(prev>min_soc+.08)&(need<.55*charger*np.maximum(tt,DT))
    dv=can&high; dc=(charge_only&(prev<reqd[d])&(urgent|low|((h>=0)&(h<6))))|(bi&must); dc&=~dv
    st=np.zeros(N,'i1'); p=np.zeros(N,'f4'); st[dc]=G2V; st[dv]=V2G; p[dc]=charger[dc]; p[dv]=-charger[dv]
    p[(prev>=.985)&(p>0)]=0; p[(prev<=min_soc)&(p<0)]=0; st[p==0]=IDLE
    prev=np.clip(prev+np.where(p>=0,eta_c*p*DT/cap,(p/eta_d)*DT/cap),.10,.99); soc[t]=prev; state[t]=st; pev[t]=p; last=c
agg=pd.DataFrame({'step':idx,'day':day,'dow':dow,'doy':doy,'hour':hour,'base_load_kw':base,'pv_kw':pv,'native_kw':native,'ev_kw':pev.sum(1),'feeder_kw':native+pev.sum(1),'price':price,'q25_kw':q25[day],'q75_kw':q75[day],'connected':conn.sum(1),'idle':(state==0).sum(1),'g2v':(state==1).sum(1),'v2g':(state==2).sum(1),'mean_soc':soc.mean(1)})
agg.to_csv(D/'aggregate_timeseries_v2.csv',index=False)
pd.DataFrame({'ev_id':np.arange(N),'capacity_kwh':cap,'charger_kw':charger,'eta_charge':eta_c,'eta_discharge':eta_d,'min_soc':min_soc,'target_soc':target,'policy':policy}).to_csv(D/'fleet_parameters_v2.csv',index=False)
np.savez_compressed(D/'digital_twin_v2.npz',soc=soc,state=state,conn=conn,pev=pev,ttd=ttd,dec_ttd=dec_ttd,dec_conn_h1=dec_conn_h1,req=req,cap=cap,charger=charger,min_soc=min_soc,target=target,policy=policy,dec_arr=dec_arr,dec_dep=dec_dep,act_arr=act_arr,act_dep=act_dep,trip=trip,eta_c=eta_c,eta_d=eta_d)
print(f'Generated leak-free v2: {DAYS} days x {N} EVs = {T*N:,} states; schedule mismatch at H=1h = {np.mean(dec_conn_h1[:-4] != conn[4:]):.3f}')
