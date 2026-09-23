# CAPSM x NERC/NPCC Academic Paper Collection

**12 academic research papers** bridging the CAPSM (Cognitive Adaptive Power System Management) PhD thesis with NERC/NPCC reliability standards and power system AI applications. All methodologies are implemented in Python using open-source tools.

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

## Repository Structure

```
Review-Papers/
├── README.md
├── requirements.txt
├── worklog.md                    # Production worklog (Papers 1-10)
├── papers/
│   ├── paper11_literature_review/    # Literature review + revision materials
│   └── paper12_cnnlstm_fault_detection/
│       ├── code/                     # PyTorch CNN-LSTM implementation
│       │   ├── model.py
│       │   ├── train.py
│       │   ├── evaluate.py
│       │   ├── data/                 # HDF5 datasets (IEEE 9/39/118)
│       │   ├── models/               # Trained checkpoints
│       │   └── results/              # Evaluation JSONs
│       └── figures/                  # Publication figures
├── scripts/                      # Python simulation scripts (Papers 1-10)
└── figures/                      # Generated PNGs + CSVs (Papers 1-10)
```

## Key Technical Notes

**Test Systems**: Papers 1-2 and 4-10 use IEEE 39-bus or 118-bus via `pypower`. Paper 3 currently uses a reproducible two-machine synthetic PMU benchmark for supervised MOD-026 parameter labels and the LBNL PMU Event Library converter for recorded PMU ingestion/morphology validation. Paper 12 uses IEEE 9/39/118-bus with synthetic PMU data.

**Real PMU Data**: Paper 3 supports the LBNL PMU Event Library via `scripts/paper3_lbnl_real_pmu_summary.py`. Clone `https://github.com/LBNL-ETA/pmu_event_library` outside this repository, then run the converter to regenerate the real-PMU summary, Figure 5, and normalized sample CSV.

**ML Substitutions**: Where the CAPSM thesis uses PyTorch, papers 1-10 use `sklearn` surrogates (MLPRegressor for CNN-LSTM/PINN). Paper 12 uses full PyTorch CNN-LSTM.

**Reproducibility**: All scripts use fixed random seeds. All results are fully reproducible.

## License

- **Python code**: MIT License
- **Paper texts**: CC-BY 4.0
