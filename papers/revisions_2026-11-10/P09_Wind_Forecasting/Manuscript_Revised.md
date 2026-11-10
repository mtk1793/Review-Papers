# Solar-Enhanced Hybrid ANN–LSTM–SVR Forecasting of Wind Power Across Three Canadian Provinces

> Working editorial draft. Source findings are unverified without reproducibility files.

**Status:** Rewritten from archived conference PDF; source results preserved but not reproduced

## Solar-Enhanced Hybrid ANN–LSTM–SVR Forecasting of Wind Power Across Three Canadian Provinces

RESEARCH WORKING DRAFT | 10 November 2026

Rewritten from archived conference PDF; source results preserved but not reproduced

## Abstract

Wind-power forecasting is sensitive to both meteorological variability and the design of the evaluation protocol. This paper revisits a source study combining artificial neural networks, long short-term memory networks, and support vector regression to estimate wind-generation output from atmospheric variables and solar-related information. The original experiments used NASA MERRA-2 reanalysis for sites in British Columbia, Manitoba, and Nova Scotia over 2017–2019, with turbine conversions for the Enercon E126/6500, Siemens SWT-3.6, and Vestas V90-2 systems. The proposed hybrid uses ANN and LSTM predictions as inputs to an SVR meta-estimator. The original manuscript reports strong fit, including R² near 0.9985 and mean squared logarithmic error near 0.001; these values are source-reported and have not been independently reproduced. The revised paper distinguishes the potential value of meteorological covariates from the statistical risks of overlapping temporal windows, ambiguous cross-validation, and stacking leakage. A chronology-aware re-evaluation plan is defined to establish whether solar-enhanced forecasting improves generalization across provinces and seasons.

## 1. Introduction

Accurate forecasts of wind production support scheduling, transmission congestion management, balancing reserves, and market decisions. Reanalysis weather products provide consistent historical meteorological fields but do not reproduce every local turbine inflow condition. The primary scientific challenge is therefore not simply to fit the available records, but to demonstrate transfer across seasons, geographies, turbines, and operating regimes. The original study proposed combining complementary learning mechanisms and using solar-related meteorological context. This rewrite organizes the method around an explicit prediction horizon, a separate meta-learning stage, and leakage-free evaluation.

## 2. Source Dataset and Equipment

The archived source uses MERRA-2 atmospheric reanalysis from 2017–2019 at approximate representative coordinates: British Columbia (55.0013°N, 125.0024°W), Manitoba (55.0013°N, 97.0010°W), and Nova Scotia (45.1960°N, 63.1654°W). It studies nominal turbine models Enercon E126/6500, Siemens SWT-3.6, and Vestas V90-2. These are model configurations rather than verified operating wind-farm measurements. Turbine-power conversion must document hub-height adjustment, power curves, cut-in/rated/cut-out speeds, air density, wake effects, and whether the target power was measured or generated synthetically.

The source states hourly data, a 70%/15%/15% train/validation/test division, and separate tenfold evaluation. How those folds respect chronological order is not established from the archived PDF. Accordingly, no independent claim of out-of-period transfer is made here.

## 3. Hybrid ANN–LSTM–SVR Architecture

The ANN component estimates static nonlinear relations among wind and solar covariates; the LSTM component processes lagged meteorological sequences; the SVR acts as a meta-regressor on predictions from the first two learners. The source describes ANN hidden widths 256 and 128 and LSTM widths 128 and 64, but full layer definitions and training hyperparameters require an executable model to reproduce. The meta-regressor must not train on in-sample predictions from base models that have seen the same target timestamps. Instead, construct out-of-fold forecasts from rolling temporal folds and train SVR on those held-out predictions.

Let z_ANN(t) and z_LSTM(t) be held-out base-model estimates of P(t+h); the stacked estimate is P_hat(t+h)=f_SVR[z_ANN(t),z_LSTM(t),x_meta(t)]. Set horizon h before window generation. Fit every scaler solely on its training fold. Evaluate against persistence, seasonal naive, standalone ANN/LSTM/SVR, and a non-stacked ensemble.

## 4. Proposed Chronological Validation

Allocate a final untouched test year or season at each site; use expanding-window temporal folds in the remaining interval. Repeat across provinces by holding out a province entirely to test geographic transfer. Separate the impact of adding solar irradiance from the effect of extra model parameters with a controlled ablation. Report the variance across locations and turbine conversion models.

Evaluate RMSE and MAE in MW and as fractions of turbine rating, bias, R², and ramp-event accuracy. Because MSLE assumes non-negative values and can underemphasize large power errors, include physically meaningful power-unit metrics. Calibrate empirical prediction intervals using a disjoint calibration window and test coverage across low-wind and high-wind bins.

## 5. Source-Reported Results and Interpretation

The archived conference PDF states a hybrid R² of approximately 0.9985 and MSLE of approximately 0.001 and reports stronger performance than individual learning baselines. Its figure-derived tabulations are not consistently legible in machine-readable text. Those results are preserved as reported historical outcomes but should not be treated as verified superiority. Reported tenfold cross-validation is difficult to interpret without fold boundaries; if random folds were applied to adjacent hourly samples, performance could be optimistic. Sensitivity tests involving SVR epsilon values of 0.1, 0.2, and 0.3 are described, although the original dataset, model weights, and executable training pipeline are not present in this package.

## 6. Limitations, Reproducibility, and Conclusion

The source document supports a clear hybrid architecture and experimental setting but is not sufficient to prove leakage-free performance or weather-to-power generalization. A defensible revised paper should re-run the original MERRA-2 data retrieval, publish temporal splits and turbine conversion, and document all models, seeds, and hyperparameters. Only then should the reported improvement be retained as an empirical conclusion. Until replication, the manuscript is a revised account of a historical study and a concrete verification protocol.

## Archival source

Kiasari and Aly, Enhancing Wind Power Forecasting Accuracy in Canada Using a Solar Data-Enhanced Hybrid Machine Learning Model: Integrating ANN, LSTM, and SVR. Source conference manuscript PDF preserved in this folder. Original bibliography and graphical results are contained in the source PDF.
