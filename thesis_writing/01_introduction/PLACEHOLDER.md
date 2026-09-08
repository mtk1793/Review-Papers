# Chapter 1 — Introduction
**Target: 12 pages | 5 figures | 3 tables**
**Status: NOT YET WRITTEN — see 90-day plan Day 1–5**

---

## Required Sections

### 1.1 Background on Power System Challenges in the Renewable Energy Era (~3 pp)
- Global energy transformation, IEA statistics (60% capacity increase 2020–2026, 4800 GW)
- Key challenges: intermittency, reduced inertia, bidirectional flows, complexity, cybersecurity, market/regulatory

### 1.2 Evolution of FACTS Devices (~2 pp)
- EPRI 1980s, shunt (SVC/STATCOM), series (TCSC), combined (UPFC)
- Role in renewable integration

### 1.3 Integration of EVs into Smart Grids (~1 pp)
- G2V, V2G, V2H, V2X, bidirectional charger requirements
- Mathematical modelling of EV fleets

### 1.4 Research Motivation (~2 pp)
- DER integration trends (132.4 GW → 528.4 GW by 2026, 16.7% CAGR)
- Resilience, technical/economic/environmental imperatives

### 1.5 Problem Statement (~1.5 pp)
**5 critical research gaps:**
1. Inadequate control architectures for heterogeneous systems
2. Limited real-time decision-making under uncertainty
3. Insufficient coordination between FACTS and DERs
4. Insufficient fault detection/localisation in resource-rich environments
5. Integration barriers between theory and practice (HIL is the bridge)

### 1.6 Research Objectives (~1.5 pp)
**5 objectives with measurable goals:**
1. Develop brain-inspired dual-process AI architecture
2. Validate on hardware-in-the-loop (3-stage pipeline)
3. Achieve measurable improvements over conventional methods
4. Demonstrate on multiple IEEE test systems
5. Publish open-source Python framework

### 1.7 Original Contributions (~1 pp)
**9 contributions:**
1. Novel brain-inspired dual-process AI control framework (System 1 + System 2)
2. Quantum-Inspired RL (QIRL) for power system optimization
3. Metacognitive arbiter for real-time mode switching
4. PINN-constrained CNN-LSTM for reflexive control
5. FACTS+EV+V2G coordinated control architecture
6. Digital twin methodology for power system validation
7. Transfer learning across IEEE test systems
8. **HIL Validation Methodology on 4-Core OPAL-RT** ← explicit, not implicit
9. Open-source Python CAPSM framework (capsim_sim)

### 1.8 Thesis Organization (~0.5 pp)
- One paragraph per chapter highlighting the HIL additions

---

## Figures Required
- [ ] Fig 1.1: Global renewable energy capacity growth (2010–2023) — bar chart from IEA data
- [ ] Fig 1.2: Traditional vs modern power system control challenges — side-by-side diagram
- [ ] Fig 1.3: Research gap identification framework — flowchart showing 5 gaps
- [ ] Fig 1.4: Overview of CAPSM framework — system architecture diagram (**KEY DIAGRAM**)
- [ ] Fig 1.5: Three-stage validation pipeline — block diagram (Offline → Simulink → OPAL-RT)

## Tables Required
- [ ] Table 1.1: Key challenges in modern power systems with high DER penetration
- [ ] Table 1.2: Comparison of conventional and AI-based control approaches
- [ ] Table 1.3: Research objectives and success metrics

## References
~15 refs from 2018–2026 (IEA reports, NERC standards, major surveys)

## Key Numbers to Use
- DER growth: 132.4 GW → 528.4 GW by 2026 (16.7% CAGR)
- System 1: <5 ms inference budget
- System 2: <50 ms inference budget
- HIL: 4-core OPAL-RT, 50us EMT timestep

## File Location When Written
`01_introduction/chapter_01.docx`
