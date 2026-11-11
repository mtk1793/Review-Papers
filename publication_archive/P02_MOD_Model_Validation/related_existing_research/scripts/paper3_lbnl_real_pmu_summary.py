"""Convert and summarize the LBNL PMU Event Library for Paper 3.

The LBNL PMU Event Library is a real distribution-PMU event archive. Its raw
CSV files contain voltage/current phasor magnitudes and angles plus sag/swell
flags. They do not provide matched dynamic simulations or MOD-026/MOD-033
parameter-error labels, so this script uses the archive as a real-PMU ingestion
and morphology check rather than as supervised attribution ground truth.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
FIG_DIR = REPO_ROOT / "figures"
DATA_DIR = REPO_ROOT / "data" / "real_pmu"

SOURCE_URL = "https://github.com/LBNL-ETA/pmu_event_library"
SOURCE_CITATION = (
    "Swenson, T., Vrettos, E., Mueller, J., and Gehbauer, C., "
    "Open PMU Event Dataset: Detection and Characterization at LBNL Campus, "
    "IEEE PES General Meeting, 2019."
)


def _event_type(raw: pd.DataFrame) -> str:
    sag = bool(raw.get("Voltage-Sag [-]", pd.Series(False, index=raw.index)).astype(bool).any())
    swell = bool(raw.get("Voltage-Swell [-]", pd.Series(False, index=raw.index)).astype(bool).any())
    if sag and swell:
        return "voltage_sag_swell"
    if sag:
        return "voltage_sag"
    if swell:
        return "voltage_swell"
    return "pmu_event"


def _load_raw_csv(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path, index_col=0)
    raw.index = pd.to_numeric(raw.index, errors="raise")
    raw = raw.sort_index()
    raw["timestamp_ns"] = raw.index.astype("int64")
    raw["t_sec"] = (raw["timestamp_ns"] - raw["timestamp_ns"].iloc[0]) / 1e9
    return raw.reset_index(drop=True)


def convert_lbnl_event(raw_path: Path) -> pd.DataFrame:
    raw = _load_raw_csv(raw_path)
    event_id = raw_path.parent.name
    bus_id = raw_path.name.replace("_raw_data.csv", "")
    event_type = _event_type(raw)

    voltage_cols = [c for c in ["L1-Mag [Vrms]", "L2-Mag [Vrms]", "L3-Mag [Vrms]"] if c in raw]
    angle_col = "L1-Ang [Deg]" if "L1-Ang [Deg]" in raw else None
    if not voltage_cols or angle_col is None:
        raise ValueError(f"Unsupported LBNL raw CSV format: {raw_path}")

    # The LBNL files are distribution PMU captures where available phase
    # channels differ by PMU. Use the voltage channel with the largest
    # pre-event median and normalize by its own pre-event baseline.
    n_base = min(20, len(raw))
    base_medians = raw.loc[: n_base - 1, voltage_cols].median(axis=0).abs()
    voltage_col = str(base_medians.idxmax())
    baseline_v = float(base_medians[voltage_col]) if float(base_medians[voltage_col]) > 0 else 1.0

    out = pd.DataFrame({
        "event_id": event_id,
        "timestamp": pd.to_datetime(raw["timestamp_ns"], unit="ns", utc=True).astype(str),
        "t_sec": raw["t_sec"],
        "bus_id": bus_id,
        "voltage_pu": raw[voltage_col] / baseline_v,
        "frequency_hz": np.nan,
        "angle_deg": raw[angle_col],
        "event_type": event_type,
        "source_dataset": "LBNL PMU Event Library",
        "source_voltage_channel": voltage_col,
    })
    return out


def collect_lbnl_events(lbnl_root: Path, max_events: int | None = None) -> pd.DataFrame:
    event_root = lbnl_root / "Event_Library"
    if not event_root.exists():
        raise FileNotFoundError(f"Expected Event_Library under {lbnl_root}")

    frames = []
    raw_files = sorted(event_root.glob("*/*/*_raw_data.csv"))
    event_ids_seen: set[str] = set()
    for raw_path in raw_files:
        event_id = raw_path.parent.name
        if max_events is not None and event_id not in event_ids_seen and len(event_ids_seen) >= max_events:
            continue
        try:
            frames.append(convert_lbnl_event(raw_path))
            event_ids_seen.add(event_id)
        except ValueError:
            continue
    if not frames:
        raise RuntimeError(f"No convertible LBNL raw PMU files found under {event_root}")
    return pd.concat(frames, ignore_index=True)


def summarize(df: pd.DataFrame) -> dict:
    event_counts = df.drop_duplicates(["event_id", "bus_id"]).groupby("event_type").size()
    samples = df.groupby(["event_id", "bus_id"]).size()
    return {
        "source_dataset": "LBNL PMU Event Library",
        "source_url": SOURCE_URL,
        "citation": SOURCE_CITATION,
        "n_rows": int(len(df)),
        "n_events": int(df["event_id"].nunique()),
        "n_pmu_event_pairs": int(df.drop_duplicates(["event_id", "bus_id"]).shape[0]),
        "n_buses": int(df["bus_id"].nunique()),
        "event_type_counts": {str(k): int(v) for k, v in event_counts.items()},
        "samples_per_pmu_event_min": int(samples.min()),
        "samples_per_pmu_event_median": float(samples.median()),
        "samples_per_pmu_event_max": int(samples.max()),
        "voltage_pu_min": float(df["voltage_pu"].min()),
        "voltage_pu_mean": float(df["voltage_pu"].mean()),
        "voltage_pu_max": float(df["voltage_pu"].max()),
        "frequency_channel_available": False,
        "mod026_parameter_labels_available": False,
    }


def save_summary_figure(df: pd.DataFrame, savepath: Path) -> None:
    pairs = df.groupby(["event_id", "bus_id"])["voltage_pu"].agg(["min", "max"]).reset_index()
    sag_pair = pairs.sort_values("min").iloc[0]
    event_id = sag_pair["event_id"]
    bus_id = sag_pair["bus_id"]
    ex = df[(df["event_id"] == event_id) & (df["bus_id"] == bus_id)].copy()

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 4.2), dpi=300)
    axes[0].plot(ex["t_sec"], ex["voltage_pu"], color="#1f77b4", lw=2)
    axes[0].axhline(0.95, color="#d62728", ls="--", lw=1.2, label="0.95 pu sag threshold")
    axes[0].set_xlabel("Time from event start (s)")
    axes[0].set_ylabel("Mean phase voltage (pu)")
    axes[0].set_title(f"Real LBNL PMU event: {event_id} / {bus_id}")
    axes[0].grid(alpha=0.3)
    axes[0].legend(fontsize=8)

    axes[1].hist(pairs["min"], bins=20, color="#2ca02c", edgecolor="white", alpha=0.85)
    axes[1].axvline(0.95, color="#d62728", ls="--", lw=1.2)
    axes[1].set_xlabel("Minimum voltage per PMU-event pair (pu)")
    axes[1].set_ylabel("Count")
    axes[1].set_title("Voltage-sag severity distribution")
    axes[1].grid(alpha=0.3)

    fig.tight_layout()
    fig.savefig(savepath, dpi=300, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lbnl_root", type=Path, help="Path to a clone of LBNL-ETA/pmu_event_library")
    parser.add_argument("--max-events", type=int, default=None, help="Optional limit for quick tests")
    parser.add_argument("--sample-rows", type=int, default=240, help="Rows to save in normalized sample CSV")
    args = parser.parse_args()

    FIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    df = collect_lbnl_events(args.lbnl_root, max_events=args.max_events)
    summary = summarize(df)

    summary_path = FIG_DIR / "paper3_lbnl_real_pmu_summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    sample_path = DATA_DIR / "lbnl_sample_normalized.csv"
    df.head(args.sample_rows).to_csv(sample_path, index=False)

    fig_path = FIG_DIR / "paper3_fig5_lbnl_real_pmu_summary.png"
    save_summary_figure(df, fig_path)

    print(json.dumps(summary, indent=2))
    print(f"Wrote {summary_path}")
    print(f"Wrote {sample_path}")
    print(f"Wrote {fig_path}")


if __name__ == "__main__":
    main()
