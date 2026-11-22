import numpy as np
import torch
from h2bench.agents import SAC,QRDQN

def test_sac_finite_update():
    model=SAC(seed=2)
    for i in range(90):
        s=np.random.default_rng(i).random(9).astype('float32')
        model.replay.add(s,float(i%10)/10,float(i%4)/4,s,0.)
    result=model.update(32)
    assert result is not None and all(np.isfinite(list(result.values())))
    assert 0<=model.choose(np.zeros(9,dtype='float32'))<=1

def test_qr_finite_update():
    model=QRDQN(seed=1)
    for i in range(90):
        s=np.random.default_rng(i).random(8).astype('float32')
        model.replay.add(s,i%3,float(i%5)/10,s,0.)
    result=model.update(32)
    assert result is not None and all(np.isfinite(list(result.values())))
    assert model.online(torch.zeros((3,8))).shape==(3,3,51)
    assert model.choose(np.zeros(8,dtype='float32')) in range(3)
