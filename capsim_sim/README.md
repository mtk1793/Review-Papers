# PhD-Thesis — CAPSM: Cognitive Adaptive Power System Management

[![CI](https://github.com/mtk1793/PhD-Thesis/actions/workflows/ci.yml/badge.svg)](https://github.com/mtk1793/PhD-Thesis/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/downloads/)
[![DOI](https://img.shields.io/badge/data-OPSD%202020--10--06-blue.svg)](https://doi.org/10.25832/time_series/2020-10-06)

A brain-inspired, dual-process AI architecture for real-time control of
modern power grids with high renewable penetration, FACTS devices, and
electric-vehicle V2G fleets. Validated end-to-end on **real measured grid
data** from the Open Power System Data (OPSD) platform.

**Author:** Mahmoud Kiasari — PhD Candidate, Department of Electrical and
Computer Engineering, Dalhousie University (Halifax, Canada).

---

## What's in this repository

```
PhD-Thesis/
├── capsim_sim/         ← Python offline validation (the runnable core)
│   ├── capsm/          Python package: data, grid, agents
│   ├── scripts/        phase0..phase6 + run_all.py + dashboard.py
│   ├── tests/          52 unit tests (pytest)
│   ├── data/           raw + processed OPSD (gitignored, ~242 MB)
│   ├── results/        auto-generated tables + figures
│   ├── thesis_artifacts/ chapter-tagged figures + tables (Phase B)
│   ├── Dockerfile      build a self-contained image (Phase C2)
│   ├── reports/        per-phase Markdown write-ups
│   └── README.md       ← start here for the Python side
├── docker-compose.yml  one-command reproduce / dashboard / test (Phase C2)
├── .github/workflows/  CI: test on Py 3.10/3.11/3.12 + reproduce + docker build
├── HIL_Project/       ← OPAL-RT HIL target (Simulink, RT-LAB, thesis chapters)
├── Chapter 1 .. 13/    ← thesis chapter PDFs
├── CAPSM Framework Development Plan.docx
└── README.md           (this file)
```

The focus right now is the **Python side and its results** — `capsim_sim/`.

---

## Quick start (four ways to use it)

### 1. Reproduce every figure in the thesis (one command)

```bash
git clone https://github.com/mtk1793/PhD-Thesis.git
cd PhD-Thesis/capsim_sim
pip install -r requirements.txt          # pinned versions
python scripts/run_all.py                # downloads ~242 MB OPSD data, runs phases 0..6
```

If you already have the OPSD data cached:
```bash
python scripts/run_all.py --skip 0       # ~3 minutes
```

Or with the Makefile:
```bash
make all          # install deps + run all phases + tests
make reproduce    # skip phase 0, reuse cached OPSD data
make test         # run pytest only
make phaseN       # run only phase N (0..6)
make dashboard    # launch the Streamlit dashboard
```

### 2. Install as a Python package

```bash
pip install -e capsim_sim
capsim --help                          # CLI with 7 subcommands
capsim download                        # Phase 0: download real OPSD data
capsim reproduce                       # Run phases 1-6
capsim run-all                         # Phases 0-6 + tests
capsim test                            # 52-test pytest suite
capsim phase 4                         # Run only phase 4 (CNN-LSTM)
capsim artifacts                       # Regenerate thesis_artifacts/ figures
capsim dashboard                       # Live Streamlit demo (see below)
```

### 3. Live dashboard (best for committee demos)

```bash
pip install -e capsim_sim[dashboard]    # adds streamlit + plotly
capsim dashboard
# → opens http://localhost:8501
```

Sliders for wind/solar penetration, controller choice (NoControl /
RuleBased / PID / System 1 CNN-LSTM / System 2 QIRL / CAPSM), and any
date window inside the real OPSD coverage (2015-01-01 → 2020-09-30).
Reuses the same `capsm.grid.QSTSEnvironment` and `capsm.agents.*` modules
that produce the thesis results — no duplicated logic.

### 4. Docker container (no Python install needed)

```bash
# Build the image (~1.2 GB, CPU-only, no GPU required):
docker compose build base

# Run the full pipeline + tests, results/ and thesis_artifacts/ mounted out:
docker compose run --rm reproduce
# → results/SUMMARY.md, results/phase*/phase*_summary.json, thesis_artifacts/...

# Run only the 52-test suite:
docker compose run --rm test

# Regenerate just the thesis artifacts:
docker compose run --rm artifacts

# Launch the dashboard (visit http://localhost:8501):
docker compose up dashboard
# Ctrl-C to stop

# Drop into an interactive shell with the capsim CLI on PATH:
docker compose run --rm shell
```

The 242 MB OPSD data is downloaded once into a named volume
(`capsim-opspd-data`) and shared between containers, so subsequent runs
skip the download.

---

## Headline result (Jan 2019, IEEE 39-bus, 721-hour real OPSD benchmark)

| Controller             | Violations (bus-h) | vs NoControl    | Inference (ms/step) | Converged |
|------------------------|--------------------:|-----------------|--------------------:|----------:|
| NoControl              |               2847 | —               |                8.7  | 721/721   |
| RuleBased (droop)      |               2846 | −1 (−0.04 %)    |                8.7  | 721/721   |
| PID (PI volt/VAR)      |               2842 | −5 (−0.18 %)    |                8.7  | 721/721   |
| System 1 (CNN-LSTM)    |               2824 | −23 (−0.81 %)   |               10.3  | 721/721   |
| System 2 (QIRL)        |               2810 | −37 (−1.30 %)   |                9.2  | 721/721   |
| **CAPSM (Arbiter)**    |               2815 | **−32 (−1.12 %)** |              10.8  | 721/721   |

All six controllers converge 721/721 hourly steps. CAPSM combines the
deliberative optimisation of System 2 with the fast-reflex response of
System 1 — coming within 0.18 % of System 2's violation count while
keeping the metacognitive arbitration layer that lets it hand off to
System 1 in emergencies. Full results are auto-generated in
`capsim_sim/results/SUMMARY.md` and chapter-tagged figures in
`capsim_sim/thesis_artifacts/`.

The 52-test pytest suite (gap policy, QSTS convergence, FACTS, EV V2G,
line trip / restore, FDI, CNN-LSTM, QIRL, arbiter) all pass.

---

## Continuous Integration

The [.github/workflows/ci.yml](.github/workflows/ci.yml) workflow runs on
every push and PR:

1. **test** — installs deps, runs the 52-test pytest suite on Python 3.10,
   3.11, and 3.12 (matrix). Caches pip downloads.
2. **reproduce** — runs `capsim run-all` on real OPSD data (caches the
   242 MB download across runs), verifies `results/SUMMARY.md` and all
   thesis artifacts are produced, uploads them as a workflow artifact
   for download.
3. **docker** — builds the Docker image with Buildx layer caching,
   smoke-tests `capsim --help` and `capsim test` inside the container.

The badge at the top of this README reflects the latest CI run on
`master`/`main`. Any code change that breaks the pipeline (PYPOWER
regression, pandas API drift, figure-regeneration failure, Dockerfile
breakage) is caught at PR time.

---

## Framework at a glance

| Layer            | Implementation                                         | Inference budget |
|------------------|--------------------------------------------------------|------------------|
| System 1 — fast  | CNN (spatial) + LSTM (temporal) + attention + FC        | < 5 ms (target)  |
| System 2 — slow  | Quantum-Inspired RL (amplitude vector + tunneling)      | < 50 ms          |
| Arbiter          | `α = sigmoid(τ(threshold − C1))`, blends System 1 & 2  | ~ 1 ms           |
| Safety           | Physics-informed penalty (voltage / thermal / SoC)     | hard constraint  |

Tested on IEEE 9-, 14-, 39-, 118-bus systems with the thesis FACTS
placement (SVC @ 14, STATCOM @ 39, TCSC on 16–17, UPFC @ 26) and three
aggregated V2G stations (buses 3, 8, 15).

---

## Thesis artifacts (auto-generated)

After `capsim run-all` (or `capsim artifacts`), the following figures and
tables are in `capsim_sim/thesis_artifacts/`:

| Chapter | File | Description |
|---|---|---|
| Ch. 5 | `ch5/qsts_convergence.md` | QSTS convergence on IEEE 9/14/39/118 |
| Ch. 5 | `ch5/facts_ev_placement.md` | FACTS + EV V2G placement table |
| Ch. 5 | `ch5/loading_margins.md` | Valley / peak loading margins |
| Ch. 6/7 | `ch6_7/fig_ch6_7_line_trip_3panel.{png,pdf}` | Line 16-17 trip figure |
| Ch. 6/7 | `ch6_7/line_trip_summary.md` | Pre-trip vs early/late-trip table |
| Ch. 10 | `ch10/controller_comparison.md` | Full 6-controller + 52-test breakdown |
| Ch. 11 | `ch11/fig_ch11_results_6panel.{png,pdf}` | 6-panel performance figure |
| Ch. 13 | `ch13/fig_ch13_reduction_vs_nocontrol.{png,pdf}` | % violation reduction |
| Ch. 13 | `ch13/reduction_vs_nocontrol.md` | Reduction table + key takeaway |

All figures are 300 dpi PNG + vector PDF (LaTeX-ready).

---

## Data attribution

Open Power System Data. 2020. Data Package Time series. Version
2020-10-06. https://doi.org/10.25832/time_series/2020-10-06. Primary
data: ENTSO-E Transparency Platform (real measured load, wind, solar,
day-ahead prices).

---

## License

MIT — see [`LICENSE`](LICENSE). If you use this work in a publication,
please cite it using [`CITATION.cff`](CITATION.cff).
