# CAPSM PhD Thesis — Writing Repository

**Topic:** Cognitive Adaptive Power System Management (CAPSM): A Brain-Inspired Dual-Process AI Framework for Coordinated Control of FACTS Devices, EV Fleets, and DERs — Validated Through Controller-Hardware-in-the-Loop Testing on a 4-Core OPAL-RT Real-Time Simulator

**Author:** Mahmoud Kiasari, Dalhousie University
**Target:** 300 pages | ~200 references (2020–2026) | Deadline: 3 months

---

## Master Plan
→ **`00_CAPS_Thesis_Writing_Plan_90_Days.md`** — the complete 90-day writing roadmap. Read this first.

---

## Folder Structure

```
thesis_writing/
├── 00_CAPS_Thesis_Writing_Plan_90_Days.md   ← MASTER PLAN (start here)
├── README.md                                  ← you are here
├── 00_front_matter/                         ← abstract, acknowledgements, TOC, declarations
├── 01_introduction/                          ← Chapter 1 (12 pp)
├── 02_literature_review/                     ← Chapter 2 (20 pp)
├── 03_proposed_framework/                   ← Chapter 3 (18 pp)
├── 04_ai_architecture/                       ← Chapter 4 (20 pp)
├── 05_optimal_placement/                  ← Chapter 5 (18 pp)
├── 06_stability/                            ← Chapter 6 (14 pp)
├── 07_fault_detection/                      ← Chapter 7 (18 pp)
├── 08_ev_integration/                       ← Chapter 8 (18 pp)
├── 09_coordinated_control/                  ← Chapter 9 (14 pp)
├── 10_validation_framework/                 ← Chapter 10 (32 pp) [CORE]
├── 11_results/                              ← Chapter 11 (24 pp)
├── 12_discussion/                           ← Chapter 12 (12 pp)
├── 13_conclusions/                          ← Chapter 13 (10 pp)
├── appendix_A_reproducibility/               ← reproducibility, data download, OPSD
├── appendix_B_tests/                        ← pytest output, test documentation
├── references/                              ← CAPSM_thesis.bib
├── figures/                                 ← all generated thesis figures (master copies)
└── tables/                                  ← all thesis tables (master copies)
```

---

## What Exists vs What Needs Writing

### Already Written (Code + Results)
- `capsim_sim/` — Python package, 52/52 pytest tests passing, Phase 0–6 complete
- All quantitative results for Chapter 11 (6-controller comparison table)
- 7 pre-generated figures from phase reports (可直接导入)
- `HIL_Project/` — OPAL-RT HIL configuration and Simulink models

### Needs Writing (13 Chapters)
Each chapter folder in this directory contains a `PLACEHOLDER.md` file with the exact sections, figure/table requirements, and writing targets from the 90-day plan.

---

## Quick-Start

1. Read `00_CAPS_Thesis_Writing_Plan_90_Days.md`
2. Run tests: `cd capsim_sim && pytest -q`
3. Generate figures: `cd capsim_sim && python scripts/run_all_experiments.py`
4. Start writing Chapter 1 (this is Day 1 of the 90-day plan)

---

## Key Numbers to Use Throughout

| Controller | Violations | Δ vs NoControl | Losses (MW) | ms/step |
|---|---|---|---|---|
| NoControl | 2847 | — | 46.11 | — |
| RuleBased | 2846 | −1 | 46.11 | 23.9 |
| PID | 2842 | −5 | 46.11 | 24.3 |
| System1 CNN-LSTM | 2822 | −25 (−0.88%) | 46.15 | 32.0 |
| System2 QIRL | 2810 | −37 (−1.30%) | 46.19 | 21.1 |
| **CAPSM** | **2813** | **−34 (−1.20%)** | **46.20** | **36.5** |

IEEE 39-bus, January 2019 (OPSD real data), 721 hours.

---

## Connected Repositories

- **PhD Thesis code:** https://github.com/mtk1793/PhD-Thesis
- **This repo (papers):** https://github.com/mtk1793/Review-Papers
- **caprim_sim package:** included here as `capsim_sim/`

---

## Branch Strategy

```
master    ← final thesis (protected)
├── thesis-writing
└── ... (individual paper branches are in the repo root)
```

---

## Citation

If this thesis or any part of the CAPSM framework is useful for your research, please cite:

```
Kiasari, M. (2026). Cognitive Adaptive Power System Management (CAPSM): 
A Brain-Inspired Dual-Process AI Framework. PhD Thesis, 
Dalhousie University, Halifax, NS, Canada.
```
