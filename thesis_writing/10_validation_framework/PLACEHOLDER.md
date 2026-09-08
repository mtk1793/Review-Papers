# Chapter 10 — Validation Framework and Methodology
**Target: 32 pages | 8 figures | 6 tables**
**Status: NOT YET WRITTEN — see 90-day plan Day 74–85**
**This is the CORE chapter — the one that justifies the thesis.**

---

## Required Sections

### 10.1 Overview: Three-Stage Validation Pipeline (~2 pp)
- Stage 1: Software-in-the-Loop (SIL) — offline simulation, full Python
- Stage 2: Processor-in-the-Loop (PIL) — PyTorch → ONNX → C++ inference
- Stage 3: Controller-Hardware-in-the-Loop (CHIL) — OPAL-RT 4-core real-time
- Progression rationale: each stage adds realism and reduces simulation assumptions

### 10.2 Stage 1: Software-in-the-Loop Simulation (~4 pp)
**10.2.1 Simulation Environment**
- `capsim_sim` Python package architecture
- IEEE 39-bus implementation with OPSD January 2019 data
- QSTS simulation: 721 hours × 15-minute resolution = 28,844 timesteps

**10.2.2 Test Scenarios**
- 6 scenarios: normal, P1, P2, P3, P7, EV stress
- Severity ranking of scenarios
- Perturbation injection protocol

**10.2.3 Metrics and Baselines**
- 6 controllers: NoControl, RuleBased, PID, System1, System2, CAPSM
- 5 metrics: violations, losses, inference time, constraint compliance, stability margin
- Statistical significance: 95% CI via bootstrap resampling

**10.2.4 Results**
- Quantitative comparison: Table 10.1 (violations), Table 10.2 (losses)
- Statistical significance analysis
- Sensitivity to hyperparameters (β, τ, window_size)

### 10.3 Stage 2: Processor-in-the-Loop (~4 pp)
**10.3.1 PyTorch to ONNX Export**
- `torch.onnx.export(system1, dummy_input, "system1.onnx")`
- Verification: ONNX Runtime output matches PyTorch output (ε < 10⁻⁶)

**10.3.2 C++ Inference Engine**
- <5 ms for System 1, <50 ms for System 2 on OPAL-RT cores
- Memory footprint: ~1 MB for CNN-LSTM, ~50 KB for QIRL

**10.3.3 PIL Results**
- Comparison: Python vs C++ inference times
- Numerical accuracy preservation across platforms

### 10.4 Stage 3: Controller-Hardware-in-the-Loop (~8 pp)
**10.4.1 OPAL-RT Infrastructure**
- 4-core OPAL-RT: Core 1 (System 1), Core 2 (System 2), Core 3 (Arbiter + Grid), Core 4 (Communication)
- 50 μs EMT timestep for grid dynamics
- Ethernet communication: IEEE 1588 PTP synchronization

**10.4.2 CHIL Test Scenarios**
- 3-phase faults at varying locations and clearing times
- EV fleet sudden disconnection (10% of load)
- Communication delay injection (0–100 ms)
- Cyber-attack FDI injection during operation

**10.4.3 CHIL Results**
- Table 10.3: Fault response timing (detection → command → actuation)
- Table 10.4: Real-time constraint satisfaction rates
- Table 10.5: OPAL-RT performance under stress scenarios
- Video demonstration: see supplementary materials

### 10.5 Comparison of Validation Stages (~3 pp)
- SIL → PIL → CHIL: what changes at each stage
- Where CAPSM control performance degrades/evolves
- Gap analysis: simulation assumptions vs hardware realities

### 10.6 Robustness and Sensitivity Analysis (~3 pp)
- Controller performance across 6 test scenarios (already in capsim_sim)
- Hyperparameter sensitivity: β ∈ [0.1, 10], τ ∈ [0.1, 1.0]
- Random seed sensitivity: 5 different seeds, mean ± std reported

### 10.7 Transfer Learning and Generalization (~3 pp)
- IEEE 39 → IEEE 118: same architecture, minimal retraining
- Domain gap: training on simulation, validation on CHIL
- Lessons learned for future deployments

### 10.8 **NEW SECTION** Code-to-Thesis Traceability Matrix (~2 pp)
- Table 10.6: For every figure/table in thesis → corresponding code in capsim_sim
- For every experiment → reproducibility instructions in Appendix A
- For every claim → evidence in test results

### 10.9 Conclusion (~1 pp)

---

## Figures Required
- [ ] Fig 10.1: Three-stage validation pipeline (SIL → PIL → CHIL)
- [ ] Fig 10.2: OPAL-RT core allocation for CAPSM
- [ ] Fig 10.3: 6-scenario severity comparison (violations per scenario)
- [ ] Fig 10.4: SIL vs PIL inference time comparison
- [ ] Fig 10.5: CHIL fault response timeline
- [ ] Fig 10.6: Hyperparameter sensitivity surfaces (β, τ)
- [ ] Fig 10.7: Transfer learning: IEEE 39 → 118 performance
- [ ] Fig 10.8: Code-to-thesis traceability matrix heatmap

## Tables Required
- [ ] Table 10.1: SIL violations by controller and scenario (6×6 matrix)
- [ ] Table 10.2: SIL losses and inference times
- [ ] Table 10.3: CHIL timing: detection → command → actuation
- [ ] Table 10.4: CHIL constraint satisfaction rates
- [ ] Table 10.5: OPAL-RT stress test results
- [ ] Table 10.6: Code-to-thesis traceability matrix

## Key Code References
- `capsim_sim/capsm/agents/system1.py`
- `capsim_sim/capsm/agents/system2.py`
- `capsim_sim/capsm/agents/arbiter.py`
- `capsim_sim/capsm/grid/ieee39.py`
- `capsim_sim/scripts/run_all_experiments.py`
- `capsim_sim/pytest.ini` — 52 passing tests

## Reproducibility
All results in this chapter are fully reproducible. See Appendix A.

## File Location When Written
`10_validation_framework/chapter_10.docx`
