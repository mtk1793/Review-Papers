"""Minimal, inspectable PyTorch SAC and quantile-regression DQN implementations.
Correctness tests establish tensor shapes, finite updates and action bounds;
scientific superiority requires real out-of-sample multi-seed experiments.
"""
from collections import deque
import random
import numpy as np
import torch
from torch import nn
import torch.nn.functional as F

torch.set_num_threads(1)

class Replay:
    def __init__(self,maxlen=100000):self.memory=deque(maxlen=maxlen)
    def add(self,s,a,r,s2,done):self.memory.append((np.asarray(s,dtype=np.float32),a,float(r),np.asarray(s2,dtype=np.float32),float(done)))
    def sample(self,n):
        b=random.sample(self.memory,n)
        return ([torch.tensor(np.stack([i[j] for i in b]),dtype=torch.float32) for j in [0,3]],
                 torch.tensor([i[1] for i in b]),torch.tensor([i[2] for i in b],dtype=torch.float32)[:,None],
                 torch.tensor([i[4] for i in b],dtype=torch.float32)[:,None])
    def __len__(self):return len(self.memory)

def mlp(in_dim,out_dim,hidden=64):
    return nn.Sequential(nn.Linear(in_dim,hidden),nn.ReLU(),nn.Linear(hidden,hidden),nn.ReLU(),nn.Linear(hidden,out_dim))

class SquashedActor(nn.Module):
    def __init__(self,state_dim=9):
        super().__init__();self.net=mlp(state_dim,2)
    def forward(self,s):
        mu,log_std=self.net(s).chunk(2,dim=-1)
        return mu,torch.clamp(log_std,-5,2)
    def sample(self,s):
        mu,logstd=self(s)
        u=torch.distributions.Normal(mu,logstd.exp()).rsample()
        a=torch.tanh(u)
        # log pi(a/2+0.5) corrected for affine scaling and tanh transformation
        logp=torch.distributions.Normal(mu,logstd.exp()).log_prob(u)
        logp-=torch.log(torch.clamp(1-a.square(),min=1e-6))
        logp+=np.log(2.)
        return (a+1.)/2.,logp.sum(-1,keepdim=True)

class SAC:
    def __init__(self,state_dim=9,seed=11,discount=.99,alpha=.1):
        torch.manual_seed(seed);random.seed(seed);np.random.seed(seed)
        self.actor=SquashedActor(state_dim)
        self.q1=mlp(state_dim+1,1);self.q2=mlp(state_dim+1,1)
        self.tq1=mlp(state_dim+1,1);self.tq2=mlp(state_dim+1,1)
        self.tq1.load_state_dict(self.q1.state_dict());self.tq2.load_state_dict(self.q2.state_dict())
        self.ao=torch.optim.Adam(self.actor.parameters(),lr=3e-4)
        self.qo=torch.optim.Adam(list(self.q1.parameters())+list(self.q2.parameters()),lr=3e-4)
        self.gamma=discount;self.alpha=alpha
        self.replay=Replay()
    def choose(self,state,deterministic=False):
        with torch.no_grad():
            s=torch.as_tensor(np.asarray(state,dtype=np.float32)[None])
            if deterministic:
                mean,_=self.actor(s);return float(((mean.tanh()+1)/2).item())
            a,_=self.actor.sample(s);return float(a.item())
    def update(self,batch_size=64):
        if len(self.replay)<batch_size:return None
        (s,s2),a,r,done=self.replay.sample(batch_size)
        a=a.to(torch.float32).reshape(-1,1)
        with torch.no_grad():
            nexta,nextlogp=self.actor.sample(s2)
            tar=r+self.gamma*(1-done)*(torch.minimum(self.tq1(torch.cat([s2,nexta],-1)),self.tq2(torch.cat([s2,nexta],-1)))-self.alpha*nextlogp)
        pred1=self.q1(torch.cat([s,a],-1));pred2=self.q2(torch.cat([s,a],-1))
        qloss=F.mse_loss(pred1,tar)+F.mse_loss(pred2,tar)
        self.qo.zero_grad();qloss.backward();self.qo.step()
        a_pi,logp=self.actor.sample(s)
        for q in (self.q1,self.q2):
            for p in q.parameters():p.requires_grad_(False)
        aloss=(self.alpha*logp-torch.minimum(self.q1(torch.cat([s,a_pi],-1)),self.q2(torch.cat([s,a_pi],-1)))).mean()
        self.ao.zero_grad();aloss.backward();self.ao.step()
        for q in (self.q1,self.q2):
            for p in q.parameters():p.requires_grad_(True)
        with torch.no_grad():
            for tgt,src in ((self.tq1,self.q1),(self.tq2,self.q2)):
                for tp,sp in zip(tgt.parameters(),src.parameters()):tp.mul_(.995).add_(sp,alpha=.005)
        return {'q_loss':float(qloss.item()),'actor_loss':float(aloss.item())}

class QuantileNet(nn.Module):
    def __init__(self,state_dim=8,n_actions=3,n_quantiles=51):
        super().__init__();self.n_actions=n_actions;self.n_quantiles=n_quantiles
        self.net=mlp(state_dim,n_actions*n_quantiles)
    def forward(self,x):return self.net(x).reshape(-1,self.n_actions,self.n_quantiles)

class QRDQN:
    def __init__(self,state_dim=8,n_actions=3,n_quantiles=51,seed=11,discount=.99):
        torch.manual_seed(seed)
        self.online=QuantileNet(state_dim,n_actions,n_quantiles)
        self.target=QuantileNet(state_dim,n_actions,n_quantiles)
        self.target.load_state_dict(self.online.state_dict())
        self.opt=torch.optim.Adam(self.online.parameters(),lr=3e-4)
        self.replay=Replay();self.gamma=discount
        self.n_quantiles=n_quantiles;self.n_actions=n_actions;self.counter=0
    def choose(self,state,epsilon=.0,risk_frac=.25):
        if random.random()<epsilon:return random.randrange(self.n_actions)
        with torch.no_grad():
            q=self.online(torch.as_tensor(np.asarray(state,dtype=np.float32)[None]))[0]
            sortedq=q.sort(dim=-1).values
            k=max(1,int(self.n_quantiles*risk_frac))
            return int(sortedq[:,:k].mean(-1).argmax())
    def update(self,batch_size=64):
        if len(self.replay)<batch_size:return None
        (s,s2),a,r,done=self.replay.sample(batch_size)
        a=a.to(torch.long).view(-1,1,1).expand(-1,1,self.n_quantiles)
        predicted=self.online(s).gather(1,a).squeeze(1)
        with torch.no_grad():
            nextq_online=self.online(s2)
            greedy=nextq_online.mean(-1).argmax(-1).view(-1,1,1).expand(-1,1,self.n_quantiles)
            nextq=self.target(s2).gather(1,greedy).squeeze(1)
            targets=r+self.gamma*(1-done)*nextq
        delta=targets[:,None,:]-predicted[:,:,None]
        huber=torch.where(delta.abs()<=1,.5*delta.square(),delta.abs()-.5)
        tau=(torch.arange(self.n_quantiles,dtype=torch.float32)+.5)/self.n_quantiles
        loss=((tau[None,:,None]-(delta.detach()<0).float()).abs()*huber).mean()
        self.opt.zero_grad();loss.backward();self.opt.step()
        self.counter+=1
        if self.counter%200==0:self.target.load_state_dict(self.online.state_dict())
        return {'qr_loss':float(loss.item())}
