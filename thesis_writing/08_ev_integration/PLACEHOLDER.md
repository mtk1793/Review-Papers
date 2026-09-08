# Chapter 8 — EV Integration and V2G Control
**Target: 18 pages | 6 figures | 5 tables**
**Status: NOT YET WRITTEN — see 90-day plan Day 61–67**

---

## Required Sections

### 8.1 Introduction (~1.5 pp)
- EV growth projections (132.4 GW → 528.4 GW by 2026)
- Grid services from EV fleets: frequency regulation, voltage support, peak shaving
- V2G potential: 10% of fleet = significant grid resource

### 8.2 EV Charging Behavior Modeling (~3 pp)
- Probabilistic models: arrival/departure times, energy requirements
- Spatial-temporal uncertainty quantification (Monte Carlo)
- IEEE 2030.1 charging profiles
- Integration with OPSD real data (January 2019)

### 8.3 V2G Service Architecture (~3 pp)
- Frequency response: droop characteristic i = i₀ + K_droop·(f − f₀)
- Voltage support: reactive power injection from EV inverters
- Demand charge management: valley filling algorithm
- Aggregation: fleet manager as single proxy for grid services

### 8.4 EV + FACTS Coordinated Control (~3 pp)
- Joint optimization: minimize combined operating cost + violations
- System 2 QIRL: evaluate joint action candidates (FACTS + EV simultaneously)
- Hierarchical: FACTS for local voltage, EV for global frequency
- Cyber-physical security: EV charging station communication vulnerabilities

### 8.5 System 1 Reflexive EV Control (~2.5 pp)
- Fast EV reactive power response (<5 ms)
- Pre-fault proactive EV charging/discharge scheduling
- CNN-LSTM prediction of EV fleet availability

### 8.6 System 2 Deliberative EV Dispatch (~2.5 pp)
- QIRL optimization over 24-hour horizon
- Multi-objective: cost + emissions + reliability
- Real-time re-dispatch under forecast errors

### 8.7 **NEW SECTION** HIL Validation of EV Integration (~2 pp)
- OPAL-RT: emulating EV fleet response with hardware EV chargers
- Communication delay impact on V2G frequency response
- Hardware-in-the-loop: real EVSE (Electric Vehicle Supply Equipment) connected to OPAL-RT

### 8.8 Conclusion (~0.5 pp)

---

## Figures Required
- [ ] Fig 8.1: EV fleet aggregation for grid services
- [ ] Fig 8.2: V2G droop characteristic for frequency response
- [ ] Fig 8.3: EV + FACTS coordinated control block diagram
- [ ] Fig 8.4: 24-hour EV dispatch optimization (System 2 output)
- [ ] Fig 8.5: Impact of V2G penetration on hosting capacity
- [ ] Fig 8.6: HIL EV test setup with OPAL-RT

## Tables Required
- [ ] Table 8.1: EV fleet grid service capabilities
- [ ] Table 8.2: Charging behavior probabilistic parameters
- [ ] Table 8.3: V2G frequency response performance
- [ ] Table 8.4: Coordinated control improvement over uncoordinated
- [ ] Table 8.5: HIL EV validation results

## Key Code References
- `capsim_sim/capsm/grid/ev_fleet.py` — EV fleet model
- `papers/paper8_ev_v2g_uvls/` — EV V2G UVLS paper implementation

## File Location When Written
`08_ev_integration/chapter_08.docx`
