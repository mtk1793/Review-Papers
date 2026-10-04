from pathlib import Path
import ast,inspect,importlib.util,numpy as np,pandas as pd
from sklearn.metrics import f1_score,matthews_corrcoef
ROOT=Path(__file__).resolve().parents[1]; R=ROOT/'results_v2'; C=ROOT/'code_v2'; TST=ROOT/'tests'; TST.mkdir(exist_ok=True)
p=np.load(R/'v2_full_test_predictions.npz'); y,raw,safe,ts=p['y'],p['raw'],p['safe'],p['ts']; uniq=np.unique(ts)
# Window-level confusion matrices permit paired block bootstrap without treating overlapping EV samples as iid.
def cm(y,p):
    z=np.zeros((3,3),dtype=np.int64)
    np.add.at(z,(y,p),1); return z
cms_raw=[];cms_safe=[]
for t in uniq:
    m=ts==t;cms_raw.append(cm(y[m],raw[m]));cms_safe.append(cm(y[m],safe[m]))
cms_raw=np.stack(cms_raw);cms_safe=np.stack(cms_safe)
def metrics_from_cm(c):
    # macro-F1 and multiclass MCC from confusion matrix.
    tp=np.diag(c).astype(float); pred=c.sum(0).astype(float); true=c.sum(1).astype(float)
    f=2*tp/np.maximum(pred+true,1); macro=f.mean()
    n=c.sum(); s=tp.sum(); num=s*n-np.dot(pred,true); den=np.sqrt(max((n*n-np.dot(pred,pred))*(n*n-np.dot(true,true)),1e-30)); mcc=num/den
    return macro,mcc
rng=np.random.default_rng(1793);B=1000; rec=[]; deltas=[]
for b in range(B):
    ii=rng.integers(0,len(uniq),len(uniq)); a=cms_raw[ii].sum(0); q=cms_safe[ii].sum(0); ma,ca=metrics_from_cm(a); mb,cb=metrics_from_cm(q); rec.append((b,ma,ca,mb,cb));deltas.append((mb-ma,cb-ca))
df=pd.DataFrame(rec,columns=['replicate','raw_macro_f1','raw_mcc','pgcare_macro_f1','pgcare_mcc']);df.to_csv(R/'v2_block_bootstrap_replicates.csv',index=False)
d=np.array(deltas); out=pd.DataFrame([
 {'metric':'macro_f1_delta','estimate':metrics_from_cm(cms_safe.sum(0))[0]-metrics_from_cm(cms_raw.sum(0))[0],'ci_low':np.quantile(d[:,0],.025),'ci_high':np.quantile(d[:,0],.975)},
 {'metric':'mcc_delta','estimate':metrics_from_cm(cms_safe.sum(0))[1]-metrics_from_cm(cms_raw.sum(0))[1],'ci_low':np.quantile(d[:,1],.025),'ci_high':np.quantile(d[:,1],.975)}])
out.to_csv(R/'v2_block_bootstrap_ci.csv',index=False)
# Static source-code invariant: physics_project must not reference realized future arrays.
src=(C/'12_train_leakfree_pgcare.py').read_text(); tree=ast.parse(src); fn=None
for node in tree.body:
    if isinstance(node,ast.FunctionDef) and node.name=='physics_project': fn=node;break
assert fn is not None
names={n.id for n in ast.walk(fn) if isinstance(n,ast.Name)}
for forbidden in {'conn','state','ttd','req','dec_conn_h1'}:
    assert forbidden not in names, f'Leak invariant failed: {forbidden} referenced in physics_project'
# The only allowed SOC access is at the forecast issue index ts, never ts+H.
for n in ast.walk(fn):
    if isinstance(n,ast.BinOp) and isinstance(n.op,ast.Add):
        ids={x.id for x in ast.walk(n) if isinstance(x,ast.Name)}
        assert not ({'ts','H'} <= ids), 'Leak invariant failed: ts+H appears in physics_project'
(TST/'LEAK_FREE_INVARIANT_PASS.txt').write_text('PASS: physics_project has no realized future array access and no ts+H expression.\n')
print(out.to_string(index=False));print('Leak invariant: PASS')
