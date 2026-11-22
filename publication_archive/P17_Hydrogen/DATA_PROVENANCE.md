# Authentic dataset strategy and location check

## Primary source: NLR/NREL NOW-23 North Atlantic

Official documentation: https://developer.nlr.gov/docs/wind/wind-toolkit/offshore-north-atlantic-download/

- WRF modelled meteorological winds, 5-minute native time base, 2-km scale, 2000–2020 inclusive. This source can support a 2020 held-out study, **not** 2021 or 2022.
- Requested region from the rejected manuscript: 45.38°N, 61.50°W (Guyborough offshore point as labeled by its authors; exact offshore siting unverified). The API picks a nearest site; code rejects a site more than 20 km away. **Coverage has not been verified**.
- Requires API key, valid contact email. Files delivered with site metadata; downloader records output SHA256 and checks continuity and location.
- Split before experiments: 2017–2018 train, 2019 calibrate, 2020 test. No test leakage; no interpolation to fill gaps.
- H2 output is derived from assumed turbine power curve and user-specified rated 700 MW. These are *modelled inputs*, not observed Nova Scotia electricity or actual curtailment.

## Alternative regional dataset: Net Zero Atlantic (NZA), 2026

https://netzeroatlantic.ca/atlantic-canada-offshore-wind-grid-integration-and-transmission-study

July 2026 report describes 1 km resolution, 5-minute regional wind data, accessible by interactive portal and full data request through NZA's ShareFile. If NOW-23 point fails coverage, this regional data is preferable for Nova Scotia. Requests require user authorization; no data included here.

## Independent historical sensitivity: ERA5 reanalysis via Open-Meteo

https://open-meteo.com/en/docs/historical-weather-api

- `scripts/download_era5.py` retrieves a *modelled historical real reanalysis*, not synthetic white noise.
- 2017–2020, hourly, 100-m wind speed. Save raw response and SHA256.
- `config/era5_hourly.json` correctly changes timestep to 60 min, not interpolated 15 min.
- Mapped power output remains an assumed turbine curve. Report forecast results and controller results as a distinct reanalysis case, not a NREL replication.

## Additional context

Nova Scotia Power (NSPI) hourly load public archive: https://www.nspower.ca/oasis/monthly-reports/hourly-total-net-nova-scotia-load . Aggregate load alone cannot reconstruct transmission thermal constraints and historical curtailed injections. Do not state derived residual energy is actual 2020 Nova Scotia curtailment.

## Missing empirical inputs that block acceptance

1. Calibrated PEM ageing coefficients from manufacturer/lab or credible published transfer function; `cold_start_equivalent_hours` defaults to 0 precisely to avoid inventing 50-equivalent-hour claims.
2. Verified annual hydrogen sales/offtake agreements and matching storage/transport; the original 800 kg/day versus 50 MW plant 340 GWh/year is incompatible without new customers or storage.
3. True time-varying market/contract tariff, grid import/export arrangement, and curtailment measurement methodology. The 42/90 $/MWh figures are scenarios only.
4. Grid bottleneck study or official curtailment traces. `export_limit_mw=300` is a model hypothesis, not proof of a 300 MW physical constraint.
5. Rejected submission version, original code and experiment runs. Current code is a replacement benchmark built here, not validation of absent original implementation.
