#!/usr/bin/env python3
"""Build figures directly from declared definitions, not illustrative fake gains."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch,ArrowStyle
import numpy as np
root=Path(__file__).resolve().parents[1];out=root/'figures';out.mkdir(exist_ok=True)

def rounded(ax,x,y,w,h,t,face='#F2F5FA',border='#234D73',size=10):
    p=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.02,rounding_size=0.045',linewidth=1.4,edgecolor=border,facecolor=face)
    ax.add_patch(p);ax.text(x+w/2,y+h/2,t,ha='center',va='center',fontsize=size,weight='semibold',color='#1F3348')
def arrow(ax,p,q):ax.annotate('',xy=q,xytext=p,arrowprops=dict(arrowstyle='-|>',color='#405F77',lw=1.5))
fig,ax=plt.subplots(figsize=(7.3,5.8),dpi=200);ax.set_xlim(0,10);ax.set_ylim(0,10);ax.axis('off')
rounded(ax,1.0,8.1,8.0,1.1,'SOURCE DATA (actual wind weather + scenario-only prices)',size=10)
rounded(ax,1.15,5.9,3.3,1.22,'SUPERVISED\nQuantile LSTM (P10/P50/P90)',face='#EDF3FC')
rounded(ax,5.5,5.9,3.3,1.22,'CALIBRATION\n2019 holdout / residual radius',face='#EDF3FC')
arrow(ax,(3,8.1),(2.8,7.12));arrow(ax,(4.5,6.5),(5.5,6.5));arrow(ax,(7.25,5.9),(7.25,4.8))
rounded(ax,5.05,3.5,4.15,1.25,'RL POLICY A\nQR-DQN: discrete risk priorities',face='#FFF6E8',border='#AC6A25')
rounded(ax,.65,3.5,3.9,1.25,'RL POLICY B\nSAC: continuous plant setpoint',face='#FFF6E8',border='#AC6A25')
arrow(ax,(5.05,4.15),(4.55,4.15));arrow(ax,(3.0,5.9),(3.0,4.75))
rounded(ax,1.6,.9,6.8,1.25,'PROJECTED PLANT OPERATIONS\nPower balance | H2 inventory | BESS SOC | ramp and wear',face='#EDF8F2',border='#31674E')
arrow(ax,(2.6,3.5),(3.2,2.15));arrow(ax,(7.3,3.5),(6.7,2.15));ax.text(5,.26,'Two RL modules; LSTM is NOT an RL agent',ha='center',fontsize=10,weight='bold',color='#9A3E2A')
fig.tight_layout();fig.savefig(out/'fig01_architecture.png',dpi=260,bbox_inches='tight');plt.close(fig)

fig,ax=plt.subplots(figsize=(7.4,4.8),dpi=200)
labels=['50 MW maximum\n8,760 h/year','30.6% of\n1,126 GWh','78.2% of\n1,126 GWh']
vals=[438,1126*.306,1126*.782]
bar=ax.bar(labels,vals,color=['#537B99','#78967F','#BD7068'])
ax.axhline(438,color='#203C53',ls='--',lw=1.5,label='Physical upper bound: 438 GWh/year')
for b,v in zip(bar,vals):ax.text(b.get_x()+b.get_width()/2,v+13,f'{v:.1f}',ha='center',fontsize=9)
ax.set_ylim(0,1030);ax.set_ylabel('Annual electrical energy (GWh)')
ax.set_title('Arithmetic audit of conflicting curtailment denominators',fontsize=12)
ax.legend(frameon=False,fontsize=9);ax.grid(axis='y',alpha=.2)
fig.tight_layout();fig.savefig(out/'fig02_feasibility_audit.png',dpi=250,bbox_inches='tight');plt.close(fig)

fig,ax=plt.subplots(figsize=(7.3,4.7),dpi=200)
labels=['Battery installed energy','Energy needed for 36 h\nat 40% of 50 MW']
vals=[20,36*20]
ax.barh(labels,vals,color=['#5685A4','#C27766'])
for i,v in enumerate(vals):ax.text(v+11,i,f'{v:,.0f} MWh',va='center',fontsize=11)
ax.set_xlim(0,840);ax.set_xlabel('Energy (MWh), ignoring losses');ax.set_title('36-hour battery autonomy claim is physically infeasible')
ax.invert_yaxis();ax.grid(axis='x',alpha=.2)
fig.tight_layout();fig.savefig(out/'fig03_battery_autonomy.png',dpi=250,bbox_inches='tight');plt.close(fig)

report=json.loads((root/'results'/'hard_feasibility_audit.json').read_text())
fig,ax=plt.subplots(figsize=(7.3,4.6),dpi=200)
ax.bar(['Annual H2 output\nfrom 340 GWh input','Contracted offtake\n800 kg/day'],
    [report['h2_production_from_340gwh_kg_at_52kwh_per_kg']/1e6,
     report['plant_800kg_per_day_offtake_annual_kg']/1e6],color=['#5B7D98','#BF837B'])
ax.set_ylabel('Million kg hydrogen / year')
ax.set_title('Throughput versus disclosed buyer demand')
for i,v in enumerate([report['h2_production_from_340gwh_kg_at_52kwh_per_kg']/1e6,
     report['plant_800kg_per_day_offtake_annual_kg']/1e6]):ax.text(i,v+.1,f'{v:.2f}',ha='center')
ax.set_ylim(0,7.2);ax.grid(axis='y',alpha=.15)
fig.tight_layout();fig.savefig(out/'fig04_offtake_gap.png',dpi=250,bbox_inches='tight');plt.close(fig)
print('Generated 4 fully reproducible figures from architecture and arithmetic, not fabricated results')
