# Manuscript result traceability

This file maps the major manuscript claims to the code and machine-readable result files that support them.

| Manuscript claim | Evidence file | Generating code |
|---|---|---|
| 365 days, 100 EVs, 3,504,000 EV-time states | `results/study_summary.json`, `data/digital_twin_arrays.npz` | `code/01_generate_digital_twin.py`, `code/02_train_core_models.py` |
| Natural class distribution 84.81% Idle / 11.38% G2V / 3.81% V2G | `results/study_summary.json`, `figures/fig3_class_distribution.png` | `code/01_generate_digital_twin.py`, `code/09_make_figures.py` |
| LightGBM macro-F1 0.7501; V2G F1 0.5471 | `results/modern_baselines.csv`, `results/pgcare_lgbm_metrics.csv` | `code/03_train_modern_baselines.py`, `code/04_build_pgcare.py` |
| PG-CARE macro-F1 0.8482; MCC 0.7663; V2G F1 0.7935 | `results/pgcare_lgbm_metrics.csv`, `results/prediction_audit_lgbm_full_test.csv` | `code/04_build_pgcare.py` |
| 90.12% conformal coverage; 4.56% ambiguous sets | `results/study_summary.json` | `code/04_build_pgcare.py` |
| 1,000-resample 95% confidence intervals and paired deltas | `results/bootstrap_ci_lgbm.csv`, `results/paired_bootstrap_lgbm.csv` | `code/07_pgcare_bootstrap.py` |
| XGB SOC/flexibility MAEs and TC-MoE negative result | `results/regression_metrics.csv` | `code/02_train_core_models.py` |
| Frozen shifted-regime LightGBM macro-F1 0.6840 vs PG-CARE 0.7970 | `results/ood_shift_metrics.csv`, `results/ood_summary.json` | `code/05_ood_and_statistics.py` |
| In-domain raw XGB net -$1,161.67 vs PG-CARE +$697.67 | `results/closed_loop_metrics.csv` | `code/02_train_core_models.py` |
| OOD raw XGB net -$1,761.48 vs PG-CARE +$742.86 | `results/ood_closed_loop_metrics.csv` | `code/05_ood_and_statistics.py` |
| Throughput-cost sensitivity / approximate break-even | `results/throughput_cost_sensitivity.csv` | `code/05_ood_and_statistics.py` |
| CPU inference timing | `results/inference_timing.csv` | `code/08_inference_timing.py` |
| Paper figures | `figures/fig1_framework.png` … `figures/fig10_confusion.png` | `code/09_make_figures.py` |
| Word manuscript | `manuscript/PG_CARE_IEEE_Transactions_Manuscript.docx` | `code/10_build_manuscript.py` |

## Evidence boundaries

The study does **not** claim measured real-world external validation, ACN-trained results, switching-level Python/Simulink equivalence, distribution power-flow validation, voltage/thermal/HIL validation, or an electrochemical battery-aging model. Reserve prices/penalties are controlled scenario assumptions.
