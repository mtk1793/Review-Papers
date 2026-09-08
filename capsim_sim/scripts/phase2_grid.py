"""Phase 2 verification: QSTS environment on real data, all test systems.

Runs uncontrolled QSTS trajectories driven by real OPSD profiles and one
contingency case, saving metric time series and figures.
"""

import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from capsm.data.opsd import load_opsd
from capsm.grid.environment import QSTSEnvironment
from capsm.plotting import save_figure, set_style

RESULTS = Path(__file__).resolve().parents[1] / "results" / "phase2"


def run_case(case_name: str, start: str, end: str, label: str) -> pd.DataFrame:
    profiles = load_opsd(start=start, end=end)
    t0 = time.time()
    env = QSTSEnvironment(case_name, profiles)
    df = env.run()
    dt = time.time() - t0
    n = len(df)
    print(f"[phase2] {label}: {case_name} {n} steps in {dt:.1f}s "
          f"({1000 * dt / n:.1f} ms/step), converged {int(df['converged'].sum())}/{n}")
    return df


def main():
    set_style()
    RESULTS.mkdir(parents=True, exist_ok=True)
    summary = {}

    df39 = run_case("case39", "2019-01-01", "2019-01-31", "jan19-month")
    df39.to_csv(RESULTS / "qsts_case39_jan2019.csv")
    summary["case39_jan2019"] = {
        "n_steps": int(len(df39)),
        "converged": int(df39["converged"].sum()),
        "mean_losses_mw": float(df39["losses_mw"].mean()),
        "max_losses_mw": float(df39["losses_mw"].max()),
        "min_vm": float(df39["vm_min"].min()),
        "max_vm": float(df39["vm_max"].max()),
        "mean_voltage_dev_pu": float(df39["voltage_deviation_pu"].mean()),
        "max_line_loading": float(df39["max_line_loading"].max()),
        "voltage_violation_hours": int(df39["n_voltage_violations"].sum()),
        "overload_hours": int(df39["n_overloaded_lines"].sum()),
        "load_min_mw": float(df39["total_load_mw"].min()),
        "load_max_mw": float(df39["total_load_mw"].max()),
    }

    profiles = load_opsd(start="2019-01-01", end="2019-01-31")
    env = QSTSEnvironment("case39", profiles)
    trip_at = "2019-01-15 12:00"
    rows = []
    obs = env.reset(start="2019-01-14")
    rows.append({**obs["metrics"], "timestamp": obs["timestamp"]})
    while True:
        if str(env.timestamps[env.t].date()) == "2019-01-15" and env.timestamps[env.t].hour == 12:
            env.trip_line(16, 17)
            print("[phase2] contingency injected: line 16-17 trip at", env.timestamps[env.t])
        obs = env.step(None)
        rows.append({**obs["metrics"], "timestamp": obs["timestamp"],
                     "tripped": (16, 17) in env._tripped})
        if str(env.timestamps[env.t]) == "2019-01-17 00:00:00+00:00":
            break
    dftrip = pd.DataFrame(rows).set_index("timestamp")
    dftrip.to_csv(RESULTS / "qsts_case39_line_trip.csv")

    for case in ["case9", "case14", "case118"]:
        df = run_case(case, "2019-01-01", "2019-01-07", "jan19-week")
        df.to_csv(RESULTS / f"qsts_{case}_jan2019_week.csv")
        summary[f"{case}_jan2019_week"] = {
            "n_steps": int(len(df)),
            "converged": int(df["converged"].sum()),
            "mean_losses_mw": float(df["losses_mw"].mean()),
            "min_vm": float(df39["vm_min"].min() if case == "case39" else df["vm_min"].min()),
            "max_line_loading": float(df["max_line_loading"].max()),
            "ms_per_step": None,
        }

    with open(RESULTS / "phase2_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True, constrained_layout=True)
    ax = axes[0]
    ax.plot(df39.index, df39["total_load_mw"], color="tab:gray", label="Total load (MW)")
    ax.set_ylabel("Load (MW)")
    ax.legend(loc="upper left")
    ax = axes[1]
    ax.plot(df39.index, df39["losses_mw"], color="tab:red", label="Losses (MW)")
    ax.set_ylabel("Losses (MW)")
    ax.legend(loc="upper left")
    ax = axes[2]
    ax.plot(df39.index, df39["vm_min"], color="tab:blue", label="min Vm")
    ax.plot(df39.index, df39["vm_max"], color="tab:orange", label="max Vm")
    ax.axhline(0.95, color="k", lw=0.5, ls="--")
    ax.axhline(1.05, color="k", lw=0.5, ls="--")
    ax.set_ylabel("Voltage (p.u.)")
    ax.legend(loc="upper left")
    fig.suptitle("Uncontrolled QSTS, IEEE 39-bus, real OPSD profiles (Jan 2019)")
    save_figure(fig, RESULTS / "fig_p2_qsts_case39_jan2019")
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True, constrained_layout=True)
    axes[0].plot(dftrip.index, dftrip["losses_mw"], color="tab:red")
    axes[0].axvline(pd.Timestamp("2019-01-15 12:00", tz="UTC"), color="k", ls="--", lw=1)
    axes[0].set_ylabel("Losses (MW)")
    axes[1].plot(dftrip.index, dftrip["vm_min"], color="tab:blue")
    axes[1].axvline(pd.Timestamp("2019-01-15 12:00", tz="UTC"), color="k", ls="--", lw=1)
    axes[1].axhline(0.95, color="k", lw=0.5, ls="--")
    axes[1].set_ylabel("min Vm (p.u.)")
    fig.suptitle("Line 16-17 trip on real operating conditions (IEEE 39-bus)")
    save_figure(fig, RESULTS / "fig_p2_line_trip")
    plt.close(fig)

    print("[phase2] summary:")
    print(json.dumps(summary, indent=2))
    print("[phase2] done. artifacts in results/phase2/")


if __name__ == "__main__":
    main()
