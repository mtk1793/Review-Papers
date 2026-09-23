# Real PMU Input Schema for Paper 3

Paper 3 uses a synthetic PMU benchmark because public disturbance archives rarely include all three items needed for supervised MOD-026-2/MOD-033 attribution: synchronized PMU traces, the matched dynamic simulation trace, and verified parameter-error labels. This directory defines the drop-in CSV contract for replacing the synthetic generator with recorded PMU events when those metadata are available from openPDC, openHistorian, utility archives, or lab PMU streams.

The repository also includes a converter for the real LBNL PMU Event Library. That archive provides real distribution-PMU voltage/current phasor events and sag/swell morphology, but it does not provide MOD-026 generator/exciter parameter-error labels. Therefore it is used for real-data ingestion and morphology validation, not supervised H/D/K_A attribution.

## Required CSV Columns

Each row is one time sample for one event and one PMU channel set.

| Column | Type | Description |
|---|---:|---|
| `event_id` | string | Stable identifier for a disturbance record. |
| `timestamp` | ISO-8601 string or float | PMU timestamp. Float values are seconds from event start. |
| `t_sec` | float | Seconds from event inception. |
| `bus_id` | string | PMU bus or terminal identifier. |
| `voltage_pu` | float | Voltage magnitude in per unit. |
| `frequency_hz` | float | Frequency in Hz. |
| `angle_deg` | float | Voltage angle in electrical degrees. |

## Optional Label Columns

These columns enable direct use in the attribution benchmark.

| Column | Type | Description |
|---|---:|---|
| `event_type` | string | Disturbance class, for example `line_trip`, `generator_trip`, or `three_phase_fault`. |
| `sim_voltage_pu` | float | Matched simulation voltage for residual-based validation. |
| `sim_frequency_hz` | float | Matched simulation frequency. |
| `sim_angle_deg` | float | Matched simulation angle. |
| `label` | int | `0=correct`, `1=H error`, `2=D error`, `3=K_A error`. |
| `parameter_error` | string | Human-readable label such as `correct`, `H+20%`, or `K_A-30%`. |
| `source_dataset` | string | Source archive name, for example `LBNL PMU Event Library`. |
| `source_voltage_channel` | string | Original voltage channel used by a converter, when applicable. |

## LBNL PMU Event Library

Clone the external archive outside this repository:

```bash
git clone https://github.com/LBNL-ETA/pmu_event_library.git /tmp/pmu_event_library
```

Then run:

```bash
python scripts/paper3_lbnl_real_pmu_summary.py /tmp/pmu_event_library
```

This writes:

- `figures/paper3_lbnl_real_pmu_summary.json`
- `figures/paper3_fig5_lbnl_real_pmu_summary.png`
- `data/real_pmu/lbnl_sample_normalized.csv`

The raw LBNL archive is not vendored here. Cite: Swenson, Vrettos, Mueller, and Gehbauer, "Open PMU Event Dataset: Detection and Characterization at LBNL Campus," IEEE PES General Meeting, 2019.

## Validation

Run the included synthetic schema example:

```bash
python scripts/paper3_real_pmu_loader.py data/real_pmu/example.csv
```

The loader validates required columns, sorts samples by event and time, reports event/sample counts, and writes an optional normalized CSV when `--out` is supplied. The included `example.csv` is synthetic and exists only to document the schema. No field PMU data are committed because the repository does not currently contain a redistributable PMU disturbance archive with ground-truth parameter labels.
