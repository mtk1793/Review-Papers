# IEEE Transactions recovery: evidence-first execution plan

**Status as delivered 2026-11-20: METHOD / CODE REBUILD AND SOFTWARE TESTS COMPLETED; OUT-OF-SAMPLE EMPIRICAL VALIDATION NOT COMPLETED.**

## Target and defensible contribution

Target: IEEE Transactions on Sustainable Energy (TSTE). The paper is a forecast-informed *hierarchical hybrid learning* framework with (i) supervised quantile-LSTM, (ii) risk-sensitive quantile-DQN arbiter and (iii) SAC continuous electrolyzer/BESS controller. The manuscript must not call the forecaster an RL agent. Sequential training of SAC/QR-DQN is not proof of independent multi-agent learning; to claim cooperative MARL in future, explicitly specify Markov games, joint training, policy nonstationarity controls, independent/central critics and agent-level rewards/actions, plus ablate coordination against a hierarchy.

## Authoritative sources and versioning

The provided paper and reviewer file are preserved in `sources/`. The reviewer describes a Table 3 not found in the supplied 10-page Word document (two numbered substantive tables). The reviewer also describes ref. [29] as a catalyst reference, but the supplied file's ref. [29] is about carbon taxation. **These are different document versions or inconsistent source references and must not be silently repaired as though identical**. Obtain the actual submitted version and its original scripts/logs; add SHAs and a change log before resubmission.

## Phases, gates, objective evidence

### G0 — Freeze and trace source
- Check submitted DOCX, source ZIP, revision/decision date and reviewer numbering against provided artifacts.
- Store checksums; list missing equations, charts, tables and erroneous claims.
- **Gate:** complete document comparison and executable baseline reproduction.

### G1 — Data provenance / no fake data
- Primary: NLR/NREL NOW-23 North Atlantic hourly/5–15-min meteorology, archive years 2000–2020. Download 2017–2020 at 15 min for the requested 45.38N, -61.50W **only after checking site coverage**. If nearest valid site is not near Guysborough, reject site selection and use locally relevant Net Zero Atlantic data instead.
- Alternative distinct sensitivity dataset: publicly accessible ERA5 hourly reanalysis at 45.38N, -61.50W, 2017–2020, no interpolation to 15 min. Explicitly label as *reanalysis*, not metered wind power or real measured curtailment.
- NSPI historical total hourly net load: https://www.nspower.ca/oasis/monthly-reports/hourly-total-net-nova-scotia-load. Align UTC carefully and consider timezone/DST. Load is insufficient alone to infer historical transmission curtailment.
- Real prices: exact retail tariff / power contract if applicable; NS does not have the assumed Boston-style hourly merchant hydrogen or generic $42/MWh spot settlement. Mark all missing price series as **scenario assumptions**.
- **Gate:** provider ID, source URL, timestamps, station grid point, completeness, SHA256, downloaded data and preprocessing notebook are included; temporal splits enforced.

### G2 — Rebuild physically accountable model
- 15-min dispatch: 700 MW assumed wind plant, 50 MW PEM electrolyzer, 20 MWh/10 MW BESS, 500 kg H2 tank, 300 MW export limit (scenario, not transmission study), ramp constraints, electrolysis efficiency 52 kWh/kg (assumed), inventory, mass/power conservation and hydrogen offtake.
- Do not assert a validated electrochemical ageing law: ramp, thermal and cold-start coefficients are uncalibrated surrogates. Report sensitivity curves and a separate engineering-literature-based parameter identification effort.
- Present nominal design life (manufacturer), accumulated equivalent-stress life (estimated), and discounted replacement cost (economic) as separate variables.
- Verify annual intake bound for 50 MW, demand/tank throughput and battery energy autonomy. Reject impossibilities before train/evaluation.
- **Gate:** all physical invariant tests pass; parameter uncertainty and calibration limits documented; no claim of full AC grid analysis or validated PEM stack life.

### G3 — Forecasting with uncertainty
- LSTM emits q0.1, q0.5, q0.9 through pinball loss. Conformal calibration on **2019 only**; 2020 untouched for evaluation.
- Report MAE, RMSE, interval coverage at 80%, mean interval width and interval/Winkler score, by season, forecast horizon and high ramp strata.
- Compare persistence, seasonal climatology, quantile linear/GBM and (if available) NWP. Temporal block bootstrap; address dependence and calibration drift. Validate no look-ahead and no shuffled contiguous samples across years.
- **Gate:** calibrated coverage reliability charts, 95% block-bootstrap confidence intervals and forecast baseline comparisons; scores generated from model outputs.

