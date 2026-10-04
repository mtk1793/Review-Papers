# PG-CARE v2 — Delivery QA Report

- Final editable Word manuscript: generated from the v2 results and visually inspected page-by-page after rendering; 6 pages, no observed clipping/overlap.
- Final IEEEtran PDF: compiled and rendered to page images; all 6 pages visually inspected, including figures/tables/references.
- Python syntax: all current v2 scripts, external-data adapters and `reproduce_v2.py` pass `py_compile`.
- Information-integrity invariant: re-run in the clean final package; **PASS**.
- Statistical verification stage: re-run from the final package; macro-F1 paired block-bootstrap delta = +0.019630, 95% CI [0.017056, 0.022081].
- Reference database: 40 records, all dated 2020–2026.
- External measured-data validation: **not claimed as executed**; acquisition adapters/protocol are included for the next phase.
- Legacy v1: retained under `legacy_v1/` and explicitly marked superseded because of the discovered future-connectivity leakage.
