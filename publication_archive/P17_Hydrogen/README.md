# Hydrogen IEEE Transactions recovery bundle

## Exact status — 20 November 2026

This is a **scientifically honest, executable research-recovery handoff**. It contains a reconstructed, tested physical and learning benchmark, quantified contradictions from the rejected paper, a full reviewer response, data-ingestion scripts and a rewritten IEEE-style research manuscript. It is **not** a validated, ready-to-submit accepted-quality paper: original research code, the reviewed manuscript version, a 2017–2020 downloaded wind dataset, calibrated degradation constants, empirical RL training and true operating prices are missing.

Tests/analytical checks are real and run. The `results/smoke_results.json` file is **SYNTHETIC SOFTWARE QA** and must not be used as experimental evidence. `scripts/run_empirical.py` fails closed until real weather and manifest are present. It cannot be bypassed by substituting generated weather without falsifying provenance.

## Files to read first

- `GOD_PLAN.md`: phased publication program with evidence gates.
- `REVIEWER_RESPONSE.md`: 12 point-by-point reviewer replies with closure status.
- `DATA_PROVENANCE.md`: primary and fallback real data sources, limitations, exact download instructions.
- `MANUSCRIPT_EVIDENCE_LEDGER.md`: quantified contradiction and evidence status.
- `manuscript/IEEE_TSE_Revised_Draft.docx`: coherent manuscript rewrite, unverified performance removed.
- `config/experiment.json`: primary NREL/NLR 15-min scenario.
- `config/era5_hourly.json`: independently labeled ERA5 1-hour sensitivity scenario.
- `sources/`: original DOCX and rejection comment text.

## Reproduce **verified** local tasks

```bash
pip install -r requirements.txt
PYTHONPATH=src pytest -q tests
python scripts/audit_claims.py
python scripts/run_smoke.py
```

## Obtain REAL wind data and execute a holdout study

Choose ONE of the actual meteorology sources and preserve its provenance. The primary source may fail due to geographical coverage; failing in that case is the correct behavior.

```bash
export NLR_API_KEY="YOUR_PERSONAL_NLR_API_KEY"
export NLR_EMAIL="YOUR_VALID_EMAIL"
python scripts/download_now23.py
python scripts/run_empirical.py --config config/experiment.json
```

Alternative, real but distinct **hourly ERA5 reanalysis**:

```bash
python scripts/download_era5.py
python scripts/run_empirical.py --config config/era5_hourly.json
```

These scripts require internet on *your* machine. This chat's container has no general internet access to download archives. Neither a download nor empirical testing is represented as completed.

## What is and is not real

| Artifact | Classification |
|---|---|
| `results/hard_feasibility_audit.json` | Exact calculations from manuscript-stated numbers |
| `results/pytest_output.txt` | Executed unit tests on deterministic toy and randomized test fixtures |
| `results/smoke_results.json` | Executed **synthetic** software-only QA, no research evidence |
| `results/empirical_results.json` | **NOT PRESENT** until real dataset is downloaded and experiments run |
| Historical price | **NOT PRESENT**; price in JSON is a disclosed scenario |
| Plant wind-to-power curve | Assumed generic cubic power curve; not measured generation |
| Stack degradation model | Uncalibrated equivalent-age surrogate, not validated electrochemistry |
| Physical grid and transmission limits | Fixed proxy export cap; not measured curtailment or a load-flow model |

## Correct interpretation

The two RL policies (continuous SAC + discrete QR-DQN) and a supervised LSTM form a **staged hierarchical learning architecture**. Such a system is not a jointly trained three-agent MARL algorithm. This distinction is central to the rejection and preserved throughout all deliverables.
