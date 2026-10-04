# PG-CARE v2 — Resolution of the Hostile Review / Upgrade Plan

This document records how the v2 package responds to the supplied critique. “Fixed” means the current package contains code/results addressing the issue. “Partial” means the issue is materially improved but not fully closed. “Open” means the package intentionally leaves it as a submission gate.

| Critique item | v2 status | Resolution / evidence |
|---|---|---|
| A1 — future target-time connectivity in physics mask | **FIXED** | New digital twin separates declared vs realized connection. A dedicated connectivity model predicts t+1h. `physics_project` receives no target-time realization arrays. AST invariant test passes. |
| A1 — conformal calibrated on leaked scores | **FIXED** | State conformal calibration is recomputed after leak-free projection. |
| A2 — same-generator “OOD” overstated | **FIXED IN CLAIMING / PARTIAL IN EVIDENCE** | v2 no longer sells shifted constants as external OOD. It adds contiguous chronology, rolling-origin, never-seen EVs and schedule corruption. True measured external validation remains open. |
| A3 — invented reserve product/economics | **FIXED** | Synthetic market-revenue result is removed from the v2 headline. Feeder QSTS reports physical delivery/shortfall instead. |
| B1 — zero measured data | **OPEN** | Acquisition adapters + explicit protocol provided. Not claimed as executed validation. |
| B2 — predicting own deterministic rule | **PARTIAL** | Realized schedule differs stochastically from declared schedule and availability must be predicted; however fleet physics/controller remain simulation-derived. Measured session calibration remains the next gate. |
| B3 — off-the-shelf methods/no theory | **PARTIAL/IMPROVED** | Added leak-free post-projection conformal proposition/proof sketch, conditional coverage, CQR and RBR. Stronger chance/CVaR theory remains possible. |
| B4 — weak TC-MoE strawman | **FIXED BY DE-EMPHASIS** | Deep-model “win” is no longer a core novelty claim. The method is backbone-agnostic and v2 centers information integrity/reliability instead. |
| B5 — only 25 references | **IMPROVED** | v2 literature database/manuscript contains 40 references, all dated 2020–2026, emphasizing recent IEEE Transactions and conformal/energy literature. |
| B6 — no network | **FIXED FOR TEST-SYSTEM EVIDENCE** | Added full-test IEEE 33-bus balanced AC QSTS and reliability-value tradeoff. Utility-feeder validation remains open. |
| C — random sampled evaluation | **FIXED** | Final evaluation uses every hourly issue time over the contiguous 85-day test interval, all 100 EVs (203,900 forecasts), plus rolling-origin analysis. |
| C — EV identity memorization | **FIXED/QUANTIFIED** | Never-seen EV split and identity/schedule/dynamic feature ablations included. |
| C — PNG/script-built manuscript only | **FIXED** | IEEEtran LaTeX + compiled PDF + vector PDF figures are included, alongside editable Word. |
| C — weak calibration metrics | **FIXED** | ECE, Brier, marginal/conditional conformal coverage, set size, singleton rate, CQR coverage/width included. |
| C — dependent forecast uncertainty | **IMPROVED** | Main improvement CI uses paired block bootstrap over forecast issue times rather than treating all EV forecasts as independent. |

## Additional improvement beyond the supplied plan

v2 adds **Reliability-Budgeted Recovery (RBR)**. The CQR lower bound is reliable but too conservative for useful feeder support. RBR recovers a validation-budgeted fraction of the gap to the point forecast only when the state prediction is singleton, future connection confidence is adequate and the CQR interval is sufficiently narrow. In the current test, RBR raises delivered V2G support from 43.13 to 53.76 MWh while retaining zero observed commitment shortfall.
