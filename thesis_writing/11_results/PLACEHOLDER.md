# Chapter 11 — Results and Analysis
**Target: 24 pages | 8 figures | 5 tables**
**Status: NOT YET WRITTEN — see 90-day plan Day 86–95**

---

## Required Sections

### 11.1 Introduction (~1 pp)
- What this chapter answers: "Does CAPSM actually work?"
- Organization: each research objective from Chapter 1 addressed in order

### 11.2 Research Objective 1: Dual-Process AI Architecture Validation (~4 pp)
- Hypothesis: System 1 + System 2 outperforms either alone
- Evidence: violation counts, loss values, inference times
- Metacognitive Arbiter effectiveness: α-mode switching frequency analysis

### 11.3 Research Objective 2: HIL Validation (~3 pp)
- Three-stage pipeline results: SIL → PIL → CHIL
- Real-time performance on OPAL-RT: timing budgets met
- Gap analysis: where simulation results differ from hardware

### 11.4 Research Objective 3: Measurable Improvements Over Conventional Methods (~4 pp)
**Primary Results Table (IEEE 39-bus, January 2019):**
| Metric | NoControl | RuleBased | PID | System1 | System2 | CAPSM |
|---|---|---|---|---|---|---|
| Violations | 2847 | 2846 | 2842 | 2822 | 2810 | **2813** |
| Δ vs NoControl | — | −1 | −5 | −25 (−0.88%) | −37 (−1.30%) | −34 (−1.20%) |
| Losses (MW) | 46.11 | 46.11 | 46.11 | 46.15 | 46.19 | 46.20 |
| Inference (ms) | — | 23.9 | 24.3 | 32.0 | 21.1 | **36.5** |

- Statistical significance: bootstrap 95% CI on Δ violations
- Multi-scenario analysis: P1, P2, P3, P7, EV stress, Normal

### 11.5 Research Objective 4: IEEE Test System Demonstration (~3 pp)
- IEEE 9-bus: proof of concept, rapid iteration
- IEEE 39-bus: primary validation (above results)
- IEEE 118-bus: scalability check
- Key differences in performance across system sizes

### 11.6 Research Objective 5: Open-Source Framework (~2 pp)
- capsim_sim package: 52 tests passing
- PyPI download stats (if available)
- Community usage and contributions (if any)

### 11.7 Additional Findings (~4 pp)
- QIRL convergence behavior: why System 2 sometimes outperforms CAPSM
- Transfer learning: IEEE 39 → 118 generalization
- EV penetration sensitivity: 0% → 30% EV fleet
- FACTS device type sensitivity: which devices matter most

### 11.8 Sensitivity and Robustness Analysis (~3 pp)
- Hyperparameter sensitivity: β, τ, window_size
- Random seed sensitivity: mean ± std across 5 seeds
- Missing PMU data: graceful degradation behavior
- Communication delay: CAPSM performance vs delay (0–100 ms)

### 11.9 **NEW SECTION** Limitations and Threats to Validity (~2 pp)
- Internal validity: simulation assumptions, OPSD data representativeness
- External validity: IEEE test systems vs real-world grids
- Construct validity: do our metrics measure what matters?
- Conclusion validity: statistical power, effect sizes

### 11.10 Conclusion (~1 pp)

---

## Figures Required
- [ ] Fig 11.1: 6-controller comparison bar chart (violations)
- [ ] Fig 11.2: CAPSM vs all baselines radar chart (5 metrics)
- [ ] Fig 11.3: Metacognitive Arbiter α-mode time series (sample episode)
- [ ] Fig 11.4: SIL → PIL → CHIL performance comparison
- [ ] Fig 11.5: Hyperparameter sensitivity surfaces
- [ ] Fig 11.6: Transfer learning: IEEE 39 → 118 (violations)
- [ ] Fig 11.7: EV penetration sensitivity analysis
- [ ] Fig 11.8: Communication delay impact on CAPSM performance

## Tables Required
- [ ] Table 11.1: Full results matrix (6 controllers × 6 scenarios)
- [ ] Table 11.2: Statistical significance (bootstrap 95% CI)
- [ ] Table 11.3: Scalability results (IEEE 9/14/39/118)
- [ ] Table 11.4: Sensitivity analysis summary
- [ ] Table 11.5: Limitations and mitigation strategies

## File Location When Written
`11_results/chapter_11.docx`
