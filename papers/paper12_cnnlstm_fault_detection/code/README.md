# System-1: CNN-LSTM Fault Detection Codebase

Complete PyTorch implementation of the System-1 CNN-LSTM dual-stream architecture
for sub-10ms fault detection in power systems.

## Files

```
code/
├── model.py          # CNN-LSTM model definition (System1_CNNLSTM)
├── generate_data.py  # PMU fault data generator (7 fault types)
├── train.py          # Training pipeline with augmentation
├── evaluate.py       # Evaluation, metrics, McNemar test, benchmarking
├── run_all.py        # Orchestrator: data -> train -> evaluate
├── requirements.txt  # Python dependencies
├── data/             # Generated HDF5 datasets
├── models/           # Trained model checkpoints
└── results/          # Evaluation outputs (JSON)
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Quick test (small dataset, CPU, ~2 min)
python run_all.py --quick --device cpu

# Full training (60K events, GPU recommended, ~20 min)
python run_all.py --device cuda
```

## Individual Steps

```bash
# 1. Generate data only
python generate_data.py

# 2. Train on IEEE 9-bus
python train.py --system IEEE9 --device cuda

# 3. Evaluate on all systems
python evaluate.py --system IEEE39 --device cuda
```

## Model Architecture

- **Input**: (batch, 256 timesteps, N_buses × 3 channels)
- **CNN Stream**: 2-layer 1D conv (64→128 filters, kernel=3)
- **LSTM Stream**: 2-layer stacked LSTM (256→256 hidden)
- **Dual Heads**: Fault classification (7 classes) + Action prediction (P,Q per bus)
- **Parameters**: ~1.87M (8.4 MB FP32)

## Dataset Sources

The synthetic dataset uses realistic fault signatures based on:
- IEEE C37.118 PMU measurement standards
- EPRI/NERC fault database distributions
- IEEE 9/39/118-bus test system topologies

For real PMU data, consider:
- FNET/GridEye public synchrophasor data (https://fnetpublic.utk.edu)
- LBNL synchrophasor datasets
- IEEE PES open data repositories

## Output

Results are saved as JSON in `results/`:
- `evaluation.json` — Accuracy, per-class metrics, confusion matrix
- `benchmark.json` — Latency percentiles (P50, P95, P99)
- `summary.json` — Cross-system comparison
