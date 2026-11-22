"""Two-stage RL training with fully disclosed fixed-policy hierarchy.

This is intentionally NOT labeled end-to-end jointly trained MARL.
"""
import numpy as np
import random
import torch
from .agents import SAC,QRDQN
from .physics import HydrogenEnv
from .evaluate import feature_vec,target_mw,battery_request

def train_hierarchy(wind,steps=15000,seed=11,plant=None,market=None,dt_hours=.25,forecast=None):
    if len(wind)<8:raise ValueError('training series too short')
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    qr=QRDQN(seed=seed);sac=SAC(seed=seed)
    env=HydrogenEnv(plant,market,dt_hours=dt_hours)
    # Stage A: train QR-DQN against FIXED rule-based power control.
    # Stage B: train SAC with the QR-DQN policy FROZEN.
    # The hierarchy is not jointly co-trained and is never called three-agent MA-RL.
    if forecast is None:forecast=np.column_stack([wind,wind,wind])
    if np.asarray(forecast).shape!=(len(wind),3):raise ValueError("forecast must be (T,3) low/median/high")
    half=steps//2
    for phase,nstep in [('qr',half),('sac',steps-half)]:
        env.reset()
        for j in range(nstep):
            i=(j+seed*17)%(len(wind)-1)
            if i==0 and j>0:env.reset()
            done=float(i==len(wind)-2)
            w=float(wind[i]);future=float(wind[i+1]);s=feature_vec(w,forecast[i,1],env,low=forecast[i,0],high=forecast[i,2])
            if phase=='qr':
                a=qr.choose(s,epsilon=max(.05,.5*(1-j/max(nstep,1))),risk_frac=.25)
                fraction=1. if a==0 else (.6 if a==1 else 0.)
            else:
                a=qr.choose(s,risk_frac=.25)
                ss=np.r_[s,[a/2.]]
                fraction=sac.choose(ss,deterministic=False)
            r=env.step(w,target_mw(a,fraction,env),battery_request(a,env,w))
            s2=feature_vec(future,forecast[i+1,1],env,low=forecast[i+1,0],high=forecast[i+1,2])
            scaled=float(r['reward_usd'])/10000.
            # no future features fed into current policy; future used only for Q target.
            if phase=='qr':
                qr.replay.add(s,a,scaled,s2,done)
                if j%4==0:qr.update(64)
            else:
                sac.replay.add(ss,fraction,scaled,np.r_[s2,[a/2.]],done)
                if j%4==0:sac.update(64)
    return sac,qr

def train_single_sac(wind,steps=7500,seed=11,plant=None,market=None,dt_hours=.25,forecast=None):
    """Independently train SAC-only baseline, no cross-sharing trained hierarchy weights."""
    random.seed(seed);np.random.seed(seed);torch.manual_seed(seed)
    model=SAC(seed=seed);env=HydrogenEnv(plant,market,dt_hours=dt_hours)
    if forecast is None:forecast=np.column_stack([wind,wind,wind])
    if np.asarray(forecast).shape!=(len(wind),3):raise ValueError("forecast must be (T,3) low/median/high")
    for j in range(steps):
        i=(j+seed*19)%(len(wind)-1)
        if i==0 and j>0:env.reset()
        done=float(i==len(wind)-2)
        w=float(wind[i]);w2=float(wind[i+1])
        s=feature_vec(w,forecast[i,1],env,low=forecast[i,0],high=forecast[i,2]);state=np.r_[s,[0.]]
        frac=model.choose(state,deterministic=False)
        rec=env.step(w,target_mw(0,frac,env),battery_request(0,env,w))
        s2=feature_vec(w2,forecast[i+1,1],env,low=forecast[i+1,0],high=forecast[i+1,2])
        model.replay.add(state,frac,rec['reward_usd']/10000.,np.r_[s2,[0.]],done)
        if j%4==0:model.update(64)
    return model
