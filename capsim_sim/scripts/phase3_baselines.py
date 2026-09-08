"""Phase 3 verification: baseline controllers on real data, Jan 2019.

Benchmarks NoControl, RuleBasedVoltage, and PIDVoltage on the IEEE 39-bus
system over one month of real OPSD profiles: aggregated metrics, economic
cost from real day-ahead prices, voltage loading margins at valley and
peak hours, and a mid-run contingency comparison.
"""

import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from capsm.agents.baselines import BASELINES, run_controller
from capsm.data.opsd import load_opsd
from capsm.grid.environment import QSTSEnvironment
from capsm.grid.stability import loading_margin
from capsm.plotting import save_figure, set_style

RESULTS = Path(__file__).resolve().parents[1] / "results" / "phase3"


def economic_cost(df: pd.DataFrame, prices: pd.Series) -> float:
    gen = df["total_gen_mw"].dropna()
    common = gen.index.intersection(prices.dropna().index)
    energy_cost_eur = float(np.sum(gen[common].to_numpy() * prices[common].to_numpy()))
    return energy_cost_eur


def summarise(df: pd.DataFrame, prices: pd.Series) -> dict:
    return {
        "n_steps": int(len(df)),
        "converged": int(df["converged"].sum()),
        "mean_losses_mw": float(df["losses_mw"].mean()),
        "max_losses_mw": float(df["losses_mw"].max()),
        "mean_voltage_dev_pu": float(df["voltage_deviation_pu"].mean()),
        "min_vm": float(df["vm_min"].min()),
        "max_vm": float(df["vm_max"].max()),
        "voltage_violation_bus_hours": int(df["n_voltage_violations"].sum()),
        "overload_line_hours": int(df["n_overloaded_lines"].sum()),
        "energy_cost_meur": economic_cost(df, prices) / 1e6,
    }


def main():
    set_style()
    RESULTS.mkdir(parents=True, exist_ok=True)
    profiles = load_opsd(start="2019-01-01", end="2019-01-31")
    prices = profiles["price_day_ahead_eur"]

    summary = {}
    frames = {}
    for ctrl_cls in BASELINES:
        ctrl = ctrl_cls()
        env = QSTSEnvironment("case39", profiles)
        t0 = time.time()
        df = run_controller(env, ctrl, start="2019-01-01")
        dt = time.time() - t0
        s = summarise(df, prices)
        s["runtime_s"] = round(dt, 1)
        s["curtailment_hours"] = int(env.curtailment_hours)
        summary[ctrl.name] = s
        frames[ctrl.name] = df
        df.to_csv(RESULTS / f"case39_jan2019_{ctrl.name}.csv")
        print(f"[phase3] {ctrl.name}: cost {s['energy_cost_meur']:.3f} MEUR, "
              f"viol {s['voltage_violation_bus_hours']}, "
              f"dev {s['mean_voltage_dev_pu']:.4f}, losses {s['mean_losses_mw']:.1f} MW")

        margins = {}
        for label in ["valley", "peak"]:
            target = df["total_load_mw"].idxmin() if label == "valley" else df["total_load_mw"].idxmax()
            env.t = int(np.flatnonzero(env.timestamps == target)[0])
            env._solve(None)
            lm = loading_margin(env)
            margins[label] = None if lm is None else round(lm, 3)
        summary[ctrl.name]["loading_margin_valley"] = margins["valley"]
        summary[ctrl.name]["loading_margin_peak"] = margins["peak"]
        print(f"[phase3]   margins: valley {margins['valley']}, peak {margins['peak']}")

    print("[phase3] contingency comparison (trip 16-17 at Jan 15 12:00, restored after 12 h)")
    cont_summary = {}
    for ctrl_cls in BASELINES:
        ctrl = ctrl_cls()
        env = QSTSEnvironment("case39", profiles)
        df = run_controller(
            env, ctrl, start="2019-01-14", n_steps=72,
            with_trip=("2019-01-15 12:00", 16, 17, 12),
        )
        pre = df.loc["2019-01-15 00:00":"2019-01-15 11:00", "losses_mw"].mean()
        during = df.loc["2019-01-15 12:00":"2019-01-16 00:00", "losses_mw"].mean()
        vm_during = df.loc["2019-01-15 12:00":"2019-01-16 00:00", "vm_min"].min()
        cont_summary[ctrl.name] = {
            "pre_losses_mw": round(float(pre), 1),
            "during_losses_mw": round(float(during), 1),
            "losses_increase_pct": round(100 * (during - pre) / pre, 1),
            "min_vm_during": round(float(vm_during), 4),
            "converged_during": int(df.loc["2019-01-15 12:00":"2019-01-16 00:00", "converged"].sum()),
        }
        df.to_csv(RESULTS / f"case39_contingency_{ctrl.name}.csv")
        print(f"[phase3]   {ctrl.name}: {cont_summary[ctrl.name]}")
    summary["contingency"] = cont_summary

    with open(RESULTS / "phase3_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    fig, axes = plt.subplots(3, 1, figsize=(10, 9), sharex=True, constrained_layout=True)
    for name, df in frames.items():
        axes[0].plot(df.index, df["losses_mw"], label=name, lw=0.9)
        axes[1].plot(df.index, df["voltage_deviation_pu"], label=name, lw=0.9)
        axes[2].plot(df.index, df["vm_min"], label=name, lw=0.9)
    axes[2].axhline(0.95, color="k", ls="--", lw=0.5)
    axes[0].set_ylabel("Losses (MW)")
    axes[1].set_ylabel("Mean |V-1.0| (p.u.)")
    axes[2].set_ylabel("min Vm (p.u.)")
    axes[0].legend()
    fig.suptitle("Baseline controllers, IEEE 39-bus, real OPSD Jan 2019")
    save_figure(fig, RESULTS / "fig_p3_baselines_jan2019")
    plt.close(fig)

    print("[phase3] done. artifacts in results/phase3/")


if __name__ == "__main__":
    main()
