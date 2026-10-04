# Recommended Code Run Order

The package preserves both the final reproduction scripts and the development archive. For a clean rerun, use the final scripts in this order:

1. `code/01_generate_digital_twin.py` — generate the 365-day fleet digital twin and aggregate time series.
2. `code/02_train_core_models.py` — train the core forecasting models and save split indices/models.
3. `code/03_train_modern_baselines.py` — train modern comparison baselines.
4. `code/04_build_pgcare.py` — apply the PG-CARE physics/conformal reliability layers.
5. `code/05_ood_and_statistics.py` — run shifted-regime/OOD tests and statistical analyses.
6. `code/06_xgb_bootstrap.py` — bootstrap intervals for XGBoost results.
7. `code/07_pgcare_bootstrap.py` — bootstrap intervals for PG-CARE results.
8. `code/08_inference_timing.py` — benchmark inference timing.
9. `code/09_make_figures.py` — regenerate manuscript figures.
10. `code/10_build_manuscript.py` — rebuild the Word manuscript.
11. `reproduce_all.py` — orchestration entry point for the reproducibility workflow.

Additional scripts such as `code/run_study.py`, `code/train_fast.py`, and `code/development_archive/*` are retained as part of the original development trail and should not be substituted silently for the final numbered pipeline.
