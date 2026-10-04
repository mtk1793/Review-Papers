# PG-CARE v2 — Leakage-Free IEEE Transactions Upgrade

This archive is the **superseding reproducibility package** for the manuscript:

**PG-CARE: Leakage-Free Physics-Guided Conformal Reliability for One-Hour-Ahead EV Flexibility Forecasting and Distribution-Feeder Support**

Authors: Mahmoud M. Kiasari and Hamed H. Aly.

## What changed from v1

The v1 draft contained a serious information-integrity flaw: the physical feasibility mask used realized target-time connectivity. That meant the post-processor had access to future information that would not be known when a one-hour-ahead forecast is issued. v2 removes that dependency completely.

The v2 pipeline now:

1. separates **declared connection schedule** from **realized connection**;
2. predicts one-hour-ahead connectivity from issuance-time history;
3. prohibits target-time state/connectivity from entering the feasibility projection;
4. recalibrates classification conformal prediction **after** the leak-free projection;
5. uses conformalized quantile regression (CQR) for upward flexibility;
6. evaluates every hour over the full contiguous 85-day test interval (203,900 EV forecasts);
7. adds rolling-origin, unseen-EV, schedule-corruption, feature-group and paired block-bootstrap analyses;
8. adds a standard IEEE 33-bus balanced AC QSTS stress test;
9. adds **Reliability-Budgeted Recovery (RBR)** to recover useful flexibility from a conservative CQR lower bound without forcing unsupported commitments;
10. retains external measured-data acquisition adapters, but does **not** claim measured-data validation has already been executed.

## Headline results

Chronological full test (203,900 forecasts):

- LightGBM raw macro-F1: **0.798645**; V2G F1: **0.669969**.
- Leak-free physical projection macro-F1: **0.813989**; V2G F1: **0.708779**.
- PG-CARE v2 conformal + abstention macro-F1: **0.818274**; V2G F1: **0.715495**.
- Paired issue-time block-bootstrap PG-CARE minus raw macro-F1: **+0.019630**, 95% CI **[+0.017056, +0.022081]**.
- Exact McNemar test: raw-wrong/PG-right = **2554**, raw-right/PG-wrong = **543**, p = **6.26e-310**.
- Marginal split-conformal coverage: **0.911667**; V2G-conditional coverage is only **0.801585** and is therefore reported as a limitation, not hidden.
- CQR upward-flexibility coverage: **0.899632** with mean interval width **6.501806 kW**.

IEEE 33-bus QSTS stress test (2,039 hourly issue times):

- Raw mean-flexibility commitment: **125.535 MWh** delivered with **8.678 MWh** commitment shortfall.
- PG-CARE CQR lower bound: **43.135 MWh**, **0 observed shortfall**.
- PG-CARE RBR: **53.762 MWh**, **0 observed shortfall**.
- Oracle realized flexibility: **152.178 MWh**.

The feeder is a deliberately stressed standard test system. Absolute voltage values must not be interpreted as a utility-feeder claim.

## Reproduction

Run from the repository/package root:

```bash
python reproduce_v2.py
```

The default runner executes the offline v2 pipeline only. External-data adapters are **not** run automatically and require the user to obtain any necessary credentials/data under the providers' terms.

Individual stages are documented in `CODE_RUN_ORDER_V2.md`.

## Evidence boundary

This package supports a **source-informed supervisory Python reconstruction** of the published MATLAB/Simulink controller logic. It does not claim switching-level equivalence to the original converter model, a field trial, a utility deployment, or arbitrary out-of-distribution conformal guarantees.

The highest-priority remaining flagship-submission gate is **executed measured-data external validation**. See `EXTERNAL_VALIDATION_PROTOCOL.md` and `LIMITATIONS_AND_SUBMISSION_GATE.md`.

## Key folders

- `manuscript/` — final editable Word, IEEEtran LaTeX source and compiled PDF.
- `code_v2/` — current leak-free analysis pipeline.
- `legacy_v1/` — superseded code/results retained for audit history; do not use for headline claims.
- `data_v2/` — v2 synthetic digital-twin arrays and aggregates.
- `results_v2/` — trained models, prediction audit, calibration, statistics and QSTS results.
- `figures_v2/` — raster and vector manuscript figures.
- `references/` — 2020–2026 literature database in CSV/BibTeX/text forms.
- `source_artifacts/` — original Simulink model and working manuscript used for provenance.
- `tests/` — information-integrity invariant result.
- `docs/` — novelty, limitations, traceability and critique-resolution records.

## Integrity

`SHA256SUMS.txt` records hashes for the final package contents. `MANIFEST.csv` records file paths, sizes and hashes.
