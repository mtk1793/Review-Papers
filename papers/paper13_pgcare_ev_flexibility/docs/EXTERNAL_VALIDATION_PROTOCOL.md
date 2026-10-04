# External measured-data validation protocol

The v2 numerical results in this package are deliberately **not** labeled as field validation. They are leak-free digital-twin + feeder-QSTS results.

For the pre-submission external validation stage:

1. **ACN-Data (Caltech/JPL)**: use `code_v2/external_data/download_acndata.py` with the researcher's own API token. Fit arrival, departure, requested-energy and session-duration distributions on Caltech; test transfer on JPL without refitting the PG-CARE reliability layer.
2. **Open Power System Data Household Data (2020-04-15)**: use `download_opsd_household.py` to replace synthetic native load/PV with measured 15-min channels. Keep EV SOC dynamics simulated and state clearly: *measured exogenous load/PV; simulated EV fleet dynamics*.
3. Re-run the exact chronological/calibration/test protocol. Do not tune on the external site.
4. Report state macro-F1/MCC, future-connectivity AUC/F1, classification conformal coverage by class/hour, CQR coverage/width, feeder voltage/loss metrics, and commitment shortfall.
5. Any measured-data result must be separately tagged in `RESULTS_TRACEABILITY_V2.md` before it appears in the paper.

This protocol is included to make the next evidence upgrade executable without pretending that it has already been completed.
