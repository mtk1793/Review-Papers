# Chapter 3 — Proposed Framework
**Target: 18 pages | 8 figures | 1 table**
**Status: NOT YET WRITTEN — see 90-day plan Day 15–25**

---

## Required Sections

### 3.1 Framework Overview and Design Philosophy (~2 pp)
- CAPSM as brain-inspired dual-process control for modern power systems
- Why dual-process cognition maps naturally to power system control
- Design principles: real-time, coordinated, adaptive, explainable

### 3.2 Brain-Inspired Dual-Process Control Architecture (~3 pp)
- System 1 (Reflexive): CNN-LSTM, sub-5ms, PMU-scale response, Kahneman fast thinking
- System 2 (Deliberative): QIRL, 50ms-scale, full optimization, Kahneman slow thinking
- Metacognitive Arbiter: executive layer deciding which system controls

### 3.3 Multi-Layer Coordination Architecture (~2 pp)
- Device layer (FACTS, EV inverters, relays)
- Local control layer (droop, PI)
- Coordinated layer (System 1 / System 2)
- Executive layer (Metacognitive Arbiter)
- Communication and timing requirements

### 3.4 Mathematical Modeling of Integrated Components (~2.5 pp)
- FACTS quasi-static models (SVC, STATCOM, TCSC, UPFC) — from facts.py
- EV fleet dynamics and aggregation — from ev_fleet.py
- Power flow constraints and operational limits
- Cyber-attack model (FDI injection)

### 3.5 Quantum-Inspired Reinforcement Learning (~2.5 pp)
- The signature QIRL equation: |ψ⟩ = (1/√Z) Σ √(exp(β·Q(s,a))) |s,a⟩
- Complex-valued probability amplitudes
- Superposition: simultaneous evaluation of 32 candidates
- Tunneling: exploration via amplitude perturbation
- Born rule action selection
- Comparison with classical DQN, PPO

### 3.6 Multi-Modal Fault Detection and Localization (~2 pp)
- Anomaly detection via autoencoder reconstruction error
- FDI detection in measurement layer
- Fault classification from voltage/current signatures
- Integration with System 1 reflexive response

### 3.7 Coordinated Control Strategies (~2 pp)
- FACTS + EV joint dispatch optimization
- V2G as flexible reactive/active resource
- Coordination under contingency conditions
- Cyber-physical security integration

### 3.8 Practical Implementation Considerations (~1 pp)
- Computational complexity: O(n) for CNN-LSTM, O(32) for QIRL
- Communication requirements: IEC 61850, C37.118, PMU bandwidth
- Scalability: IEEE 9 → 14 → 39 → 118 → 300 bus

### 3.9 Summary and Transition (~0.5 pp)
- Bridge to Chapters 4–9 (each component in detail)

### 3.10 **NEW SECTION** HIL-Ready Architecture Design (~1 pp)
- How CAPSM is designed for OPAL-RT from the start
- 4-core allocation matching the hardware topology
- ONNX export for real-time inference

---

## Figures Required
- [ ] Fig 3.1: High-level CAPSM system architecture (System 1 / System 2 / Arbiter / Grid) — **KEY DIAGRAM**
- [ ] Fig 3.2: Hierarchical control layers (device → local → coordinated → executive)
- [ ] Fig 3.3: Temporal coordination Gantt chart (System 1: 5ms, System 2: 50ms, Arbiter: 10ms)
- [ ] Fig 3.4: Bloch sphere visualization of QIRL quantum state superposition
- [ ] Fig 3.5: Multi-modal fault detection fusion architecture
- [ ] Fig 3.6: Ancillary service capability heatmap (FACTS + EV services)
- [ ] Fig 3.7: OPAL-RT topology for CAPSM deployment
- [ ] Fig 3.8: Timing diagram of CAPSM real-time execution

## Tables Required
- [ ] Table 3.1: Ancillary service capabilities of CAPSM (voltage, frequency, congestion, etc.)

## Key Code References
- `capsim_sim/capsm/agents/system1.py` — System 1 CNN-LSTM
- `capsim_sim/capsm/agents/system2.py` — System 2 QIRL
- `capsim_sim/capsm/agents/arbiter.py` — Metacognitive Arbiter
- `capsim_sim/capsm/grid/facts.py` — FACTS device models
- `capsim_sim/capsm/grid/ev_fleet.py` — EV fleet model

## File Location When Written
`03_proposed_framework/chapter_03.docx`
