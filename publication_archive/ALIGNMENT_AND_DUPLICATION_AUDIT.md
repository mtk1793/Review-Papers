# Cross-paper reconciliation audit

Date: 2026-11-10. Comparison based on the repository's current 13-paper README, existing paths, and the separate 16-paper revision archive.

## High-priority overlaps and non-equivalences

| Paper relation | Aligned scientific question | Important difference | Decision |
|---|---|---|---|
| P01 PRC ↔ repo Papers 1, 4, 10 | Protection reliability and evidence | Regulatory review vs numerical test cases | Cross-cite; don't reuse plot or outcomes as review evidence without attribution |
| P02 MOD ↔ repo Paper 3 | Dynamic model validation | Conceptual leakage-aware draft vs prior model-validation experiment | Treat prior code/data as validation candidate; verify MOD standards and measured event data |
| P03 CNN-LSTM validation ↔ V-CNNLSTM-RC existing DOCX | Calibration, uncertainty and leakage | Existing abstract includes unreplicated metrics | Reproduce before accepting summary figures |
| P04 EV SoC hybrid ↔ repo Paper 13 PG-CARE | One-hour EV forecasts | SoC/mode/state target and PG-CARE flexibility targets differ | Explicitly separate classification, SoC regression, connectivity, flexibility and control |
| P10 EV V2G controller ↔ repo Paper 13 | Grid-facing EV management | MATLAB controller antecedent vs Python PG-CARE reconstruction | Cite antecedent; do not imply switching-level hardware equivalence |
| P05 SVC ↔ P13 FACTS ↔ repo Paper 6 | FACTS performance | SVC firing angle, adaptive control and hosting capacity are three distinct claims | Distinct baselines and closed-loop stability evidence |
| P06 GA THD ↔ P07 PINN THD | Same underlying harmonic domain | Feature selection vs physics-guided sequence prediction | Check potential shared dataset, no duplicate primary results |
| P08 solar ↔ P09 wind | Weather-driven forecasting | Distinct targets, time windows, geography and source provenance | Avoid transfer of reported metric without new evaluation |
| P11 smart grid ↔ repo Paper 11 | Literature reviews | Smart-grid review vs CNN-LSTM fault-detection survey | **Different manuscripts; duplicate numbering only** |
| P14 hydrogen ↔ P15 storage ↔ P16 hybrid EV | Storage integration | Proposed multi-agent experiments vs review vs conceptual charging proposal | Prevent conceptual figures from appearing as empirical outcomes |

## Required reconciliation before submissions

1. Define exact targets, units, horizons and dataset IDs in every paper.
2. Record data split dates; separate training, validation and test in time-dependent papers.
3. Use one evidence register linking each quantitative statement to code, data, figure or published source.
4. Version-lock NERC standard text and Canadian jurisdiction interpretation at the manuscript cutoff date.
5. Verify DOI, author, year, journal and in-text citation numbering; imported BibTeX is not final metadata.
6. Review already published papers for duplicate-publication constraints and preserve coauthor/rights approvals.
7. Distinguish runnable numerical simulations from proposed methods; never fill missing results by analogy.
8. Keep the repository's existing original 13-paper research outputs unchanged until the corresponding author approves a validated replacement.

**Result:** topic map is reconciled; mathematical claims, experiments and bibliography are **not** fully harmonized or independently verified.
