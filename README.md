# Academic Paper Collection — CAPSM x NERC/NPCC + CNN-LSTM + PG-CARE EV Forecasting

**13 academic research papers**: Papers 1-10 bridge the CAPSM (Cognitive Adaptive Power System Management) PhD thesis with NERC/NPCC reliability standards, Papers 11-12 cover System-1 CNN-LSTM fault detection, and Paper 13 adds PG-CARE physics-guided conformal reliability for one-hour-ahead EV flexibility forecasting and risk-aware V2G dispatch. All methodologies are implemented in Python using open-source tools.

## Paper Inventory

### Part I: CAPSM x NERC/NPCC Standards (Papers 1-10)

| # | Paper | NERC Standards | Test System |
|---|-------|---------------|-------------|
| 1 | PRC-029-1 Ride-Through Verification | PRC-029-1, FAC-002-4, TPL-001-5.1 | IEEE 39-bus |
| 2 | Metacognitive RL for Corrective Actions | TPL-001-5.1, FAC-014-3 | IEEE 118-bus |
| 3 | CNN-LSTM-Surrogate Model Validation (MOD-026-2) | MOD-026-2, MOD-033, MOD-032-1 | Two-machine synthetic PMU benchmark + LBNL real-PMU ingestion case study |
| 4 | UFLS Adequacy with High IBR | PRC-006-5, PRC-006-NPCC-2, MOD-027 | IEEE 39/118-bus |
| 5 | False Data Injection Detection | PRC-023-6, PRC-026-2, CIP-003/005 | IEEE 39/118-bus |
| 6 | FACTS Hosting Capacity | FAC-002-4, FAC-014-3, TPL-001-5.1 | IEEE 39/118-bus |
| 7 | Probabilistic Hosting Capacity (QSTS) | TPL-001-5.1, MOD-031-3, MOD-032-1 | IEEE 118-bus |
| 8 | EV V2G + UVLS Coordination | PRC-010-2, TPL-001-5.1, FAC-002-4 | IEEE 39/118-bus |
| 9 | Real-Time Outage Coordination | IRO-017-1, FAC-014-3, TPL-001-5.1 | IEEE 39/118-bus |
| 10 | Relay Loadability Screening (PINN) | PRC-023-6, FAC-014-3, PRC-026-2 | IEEE 39/118-bus |

### Part II: System-1 CNN-LSTM Fault Detection (Papers 11-12)

| # | Paper | Focus | Status |
|---|-------|-------|--------|
| 11 | Literature Review & Research Gaps | Survey of CNN-LSTM fault detection in power systems | Revision in progress |
| 12 | CNN-LSTM Reflexive Fault Detection | Sub-10ms fault detection with dual-stream CNN-LSTM architecture | Under preparation |

### Part III: PG-CARE EV Flexibility Forecasting (Paper 13)

| # | Paper | Focus | Status |
|---|-------|-------|--------|
| 13 | PG-CARE: Physics-Guided Conformal Reliability for One-Hour-Ahead EV Flexibility Forecasting and Risk-Aware V2G Dispatch | 365-day / 100-EV digital twin (15-min supervisory), LightGBM + physics projection + split-conformal sets, XGBoost flexibility regression with risk-calibrated reserve commitment; IEEE Transactions-style manuscript (PDF + DOCX), 10 figures, full code/data/models | Complete — full reproducibility package in `papers/paper13_pgcare_ev_flexibility/` |

**Paper 13 headline results (chronological held-out test)**: raw LightGBM macro-F1 0.7501 → LightGBM + physics 0.8424 → full PG-CARE 0.8482 (MCC 0.7663, V2G F1 0.7935); 90% conformal marginal coverage 0.9012 with 4.56% ambiguous-set rate. Frozen 90-day shifted regime (no retraining): PG-CARE macro-F1 0.7970 vs raw LightGBM 0.6840. Closed-loop reserve study ($0.18/kWh revenue, $0.55/kWh shortfall penalty assumptions): raw XGBoost –$1,161.67 net / 11.49 MWh shortfall vs PG-CARE +$697.67 net / 2.32 MWh shortfall. See `papers/paper13_pgcare_ev_flexibility/README.md` and `RESULTS_TRACEABILITY.md` for the claim-to-evidence map.

## Quick Start

### Prerequisites

- Python 3.12+
- pip

### Install (Papers 1-10)

```bash
pip install -r requirements.txt
```

### Install (Paper 12)

```bash
cd papers/paper12_cnnlstm_fault_detection/code
pip install -r requirements.txt
```

### Regenerate Figures (Papers 1-10)

```bash
cd scripts

python paper1_prc029_ridethrough.py
python paper2_qirl_corrective_actions.py
python paper3_cnnlstm_model_validation.py
python paper4_ufls_ibr_cosimulation.py
python paper5_fdi_dual_process_detection.py
python paper6_facts_hosting_capacity.py
python paper7_probabilistic_hosting_capacity.py
python paper8_ev_v2g_uvls.py
python paper9_outage_coord_arbiter.py
python paper10_relay_loadability_pinn.py
```

### Run Paper 12

