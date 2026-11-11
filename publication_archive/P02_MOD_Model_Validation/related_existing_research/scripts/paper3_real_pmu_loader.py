"""Validate and normalize real PMU CSV inputs for Paper 3.

This script provides the field-data ingestion contract for the Paper 3
MOD-026-2/MOD-033 validation pipeline. It intentionally does not fabricate
ground-truth labels; if label columns are absent, the file can still be used
for unsupervised novelty scoring but not for supervised attribution metrics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "event_id",
    "timestamp",
    "t_sec",
    "bus_id",
    "voltage_pu",
    "frequency_hz",
    "angle_deg",
}

OPTIONAL_COLUMNS = {
    "event_type",
    "sim_voltage_pu",
    "sim_frequency_hz",
    "sim_angle_deg",
    "label",
    "parameter_error",
}


def load_real_pmu_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS.difference(df.columns))
    if missing:
        raise ValueError(f"Missing required PMU columns: {', '.join(missing)}")

    df = df.copy()
    df["event_id"] = df["event_id"].astype(str)
    df["bus_id"] = df["bus_id"].astype(str)
    for col in ["t_sec", "voltage_pu", "frequency_hz", "angle_deg"]:
        df[col] = pd.to_numeric(df[col], errors="raise")
    if "label" in df.columns:
        df["label"] = pd.to_numeric(df["label"], errors="raise").astype(int)

    return df.sort_values(["event_id", "bus_id", "t_sec"]).reset_index(drop=True)


def summarize(df: pd.DataFrame) -> dict:
    has_simulation = {"sim_voltage_pu", "sim_frequency_hz", "sim_angle_deg"}.issubset(df.columns)
    has_labels = "label" in df.columns or "parameter_error" in df.columns
    sample_counts = df.groupby("event_id").size()
    return {
        "n_rows": int(len(df)),
        "n_events": int(df["event_id"].nunique()),
        "n_buses": int(df["bus_id"].nunique()),
        "samples_per_event_min": int(sample_counts.min()) if len(sample_counts) else 0,
        "samples_per_event_max": int(sample_counts.max()) if len(sample_counts) else 0,
        "has_matched_simulation_columns": bool(has_simulation),
        "has_attribution_labels": bool(has_labels),
        "optional_columns_present": sorted(OPTIONAL_COLUMNS.intersection(df.columns)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="PMU event CSV to validate")
    parser.add_argument("--out", type=Path, help="Optional normalized CSV output path")
    args = parser.parse_args()

    df = load_real_pmu_csv(args.csv)
    summary = summarize(df)
    print(json.dumps(summary, indent=2))

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(args.out, index=False)
        print(f"Wrote normalized PMU CSV: {args.out}")


if __name__ == "__main__":
    main()
