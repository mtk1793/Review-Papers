#!/usr/bin/env python3
"""Generate ONLY source-provenance-validated real-data results tables and figures."""
import csv,json,sys
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
root=Path(__file__).resolve().parents[1]
path=root/'results'/'empirical_results.json'
if not path.exists():raise SystemExit('NO EMPIRICAL DATA: run run_empirical.py with real wind and verified provenance first')
r=json.loads(path.read_text())
if r.get('not_historical_hydrogen_market_or_AC_powerflow') is not True or not r.get('data_file_sha256'):
    raise SystemExit('RESULT VALIDATION FAILED: missing input provenance and evidence qualification')
methods=list(r['baselines']); vals=[r['baselines'][x]['scenario_net_usd'] for x in methods]
seeds=r['trained_by_seed'];rlvals=[seeds[x]['hierarchical']['scenario_net_usd'] for x in seeds]
lo,hi=r['seed_t_ci95_net_usd'];methods+=['hierarchical (seed mean)'];vals+=[float(np.mean(rlvals))]
with (root/'results'/'table_controller_comparison.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['method','scenario_net_usd','not_bankable_npv'])
    for a,b in zip(methods,vals):w.writerow([a,b,True])
fig,ax=plt.subplots(figsize=(8,4.6));bars=ax.bar(methods,vals)
ax.errorbar([len(methods)-1],[vals[-1]],yerr=[[vals[-1]-lo],[hi-vals[-1]]],fmt='none',capsize=5)
ax.set_ylabel('Scenario net cash (USD, NOT NPV)');ax.set_title('Holdout scenario cash; seed 95% t interval shown for hierarchy')
ax.tick_params(axis='x',rotation=20);ax.grid(axis='y',alpha=.15);fig.tight_layout()
fig.savefig(root/'figures'/'empirical_cash.png',dpi=240);plt.close(fig)
fc=r['forecast'];fig,ax=plt.subplots(figsize=(7,3.9))
keys=['median_mae_mw','median_rmse_mw','interval_mean_width_mw'];ax.bar(keys,[fc[k] for k in keys]);ax.tick_params(axis='x',rotation=15)
ax.set_ylabel('MW');ax.set_title(f"Forecast holdout diagnostics; 80% interval coverage {fc['interval_80_coverage']:.3f}")
fig.tight_layout();fig.savefig(root/'figures'/'empirical_forecast.png',dpi=240);plt.close(fig)
(root/'results'/'empirical_results_readme.txt').write_text('These are modelled wind/scenario-pricing outcomes, not true NS operating results. Source SHA256: '+r['data_file_sha256']+'\n')
print('Created reproducible empirical figures (real weather and assumed economics are distinguished).')
