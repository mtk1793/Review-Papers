# PG-CARE v2 — Code Run Order

All commands assume the package/repository root as the working directory.

## Offline v2 pipeline

1. `python code_v2/11_generate_leakfree_twin.py`
   - Generates the 365-day, 100-EV leak-free digital twin with declared and realized schedules separated.

2. `python code_v2/12_train_leakfree_pgcare.py`
   - Trains future-connectivity, state and flexibility models.
   - Performs leak-free feasibility projection, state conformal calibration, CQR and full contiguous test evaluation.

3. `python code_v2/13_generalization_ablation.py`
   - Runs rolling-origin, unseen-EV, schedule-corruption and feature-group experiments.

4. `python code_v2/14_ieee33_qsts.py`
   - Runs the IEEE 33-bus balanced AC QSTS stress test and RBR comparison.

5. `python code_v2/15_block_bootstrap_and_tests.py`
   - Runs issue-time block bootstrap and the source-code leak invariant.

6. `python code_v2/16_make_v2_figures.py`
   - Regenerates manuscript figures in PNG and vector PDF.

7. `python code_v2/17_build_v2_manuscript.py`
   - Regenerates the editable Word manuscript.

8. `python code_v2/18_build_v2_latex.py`
   - Regenerates the IEEEtran `.tex` source. Compile with `pdflatex` as needed.

Or run stages 1–8 in sequence with:

```bash
python reproduce_v2.py
```

## External measured-data adapters (optional, not part of the reproduced headline evidence)

- `code_v2/external_data/download_acndata.py`
- `code_v2/external_data/download_opsd_household.py`

These are provided for the next validation phase. Do not represent the current manuscript as having executed external measured-data validation merely because these adapters exist.

## Legacy v1

The `legacy_v1/` directory is audit history only. Its physics post-processing is superseded because the hostile review correctly identified target-time connectivity leakage. Do not reuse v1 headline numbers in the v2 manuscript.
