"""Approximate feeder QSTS using the standard IEEE 33-bus radial feeder.
A backward/forward sweep solves the balanced AC radial power flow at hourly issue times.
The study evaluates delivered V2G flexibility, not an invented market settlement product.
"""
from pathlib import Path
import numpy as np,pandas as pd,json
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'data_v2';R=ROOT/'results_v2';R.mkdir(exist_ok=True)
z=np.load(D/'digital_twin_v2.npz'); pred=np.load(R/'v2_full_test_predictions.npz'); agg=pd.read_csv(D/'aggregate_timeseries_v2.csv'); summary=json.load(open(R/'v2_summary.json')); RBR_BETA=float(summary.get('rbr_beta',0.0))
soc,state,conn,pev=[z[k] for k in ['soc','state','conn','pev']]; charger=z['charger']; policy=z['policy']; cap=z['cap']; min_soc=z['min_soc']
ts,es=pred['ts'],pred['es']; y=pred['y']; up_true=pred['up_true']; up_mean=pred['up_mean']; up_lower=pred['up_lower']; up_upper=pred['up_upper']; safe=pred['safe']; raw=pred['raw']; pc=pred['pc']; setsize=pred['setsize']; N=soc.shape[1]; H=4
# IEEE 33-bus line data: from,to,R(ohm),X(ohm)
branches=np.array([
[1,2,.0922,.0470],[2,3,.4930,.2511],[3,4,.3660,.1864],[4,5,.3811,.1941],[5,6,.8190,.7070],[6,7,.1872,.6188],[7,8,.7114,.2351],[8,9,1.0300,.7400],[9,10,1.0440,.7400],[10,11,.1966,.0650],[11,12,.3744,.1238],[12,13,1.4680,1.1550],[13,14,.5416,.7129],[14,15,.5910,.5260],[15,16,.7463,.5450],[16,17,1.2890,1.7210],[17,18,.7320,.5740],[2,19,.1640,.1565],[19,20,1.5042,1.3554],[20,21,.4095,.4784],[21,22,.7089,.9373],[3,23,.4512,.3083],[23,24,.8980,.7091],[24,25,.8960,.7011],[6,26,.2030,.1034],[26,27,.2842,.1447],[27,28,1.0590,.9337],[28,29,.8042,.7006],[29,30,.5075,.2585],[30,31,.9744,.9630],[31,32,.3105,.3619],[32,33,.3410,.5302]],float)
# Standard bus loads (kW,kvar), buses 2..33.
loads=np.array([[100,60],[90,40],[120,80],[60,30],[60,20],[200,100],[200,100],[60,20],[60,20],[45,30],[60,35],[60,35],[120,80],[60,10],[60,20],[60,20],[90,40],[90,40],[90,40],[90,40],[90,40],[90,50],[420,200],[420,200],[60,25],[60,25],[60,20],[120,70],[200,600],[150,70],[210,100],[60,40]],float)
# p.u. bases.
VBASE_KV=12.66; SBASE_MVA=100.; ZBASE=(VBASE_KV**2)/SBASE_MVA; zpu=(branches[:,2]+1j*branches[:,3])/ZBASE
parent=np.zeros(34,int); br_of=np.zeros(34,int); children=[[] for _ in range(34)]
for k,(f,t,_,_) in enumerate(branches): parent[int(t)]=int(f); br_of[int(t)]=k; children[int(f)].append(int(t))
order=list(range(33,1,-1))
def pf(Pkw,Qkvar,maxit=50):
    S=np.zeros(34,complex); S[2:]=(Pkw+1j*Qkvar)/100000.0 # kW on 100 MVA base
    V=np.ones(34,complex)
    Ibr=np.zeros(32,complex)
    for _ in range(maxit):
        Vold=V.copy(); Iinj=np.zeros(34,complex); nz=np.abs(V)>1e-8; Iinj[nz]=np.conj(S[nz]/V[nz])
        # backward currents from leaves.
        Itot=Iinj.copy()
        for b in order:
            for ch in children[b]: Itot[b]+=Itot[ch]
            if b!=1: Ibr[br_of[b]]=Itot[b]
        V[1]=1+0j
        # forward voltages.
        stack=[1]
        while stack:
            f=stack.pop()
            for ch in children[f]:
                k=br_of[ch]; V[ch]=V[f]-zpu[k]*Ibr[k]; stack.append(ch)
        if np.max(np.abs(V-Vold))<1e-9: break
    # substation power and branch loss.
    Ssub=V[1]*np.conj(sum(Ibr[k] for k,(f,t,_,_) in enumerate(branches) if int(f)==1))*SBASE_MVA
    loss_pu=np.sum((np.abs(Ibr)**2)*zpu.real); return np.abs(V[1:]),Ssub.real*1000,loss_pu*SBASE_MVA*1000
