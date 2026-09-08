# Thesis Tables

This directory contains CSV source data for all tables in the CAPSM thesis.

## Table List
| Table | Caption | Source Data | Status |
|-------|---------|-------------|--------|
| Table 1.1 | Power system challenges | manual | TODO |
| Table 1.2 | AI vs conventional control comparison | manual | TODO |
| Table 3.1 | Ancillary services of CAPSM | caps.py output | TODO |
| Table 4.1 | System design requirements | caps.py output | TODO |
| Table 10.1 | SIL violations 6×6 | run_all_experiments.py | TODO |
| Table 10.2 | SIL losses and inference | run_all_experiments.py | TODO |
| Table 11.1 | Full results matrix | run_all_experiments.py | TODO |
| ... | ... | ... | TODO |

## Key Existing Data (can be reused directly)
- `figures/paper1_results.csv` → Table 11.1 source
- `figures/paper2_summary.csv` → Table 11.1 source
- `figures/paper3_summary.json` → Table 7.2 source
- `figures/paper10_summary.json` → Table 7.1 source

## Generating All Tables
```bash
cd ../capsim_sim
python scripts/run_all_experiments.py
# Outputs CSV files to ../thesis_writing/tables/
```
