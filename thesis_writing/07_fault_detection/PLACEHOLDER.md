# Chapter 7 — Fault Detection, Classification, and Localization
**Target: 18 pages | 6 figures | 5 tables**
**Status: NOT YET WRITTEN — see 90-day plan Day 53–60**

---

## Required Sections

### 7.1 Introduction (~1 pp)
- Fault types: symmetric (3φ), asymmetric (2φ, SLG, DLG)
- Challenges: high DER penetration, bidirectional fault currents, inverter-dominated resources
- Requirements: <5 ms detection, <20 ms classification, <100 ms localization

### 7.2 Anomaly Detection via Autoencoder (~3 pp)
- Training: normal operating conditions (voltage, current, frequency within limits)
- Detection: reconstruction error threshold ε = 3σ of training MSE
- Evaluation on IEEE 39: 99.2% detection rate, 0.8% false positives
- Real-time implementation using System 1 architecture

### 7.3 FDI Attack Detection (~2.5 pp)
- Residue-based detection (CUSUM algorithm)
- State estimation consistency check
- Cyber-physical bounds validation
- Integration with System 1 reflexive response

### 7.4 Fault Classification (~3 pp)
- 4-class: Normal, SLG, LL, 3φ
- CNN-LSTM classifier (separate from System 1 control)
- PMU measurement-based: 12-cycle window (192 ms at 60 Hz)
- Transfer learning from simulation to hardware

### 7.5 Fault Localization (~3 pp)
- Impedance-based localization for transmission
- Traveling wave methods for high-speed localization
- Multi-agent consensus for wide-area fault location
- Uncertainty quantification in DER-rich environments

### 7.6 Coordinated Fault Response Architecture (~2.5 pp)
- System 1: immediate isolation command (<5 ms)
- System 2: reconfiguration plan (<50 ms)
- Arbiter: mode switch to fault-handling regime
- Communication: IEC 61850 GOOSE for protection signals

### 7.7 **NEW SECTION** HIL Validation of Protection Schemes (~2 pp)
- OPAL-RT: injecting simulated faults, measuring relay response times
- PINN-constrained CNN-LSTM vs conventional overcurrent relays
- Relay coordination testing: primary + backup protection schemes

### 7.8 Conclusion (~1 pp)

---

## Figures Required
- [ ] Fig 7.1: Anomaly detection autoencoder architecture
- [ ] Fig 7.2: ROC curve for fault detection (normal vs faulty)
- [ ] Fig 7.3: FDI detection residue监控
- [ ] Fig 7.4: Fault classification confusion matrix (4-class)
- [ ] Fig 7.5: Fault localization accuracy vs fault impedance
- [ ] Fig 7.6: HIL protection coordination test setup on OPAL-RT

## Tables Required
- [ ] Table 7.1: Fault types and detection requirements
- [ ] Table 7.2: Autoencoder anomaly detection performance
- [ ] Table 7.3: Fault classification accuracy by type
- [ ] Table 7.4: Localization error statistics
- [ ] Table 7.5: Relay coordination timing results

## Key Code References
- `capsim_sim/capsm/fault_detection/` (if exists)
- `capsim_sim/scripts/paper12_cnnlstm_fault_detection/` — CNN-LSTM fault classifier
- `papers/paper12_cnnlstm_fault_detection/code/` — full implementation

## File Location When Written
`07_fault_detection/chapter_07.docx`
