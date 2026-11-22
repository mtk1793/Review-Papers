import numpy as np
import torch
from h2bench.forecast import QuantileLSTM,make_windows,quantile_loss,conformal_radius,score_forecast

def test_forecast_shapes_and_backward():
    t=np.linspace(0,1,100).astype('float32');x,y=make_windows(t,12,3)
    q=QuantileLSTM(hidden=8)(torch.tensor(x));assert q.shape==(86,3)
    loss=quantile_loss(q,torch.tensor(y));loss.backward()
    assert np.isfinite(float(loss.item()))

def test_conformal():
    y=np.asarray([1.,2.,3.,4.,5.]);lo=y-.5;hi=y+.5
    assert conformal_radius(y,lo,hi)==0.
    q=np.array([[0.,1.,2.],[1.,2.,3.],[2.,3.,4.],[3.,4.,5.],[4.,5.,6.]])
    scores=score_forecast(y,q)
    assert scores['median_mae_mw']==0
    assert scores['interval_80_coverage']==1.0
