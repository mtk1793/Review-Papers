# Publication archive alignment — 2026-11-10

This folder is a **cross-reference and import scaffold**, not a completed upload of the local 101 MB archive. GitHub connector operations in this session cannot ingest the local binary Word/PDF/image bytes, so the actual manuscripts and source files still need binary transfer. The canonical local archive has 16 paper folders and 289 files. Do not label this repository synchronization as complete until the content checklist is verified.

Existing **13-paper program** remains at `papers/`, including Papers 1–10 CAPSM/NERC, Paper 11 System-1 survey, Paper 12 CNN–LSTM fault detection, and Paper 13 PG-CARE. Those numbers must not be confused with the 16 archival identifiers `P01`–`P16` here.

## Separate tracks

- **Standards-to-performance:** P01 → P02 and existing NERC papers. Formal NERC/PRC compliance is not experimental model validation.
- **ML validation:** P03 underpins P02; existing CNN–LSTM paper and executable code remain separate until verified.
- **EV:** P10 controller → P04 prediction → earlier PG-CARE paper13 flexibility; preserve target definitions, datasets, methods and publication provenance.
- **FACTS/power quality:** P05, P06, P07, P13 are related but address different physical outputs and benchmarks.
- **Renewables/storage:** P08, P09, P11, P14, P15, P16 form a related literature/experimental theme, not one shared validated dataset.
- **New load centers:** P12 connects planning, storage and reliability but has no equivalent earlier paper.

| Archive ID | Topic | Source status | Existing-repo relationship |
|---|---|---|---|
| [P01_PRC_Canada](P01_PRC_Canada/README.md) | Canadian PRC reliability standards review | Source-based editorial revision | Existing PRC-029 ride-through, PRC-006 UFLS, PRC-023 relay screening, and associated compliance papers |
| [P02_MOD_Model_Validation](P02_MOD_Model_Validation/README.md) | CNN-LSTM validation under MOD-026 and MOD-033 | New proposed methodology; no new validation | papers/CNNLSTM_ModelValidation_MOD026_AcademicPaper_2026-09-08.docx; root Paper 3 code and figures |
| [P03_CNNLSTM_Generic_Validation](P03_CNNLSTM_Generic_Validation/README.md) | Leakage-aware CNN-LSTM validation protocol | Source-based editorial revision; reported results not reproduced | papers/V-CNNLSTM-RC_ValidationFramework_AcademicPaper_2026-09-09.docx |
| [P04_EV_SoC_Hybrid](P04_EV_SoC_Hybrid/README.md) | One-hour-ahead EV state prediction | Source-based editorial revision | papers/paper13_pgcare_ev_flexibility/; papers/paper13_pgcare_ev_flexibility/source_artifacts/ |
| [P05_SVC_CatBoost_LightGBM](P05_SVC_CatBoost_LightGBM/README.md) | CatBoost-LightGBM SVC firing-angle estimation | Source-based editorial revision | papers/FACTS_Placement_HostingCapacity_AcademicPaper_2026-09-08.docx |
| [P06_THD_GA_FeatureSelection](P06_THD_GA_FeatureSelection/README.md) | GA feature selection for harmonic-distortion forecasting | Source-based editorial revision | CAPSM feature selection methods; no direct matching repository paper |
| [P07_THD_PINN_LSTM](P07_THD_PINN_LSTM/README.md) | Physics-informed LSTM for THD forecasting | Source-based editorial revision | papers/Relay_Loadability_PINN_PRC023_AcademicPaper_2026-09-08.docx (PINN techniques only) |
| [P08_Solar_Forecasting](P08_Solar_Forecasting/README.md) | Solar generation forecasting robustness | Source-based editorial revision | No direct match in earlier 13-paper program |
| [P09_Wind_Forecasting](P09_Wind_Forecasting/README.md) | Wind forecasting with solar covariates | Reconstructed editable article from archived PDF | No direct match in earlier 13-paper program |
| [P10_EV_Fleet_Control](P10_EV_Fleet_Control/README.md) | EV fleet V2G/G2V real-time control | Source-based editorial revision | papers/paper13_pgcare_ev_flexibility/source_artifacts/ |
| [P11_SmartGrid_Review](P11_SmartGrid_Review/README.md) | Smart grid, renewable energy, storage and ML review | Source-based editorial revision | papers/paper11_literature_review/ (different subject) |
| [P12_AI_DataCenters](P12_AI_DataCenters/README.md) | AI data center energy infrastructure review | Source-based editorial revision | CAPSM planning and storage context, but no direct matching paper |
| [P13_FACTS_ML_Framework](P13_FACTS_ML_Framework/README.md) | Intelligent FACTS control framework | Source-based editorial revision | papers/FACTS_Placement_HostingCapacity_AcademicPaper_2026-09-08.docx |
| [P14_Hydrogen_MARL](P14_Hydrogen_MARL/README.md) | Hydrogen-wind-battery multi-agent coordination | New research protocol; no new experiments | CAPSM metacognitive RL and coordinated scheduling studies |
| [P15_Storage_Planning_Review](P15_Storage_Planning_Review/README.md) | BESS, pumped hydro, EV and hydrogen planning review | New review protocol; no completed systematic review | P10 EV fleet, P14 hydrogen, and P11 smart grid context |
| [P16_Solar_Hydrogen_EV](P16_Solar_Hydrogen_EV/README.md) | Solar-hydrogen EV-charging concept | Source-based editorial revision | P10 EV fleet control; P14 hydrogen; P15 storage review |

## Integrity gates

1. Manuscripts are revised editorial drafts, not automatically submission-ready papers.
2. No new PSS/E/PSCAD/MATLAB/PyTorch experiments were performed when creating the ZIP package.
3. All inherited numerical claims remain **source-reported** until independently reproduced.
4. DOI-only BibTeX anchors in that package are **not verified full references**.
5. P02, P14 and P15 were newly drafted **methods/review protocols** because complete originals were inaccessible.
6. P09 was reconstructed from an existing PDF. Avoid representing it as an unpublished original.
7. Source files may have rights or co-author restrictions; this repository is **public**. Confirm permissions before exposing original drafts or privately held results.

## Intended final structure

Each `Pxx_*/` folder should ultimately have `manuscript/Manuscript_Revised.{docx,pdf,md}`, `sources/Source_Original.*` where available, `figures/`, `references/references_to_verify.bib`, `audit/` (notes/checklists), and `README.md`. Use `scripts/import_publications.py` for local import after downloading the 101 MB ZIP. Existing repository files remain untouched.
