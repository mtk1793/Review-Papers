**# PG-CARE → IEEE Transactions Upgrade Plan**



**\*\*Manuscript:\*\*** *\*Physics-Guided Conformal Reliability for One-Hour-Ahead Electric-Vehicle Flexibility Forecasting and Risk-Aware V2G Dispatch\**

**\*\*Target:\*\*** IEEE Transactions on Smart Grid (primary) / IEEE Transactions on Transportation Electrification (fallback)

**\*\*Duration estimate:\*\*** 6–8 weeks

**\*\*Acceptance criterion for every phase:\*\*** every claim-evidence pair must survive a hostile reviewer re-running \`reproduce_all.py\` on a clean machine.



**---**



**## PART 1 — BRUTAL CRITIQUE (what must change and why)**



**### A. Integrity problems (rejection-with-prejudice items)**



\| # | Finding | Evidence | Consequence |

\|---|---------|----------|-------------|

\| A1 | **\*\*Future-information leakage in the physics mask.\*\*** The mask uses true connectivity at the target time \`conn[tf]\` (\`tf = ts+H\`) — ground-truth future info not available at forecast time. In the twin, an EV disconnected at t+H is Idle by construction, so the mask hands the classifier the answer for every disconnected EV. | \`code/04_build_pgcare.py:16\`, \`code/02_train_core_models.py:65\`, \`code/05_ood_and_statistics.py:81\` | The headline arc (LightGBM 0.7501 → +physics 0.8424 → PG-CARE 0.8482; V2G F1 +0.2464) is substantially leakage, not physics. Conformal threshold is calibrated on leaked scores, so the 90.12% coverage claim inherits the leak. |

\| A2 | **\*\*The "OOD regime" is not OOD.\*\*** Same generator, shifted constants (arrival 18.2→18.8, σ 1.7→2.0, load bump 1.10–1.35→1.18–1.45). | \`code/05_ood_and_statistics.py:19–31\` | Tests interpolation within one synthetic family. A reviewer will dismiss the generalization claim in one line. |

\| A3 | **\*\*The closed-loop "reserve" product is invented.\*\*** Request = \`0.12·N·mean(charger)\` whenever load > Q75; prices $0.18/$0.55 are scenario assumptions. "Risk-aware dispatch" is a scalar ρ\*=0.10 picked from a 19-point grid. | \`code/02_train_core_models.py:80–82\`, \`code/05_ood_and_statistics.py:103\` | No ISO product (ELRP/FCAS/regulation), no settlement logic. "Dispatch" claim is unsupported. |



**### B. Novelty problems (why TSG/TTE reviewers push back even after A is fixed)**



\| # | Finding | Why it matters |

\|---|---------|----------------|

\| B1 | **\*\*Zero measured data.\*\*** Load = \`N·(Gaussian diurnal)·AR(1)\`, PV = \`sin^1.7\` curve, price = 3-step TOU + noise (\`01_generate_digital_twin.py:26–29\`). | 2025–26 competitors publish with real data: Thrän et al. (TPWRS, real domestic-charger dataset), Aljabri 2026 (TSG, real smart-meter data), Wu 2026 (Applied Energy, integrated forecast-then-optimize). Real data is table stakes now. |

\| B2 | **\*\*The forecast target is your own rule.\*\*** The 3-class label is the twin controller's own deterministic policy output. | ML is trained to predict the output of a rule you wrote — self-fulfilling unless inputs are stochastic and measured. |

\| B3 | **\*\*Methods off-the-shelf, no theory.\*\*** LightGBM/XGBoost/CatBoost + standard split-conformal + rule mask. No proposition that coverage survives mask+renormalization; no conditional coverage by class/hour; no CQR for the flexibility regression — the monetized quantity is a point forecast × scalar. | The "conformal reliability" novelty claim needs a validity argument, not just an empirical marginal coverage number. |

\| B4 | **\*\*TC-MoE is a strawman.\*\*** Two 32-channel conv layers, 12 epochs, 30k samples; macro-F1 0.61 vs LightGBM 0.75. | Reads as "they didn't tune the network," not "trees win." Currently weakens the paper. |

\| B5 | **\*\*25 references.\*\*** TSG/TTE norm is 45–60 with a structured positioning section. Missing: ACN-Data/ACN-Sim line, aggregate-flexibility envelopes (Thrän TPWRS; Taheri/Kekatos TSG; Mukhi et al.), conformal-in-power-systems, probabilistic EV forecasting. | Bibliography is a placeholder, not a related-work section. |

\| B6 | **\*\*No network.\*\*** No bus, no voltage, no transformer — yet the title says "V2G Dispatch." | A scalar energy commitment against a synthetic curve is not dispatch to a grid reviewer. |



**### C. Craft problems**



\- Evaluation on 30k/10k/20k randomly sampled (t, EV) windows, not the contiguous test period; no rolling-origin; no McNemar / Diebold–Mariano (bootstrap only).

\- Static per-EV identity features (policy/min_soc/cap/charger) with N=100 EVs — the model partly memorizes 100 EVs. Unacknowledged; no feature-group ablation.

\- Manuscript is a script-built DOCX with matplotlib PNGs. Transactions expects IEEEtran LaTeX, vector figures.

\- 27 MB zip archived inside the git repo — belongs in a GitHub Release / Zenodo.

\- No calibration metrics (ECE/Brier), no coverage–set-size tradeoffs, no Winkler scores.



**\*\*Verdict:\*\*** well-packaged, honestly-labeled, methodologically-leaky synthetic study. Would be desk-rejected at TSG today. The bones are good — composition idea, value-vs-accuracy result, auditability — and become Transactions-grade once the evidence underneath is fixed.



\---



\## PART 2 — EXECUTION PLAN



\### Phase 0 — Integrity repair (\~3 days) · non-negotiable, first



1\. \*\*Kill the leakage.\*\*

   - Train a connectivity classifier ĉ(t+H) from history (same feature window; binary target \`conn[t+H]\`).

   - Owner-declared schedule becomes an explicit \*\*input feature\*\*, clearly labeled \*declared\* (as real aggregators receive), never ground truth.

   - \`mask()\` v2 uses ĉ + declared schedule + current SOC only. \*\*Code invariant:\*\* no array indexed beyond \`ts\` may enter the mask; enforce with a unit test that fails on any \`tf\`-indexed access.

2\. \*\*Recalibrate conformal threshold on leak-free scores.\*\* Report marginal, per-class, and per-hour conditional coverage.

3\. \*\*Evaluation upgrade.\*\* Full contiguous test period + rolling-origin evaluation; McNemar (classification pairs), Diebold–Mariano (regression pairs), model confidence set.

4\. \*\*TC-MoE v2.\*\* Optuna (\~100 trials), early stopping on validation macro-F1, ≥150 epochs, class-balanced sampling. Report tuning budget for fairness.

5\. \*\*Republish honest numbers.\*\* Expect +physics to drop (\~0.78–0.80 macro-F1 territory is realistic). If the honest delta is too thin to carry a paper, Phase 3's CQR/CVaR layer becomes the headline instead — decide at the gate.



\*\*Gate:\*\* honest numbers + leak-free invariant test green + full-test evaluation committed.



\### Phase 1 — Measured inputs (Ausgrid + CAISO LMP + ACN-Data) (\~1–2 weeks)



Keep the twin as simulation; drive it with measured exogenous inputs.



1\. \*\*Native load + PV:\*\* Ausgrid Solar Home Electricity Data (free, 300 homes, 1 year, 30-min, includes rooftop PV) → measured net load, resampled 30→15 min with documented interpolation. Replaces \`base/pv/native\`.

   - \*Alternative if Ausgrid unavailable:\* UK Power Networks SmartMeter London (5,567 homes, no PV).

2\. \*\*Prices:\*\* CAISO day-ahead LMPs (free, OASIS) → replaces stylized TOU. Match timezone/season to the load year.

3\. \*\*EV mobility:\*\* ACN-Data (Caltech + JPL, free API) → GMM fits of arrival / departure / session-kWh; sample the twin's \`arr/dep/trip\` from measured distributions (methodology of Lee/Li/Low, e-Energy '19 — cite it). Bulk-download early to respect API limits.

4\. \*\*Framing:\*\* "measured feeder load, measured prices, measured session patterns; simulated fleet SOC dynamics." This statement answers the real-data objection head-on and fixes B2 (rule-output labels under measured stochastic inputs).

5\. \*\*Retain the original fully-synthetic run as an ablation appendix\*\* — it retroactively becomes the controlled-experiment arm, legitimizing the original work.



\*\*Gate:\*\* new digital twin runs end-to-end on measured inputs; distributions of load/price/sessions plotted vs synthetic for the paper.



\### Phase 2 — Grid layer (\~4–5 days)



1\. pandapower IEEE 33-bus (or CIGRE EU LV feeder); attach fleet + measured load at buses.

2\. QSTS power flow over the full test period.

3\. Report: EN 50160 voltage-band (±10%) violations, transformer loading, PG-CARE vs raw-XGB vs oracle.

4\. One new figure + one new table. This converts "dispatch" from a scalar promise into a grid statement.



\*\*Gate:\*\* voltage/loading results committed; dispatch claim now grid-backed.



\### Phase 3 — Method hardening (\~1–2 weeks)



1\. \*\*Theory:\*\* proposition + proof sketch — marginal coverage preserved when the mask is a deterministic function of (x, declared inputs) alone; empirical conditional-coverage tables (class, hour, set size).

2\. \*\*CQR for flexibility regression\*\* — quantile-LGBM lower/upper bounds, conformalized on validation; replaces scalar ρ with \*\*CVaR commitment optimization\*\* over the conformal/quantile sets.

3\. \*\*Baselines:\*\* quantile-LGBM + one tuned deep probabilistic model (TFT or DeepAR-lite; MC-dropout acceptable). Report coverage/width/Winkler.

4\. \*\*Feature-group ablation:\*\* identity vs dynamic vs schedule features — answers the EV-memorization question.

5\. Keep 1,000-resample paired bootstrap; add per-window deltas.



\*\*Gate:\*\* honest conformal + CQR numbers committed; novelty claim now theory-backed.



\### Phase 4 — Market reality (\~3–4 days)



1\. Define the reserve product (CAISO ELRP-style or symmetric reserve); pull actual settlement structure.

2\. Redo closed-loop study against the defined product: revenue, penalties, delivered/shortfall energy.

3\. Sensitivity over revenue/penalty ratio and throughput (degradation) cost; state break-even explicitly.



\*\*Gate:\*\* economics table references a real product definition.



\### Phase 5 — Manuscript & packaging (\~1 week)



1\. IEEEtran LaTeX; vector figures (PDF); TSG-style tables.

2\. 45–60 references including: ACN-Data/ACN-Sim; Thrän et al. TPWRS; Taheri/Kekatos TSG 2022; Mukhi et al. 2025; Aljabri TSG 2026; Wu 2026 Applied Energy; conformal-in-power-systems line.

3\. Claims rewritten to match honest evidence: "measured load/prices/sessions; simulated fleet dynamics; no switching-level equivalence; no field trial."

4\. Data availability statement + GitHub repo + \*\*Zenodo DOI\*\*.

5\. \*\*Remove the 27 MB zip from the git repo\*\* → GitHub Release / Zenodo archive.



\*\*Gate:\*\* manuscript compiles in IEEEtran; claim↔evidence table regenerated from \`RESULTS_TRACEABILITY.md\`.



\### Phase 6 — Verify & submit (\~2–3 days)



1\. Clean-machine \`reproduce_all.py\` end-to-end; byte-comparable results; CI running the leak-free invariant test.

2\. Final internal review against this critique list — every A/B/C item must have a resolution or an explicit limitation statement.

3\. Submit to TSG. Fallback TTE.



\---



\## Risk register



\| Risk | Likelihood | Mitigation |

\|------|-----------|------------|

\| Honest post-fix deltas shrink too much | Medium | Phase 3 CQR/CVaR + real-data results carry the novelty; classification delta becomes one of several results |

\| ACN-Data API rate limits | Medium | Bulk-download sessions on day 1; cache as CSV |

\| Ausgrid data vintage (2012–13) | Certain | State it plainly — measured vintage ≠ synthetic; add London SmartMeter as second load source if reviewers push |

\| Coverage guarantee degrades under mask in practice | Medium | Report conditional coverage honestly; if class-conditional coverage fails, that itself is a publishable finding with the fix |

\| Timeline slip from tuning | Medium | TC-MoE tuning is parallelizable; hard-cap Optuna at 2 days |



\## Cost: $0 — all datasets (Ausgrid, CAISO OASIS, ACN-Data) are free.
