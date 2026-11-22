"""LSTM quantile forecaster, split-conformal calibration and nonparametric scores.

This is supervised *forecasting*, not a third RL agent.
Conformal coverage in dependent time series is empirical, not distribution-free guaranteed.
"""
import numpy as np
import torch
from torch import nn

def make_windows(array, lookback=24, horizon=4):
    x=np.asarray(array,dtype=np.float32).reshape(-1)
    if len(x)<lookback+horizon:raise ValueError('insufficient observations for lookback+horizon')
    xs=[];ys=[]
    for t in range(lookback,len(x)-horizon+1):
        xs.append(x[t-lookback:t]);ys.append(x[t+horizon-1])
    return np.asarray(xs,dtype=np.float32)[:,:,None],np.asarray(ys,dtype=np.float32)

class QuantileLSTM(nn.Module):
    def __init__(self,hidden=32,quantiles=(.1,.5,.9)):
        super().__init__()
        self.quantiles=tuple(quantiles)
        self.lstm=nn.LSTM(1,hidden,batch_first=True,num_layers=1)
        self.head=nn.Linear(hidden,len(self.quantiles))
    def forward(self,x):
        _,(h,_) = self.lstm(x)
        return self.head(h[-1])

def quantile_loss(pred,target,quantiles=(.1,.5,.9)):
    errors=target[:,None]-pred
    tau=torch.tensor(quantiles,dtype=pred.dtype,device=pred.device)[None,:]
    return torch.maximum(tau*errors,(tau-1)*errors).mean()

def fit_quantile_lstm(train_series,epochs=10,lookback=24,horizon=4,hidden=32,seed=11):
    torch.manual_seed(seed);torch.set_num_threads(1)
    x,y=make_windows(np.asarray(train_series)/700.,lookback,horizon)
    model=QuantileLSTM(hidden=hidden)
    opt=torch.optim.Adam(model.parameters(),lr=1e-3)
    X=torch.tensor(x);Y=torch.tensor(y)
    for epoch in range(epochs):
        order=torch.randperm(len(X))
        for batch in order.split(256):
            q=model(X[batch]); loss=quantile_loss(q,Y[batch]);opt.zero_grad();loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(),1.);opt.step()
    return model

@torch.no_grad()
def predict_quantiles(model,series,lookback=24,horizon=4):
    x,_=make_windows(np.asarray(series)/700.,lookback,horizon)
    q=model(torch.tensor(x)).numpy()*700.
    return np.sort(np.clip(q,0.,700.),axis=1)

def conformal_radius(ycal,lower,upper,miscoverage=.20):
    """Nonconformity score max(lower-y, y-upper, 0), finite-sample quantile.
    Use blockwise empirical coverage diagnostics for temporal dependence.
    """
    s=np.maximum.reduce([np.asarray(lower)-ycal,ycal-np.asarray(upper),np.zeros_like(ycal)])
    n=len(s);k=min(n,int(np.ceil((n+1)*(1-miscoverage))))
    return float(np.sort(s)[k-1])

def score_forecast(y,q,cal_radius=0.):
    y=np.asarray(y);q=np.asarray(q)
    assert q.shape==(len(y),3)
    lo=np.clip(q[:,0]-cal_radius,0,700);hi=np.clip(q[:,2]+cal_radius,0,700)
    coverage=float(np.mean((y>=lo)&(y<=hi)))
    width=float(np.mean(hi-lo))
    alpha=.20
    winkler=float(np.mean(hi-lo+2/alpha*(lo-y)*(y<lo)+2/alpha*(y-hi)*(y>hi)))
    return {'median_mae_mw':float(np.mean(abs(y-q[:,1]))),'median_rmse_mw':float(np.sqrt(np.mean((y-q[:,1])**2))),
            'interval_80_coverage':coverage,'interval_mean_width_mw':width,'interval_score_80':winkler}
