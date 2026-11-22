# Validation evidence — 20 Nov 2026

**Software/unit test status: PASS — 18 tests executed.** See `results/pytest_output.txt`.

**Executed synthetic smoke test: PASS.** See `results/smoke_results.json` and `results/smoke_console.txt`. The sequence was generated using a seeded sine function and Gaussian noise: IT IS NOT REAL HISTORICAL WIND. No values from it may appear as research findings.

**Analytical input-consistency audit: PASS.** See `results/hard_feasibility_audit.json` and `scripts/audit_claims.py` for reproducible bounds and offtake inconsistency. No network or dataset needed for these checks.

**Real-data empirical results: BLOCKED / NOT EXECUTED.** The primary official NLR source is known and documented, but the execution environment lacks network access and user-specific API credentials; the reviewer package does not contain original source code, raw dataset files, calibration measurements, or historical market price series. See `results/empirical_attempt.txt` for the explicit fail-closed command outcome. An alternative ERA5 real archive downloader is included and can run on a network-connected machine without a key.

**ML model code test extent:** finite autograd updates, action bounds, tensor shapes, quantile-loss backpropagation. **Not proven:** RL convergence, seed robustness, calibrated 2020 forecasting, improved stack health, actual market arbitrage, genuine multi-agent interaction, end-to-end wall-clock latency, comparative statistical significance or realistic NPV.

**Reviewer source mismatch:** `Comments.txt` refers to Table 3 and a Pd–Ag ethanol catalyst citation [29] not appearing in the uploaded source version in that configuration. Submitted-to-review version not supplied.

**Manuscript:** fully regenerated 4-page two-column research draft and visually rendered. It explicitly discloses validation pending; it is not a final submission manuscript.

## Validation test breakdown

- Physical/engineering: power balance, ramp, battery/tank bounds, production mass balance, annual electrolyzer cap, BESS autonomy, turbine curve.
- Forecasting: LSTM/quantile-loss tensor shapes and backward pass; conformal score and interval coverage.
- Learning: SAC finite critic/actor update and continuous action constraint; QR-DQN finite update and 51 quantiles.
- Data: NLR metadata/header parsing and strict train/holdout year validation.
- Economics: discounting and replacement threshold scheduling.
- Scheduling: LP-MPC solver feasibility and conservation when projected into the physical environment.

## Acceptance decision

DO NOT SUBMIT AS EMPIRICALLY VALIDATED. Research results require sourced test inputs, physical calibration, independently trained baselines and a regenerated figures/tables/results file. Verify official IEEE Author Kit requirements before final production.
