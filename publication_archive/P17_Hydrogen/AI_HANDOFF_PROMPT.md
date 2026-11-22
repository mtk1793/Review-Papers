# Instructions to an independent research-validation AI

You are responsible for turning the attached research recovery repository into a scientifically verifiable IEEE Transactions on Sustainable Energy paper, not for making it sound more certain. Read `sources/Comments.txt`, `sources/Hydrogen paper.docx`, `GOD_PLAN.md`, `MANUSCRIPT_EVIDENCE_LEDGER.md`, and `VALIDATION_REPORT.md` before editing anything.

Never state or fabricate new experimental performance without the matching real dataset, verified calibration, executable code, frozen configuration, baseline training checkpoints, 5+ seeds, and statistical evidence. Do not copy synthetic smoke-test metrics into paper tables. Do not invent missing author identities or study data.

Execute these sequentially:

1. **Source audit:** Match the actual journal-submitted original document to the current DOCX and review comments. Record table 3/quote/reference numbering differences. Capture source SHA256 and license.
2. **Geographical authenticity:** Obtain NLR NOW-23 if it actually covers 45.38N, -61.50W; reject distant nearest stations. If not, obtain original regional NZA data or use explicitly named hourly ERA5 as an alternative, never conflate datasets.
3. **Real market / H2 buyer provenance:** Get historical tariff or transactable power market contract with site-level boundary; prevent H2 production surplus from being counted as sold revenue when the inventory and 800 kg/day demand are saturated.
4. **Wear coefficients:** Determine whether literature/manufacturer parameters can be calibrated; otherwise report cost/ageing sensitivity only. Separate physical stack health prediction from economic wear surcharge.
5. **Reproduce** `PYTHONPATH=src pytest -q tests` and rerun on an untouched chronological 2020 holdout; freeze train 2017–2018 / calibration 2019 and all hyperparameters prior to 2020.
6. **Improve modelling:** Add matching MILP/MPC benchmark with min-load/start logic, multi-horizon probabilistic forecaster baselines, full error-to-control propagation, operational demand/cost realism, dynamic price scenarios and grid feasibility, document no physical AC/PSS/E validation unless executed.
7. **Statistical results:** Run ≥5 independently trained seeds for all learned variants, paired heldout weather/price episodes, 80/90% forecast calibration diagnostics, 95% temporally blocked CIs and economic sensitivities. No cherry-picked seed or omitted negative outcomes.
8. **Manuscript:** Derive every result claim from validated output artifacts, regenerate full-resolution vector figures and tables with uncertainty. Maintain hierarchical hybrid formulation; do not call LSTM an RL agent. Expand results and comparison sections to the accepted journal's author instructions, and state limitations without boilerplate reporting of package names.
9. **Closure:** For each of 12 reviewer points, cite exact new figure/table, section, experiment SHA, and pass/fail. Produce a reviewer-response Word document and submission checklist. Run manuscript consistency assertions automatically.

**Current package cannot be called submission-ready or fully empirical.** Priority is evidence closure, not formatting. Generate a sealed final result manifest containing original source hash, data hashes, git commit, config, random seeds, hardware, execution times, exact dependencies and outputs.
