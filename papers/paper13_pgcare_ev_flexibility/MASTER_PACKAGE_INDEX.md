# PG-CARE v2 Master Reproducibility Package

This archive is the complete master package for the leakage-free PG-CARE v2 study.

## Primary manuscript
- `manuscript/PG_CARE_Leakage_Free_IEEE_Transactions_Manuscript.docx`
- `manuscript/PG_CARE_Leakage_Free_IEEE_Transactions_Manuscript.pdf`
- `manuscript/PG_CARE_Leakage_Free_IEEE_Transactions_Manuscript.tex`

## Reproduction entry point
- `reproduce_v2.py`
- `docs/CODE_RUN_ORDER_V2.md`
- `requirements_v2.txt`
- `ENVIRONMENT_V2.txt`

## Final v2 source code
- `code_v2/11_generate_leakfree_twin.py`
- `code_v2/12_train_leakfree_pgcare.py`
- `code_v2/13_generalization_ablation.py`
- `code_v2/14_ieee33_qsts.py`
- `code_v2/15_block_bootstrap_and_tests.py`
- `code_v2/16_make_v2_figures.py`
- `code_v2/17_build_v2_manuscript.py`
- `code_v2/18_build_v2_latex.py`
- external-data adapters under `code_v2/external_data/`

## Data
- `data_v2/digital_twin_v2.npz` — leak-free digital-twin arrays
- `data_v2/aggregate_timeseries_v2.csv`
- `data_v2/fleet_parameters_v2.csv`

## Trained models / prediction artifacts / statistics
All final model files, prediction arrays, classification metrics, calibration results, CQR results,
rolling-origin results, schedule stress tests, unseen-EV tests, block-bootstrap outputs, and QSTS results are under `results_v2/`.

## Grid study
- `code_v2/14_ieee33_qsts.py`
- `results_v2/v2_ieee33_qsts_timeseries.csv`
- `results_v2/v2_ieee33_qsts_summary.csv`

## Source provenance
- `source_artifacts/V2GStronge2_published_controller.slx`
- `source_artifacts/Published_Controller_Working_Manuscript.docx`
- `docs/SOURCE_PROVENANCE.md`

## Figures
Final PNG and vector PDF figures are under `figures_v2/`.

## References
2020–2026 bibliography files are under `references/` in CSV, text, and BibTeX formats.

## Audit / limitations / novelty
- `docs/RESULTS_TRACEABILITY_V2.md`
- `docs/NOVELTY_AND_EVIDENCE_V2.md`
- `docs/LIMITATIONS_AND_SUBMISSION_GATE.md`
- `docs/REVISION_RESPONSE_TO_CRITIQUE.md`
- `docs/USER_SUPPLIED_HOSTILE_REVIEW_AND_UPGRADE_PLAN.md`
- `docs/USER_SUPPLIED_UPGRADE_PLAN_RAW.md` (raw uploaded plan, when available)
- `tests/LEAK_FREE_INVARIANT_PASS.txt`

## Legacy v1
The complete earlier pipeline, models, data, figures, manuscript, and results are preserved under `legacy_v1/` for scientific auditability. They are superseded by v2 and must not be used for headline v2 claims.

## Integrity
- `MASTER_FILE_INVENTORY.csv` lists every file, size, and SHA-256 digest.
- `MASTER_SHA256SUMS.txt` contains SHA-256 digests for all files except itself and the inventory.
