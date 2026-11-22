# Point-by-point response to referee — evidence-bounded draft

**Important:** These replies describe work done in THIS recovery package. They are not claims that the final empirical study, accepted-paper revision or original-code reproduction has been completed. Current status: must not resubmit.

**Reviewer 1 — model is not three-agent MARL.**
Agree. The LSTM has no RL transition, reward or policy, and sequential training cannot be characterized as jointly trained MARL. We have retitled the method a forecast-informed *hierarchical hybrid RL* framework, separated supervised and RL roles, and formalized the staged QR-DQN/SAC optimization. A true Markov-game MARL extension would require additional algorithms and is not claimed. STATUS: conceptual correction completed; experiments pending.

**Reviewer 2 — overlong, undersourced introduction.**
Agree. Reconstructed a concise problem statement centered on controllability and qualified economic value. Unsupported references to specific cold-snap expenses, unique project figures, claimed Nova Scotia market prices and exact industrial impacts were removed. Publisher-supported electrolysis, wind data and RL references are cited contextually. STATUS: rewritten.

**Reviewer 3 — end-of-paragraph citation stacking.**
Agree. Citation placement rewritten adjacent to the supported technical claim, with distinct work cited when introducing model choices. Source-to-claim mapping remains subject to final bibliography verification. STATUS: substantially addressed in draft.

**Reviewer 4 — probabilistic forecast calibration/statistical significance.**
We implemented quantile regression LSTM with pinball loss and split-conformal residual widening, 2019 calibration and untouched 2020 holdout structure, coverage/width/Winkler scores and temporal bootstrap. No observed forecast scores are yet reported because source time-series files are not available in the execution container. STATUS: algorithm implemented/tested; **OPEN** empirical calibration and significance.

**Reviewer 5 — contradictory lifetime outcomes.**
We distinguish nominal design hours, calculated cumulative equivalent-stress hours and discounted replacement consequences. Numerically, (19,100–17,500)/17,500 is **9.14%**, not 8.1%; the 72,800/60,000 comparison is **21.33%**, but from another incompatible lifetime definition. Both effect-size claims are withdrawn pending a single calibrated rerun. STATUS: factual discrepancy corrected; **OPEN** life validation.

**Reviewer 6 — Table 2 not cited.**
Table II is introduced before the model assumptions; all primary table headings are now cited in nearby prose and positioned with explicit units. STATUS: addressed in draft.

**Reviewer 7 — Table 3 shows 78.2%, section I.b 30.6%.**
The version provided contains no substantive Table 3. Using 1,126 GWh as total curtailment denominator, 78.2% would require approximately 880.5 GWh absorbed by a 50 MW electrolyzer, exceeding its absolute 438 GWh/year electrical input capacity. We therefore remove 78.2% and define denominators explicitly. The quantity 340/1,126=30.2% is arithmetic, but not experimentally validated. STATUS: inconsistency diagnosed; **OPEN** actual submitted version and data.

**Reviewer 8 — all inconsistencies and final one set of results.**
The code now generates metrics from one run and exports structured output; unsupported abstract and conclusion performance numbers are removed. No complete 2020 empirical result has been substituted. STATUS: source claims audited; **OPEN** one final empirical evidence table.

**Reviewer 9 — mean ±95% CI missing from tables/figures.**
Implemented paired circular-block bootstrap and multi-seed aggregation with the intent to report mean, CI and effect direction. Synthetic smoke results are marked non-publishable. STATUS: statistics code tested; **OPEN** empirical tables and charts with real CIs.

**Reviewer 10 — erroneous [29] citation.**
The uploaded Word version lists a carbon-taxation article at [29], whereas this reviewer describes a Pd–Ag/ethanol electrooxidation citation at [29]. These cannot both refer to the same bibliography. The reconstructed manuscript does not cite either as evidence for PEM thermal-threshold degradation. STATUS: bad support removed; **OPEN** exact rejected source version.

**Reviewer 11 — duplicate references.**
The uploaded bibliography repeats Rakousky (2016) at [4]/[26] and Scheepers (2020) at [5]/[21]; entries [1]/[28] are not identical in the uploaded version, creating another reviewer-version discrepancy. The reconstructed reference list uses one record per unique paper and publisher metadata where verified. STATUS: addressed in reconstructed draft; **OPEN** reconciliation with actual submitted version.

**Reviewer 12 — proofreading and report-like prose.**
Rewrote sections into coherent journal-style paragraphs; removed overextended bullet enumerations and rhetorical claims, normalized definitions, and used one contribution narrative. STATUS: editorial draft completed; final copyedit after results pending.

## Before responding officially

Replace every OPEN status with links/figure-table numbers from **actual executed, authentic-data outputs**. Reconcile source-version discrepancies and include the exact target journal's author kit. Do not send this preliminary response to the editor as though the empirical tasks were complete.
