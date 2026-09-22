# Real PMU Input Schema for Paper 3

Paper 3 uses a synthetic PMU benchmark because public disturbance archives rarely include all three items needed for supervised MOD-026-2/MOD-033 attribution: synchronized PMU traces, the matched dynamic simulation trace, and verified parameter-error labels. This directory defines the drop-in CSV contract for replacing the synthetic generator with recorded PMU events when those metadata are available from openPDC, openHistorian, utility archives, or lab PMU streams.

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

## Validation

Run the included synthetic schema example:

```bash
python scripts/paper3_real_pmu_loader.py data/real_pmu/example.csv
```

The loader validates required columns, sorts samples by event and time, reports event/sample counts, and writes an optional normalized CSV when `--out` is supplied. The included `example.csv` is synthetic and exists only to document the schema. No field PMU data are committed because the repository does not currently contain a redistributable PMU disturbance archive with ground-truth parameter labels.
