# PG-CARE v2 — Claim-to-Evidence Traceability

This file maps manuscript-level claims to the exact code and result artifacts that support them.

| Claim | Primary result file | Generating code |
|---|---|---|
| Declared vs realized one-hour connection schedules are separated | `data_v2/digital_twin_v2.npz` | `code_v2/11_generate_leakfree_twin.py` |
| Target-time connectivity is prohibited from the feasibility mask | `tests/LEAK_FREE_INVARIANT_PASS.txt` | `code_v2/15_block_bootstrap_and_tests.py` |
| Future-connectivity model performance | `results_v2/v2_summary.json` | `code_v2/12_train_leakfree_pgcare.py` |
| Raw / physics / PG-CARE classification metrics | `results_v2/v2_classification_metrics.csv` | `code_v2/12_train_leakfree_pgcare.py` |
| Marginal conformal calibration / ECE / Brier | `results_v2/v2_calibration_metrics.csv` | `code_v2/12_train_leakfree_pgcare.py` |
| Class/hour conditional coverage | `results_v2/v2_conditional_coverage.csv` | `code_v2/12_train_leakfree_pgcare.py` |
| CQR flexibility interval performance | `results_v2/v2_cqr_metrics.csv` | `code_v2/12_train_leakfree_pgcare.py` |
| Full test predictions used for later analysis | `results_v2/v2_full_test_predictions.npz` | `code_v2/12_train_leakfree_pgcare.py` |
| McNemar paired classification test | `results_v2/v2_mcnemar.csv` | `code_v2/12_train_leakfree_pgcare.py` |
| Rolling-origin behavior | `results_v2/v2_rolling_origin_metrics.csv` | `code_v2/13_generalization_ablation.py` |
| Never-seen EV evaluation | `results_v2/v2_unseen_ev_metrics.csv` | `code_v2/13_generalization_ablation.py` |
| Feature-group ablation | `results_v2/v2_feature_group_ablation.csv` | `code_v2/13_generalization_ablation.py` |
| Declared-schedule corruption stress test | `results_v2/v2_schedule_stress.csv` | `code_v2/13_generalization_ablation.py` |
| IEEE 33-bus QSTS results and RBR tradeoff | `results_v2/v2_ieee33_qsts_summary.csv`, `v2_ieee33_qsts_timeseries.csv` | `code_v2/14_ieee33_qsts.py` |
| Paired issue-time block-bootstrap uncertainty | `results_v2/v2_block_bootstrap_ci.csv`, `v2_block_bootstrap_replicates.csv` | `code_v2/15_block_bootstrap_and_tests.py` |
| Vector/raster figures | `figures_v2/*` | `code_v2/16_make_v2_figures.py` |
| Editable Word manuscript | `manuscript/PG_CARE_Leakage_Free_IEEE_Transactions_Manuscript.docx` | `code_v2/17_build_v2_manuscript.py` |
| IEEEtran LaTeX manuscript | `manuscript/PG_CARE_Leakage_Free_IEEE_Transactions_Manuscript.tex` | `code_v2/18_build_v2_latex.py` |
| IEEE-style PDF | `manuscript/PG_CARE_Leakage_Free_IEEE_Transactions_Manuscript.pdf` | LaTeX build from the preceding source |

## Important non-claims

The archive does **not** support any claim that:

- the Python supervisory twin is switching-level equivalent to the original Simulink power-electronic model;
- the study has completed field-data external validation;
- marginal split-conformal validity implies V2G-class conditional validity;
- RBR has a formal optimality theorem;
- the stressed IEEE 33-bus voltages represent a specific real utility feeder;
- the old v1 economic/market scenario is a validated ISO settlement product.

Those boundaries are intentional and should be preserved in any revision or submission.
