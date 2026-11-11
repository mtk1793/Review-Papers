# PG-CARE v2 — Limitations and Flagship-Submission Gate

## What is now fixed

- Target-time connectivity leakage in the physical mask: fixed.
- Conformal calibration on leaked scores: fixed by recalibrating after the leak-free projection.
- Random-window headline evaluation: replaced by a full contiguous 85-day chronological test and rolling-origin reporting.
- EV-identity memorization concern: directly evaluated with never-seen EVs and feature-group ablation.
- No feeder layer: addressed with an IEEE 33-bus balanced AC QSTS stress test.
- Point-only flexibility uncertainty: addressed with CQR.
- Over-conservative CQR lower-bound commitment: partially addressed by RBR.
- iid-style uncertainty over dependent EV forecasts: replaced by paired issue-time block bootstrap for the main delta.

## What is still unresolved

### 1. Executed measured-data external validation — highest priority

The v2 study still uses a source-informed stochastic supervisory digital twin for the fleet state/SOC dynamics. External-data adapters and an acquisition protocol are included, but no measured ACN/OPSD experiment is claimed in the manuscript.

Before calling this a fully mature flagship TSG submission, the strongest next experiment is:

- fit/validate arrival, departure and session-energy behavior from ACN-Data or an equivalent public session dataset;
- drive load/PV from measured profiles;
- freeze the v2 model or specify a clearly bounded adaptation procedure;
- report transfer/calibration degradation without silently retraining on the test domain.

### 2. V2G-conditional coverage

Marginal state coverage is ~91.2%, but V2G-conditional coverage is ~80.2%. Standard split conformal does not guarantee arbitrary class-conditional or distribution-shift coverage. A final flagship version should investigate Mondrian/class-conditional calibration, adaptive conformal methods or a V2G-specific safety threshold.

### 3. Feeder realism

The IEEE 33-bus study is a standardized stress test, not a utility feeder model. Future work should include an actual distribution feeder or a more realistic unbalanced test system with transformer/phase detail.

### 4. RBR theory

RBR is validation-calibrated and empirically useful, but it does not currently have a formal optimality or chance-constraint guarantee. A CVaR/chance-constrained commitment formulation could strengthen the theoretical contribution.

### 5. Market/settlement claims intentionally removed

The earlier synthetic reserve-revenue narrative is not used as a headline result because it was not tied to a specific market product and settlement rule. Market economics should return only after a real product definition, price series and penalty/availability rules are encoded.

## Submission assessment

**Current v2:** materially more defensible than v1 and suitable for serious internal review / pre-submission development.

**For strongest IEEE Transactions on Smart Grid submission:** execute external measured-data validation and improve V2G-conditional calibration before submission. The present paper states these limitations explicitly rather than claiming them away.
