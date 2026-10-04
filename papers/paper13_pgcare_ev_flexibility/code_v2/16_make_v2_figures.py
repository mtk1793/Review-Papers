from pathlib import Path
import numpy as np,pandas as pd,matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'results_v2';D=ROOT/'data_v2';F=ROOT/'figures_v2';F.mkdir(exist_ok=True)
# 1 framework
fig,ax=plt.subplots(figsize=(9,2.8)); ax.axis('off')
labels=['History + declared\nschedule','State + connectivity\nforecasters','Leak-free physics\nprojection','Split conformal\nstate sets + CQR','Abstain / reliability-\nbudgeted recovery','IEEE 33-bus\nQSTS']
xs=np.linspace(.08,.92,len(labels))
for x,l in zip(xs,labels): ax.text(x,.55,l,ha='center',va='center',bbox=dict(boxstyle='round,pad=.45',fc='white',ec='black'),fontsize=9)
for a,b in zip(xs[:-1],xs[1:]): ax.annotate('',xy=(b-.065,.55),xytext=(a+.065,.55),arrowprops=dict(arrowstyle='->'))
ax.text(.5,.12,'No realized target-time connectivity, state, SOC, or flexibility enters the decision layer',ha='center',fontsize=9,fontweight='bold')
fig.tight_layout(); fig.savefig(F/'fig1_v2_framework.pdf',bbox_inches='tight');fig.savefig(F/'fig1_v2_framework.png',dpi=220,bbox_inches='tight');plt.close(fig)
# 2 declared vs actual schedule example
z=np.load(D/'digital_twin_v2.npz'); ev=3; days=np.arange(7); da=z['dec_arr'][days,ev];aa=z['act_arr'][days,ev];dd=z['dec_dep'][days,ev];ad=z['act_dep'][days,ev]
fig,ax=plt.subplots(figsize=(7,3));x=np.arange(len(days));ax.plot(x,da,'o-',label='Declared arrival');ax.plot(x,aa,'s--',label='Actual arrival');ax.plot(x,dd,'o-',label='Declared departure');ax.plot(x,ad,'s--',label='Actual departure');ax.set_xlabel('Day');ax.set_ylabel('Clock hour');ax.set_ylim(0,24);ax.legend(ncol=2,fontsize=8);ax.grid(alpha=.25);fig.tight_layout();fig.savefig(F/'fig2_schedule_uncertainty.pdf');fig.savefig(F/'fig2_schedule_uncertainty.png',dpi=220);plt.close(fig)
# 3 classification
m=pd.read_csv(R/'v2_classification_metrics.csv');fig,ax=plt.subplots(figsize=(6.7,3.1));xx=np.arange(len(m));w=.24
for i,c in enumerate(['macro_f1','mcc','v2g_f1']):ax.bar(xx+(i-1)*w,m[c],width=w,label=c.replace('_',' ').upper())
ax.set_xticks(xx,m.model,rotation=12,ha='right');ax.set_ylim(.6,1);ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(F/'fig3_leakfree_metrics.pdf');fig.savefig(F/'fig3_leakfree_metrics.png',dpi=220);plt.close(fig)
# 4 rolling macro F1
r=pd.read_csv(R/'v2_rolling_origin_metrics.csv');fig,ax=plt.subplots(figsize=(6.6,3));
for name,g in r.groupby('model'):ax.plot(g.start_day,g.macro_f1,'o-',label=name)
ax.set_xlabel('Test-window start day');ax.set_ylabel('Macro-F1');ax.set_ylim(.65,.86);ax.grid(alpha=.25);ax.legend();fig.tight_layout();fig.savefig(F/'fig4_rolling_origin.pdf');fig.savefig(F/'fig4_rolling_origin.png',dpi=220);plt.close(fig)
# 5 ablation
ab=pd.read_csv(R/'v2_feature_group_ablation.csv');fig,ax=plt.subplots(figsize=(6.5,3));ax.bar(ab.feature_set,ab.macro_f1);ax.set_ylabel('Unseen-EV macro-F1');ax.set_ylim(.6,.82);ax.tick_params(axis='x',rotation=18);ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(F/'fig5_feature_ablation.pdf');fig.savefig(F/'fig5_feature_ablation.png',dpi=220);plt.close(fig)
# 6 conditional coverage
cc=pd.read_csv(R/'v2_conditional_coverage.csv');c=cc[cc.group=='class'];h=cc[cc.group=='hour_block'];fig,ax=plt.subplots(figsize=(6.5,3));ax.bar(['Idle','G2V','V2G'],c.coverage);ax.axhline(.9,ls='--',lw=1,label='Nominal 90%');ax.set_ylim(.75,1);ax.set_ylabel('Conformal coverage');ax.legend(fontsize=8);ax.grid(axis='y',alpha=.2);fig.tight_layout();fig.savefig(F/'fig6_class_coverage.pdf');fig.savefig(F/'fig6_class_coverage.png',dpi=220);plt.close(fig)
# 7 feeder tradeoff
q=pd.read_csv(R/'v2_ieee33_qsts_summary.csv');q=q[q.strategy!='No forecast V2G'];fig,ax=plt.subplots(figsize=(6.4,3.2));ax.scatter(q.commit_shortfall_mwh,q.mean_loss_kw,s=65)
for _,row in q.iterrows():ax.annotate(row.strategy,(row.commit_shortfall_mwh,row.mean_loss_kw),xytext=(5,3),textcoords='offset points',fontsize=7)
ax.set_xlabel('Commitment shortfall (MWh)');ax.set_ylabel('Mean feeder loss (kW)');ax.grid(alpha=.25);fig.tight_layout();fig.savefig(F/'fig7_qsts_tradeoff.pdf');fig.savefig(F/'fig7_qsts_tradeoff.png',dpi=220);plt.close(fig)
# 8 CQR interval example
pa=pd.read_csv(R/'v2_prediction_audit_sample.csv').iloc[::400].head(80);fig,ax=plt.subplots(figsize=(6.6,3));x=np.arange(len(pa));ax.fill_between(x,pa.up_lower_kw,pa.up_upper_kw,alpha=.25,label='90% CQR interval');ax.plot(x,pa.up_true_kw,'.',ms=3,label='True up-flex');ax.plot(x,pa.up_mean_kw,lw=1,label='Point forecast');ax.set_ylabel('Per-EV up-flex (kW)');ax.set_xlabel('Sample index');ax.legend(fontsize=8,ncol=3);fig.tight_layout();fig.savefig(F/'fig8_cqr.pdf');fig.savefig(F/'fig8_cqr.png',dpi=220);plt.close(fig)
print('figures',len(list(F.glob('*'))))
