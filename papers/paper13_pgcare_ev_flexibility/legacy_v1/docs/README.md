# PG-CARE EV Flexibility Forecasting — Full Reproducibility Package

This package supports the IEEE Transactions-style manuscript:

**Physics-Guided Conformal Reliability for One-Hour-Ahead Electric-Vehicle Flexibility Forecasting and Risk-Aware V2G Dispatch**

Authors: Mahmoud Mohammadnezhad Kiasari and Hamed H. Aly.

## Scientific provenance

The supervisory EV logic is a Python reconstruction/extension of the published MATLAB/Simulink controller in:

M. M. Kiasari and H. H. Aly, “A proposed controller for real-time management of electrical vehicle battery fleet with MATLAB/SIMULINK,” *Journal of Energy Storage*, vol. 99, Art. no. 113235, 2024, doi: 10.1016/j.est.2024.113235.

The original `.slx` source and a historical manuscript snapshot are retained in `source_artifacts/`. See `SOURCE_PROVENANCE.md` for the exact Google Drive file/folder IDs and source hash.

The Python model reproduces the **supervisory** concepts: owner policy, minimum-SOC protection, plug-in availability, prior-day Q1/Q3 load thresholds, G2V/V2G/Idle state selection, charger constraints, and SOC energy balance. It is an averaged 15-min fleet model and does **not** claim switching-level equivalence to the original 10-kHz converter simulation.

## Study scale

- 365 days
- 100 heterogeneous EVs
- 15-min supervisory interval
- 3,504,000 EV-time states
- Natural state distribution: 84.81% Idle, 11.38% G2V, 3.81% V2G
- No SMOTE or synthetic minority oversampling for final state labels
- Strict chronological 60/20/20 train/validation/test periods
- Deterministic sampled budgets: 30,000 / 10,000 / 20,000 EV-window examples
- 2-h historical window; 1-h forecast horizon

## PG-CARE

PG-CARE means **Physics-Guided Conformal Adaptive Reliability Engine**. The final pathway is:

1. Modern expert pool: LightGBM, XGBoost, CatBoost, Random Forest, Logistic Regression, and TC-MoE.
2. Validation-based expert selection. LightGBM is selected for operating-state classification; the TC-MoE negative result is retained.
3. Physics-feasibility projection based on future connectivity, owner participation, SOC margin, charger rating, and departure requirement.
4. Split-conformal reliability sets calibrated only on the chronological validation period.
5. Conservative fallback for ambiguous/non-singleton sets.
6. XGBoost aggregate upward-flexibility regression plus a validation-selected reserve-commitment factor under asymmetric shortfall penalties.

## Headline reproduced results

### Chronological held-out test

- Raw LightGBM: macro-F1 **0.7501**, MCC **0.6768**, V2G F1 **0.5471**.
- LightGBM + physics: macro-F1 **0.8424**, MCC **0.7608**, V2G F1 **0.7969**.
- Full PG-CARE: macro-F1 **0.8482**, MCC **0.7663**, V2G F1 **0.7935**.
- 90% conformal marginal coverage: **0.9012**; ambiguous-set rate: **4.56%**.
- Paired bootstrap PG-CARE minus LightGBM (1,000 resamples): macro-F1 **+0.0981 [0.0902, 0.1054]**, MCC **+0.0896 [0.0811, 0.0974]**, V2G F1 **+0.2464 [0.2255, 0.2664]**.

### Frozen 90-day shifted regime — no retraining

- Raw LightGBM: macro-F1 **0.6840**, V2G F1 **0.4007**.
- PG-CARE: macro-F1 **0.7970**, V2G F1 **0.7066**.
- LightGBM conformal coverage: **0.8942**; ambiguous-set rate: **4.20%**.

The shifted regime uses later arrivals, earlier departures, longer trips, heavier/peakier native load, lower PV, and more volatile time-of-use prices. It is a deliberately synthetic OOD stress test, not an external measured dataset.

### Closed-loop reserve-value study

Study assumptions: $0.18/kWh delivered reserve revenue and $0.55/kWh shortfall penalty. These are scenario assumptions, not market quotations.

- Raw XGBoost flexibility forecast: **-$1,161.67** net, **11.49 MWh** shortfall.
- PG-CARE risk-calibrated commitment: **+$697.67** net, **2.32 MWh** shortfall.
- Shifted regime: raw XGBoost **-$1,761.48** vs PG-CARE **+$742.86**.
- Throughput-cost sensitivity is provided instead of claiming a full electrochemical aging model.

## Reproduction

Install the exact recorded dependencies:

```bash
python -m pip install -r requirements.txt
```

Then run:

```bash
python reproduce_all.py
```

The final deterministic sequence is:

1. `code/01_generate_digital_twin.py`
2. `code/02_train_core_models.py`
3. `code/03_train_modern_baselines.py`
4. `code/04_build_pgcare.py`
5. `code/05_ood_and_statistics.py`
6. `code/07_pgcare_bootstrap.py`
7. `code/08_inference_timing.py`
8. `code/09_make_figures.py`
9. `code/10_build_manuscript.py`

Earlier exploratory/duplicate scripts are retained in `code/development_archive/` for auditability but are not part of the final reproduction path.

## Key package documents

- `RESULTS_TRACEABILITY.md` — maps every major manuscript claim to a code/output file.
- `DATA_DICTIONARY.md` — describes the generated data and model features.
- `SOURCE_PROVENANCE.md` — documents the original Simulink artifact and source lineage.
- `MANIFEST.csv` — artifact inventory.
- `SHA256SUMS.txt` — integrity hashes.
- `references/references_2020_2026.csv` and `.bib` — 25-paper 2020–2026 bibliography used for positioning.
- `manuscript/PG_CARE_IEEE_Transactions_Manuscript.docx` — final Word manuscript.
- `manuscript/PG_CARE_IEEE_Transactions_Manuscript.pdf` — rendered PDF preview.

## Evidence boundaries

The manuscript explicitly does **not** claim:

- measured external-field validation;
- use of ACN-Data or another public EV dataset to fit the reported results;
- switching-level Python/Simulink equivalence;
- distribution-network power-flow, voltage, transformer-thermal, or HIL validation;
- market-specific reserve revenue;
- electrochemical battery-aging validation.

These boundaries are deliberate so the evidence remains reproducible and auditable.
