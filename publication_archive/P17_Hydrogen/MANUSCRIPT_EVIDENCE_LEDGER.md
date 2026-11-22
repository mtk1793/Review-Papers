# Source claim audit — do not transfer old metrics without reproduction

Based strictly on the uploaded `Hydrogen paper.docx` (10 pages) and `Comments.txt`, plus arithmetic independent of an empirical dataset.

| Claim / issue | Rejected paper and reviewer | Audit determination | Action |
|---|---|---|---|
| Three MA-RL agents | LSTM + SAC + QR-DQN | LSTM is supervised, not RL; only two RL modules | Title and architecture changed to hierarchical hybrid |
| NREL wind 2020–2022 | Three-year 2020–2022 source asserted | Old WIND Toolkit Canada 2007–2014, NOW-23 NA 2000–2020 | 2020 available in principle, 2021–2022 invalid for claimed source |
| Electrolyzer life | 17,500 to 19,100 and 8.1%; conclusion 60,000 to 72,800 and 21.3% | 17,500→19,100 is +9.14%; 60,000→72,800 is +21.33%, different runs | Remove from abstract until re-executed; separate distinct lifetime metrics |
| 78.2% and 30.6% curtailment capture | Reviewer Table 3 78.2%; supplied Word main text 30.6% | Of 1,126 GWh, 78.2% is 880.5 GWh >438 GWh input upper bound | Disallow without a new, explicitly defined denominator |
| Wind 1,126 GWh and 340 GWh utilization | Word pp.6,8 | 340/1,126≈30.2%, physically possible as *electrical input* at 50 MW but not proof of actual curtailment | Need measured/validated model and plant offtake capacity |
| 800 kg/day offtake and 340 GWh/year conversion | Word pp.4,7 | 340 GWh /52 kWh/kg≈6.54 million kg/year; sales at 800/day =292,000 kg/year. Implied demand gap ~22.4x | Resolve market scope, storage, exports; accounting cannot count unsold as revenue |
| 20 MWh BESS supports 36h at 40% electrolyzer output | Word p.7 | 0.4×50MW×36h=720 MWh before losses; 20 MWh sustains 20MW for 1h | Rewrite operational case; prohibit invalid BESS autonomy |
| $9 for 100 kg H2 per hour at $180/MWh | Word p.4 | At 52 kWh/kg, cost is $936/100 kg, excluding other OPEX | Fix energy unit and money arithmetic |
| Different net-present values | $34.7M, $96.1M, $100.5M appear | Different assumptions/scenarios not consistently identified or reproducible | Withdraw numerical NPV claims pending benchmark with complete CAPEX/OPEX |
| 95% CI claimed but absent | reviewer comment 9 | No numerical CI entries in supplied paper's comparative figures | Must run multi-seed and paired block-bootstrap |
| Reviewer ref [29] mismatches supplied ref [29] | Reviewer calls [29] Pd–Ag ethanol catalyst; Word ref [29] carbon taxation paper | Source-version conflict; cannot reconcile by guessing | Obtain actual reviewed file; rebuild source mapping |
| Duplicates | [4]/[26] Rakousky, [5]/[21] Scheepers identical in supplied file | Confirmed duplicate bibliography entries | New bibliography deduplicated, DOI verified against publisher |
| Table 3 absent in uploaded manuscript | Reviewer discusses Table 3, DOCX has Tables 1 and 2 only | Source/review mismatch | Freeze actual submitted version before final response |

## Evidence classes

- **PROVEN:** conservation and annual capacity bounds given parameters, deterministic arithmetic, code unit tests.
- **ASSUMED:** site location, nominal 700 MW plant, electrolyzer efficiency, prices, export limit, battery/tank, economic horizon, ageing coefficients.
- **NOT EXECUTED:** sourced 2020 experiment, 5-seed hierarchy training on real data, statistical empirical superiority, 15-year bankable NPV, validated stack-life improvement, wall-clock 800ms on commodity hardware.

An evidence ledger should be part of each submission revision; section headings/claims must cite proof files under `results/`.