# Map EVs to five stressed buses.
ev_buses=np.array([7,14,24,30,32]); ev_bus=ev_buses[np.arange(N)%len(ev_buses)]
baseP=loads[:,0]; baseQ=loads[:,1]; mean_native=agg.native_kw.iloc[280*96:].mean(); q75=agg.q75_kw.to_numpy(); native=agg.native_kw.to_numpy()
# Predictions contain all 100 EVs for each hourly issue time, ordered by t then EV.
unique_t=np.unique(ts); rows=[]
for t in unique_t:
    m=ts==t; tf=int(t+H); scale=max(.45,float(native[tf]/mean_native)); P0=baseP*scale; Q0=baseQ*scale
    # Actual charging-only EV demand at horizon; ignore native controller V2G to isolate forecasting-led support.
    for b in ev_buses:
        ee=np.where(ev_bus==b)[0]; g2v=((state[tf,ee]==1)*charger[ee]).sum(); P0[b-2]+=g2v
    stress=bool(native[tf]>q75[tf])
    true=up_true[m]; mean=up_mean[m]; low=up_lower[m]; high=up_upper[m]; pcm=pc[m]; ssm=setsize[m]
    # Reliability-budgeted recovery (RBR): recover a fraction of headroom above the CQR lower bound
    # only for singleton classification forecasts with high predicted connectivity and narrow CQR intervals.
    width=np.maximum(0,high-low); normw=width/np.maximum(charger,1e-3); rel=np.clip(1-normw,0,1); gamma=RBR_BETA*rel*(ssm==1)*(pcm>=.70); rbr=np.maximum(0,low+gamma*np.maximum(0,mean-low))
    # Per-EV support capacities under four policies.
    caps={'No forecast V2G':np.zeros(N),
          'Raw mean flexibility':np.minimum(mean,true) if stress else np.zeros(N),
          'PG-CARE CQR lower':np.minimum(low,true) if stress else np.zeros(N),
          'PG-CARE RBR':np.minimum(rbr,true) if stress else np.zeros(N),
          'Oracle flexibility':true if stress else np.zeros(N)}
    commits={'No forecast V2G':np.zeros(N),'Raw mean flexibility':mean if stress else np.zeros(N),'PG-CARE CQR lower':low if stress else np.zeros(N),'PG-CARE RBR':rbr if stress else np.zeros(N),'Oracle flexibility':true if stress else np.zeros(N)}
    for name,deliv in caps.items():
        P=P0.copy()
        for b in ev_buses: P[b-2]-=deliv[ev_bus==b].sum()
        V,Psub,loss=pf(P,Q0)
        commit=commits[name]
        rows.append({'t':int(t),'tf':tf,'strategy':name,'stress':stress,'min_v_pu':float(V.min()),'voltage_buses_below_0p95':int(np.sum(V<.95)),'substation_kw':float(Psub),'loss_kw':float(loss),'committed_v2g_kw':float(commit.sum()),'delivered_v2g_kw':float(deliv.sum()),'shortfall_kw':float(np.maximum(0,commit.sum()-true.sum()))})
out=pd.DataFrame(rows);out.to_csv(R/'v2_ieee33_qsts_timeseries.csv',index=False)
summary=[]
for name,g in out.groupby('strategy'):
    summary.append({'strategy':name,'steps':len(g),'stress_steps':int(g.stress.sum()),'min_voltage_pu':g.min_v_pu.min(),'voltage_violation_bus_steps':int(g.voltage_buses_below_0p95.sum()),'mean_loss_kw':g.loss_kw.mean(),'peak_substation_kw':g.substation_kw.max(),'v2g_delivered_mwh':g.delivered_v2g_kw.sum()/1000,'commit_shortfall_mwh':g.shortfall_kw.sum()/1000})
pd.DataFrame(summary).to_csv(R/'v2_ieee33_qsts_summary.csv',index=False)
print(pd.DataFrame(summary).to_string(index=False))
