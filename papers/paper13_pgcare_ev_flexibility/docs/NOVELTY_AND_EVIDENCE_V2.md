# PG-CARE v2 — Defensible Novelty and Evidence

## Central novelty

The defensible contribution is **not** LightGBM, conformal prediction, a rule-based EV controller, CQR, or the IEEE 33-bus feeder individually.

The contribution is an **information-safe reliability envelope for EV flexibility forecasting** that composes:

1. one-hour-ahead prediction of future connection availability instead of using realized future availability;
2. physical feasibility projection restricted to issuance-time information and declared schedules;
3. split-conformal state uncertainty calibrated after that projection;
4. conformalized quantile regression for upward flexibility;
5. abstention from unsupported state commitments; and
6. reliability-budgeted recovery that converts uncertainty width and connection confidence into a tunable feeder-support commitment.

The resulting scientific question is not simply “which classifier is most accurate?” It is:

> How much one-hour-ahead EV flexibility can be committed to grid support when forecasts must remain information-safe, physically feasible and explicitly uncertainty-aware?

## Four manuscript contributions

### C1 — Leakage-free availability-aware forecasting

A separate one-hour-ahead connection model replaces the earlier use of realized target-time connectivity. Declared schedules are treated as information available to an aggregator; realized connection remains a target/outcome only.

Evidence: future-connectivity accuracy 0.9702, F1 0.9722, AUC 0.9960, with an automated AST invariant test preventing target-time arrays from entering the feasibility mask.

### C2 — Post-projection conformal reliability

State probabilities are physically projected using issuance-time information and then calibrated. CQR is used for upward-flexibility intervals. A proof sketch in the manuscript states the limited condition under which ordinary split-conformal marginal validity remains applicable after a deterministic issuance-time projection.

Evidence: marginal state coverage 0.9117 at nominal 0.90; CQR empirical coverage 0.8996. Crucially, V2G conditional coverage is only 0.8016, which is reported rather than misrepresented as guaranteed.

### C3 — Generalization and anti-memorization evaluation

The study uses a contiguous 85-day chronological test interval, rolling-origin blocks, never-seen EV IDs, schedule corruption and feature-group ablations. These tests distinguish dynamic predictive information from static EV identity and declared-schedule information.

Evidence: unseen-EV macro-F1 0.7857; 12% schedule corruption gives 0.7766; dynamic-only ablation falls to 0.6488.

### C4 — Reliability-to-grid-value layer

A standard IEEE 33-bus AC QSTS stress test converts forecast uncertainty into a feeder-level reliability–value tradeoff. RBR recovers part of the conservatism of the CQR lower bound while retaining zero observed commitment shortfall in the reported test.

Evidence: raw mean commitment delivers 125.54 MWh but incurs 8.68 MWh shortfall; CQR lower bound delivers 43.13 MWh with zero observed shortfall; RBR delivers 53.76 MWh with zero observed shortfall.

## Extra improvement added in v2: RBR

Pure lower-bound commitment is reliable but frequently over-conservative because the CQR lower bound is zero for a large fraction of samples. RBR uses only forecast-time quantities—classification-set singleton status, predicted connection probability and interval width—to recover a validation-budgeted fraction of the gap between the lower bound and point forecast.

RBR is deliberately described as a **validation-calibrated recovery policy**, not a proven globally optimal controller.

## Why the smaller classification gain is better evidence

The previous draft reported a much larger gain from the physical mask. That gain was contaminated by target-time connectivity leakage. In v2, raw macro-F1 0.7986 rises to 0.8140 after leak-free projection and 0.8183 after conformal abstention. The smaller improvement is more credible because the model no longer receives future realization information.

A paired issue-time block bootstrap estimates the macro-F1 gain at +0.0196 with 95% CI [+0.0171, +0.0221].
