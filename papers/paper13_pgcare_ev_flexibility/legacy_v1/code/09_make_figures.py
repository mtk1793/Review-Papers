from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
ROOT=Path(__file__).resolve().parents[1]; D=ROOT/'data'; R=ROOT/'results'; F=ROOT/'figures'; F.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'serif','font.size':9,'axes.titlesize':9,'axes.labelsize':9,'legend.fontsize':8,'figure.dpi':150,'savefig.dpi':400})

def save(name):
    plt.tight_layout(); plt.savefig(F/name,bbox_inches='tight'); plt.close()

# Fig 1 architecture
fig,ax=plt.subplots(figsize=(7.2,3.2)); ax.axis('off')
boxes=[
 (0.02,0.34,0.16,0.34,'Published MATLAB/\nSimulink controller\nV2G / G2V / Idle'),
 (0.22,0.34,0.16,0.34,'365-day Python\ndigital twin\n100 EVs'),
 (0.42,0.34,0.16,0.34,'Forecast experts\nLightGBM + TC-MoE\nstate / SoC / flex.'),
 (0.62,0.34,0.16,0.34,'PG-CARE reliability\nphysics projection +\nconformal safety'),
 (0.82,0.34,0.16,0.34,'Risk-calibrated\nreserve commitment\nclosed-loop value')]
for x,y,w,h,t in boxes:
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.012',linewidth=1.2,edgecolor='black',facecolor='white'))
    ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=6.6)
for i in range(len(boxes)-1):
    x1=boxes[i][0]+boxes[i][2]; x2=boxes[i+1][0]
    ax.add_patch(FancyArrowPatch((x1+0.006,.51),(x2-0.006,.51),arrowstyle='-|>',mutation_scale=12,linewidth=1.1,color='black'))
ax.text(.50,.88,'Source-informed physical layer',ha='center',fontsize=9,fontweight='bold')
ax.text(.70,.13,'Reliability and operational-value layer',ha='center',fontsize=9,fontweight='bold')
save('fig1_framework.png')

# Fig 2 one representative week
agg=pd.read_csv(D/'aggregate_timeseries.csv'); sl=agg[(agg.day>=175)&(agg.day<182)].copy(); x=(sl.step-sl.step.iloc[0])/96
fig,ax=plt.subplots(figsize=(7.1,2.8)); ax.plot(x,sl.native_kw,label='Native net load',linewidth=1.0); ax.plot(x,sl.feeder_kw,label='With EV controller',linewidth=.9,linestyle='--'); ax.set_xlabel('Day in representative week'); ax.set_ylabel('Power (kW)'); ax.grid(True,alpha=.25); ax.legend(ncol=2,frameon=False); save('fig2_week_operation.png')

# Fig 3 class distribution
summ=json.load(open(R/'study_summary.json')); vals=[summ['idle_fraction'],summ['g2v_fraction'],summ['v2g_fraction']]
fig,ax=plt.subplots(figsize=(4.2,2.8)); bars=ax.bar(['Idle','G2V','V2G'],np.array(vals)*100,edgecolor='black',facecolor=['white','.70','.35']); ax.set_ylabel('Fraction of EV-time states (%)'); ax.set_ylim(0,95); ax.grid(axis='y',alpha=.25)
for b,v in zip(bars,vals): ax.text(b.get_x()+b.get_width()/2,b.get_height()+1,f'{100*v:.1f}%',ha='center',fontsize=8)
save('fig3_class_distribution.png')

# Fig 4 classification benchmark
base=pd.read_csv(R/'classification_metrics.csv'); modern=pd.read_csv(R/'modern_baselines.csv'); pg=pd.read_csv(R/'pgcare_lgbm_metrics.csv')
sel=pd.concat([base[base.model.isin(['Persistence','Random Forest','XGBoost','TC-MoE alone'])],modern[modern.model=='LightGBM'][['model','accuracy','balanced_accuracy','macro_f1','mcc','idle_f1','g2v_f1','v2g_f1']],pg[pg.model.str.startswith('PG-CARE')]],ignore_index=True)
fig,ax=plt.subplots(figsize=(7.2,3.1)); xx=np.arange(len(sel)); w=.25
ax.bar(xx-w,sel.macro_f1,w,label='Macro-F1',facecolor='white',edgecolor='black'); ax.bar(xx,sel.mcc,w,label='MCC',facecolor='.65',edgecolor='black'); ax.bar(xx+w,sel.v2g_f1,w,label='V2G F1',facecolor='.25',edgecolor='black'); ax.set_xticks(xx); ax.set_xticklabels(['Persist.','RF','XGB','TC-MoE','LightGBM','PG-CARE'],rotation=18,ha='right'); ax.set_ylim(0,1); ax.set_ylabel('Score'); ax.grid(axis='y',alpha=.25); ax.legend(ncol=3,frameon=False,loc='lower right'); save('fig4_model_comparison.png')

