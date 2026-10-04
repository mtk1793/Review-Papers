# Data dictionary

## `data/aggregate_timeseries.csv`

Each row is one 15-min fleet time step.

- `step`: integer simulation step.
- `day`, `dow`, `doy`, `hour`: calendar/time indices.
- `base_load_kw`: modeled native gross load before PV.
- `pv_kw`: modeled PV production.
- `native_kw`: native net demand after PV.
- `ev_kw`: aggregate EV charging (+) / discharging (-) power.
- `feeder_kw`: native net load plus aggregate EV power.
- `price`: stylized time-of-use study price.
- `q25_kw`, `q75_kw`: previous-day native-load quartile thresholds.
- `connected`: number of connected EVs.
- `idle`, `g2v`, `v2g`: number of EVs in each operating state.
- `mean_soc`: mean fleet SOC.

## `data/digital_twin_arrays.npz`

- `soc[T,N]`: EV SOC fraction.
- `state[T,N]`: 0=Idle, 1=G2V, 2=V2G.
- `conn[T,N]`: connected flag.
- `pev[T,N]`: EV power in kW; charging positive, discharging negative in this Python implementation.
- `ttd[T,N]`: time to departure in hours.
- `req[T,N]`: required departure SOC.
- `cap[N]`: battery capacity in kWh.
- `charger[N]`: charger rating in kW.
- `min_soc[N]`, `target[N]`: owner minimum and target SOC.
- `policy[N]`: 0 disconnected, 1 charge-only, 2 bidirectional.
- `arr[D,N]`, `dep[D,N]`: daily arrival/departure times.
- `trip[D,N]`: daily trip energy in kWh.
- `eta_c[N]`, `eta_d[N]`: charging/discharging efficiencies.

## Forecast feature tensor

The learning window uses 8 consecutive 15-min samples (2 h), with 16 features per sample: SOC; connection; one-hot Idle/G2V/V2G current state; normalized time-to-departure; required SOC; normalized native load; normalized price; sine/cosine time-of-day; native-load position in the Q1/Q3 range; battery capacity; charger rating; minimum SOC; owner policy. The target horizon is 4 steps (1 h).

## Auxiliary targets

- Future SOC fraction.
- Upward flexibility kW: future feasible V2G capability.
- Downward flexibility kW: future feasible charging capability.

## OOD files

`ood_aggregate_timeseries.csv` and `ood_shift_arrays.npz` use a separately generated 90-day shifted regime. No model is retrained on these files.
