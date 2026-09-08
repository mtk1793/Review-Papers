# Chapter 9 — Coordinated Multi-Controller Framework
**Target: 14 pages | 5 figures | 4 tables**
**Status: NOT YET WRITTEN — see 90-day plan Day 68–73**

---

## Required Sections

### 9.1 Introduction (~1.5 pp)
- The coordination problem: 6+ controllers, multiple objectives, real-time constraints
- Why uncoordinated control fails: conflicts, oscillations, suboptimal setpoints

### 9.2 Hierarchical Coordination Architecture (~3 pp)
- Layer 1: Device-level (local PI/droop control)
- Layer 2: Coordinated (System 1 / System 2)
- Layer 3: Executive (Metacognitive Arbiter)
- Communication: IEC 61850 GOOSE messages between layers

### 9.3 ADMM-Based Distributed Optimization (~3 pp)
- Problem decomposition: each controller solves local subproblem
- Consensus variable: shared boundary state
- Convergence analysis: bounded communications, tolerance ε = 10⁻⁴
- Scalability: O(n) per iteration for n controllers

### 9.4 System 1 Reflexive Coordination (~2.5 pp)
- Fast consensus via gossip protocol
- Local information sharing: voltage, angle, power flow
- Pre-computed coordination tables for common events

### 9.5 System 2 Deliberative Coordination (~2.5 pp)
- Global optimization over all controllers simultaneously
- QIRL evaluation of joint action candidates
- Constraint negotiation: priority-based conflict resolution

### 9.6 Mode Switching and Contingency Handling (~2 pp)
- Normal → Alert → Emergency → Restoration modes
- Arbiter decision logic for mode transitions
- Communication failure fallback procedures

### 9.7 **NEW SECTION** CHIL Validation of Coordinated Control (~1.5 pp)
- OPAL-RT: 3+ controllers running simultaneously in real-time
- Controller-hardware-in-the-loop for each FACTS device
- End-to-end latency measurement: PMU → Controller → Actuator

### 9.8 Conclusion (~0.5 pp)

---

## Figures Required
- [ ] Fig 9.1: Three-layer coordination hierarchy
- [ ] Fig 9.2: ADMM consensus algorithm flowchart
- [ ] Fig 9.3: Mode switching state machine
- [ ] Fig 9.4: Controller communication architecture
- [ ] Fig 9.5: CHIL test setup with multiple OPAL-RT cores

## Tables Required
- [ ] Table 9.1: Coordination protocol specifications
- [ ] Table 9.2: ADMM convergence results
- [ ] Table 9.3: Mode switching decision criteria
- [ ] Table 9.4: CHIL coordination validation results

## Key Code References
- `capsim_sim/capsm/agents/arbiter.py` — MetacognitiveArbiter
- `capsim_sim/capsm/coordination/` (if exists)

## File Location When Written
`09_coordinated_control/chapter_09.docx`
