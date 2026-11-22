"""Receding-horizon LP scheduling diagnostic with explicit battery and H2 states.

Not a MILP: minimum load and on/off are projected by plant after LP solve;
therefore this is only a transparent deterministic *LP-MPC relaxation*, not a
fully matched degradation-aware commercial MPC benchmark.
"""
from scipy.optimize import linprog
from scipy.sparse import lil_matrix
import numpy as np
from .physics import HydrogenEnv
from .evaluate import metrics
import pandas as pd

def solve_lp_mpc(wind_future,env,horizon=8):
    p=env.p;m=env.m;dt=env.dt;eta=np.sqrt(p.roundtrip_efficiency)
    w=np.asarray(wind_future[:horizon],dtype=float)
    N=len(w)
    if N<1:raise ValueError('no wind forecast')
    # e, charge, discharge, export, curtail, SOCend, H2end, delivered, shortfall, ramp_plus, ramp_minus
    cols=11;J=lambda t,k:t*cols+k
    c=np.zeros(N*cols);bounds=[]
    for t in range(N):
        for k in range(cols):
            if k==0:bd=(0,p.electrolyzer_capacity_mw)
            elif k in (1,2):bd=(0,p.bess_power_mw)
            elif k==3:bd=(0,p.export_limit_mw)
            elif k==4:bd=(0,None)
            elif k==5:bd=(0,p.bess_energy_mwh)
            elif k==6:bd=(0,p.h2_tank_capacity_kg)
            elif k in (7,8):bd=(0,p.hydrogen_demand_kg_per_day*dt/24)
            else:bd=(0,p.ramp_limit_mw_per_min*dt*60)
            bounds.append(bd)
        c[J(t,3)]=-m.energy_export_price_usd_per_mwh*dt
        c[J(t,7)]=-m.h2_sale_price_usd_per_kg
        c[J(t,8)]=m.h2_unmet_demand_penalty_usd_per_kg
        c[J(t,9)]=c[J(t,10)]=p.stack_replacement_usd/p.stack_design_life_eq_hours*p.ramp_wear_eq_hours_per_mw2*max(p.electrolyzer_capacity_mw,1.)
    # 5 equality constraints per step: power balance, SOC, H2, delivery, ramp.
    eq=lil_matrix((5*N,N*cols),dtype=float);rhs=np.zeros(5*N)
    for t in range(N):
        j=5*t
        for k,v in [(0,1),(1,1),(2,-1),(3,1),(4,1)]:eq[j,J(t,k)]=v
        rhs[j]=w[t]
        for k,v in [(5,1),(1,-eta*dt),(2,dt/eta)]:eq[j+1,J(t,k)]=v
        if t:eq[j+1,J(t-1,5)]=-1
        else:rhs[j+1]=env.soc_mwh
        eq[j+2,J(t,6)]=1
        eq[j+2,J(t,0)]=-dt/p.h2_specific_energy_mwh_per_kg
        eq[j+2,J(t,7)]=1
        if t:eq[j+2,J(t-1,6)]=-1
        else:rhs[j+2]=env.h2_kg
        eq[j+3,J(t,7)]=1;eq[j+3,J(t,8)]=1
        rhs[j+3]=p.hydrogen_demand_kg_per_day*dt/24
        eq[j+4,J(t,0)]=1;eq[j+4,J(t,9)]=-1;eq[j+4,J(t,10)]=1
        if t:eq[j+4,J(t-1,0)]=-1
        else:rhs[j+4]=env.previous_mw
    sol=linprog(c,A_eq=eq.tocsr(),b_eq=rhs,bounds=bounds,method='highs')
    if not sol.success:raise RuntimeError('LP-MPC failed: '+str(sol.message))
    v=sol.x[:cols]
    return {'desired_electrolyzer_mw':float(v[0]),'battery_request_mw':float(v[1]-v[2]),
        'optimizer_objective_usd':float(sol.fun),'assumption':'linear relaxation; no binary min-load or start penalties'}

def evaluate_lp_mpc(wind_mw,oracle=False,horizon=8,plant=None,market=None,dt_hours=.25):
    env=HydrogenEnv(plant,market,dt_hours=dt_hours);rows=[]
    wind=np.asarray(wind_mw,dtype=float)
    for t,w in enumerate(wind):
        # Oracle gets genuinely future observed wind; non-oracle uses
        # available current wind as persistence forecast, never future samples.
        forecast=wind[t:t+horizon] if oracle else np.repeat(float(w),min(horizon,len(wind)-t))
        opt=solve_lp_mpc(forecast,env,horizon=horizon)
        r=env.step(float(w),opt['desired_electrolyzer_mw'],opt['battery_request_mw'])
        r['step']=t;r['oracle']=bool(oracle)
        rows.append(r)
    return pd.DataFrame(rows)
