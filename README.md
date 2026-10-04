# Academic Paper Collection — CAPSM x NERC/NPCC + CNN-LSTM + PG-CARE EV Forecasting

**13 academic research papers**: Papers 1-10 bridge the CAPSM (Cognitive Adaptive Power System Management) PhD thesis with NERC/NPCC reliability standards, Papers 11-12 cover System-1 CNN-LSTM fault detection, and Paper 13 adds leakage-free PG-CARE physics-guided conformal reliability for one-hour-ahead EV flexibility forecasting with distribution-feeder support. All methodologies are implemented in Python using open-source tools.

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
| 13 | PG-CARE v2: Leakage-Free Physics-Guided Conformal Reliability for One-Hour-Ahead EV Flexibility Forecasting and Distribution-Feeder Support | Leak-free pipeline (declared schedule vs realized connection, predicted connectivity, no target-time info in mask) + CQR flexibility intervals + IEEE 33-bus QSTS + RBR recovery; IEEEtran LaTeX + Word + PDF manuscript, raster + vector figures, full code/data/models/tests | Complete — superseding v2 reproducibility package in `papers/paper13_pgcare_ev_flexibility/` (v1 retained under `legacy_v1/`) |

**Paper 13 headline results (v2, chronological full test — 203,900 forecasts over 85 days)**: raw LightGBM macro-F1 0.7986 (V2G F1 0.6700) → leak-free physics projection 0.8140 (V2G F1 0.7088) → PG-CARE v2 conformal + abstention 0.8183 (V2G F1 0.7155). Paired issue-time block-bootstrap delta +0.0196 [0.0171, 0.0221]; exact McNemar p = 6.26e-310. Split-conformal marginal coverage 0.9117 (V2G-conditional 0.8016, reported as a limitation); CQR flexibility coverage 0.8996 at 6.50 kW mean width. IEEE 33-bus QSTS: raw mean-flexibility commitment 125.5 MWh / 8.68 MWh shortfall vs CQR lower bound 43.1 MWh / 0 shortfall vs RBR 53.8 MWh / 0 shortfall (oracle 152.2 MWh). See `papers/paper13_pgcare_ev_flexibility/README.md` and `docs/RESULTS_TRACEABILITY_V2.md` for the claim-to-evidence map.

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

### Run Paper 13 (PG-CARE v2, leakage-free)

```bash
cd papers/paper13_pgcare_ev_flexibility

# Pinned v2 environment
python -m pip install -r requirements_v2.txt

# One-command full v2 reproduction (offline pipeline only; external-data adapters need user credentials)
python reproduce_v2.py
```

Paper 13 original v2 bundle is also archived as `papers/paper13_pgcare_ev_flexibility/PG_CARE_Transactions_v2_MASTER_All_Files_Code_Data_Models.zip` (53 MB). The superseded v1 package is retained under `legacy_v1/` for audit history.

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
│   ├── paper13_pgcare_ev_flexibility/  # PG-CARE v2 leakage-free (Paper 13)
│   │   ├── README.md                   # v2 overview + reproduction guide
│   │   ├── PG_CARE_Transactions_v2_MASTER_All_Files_Code_Data_Models.zip  # Original v2 bundle (53 MB)
│   │   ├── reproduce_v2.py             # One-command v2 reproduction entry point
│   │   ├── requirements_v2.txt         # Pinned v2 env
│   │   ├── docs/                       # Traceability, novelty, limitations, critique-resolution records
│   │   ├── code_v2/                    # Leak-free pipeline (connectivity prediction → CQR → QSTS → figures)
│   │   ├── data_v2/                    # v2 digital-twin arrays + aggregates
│   │   ├── results_v2/                 # Models, audits, calibration, statistics, QSTS results
│   │   ├── figures_v2/                 # Raster + vector manuscript figures
│   │   ├── manuscript/                 # IEEEtran LaTeX + Word + compiled PDF
│   │   ├── references/                 # 2020–2026 bibliography (.bib/.csv/.txt)
│   │   ├── source_artifacts/           # Published Simulink controller (.slx) + manuscript snapshot
│   │   ├── tests/                      # Information-integrity invariant tests
│   │   └── legacy_v1/                  # Superseded v1 package (audit history only)
├── scripts/                      # Python simulation scripts (Papers 1-10)
└── figures/                      # Generated PNGs + CSVs (Papers 1-10)
```

## Key Technical Notes

**Test Systems**: Papers 1-2 and 4-10 use IEEE 39-bus or 118-bus via `pypower`. Paper 3 currently uses a reproducible two-machine synthetic PMU benchmark for supervised MOD-026 parameter labels and the LBNL PMU Event Library converter for recorded PMU ingestion/morphology validation. Paper 12 uses IEEE 9/39/118-bus with synthetic PMU data.

**Real PMU Data**: Paper 3 supports the LBNL PMU Event Library via `scripts/paper3_lbnl_real_pmu_summary.py`. Clone `https://github.com/LBNL-ETA/pmu_event_library` outside this repository, then run the converter to regenerate the real-PMU summary, Figure 5, and normalized sample CSV.

**ML Substitutions**: Where the CAPSM thesis uses PyTorch, papers 1-10 use `sklearn` surrogates (MLPRegressor for CNN-LSTM/PINN). Paper 12 uses full PyTorch CNN-LSTM.

**Reproducibility**: All scripts use fixed random seeds. All results are fully reproducible.

**Paper 13 provenance & boundaries (v2)**: PG-CARE supervisory EV logic is a Python reconstruction/extension of the published MATLAB/Simulink controller in Kiasari & Aly, *Journal of Energy Storage* vol. 99, Art. 113235 (2024). The original `.slx` snapshot is retained in `papers/paper13_pgcare_ev_flexibility/source_artifacts/`. v2 removes the v1 target-time-connectivity flaw: declared schedule vs realized connection are separated, connectivity is predicted from issuance-time history, and conformal/CQR layers are calibrated after the leak-free projection. The study is a source-informed supervisory simulation — no claim of switching-level equivalence, field trial, utility deployment, or OOD conformal guarantees. Dependency pinning is per-paper (`requirements_v2.txt`); integrity hashes in `SHA256SUMS.txt`/`MASTER_SHA256SUMS.txt`, claim map in `docs/RESULTS_TRACEABILITY_V2.md`, remaining flagship-submission gate (executed measured-data validation) in `docs/LIMITATIONS_AND_SUBMISSION_GATE.md`.

## License

- **Python code**: MIT License
- **Paper texts**: CC-BY 4.0
