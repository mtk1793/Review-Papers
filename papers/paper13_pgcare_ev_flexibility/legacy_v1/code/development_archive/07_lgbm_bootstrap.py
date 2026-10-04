from pathlib import Path
import numpy as np,pandas as pd
from sklearn.metrics import f1_score,matthews_corrcoef
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results';SEED=1793
a=pd.read_csv(R/'prediction_audit_lgbm_full_test.csv');y=a.true.to_numpy(int);b=a.lgbm.to_numpy(int);p=a.pgcare_lgbm.to_numpy(int);M=len(y);rng=np.random.default_rng(SEED+3000);B=1000
def met(yy,pp):return (f1_score(yy,pp,average='macro'),matthews_corrcoef(yy,pp),f1_score(yy,pp,labels=[2],average='macro',zero_division=0))
rows=[]
for name,pred in [('LightGBM',b),('PG-CARE',p)]:
 vals=np.zeros((B,3))
 for i in range(B):
  q=rng.integers(0,M,M);vals[i]=met(y[q],pred[q])
 est=met(y,pred)
 for j,k in enumerate(['macro_f1','mcc','v2g_f1']):rows.append({'model':name,'metric':k,'estimate':est[j],'ci_low':np.quantile(vals[:,j],.025),'ci_high':np.quantile(vals[:,j],.975)})
d=np.zeros((B,3))
for i in range(B):
 q=rng.integers(0,M,M);d[i]=np.array(met(y[q],p[q]))-np.array(met(y[q],b[q]))
est=np.array(met(y,p))-np.array(met(y,b));drows=[]
for j,k in enumerate(['macro_f1','mcc','v2g_f1']):drows.append({'metric':k,'delta_estimate':est[j],'ci_low':np.quantile(d[:,j],.025),'ci_high':np.quantile(d[:,j],.975)})
pd.DataFrame(rows).to_csv(R/'bootstrap_ci_lgbm.csv',index=False);pd.DataFrame(drows).to_csv(R/'paired_bootstrap_lgbm.csv',index=False)
print(pd.DataFrame(rows).to_string(index=False));print(pd.DataFrame(drows).to_string(index=False))
