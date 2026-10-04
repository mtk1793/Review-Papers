# PG-CARE v2 — Data Dictionary

## `data_v2/digital_twin_v2.npz`

The primary v2 simulated supervisory dataset. Arrays are indexed by time and EV unless otherwise noted. The generator uses 365 days, 15-minute resolution and 100 heterogeneous EVs.

Core concepts:

- **declared schedule**: information assumed available to the aggregator before the forecast horizon (declared/expected plug-in and departure behavior);
- **realized connection**: stochastic outcome used as target/evaluation data and never supplied directly to the one-hour-ahead physical feasibility mask;
- **SOC**: simulated battery state of charge;
- **state**: supervisory operating state (Idle, G2V, V2G);
- **native/system load and price context**: simulated exogenous supervisory context;
- **EV static parameters**: capacity, charger power, min-SOC and participation policy.

The exact array keys, shapes and feature construction should be read directly from `code_v2/11_generate_leakfree_twin.py` and `code_v2/12_train_leakfree_pgcare.py`; those files are authoritative if this summary and code ever diverge.

## `data_v2/aggregate_timeseries_v2.csv`

Time-indexed system/fleet aggregate values used for visualization and feeder coupling.

## `data_v2/fleet_parameters_v2.csv`

One row per simulated EV with fixed fleet parameters.

## Model input channels

The main state/availability pipeline constructs a 2-hour history (8 × 15-minute steps) with 17 channels spanning:

- current/recent SOC and connectivity;
- recent operating-state indicators;
- declared time-to-departure / schedule information;
- requested SOC;
- normalized native load and price context;
- time-of-day encoding;
- load-quantile context;
- static battery/charger/min-SOC/policy information;
- declared one-hour connection indicator.

## Chronological partition

- train: days 0–199;
- conformal calibration: days 200–239;
- validation: days 240–279;
- final test: days 280–364.

The final test is evaluated hourly for every EV, yielding 203,900 forecasts.

## Information-integrity rule

The physical feasibility projection may use only issuance-time information, declared schedules and predicted future-connectivity probability. It may not use realized target-time connectivity, target state or target flexibility. The invariant is checked by `code_v2/15_block_bootstrap_and_tests.py` and recorded in `tests/LEAK_FREE_INVARIANT_PASS.txt`.