```bash
cd papers/paper12_cnnlstm_fault_detection/code

# Quick test (small dataset, CPU, ~2 min)
python run_all.py --quick --device cpu

# Full training (60K events, GPU recommended, ~20 min)
python run_all.py --device cuda
```

### Run Paper 13 (PG-CARE)

```bash
cd papers/paper13_pgcare_ev_flexibility

# Exact dependencies for the PG-CARE study (separate from root requirements.txt)
python -m pip install -r requirements.txt

# One-command full reproduction (digital twin → training → PG-CARE → OOD/stats → figures → manuscript)
python reproduce_all.py
```

Paper 13 original bundle is also archived as `papers/paper13_pgcare_ev_flexibility/PG_CARE_All_Code_Data_Models_Manuscript.zip` (27 MB).

## Repository Structure

```
Review-Papers/
├── README.md
├── requirements.txt              # Papers 1-10 (root env)
├── worklog.md                    # Production worklog (Papers 1-10)
├── papers/
│   ├── paper11_literature_review/    # Literature review + revision materials
│   ├── paper12_cnnlstm_fault_detection/
│   │   ├── code/                     # PyTorch CNN-LSTM implementation
│   │   │   ├── model.py
│   │   │   ├── train.py
│   │   │   ├── evaluate.py
│   │   │   ├── data/                 # HDF5 datasets (IEEE 9/39/118)
│   │   │   ├── models/               # Trained checkpoints
│   │   │   └── results/              # Evaluation JSONs
│   │   └── figures/                  # Publication figures
│   ├── paper13_pgcare_ev_flexibility/  # PG-CARE EV forecasting (Paper 13)
│   │   ├── README.md                   # Study overview + reproduction guide
│   │   ├── PG_CARE_All_Code_Data_Models_Manuscript.zip  # Original bundle (27 MB)
│   │   ├── reproduce_all.py            # One-command reproduction entry point
│   │   ├── requirements.txt            # Pinned Paper 13 env (numpy, torch, lightgbm, xgboost, catboost, ...)
│   │   ├── CODE_RUN_ORDER.md / DATA_DICTIONARY.md / RESULTS_TRACEABILITY.md / SOURCE_PROVENANCE.md
│   │   ├── code/                       # 01_digital_twin → 02/03_train → 04_pgcare → 05_ood → 07/08_bootstrap/timing → 09_figures → 10_manuscript (+ development_archive/)
│   │   ├── data/                       # Fleet params, aggregate time series, digital-twin arrays
│   │   ├── results/                    # Metrics, bootstrap CIs, trained models (xgb/lgbm/catboost/tcmoe), audit CSVs
│   │   ├── figures/                    # fig1_framework … fig10_confusion (manuscript-ready PNGs)
│   │   ├── manuscript/                 # PG_CARE_IEEE_Transactions_Manuscript.{docx,pdf}
│   │   ├── references/                 # 25-paper 2020–2026 bibliography (.bib/.csv/.txt)
│   │   └── source_artifacts/           # Published Simulink controller (.slx) + working manuscript snapshot
├── scripts/                      # Python simulation scripts (Papers 1-10)
└── figures/                      # Generated PNGs + CSVs (Papers 1-10)
```

## Key Technical Notes

**Test Systems**: Papers 1-2 and 4-10 use IEEE 39-bus or 118-bus via `pypower`. Paper 3 currently uses a reproducible two-machine synthetic PMU benchmark for supervised MOD-026 parameter labels and the LBNL PMU Event Library converter for recorded PMU ingestion/morphology validation. Paper 12 uses IEEE 9/39/118-bus with synthetic PMU data.

**Real PMU Data**: Paper 3 supports the LBNL PMU Event Library via `scripts/paper3_lbnl_real_pmu_summary.py`. Clone `https://github.com/LBNL-ETA/pmu_event_library` outside this repository, then run the converter to regenerate the real-PMU summary, Figure 5, and normalized sample CSV.

**ML Substitutions**: Where the CAPSM thesis uses PyTorch, papers 1-10 use `sklearn` surrogates (MLPRegressor for CNN-LSTM/PINN). Paper 12 uses full PyTorch CNN-LSTM.

**Reproducibility**: All scripts use fixed random seeds. All results are fully reproducible.

**Paper 13 provenance & boundaries**: PG-CARE supervisory EV logic is a Python reconstruction/extension of the published MATLAB/Simulink controller in Kiasari & Aly, *Journal of Energy Storage* vol. 99, Art. 113235 (2024). The original `.slx` snapshot is retained in `papers/paper13_pgcare_ev_flexibility/source_artifacts/` with Drive IDs/hashes in `SOURCE_PROVENANCE.md`. The study is a 365-day averaged 15-min fleet model — no claim of switching-level equivalence, measured external-field validation, ACN-Data fitting, network power-flow/HIL validation, market-specific revenue, or electrochemical aging validation. Dependency pinning is per-paper (`papers/paper13_pgcare_ev_flexibility/requirements.txt`); integrity hashes in `SHA256SUMS.txt`, claim map in `RESULTS_TRACEABILITY.md`.

## License

- **Python code**: MIT License
- **Paper texts**: CC-BY 4.0
