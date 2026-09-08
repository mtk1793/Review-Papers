# Thesis Figures

This directory contains master copies of all figures generated for the CAPSM thesis.

## Generating Figures
```bash
cd ../capsim_sim
python scripts/generate_thesis_artifacts.py --output_dir ../thesis_writing/figures/
```

## Figure List
| Figure | Caption | Source Script | Status |
|--------|---------|---------------|--------|
| Fig 1.1 | Global renewable capacity growth | generate_thesis_artifacts.py | TODO |
| Fig 1.2 | Traditional vs modern control challenges | generate_thesis_artifacts.py | TODO |
| Fig 1.3 | Research gap flowchart | manual | TODO |
| Fig 1.4 | CAPSM framework overview | draw_architecture.py | TODO |
| Fig 1.5 | Three-stage validation pipeline | draw_pipeline.py | TODO |
| ... | (all thesis figures) | ... | TODO |

## Naming Convention
- Source: `paper{N}_fig{M}_{description}.png` (from `figures/` repo root)
- Thesis: `fig{N}_{chapter}_{description}.png`

## Key Existing Figures (can be reused directly)
- `figures/paper1_fig1_envelopes.png` → Fig 10.3 (SIL results)
- `figures/paper2_fig2_pareto.png` → Fig 11.2 (Pareto comparison)
- `figures/paper3_fig3_confusion_matrix.png` → Fig 7.4 (fault classification)
- `figures/paper5_fig1_roc_voltage_fdi.png` → Fig 7.2 (FDI detection)