# Fig 5 reliability ablation
p=pg.copy(); fig,ax=plt.subplots(figsize=(5.3,2.9)); xx=np.arange(3); ax.plot(xx,p.macro_f1,'o-',label='Macro-F1'); ax.plot(xx,p.v2g_f1,'s--',label='V2G F1'); ax.set_xticks(xx); ax.set_xticklabels(['LightGBM','+ physics\nprojection','+ conformal\nsafety']); ax.set_ylim(.5,.9); ax.set_ylabel('Score'); ax.grid(True,alpha=.25); ax.legend(frameon=False); save('fig5_reliability_ablation.png')

# Fig 6 OOD shifted regime
ood=pd.read_csv(R/'ood_shift_metrics.csv'); o=ood[ood.model.isin(['LightGBM','LightGBM + physics','PG-CARE (LightGBM)'])]
fig,ax=plt.subplots(figsize=(5.4,2.9)); xx=np.arange(len(o)); w=.27; ax.bar(xx-w,o.macro_f1,w,label='Macro-F1',facecolor='white',edgecolor='black'); ax.bar(xx,o.mcc,w,label='MCC',facecolor='.65',edgecolor='black'); ax.bar(xx+w,o.v2g_f1,w,label='V2G F1',facecolor='.25',edgecolor='black'); ax.set_xticks(xx); ax.set_xticklabels(['LightGBM','+ physics','PG-CARE']); ax.set_ylim(0,1); ax.set_ylabel('OOD score'); ax.grid(axis='y',alpha=.25); ax.legend(ncol=3,frameon=False); save('fig6_ood_generalization.png')

# Fig 7 reserve economics
ops=pd.read_csv(R/'closed_loop_metrics.csv'); o=ops[ops.strategy.isin(['Persistence','XGBoost','PG-CARE risk-calibrated','Oracle'])]
fig,ax=plt.subplots(figsize=(6.0,3.0)); xx=np.arange(len(o)); bars=ax.bar(xx,o['net_value_$'],edgecolor='black',facecolor=['white','.75','.45','.20']); ax.axhline(0,color='black',linewidth=.8); ax.set_xticks(xx); ax.set_xticklabels(['Persistence','Raw XGB','PG-CARE','Oracle']); ax.set_ylabel('Test-period net reserve value ($)'); ax.grid(axis='y',alpha=.25)
for b,v in zip(bars,o['net_value_$']): ax.text(b.get_x()+b.get_width()/2,v+(100 if v>=0 else -220),f'{v:,.0f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=8)
save('fig7_closed_loop_value.png')

# Fig 8 shortfall comparison
fig,ax=plt.subplots(figsize=(5.4,2.8)); o=ops[ops.strategy.isin(['Persistence','XGBoost','PG-CARE risk-calibrated','Oracle'])]; bars=ax.bar(['Persistence','Raw XGB','PG-CARE','Oracle'],o.shortfall_mwh,edgecolor='black',facecolor=['white','.75','.45','.20']); ax.set_ylabel('Reserve shortfall (MWh)'); ax.grid(axis='y',alpha=.25); save('fig8_shortfall.png')

# Fig 9 throughput-cost sensitivity
deg=pd.read_csv(R/'throughput_cost_sensitivity.csv'); fig,ax=plt.subplots(figsize=(5.7,3.0))
for name,lsn in [('XGBoost','--'),('PG-CARE risk-calibrated','-'),('Oracle',':')]:
 q=deg[deg.strategy==name]; ax.plot(q['throughput_cost_$/kWh'],q['net_after_throughput_$'],marker='o',linestyle=lsn,label=name.replace(' risk-calibrated',''))
ax.axhline(0,color='black',linewidth=.8); ax.set_xlabel('Assumed battery-throughput cost ($/kWh)'); ax.set_ylabel('Net value after throughput proxy ($)'); ax.grid(True,alpha=.25); ax.legend(frameon=False); save('fig9_throughput_sensitivity.png')
print('Wrote figures to',F)

# Fig 10 normalized confusion matrices, final selected expert versus PG-CARE
from sklearn.metrics import confusion_matrix
audit=pd.read_csv(R/'prediction_audit_lgbm_full_test.csv')
labels=['Idle','G2V','V2G']; fig,axs=plt.subplots(1,2,figsize=(7.0,2.8))
for ax,col,title in zip(axs,['lgbm','pgcare_lgbm'],['Raw LightGBM','PG-CARE']):
    cm=confusion_matrix(audit['true'],audit[col],labels=[0,1,2],normalize='true')
    ax.imshow(cm,vmin=0,vmax=1,cmap='Greys')
    for i in range(3):
        for j in range(3):
            ax.text(j,i,f'{cm[i,j]:.2f}',ha='center',va='center',fontsize=8,color='white' if cm[i,j]>.55 else 'black')
    ax.set_xticks(range(3),labels,fontsize=8); ax.set_yticks(range(3),labels,fontsize=8)
    ax.set_xlabel('Predicted state',fontsize=8); ax.set_ylabel('True state',fontsize=8); ax.set_title(title,fontsize=9)
fig.subplots_adjust(wspace=.35,bottom=.20,top=.86,left=.09,right=.98)
fig.savefig(F/'fig10_confusion.png',dpi=220,bbox_inches='tight'); plt.close(fig)
print('Wrote fig10_confusion.png')