### G4 — Controllers and architecture
- Phase A train QR-DQN over discrete dispatch priorities using fixed reference setpoint controller; 51 return quantiles, lower-tail CVaR proxy (lowest 25%).
- Phase B train continuous-action SAC with QR-DQN policy frozen. Explicitly describe this as staged hierarchical RL, not joint MARL.
- Independent single-agent SAC training is now implemented as a separate checkpoint; it still requires real-data evaluation for a fair no-arbitrage ablation. A diagnostic LP-MPC relaxation is implemented; a competitive MILP or MPC with all matched integer operating constraints remains required and oracle MPC clearly labeled as unattainable upper bound.
- Use stochastic, real or clearly scenario-defined price models to establish that CVaR yields value under *market* tail risk; constant prices support only risk over wind/control outcomes.
- **Gate:** train/validation loss, reward curves, stability across >=5 seeds, fair wall-clock accounting and strong baselines. No hyperparameter retuning on 2020.

### G5 — Evidence-led results
- Define and separate denominators: (a) energy absorbed / theoretical residual available, (b) energy absorbed / plant maximum, (c) share of original claimed 1126 GWh, (d) physical curtailment before and after optimization. Do not call all of these 'curtailment utilization'.
- Metrics: plant output kg, delivered kg, unmet kg, power and H2 balance, BESS SOC, ramp/starts, equivalent ageing hours, constrained export, actually curtailed wind, scenario cash and true 15-year discounted NPV (separate validated CAPEX/OPEX, transport, certification, replacements, penalties and discount rate).
- Report 5+ RL seeds + paired temporal blocks of identical held-out weather/price episodes. Include mean, SD, 95% CI (block bootstrap for time, seed variability separately) and corrected comparisons. Report negative findings.
- Ablations: no degradation, no quantile risk, point forecast, no forecast, no BESS, no hierarchy, risk aversion 0/0.1/0.25/0.5, ageing coefficient sensitivities 0/2/10/50 equivalent hours per start, market volatility, storage capacity.
- **Gate:** data-led regenerated tables/figures; no number manually transcribed into the manuscript; prove the result arithmetic with independent scripts.

### G6 — Resubmission writing and formatting
- Journal-aligned title, 200–250-word abstract containing only *verified* effect sizes; prior-work gap; formal optimization; 2–3 main equations per component; data provenance; experimental protocol; results with uncertainty; honest limitations.
- Never use 'real-world commercial deployment ready' from model simulation. Avoid 'first-ever' without a complete systematic review. Preserve objective citations next to supported assertions.
- Independent crosschecks: paper table names/numbers, all in-text captions, equation symbols and subscripts, duplicate DOI audit, figure units, English proofreading, IEEE Author Kit and plagiarism checks.
- IEEE TSTE requirements: use current official author kit at https://ieee-pes.org/publications/authors-kit/ ; 12-page accepted-paper limit before compulsory page charges for newer submissions is not permission to ignore initial submission constraints.
- **Gate:** independent scholarly review and release checklist with evidence links all PASS. Current package does **NOT** meet this gate.

## Pass/fail dashboard on the current handoff

| Gate | Status | Verified evidence / missing item |
|---|---|---|
| G0 source freeze | PARTIAL | Supplied Word + reviewer text copied; submitted version and original code are absent |
| G1 real wind download | BLOCKED | Source documented; no API key, downloaded time series or coverage proof in this environment |
| G2 hard constraints | PASS for software / UNVALIDATED physical parameters | 18 unit tests and analytical contradiction audit; coefficients are scenarios |
| G3 forecast algorithms | PASS software / NOT empirical | Quantile LSTM and conformal test; no 2017–2020 scores |
| G4 hierarchical RL algorithms | PASS software / NOT converged | SAC and QR-DQN shape/gradient tests, smoke test; independent SAC/MPC needed |
| G5 rigorous comparative statistics | BLOCKED | Bootstrap utilities implemented; no 2020 holdout or statistical significance claimed |
| G6 publishable paper | RESEARCH DRAFT ONLY | Rewritten evidence-bounded journal draft; numerical results section deliberately pending |

## Publication decision rule

**DO NOT SUBMIT** until (i) a real source with verified Nova Scotia location and data license is acquired and validated, (ii) strong baselines and >=5 seeds are run, (iii) PEM wear parameters are externally justified, (iv) complete financial premises are replaced with documented costs and prices, (v) tables/figures and abstract are regenerated from untouched test outputs, (vi) each reviewer issue is explicitly closed with evidence. Do not use synthetic smoke-test outputs in a research result table.

## Final execution commands (Python 3.11+, installed dependencies)

```bash
pip install -r requirements.txt
export PYTHONPATH=src
pytest -q tests
python scripts/audit_claims.py
python scripts/run_smoke.py                 # synthetic smoke TEST, not scientific evidence
# Primary source; set API key and contact info via local environment ONLY
export NLR_API_KEY="your-key"
export NLR_EMAIL="your-email"
python scripts/download_now23.py
python scripts/run_empirical.py --config config/experiment.json
# Alternative real ERA5 weather, separate hourly experiment
python scripts/download_era5.py
python scripts/run_empirical.py --config config/era5_hourly.json
```

## Data security

Keep API keys, emails and consent-limited source data out of code releases. Nothing in this package connects to unpublished utility datasets. Report timestamps, time zone, coordinate coverage, unit conversions and license before public distribution.
