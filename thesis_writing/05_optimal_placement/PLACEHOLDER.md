# Chapter 5 — Optimal Placement of FACTS Devices and EVs
**Target: 18 pages | 6 figures | 5 tables**
**Status: NOT YET WRITTEN — see 90-day plan Day 36–45**

---

## Required Sections

### 5.1 Introduction and Problem Formulation (~2 pp)
- Optimal placement as combinatorial optimization
- Objective: minimize violations + losses + device cost
- Decision variables: location, type, rating of FACTS; EV aggregation points
- Constraints: AC power flow, thermal limits, voltage limits, device ratings

### 5.2 Power Flow Modeling with FACTS Devices (~3 pp)
- DC power flow limitations and why AC is needed
- FACTS device models in power flow (from facts.py)
  - SVC: reactive power injection Q = −B·V²
  - STATCOM: reactive current injection I_q
  - TCSC: series reactance modulation X_TCSC
  - UPFC: combined shunt + series + voltage injection model
- Implementation: `facts.py` line 31–120

### 5.3 EV Fleet Aggregation Modeling (~2.5 pp)
- Deterministic vs probabilistic EV models
- Fleet-level aggregation for grid services
- V2G capacity bounds (10% of fleet capacity per event)
- Spatial-temporal uncertainty quantification

### 5.4 Optimization Formulation (~3 pp)
**Objective:** min Σᵗ [violations(t) + 0.1·losses(t) + 0.001·device_cost]
**Decision variables:** placement locations, device types, control setpoints, EV dispatch
**Algorithm:** QIRL-based placement optimizer (derived from system2.py principles)

### 5.5 Placement Results and Analysis (~5 pp)
- IEEE 39-bus: optimal locations for 4 FACTS + 3 EV aggregations
- Sensitivity analysis: # devices vs performance improvement
- Comparison with PSO, GA, CPLEX-based baselines
- Economic analysis: device cost vs system benefit

### 5.6 Scalability Analysis (~2 pp)
- IEEE 9 → 14 → 39 → 118 → 300 bus scaling
- Computational time vs system size
- Parallelization opportunities

### 5.7 HIL Considerations (~1 pp)
- Real-time OPAL-RT implementation of optimal setpoints
- Interpolation between offline-computed optimal points

---

## Figures Required
- [ ] Fig 5.1: FACTS placement optimization flowchart
- [ ] Fig 5.2: IEEE 39-bus with optimal FACTS + EV locations (geographical diagram)
- [ ] Fig 5.3: Sensitivity analysis: # devices vs violation reduction
- [ ] Fig 5.4: Scalability: computational time vs bus count (log-log)
- [ ] Fig 5.5: Cost-benefit analysis: device cost vs system loss reduction
- [ ] Fig 5.6: Convergence curve of QIRL placement optimizer

## Tables Required
- [ ] Table 5.1: Optimal FACTS placement parameters
- [ ] Table 5.2: Optimal EV aggregation locations
- [ ] Table 5.3: Performance comparison: optimal vs rule-based placement
- [ ] Table 5.4: Scalability results across IEEE test systems
- [ ] Table 5.5: Economic analysis of device investment

## Key Code References
- `capsim_sim/capsm/grid/facts.py` — FACTS models
- `capsim_sim/capsm/grid/ev_fleet.py` — EV fleet model
- `capsim_sim/scripts/phase2_grid.py` — placement experiments

## File Location When Written
`05_optimal_placement/chapter_05.docx`
