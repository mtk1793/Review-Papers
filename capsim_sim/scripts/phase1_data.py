"""Phase 1 verification: cache build, sanity figures, ramp mining, samples."""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from capsm.data.disaggregate import RENEWABLE_SITES, penetration_summary
from capsm.data.opsd import SPLITS, PRICE_WINDOW, apply_gap_policy, build_cache, load_opsd, mine_ramp_events
from capsm.plotting import save_figure, set_style

RESULTS = Path(__file__).resolve().parents[1] / "results" / "phase1"
TESTS_DATA = Path(__file__).resolve().parents[1] / "tests" / "data"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def main():
    set_style()
    RESULTS.mkdir(parents=True, exist_ok=True)
    TESTS_DATA.mkdir(parents=True, exist_ok=True)

    raw_path = DATA_DIR / "raw" / "time_series_60min_singleindex.csv"
    df_raw = pd.read_csv(raw_path, usecols=[
        "utc_timestamp",
        "DE_load_actual_entsoe_transparency",
        "DE_load_forecast_entsoe_transparency",
        "DE_solar_generation_actual",
        "DE_wind_onshore_generation_actual",
        "DE_wind_offshore_generation_actual",
        "DE_LU_price_day_ahead",
    ])
    df_raw = df_raw.rename(columns={
        "utc_timestamp": "timestamp",
        "DE_load_actual_entsoe_transparency": "load_actual_mw",
        "DE_load_forecast_entsoe_transparency": "load_forecast_mw",
        "DE_solar_generation_actual": "solar_mw",
        "DE_wind_onshore_generation_actual": "wind_onshore_mw",
        "DE_wind_offshore_generation_actual": "wind_offshore_mw",
        "DE_LU_price_day_ahead": "price_day_ahead_eur",
    })
    df_raw["timestamp"] = pd.to_datetime(df_raw["timestamp"], utc=True)
    df_raw = df_raw.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")
    _, gap_report = apply_gap_policy(df_raw)
    with open(RESULTS / "gap_policy_report.json", "w") as f:
        json.dump(gap_report, f, indent=2)
    print("[phase1] gap policy applied:")
    for col, n in gap_report["interpolated"].items():
        print(f"  {col}: interpolated {n}, left NaN {gap_report['left_nan'][col]}")

    df = build_cache()
    print(f"[phase1] cache built: {len(df):,} rows x {len(df.columns)} cols")
    for name, (s, e) in SPLITS.items():
        part = df.loc[s:e]
        print(f"  split {name}: {s} -> {e}  ({len(part):,} h)")
    print(f"  price window: {PRICE_WINDOW[0]} -> {PRICE_WINDOW[1]}")

    sample = df_raw.loc["2016-01-01":"2016-01-08"]
    sample.to_csv(TESTS_DATA / "sample_opsd_week.csv")
    print(f"[phase1] test sample written: {len(sample)} rows")

    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=False, constrained_layout=True)
    winter = df.loc["2016-01-04":"2016-01-11", "load_actual_mw"]
    summer = df.loc["2016-07-04":"2016-07-11", "load_actual_mw"]
    axes[0].plot(winter.index, winter, color="tab:blue")
    axes[0].set_ylabel("MW")
    axes[0].set_title("German national load, winter week (Jan 2016)")
    axes[1].plot(summer.index, summer, color="tab:red")
    axes[1].set_ylabel("MW")
    axes[1].set_title("Summer week (Jul 2016)")
    fig.autofmt_xdate()
    save_figure(fig, RESULTS / "fig_p1_load_weeks")
    plt.close(fig)

    df["month"] = df.index.month
    season = {12: "winter", 1: "winter", 2: "winter", 3: "spring", 4: "spring", 5: "spring",
              6: "summer", 7: "summer", 8: "summer", 9: "autumn", 10: "autumn", 11: "autumn"}
    df["season"] = df["month"].map(season)
    diurnal = df.groupby([df["season"], df.index.hour])["load_actual_mw"].mean().unstack(0)
    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    for col in diurnal.columns:
        ax.plot(diurnal.index, diurnal[col], label=col)
    ax.set_xlabel("Hour of day (UTC)")
    ax.set_ylabel("Mean load (MW)")
    ax.set_title("Mean diurnal load profile by season (real OPSD data, 2015-2020)")
    ax.legend()
    save_figure(fig, RESULTS / "fig_p1_diurnal_seasonal")
    plt.close(fig)

    events = mine_ramp_events(df)
    for w, ev in events.items():
        ev.to_csv(RESULTS / f"ramp_events_{w}h.csv")
        print(f"[phase1] ramp events ({w} h): {len(ev)} events; largest up {ev['ramp_mw'].max():.0f} MW, "
              f"largest down {ev['ramp_mw'].min():.0f} MW")

    top3h = events[3].iloc[0]
    t_end = top3h.name
    t_start = t_end - pd.Timedelta(hours=36)
    window = df.loc[t_start:t_end]
    re_total = window["wind_onshore_mw"].fillna(0) + window["wind_offshore_mw"].fillna(0) + window["solar_mw"].fillna(0)
    fig, ax = plt.subplots(figsize=(9, 5), constrained_layout=True)
    ax.plot(window.index, re_total, label="Wind + solar", color="tab:green")
    ax2 = ax.twinx()
    ax2.plot(window.index, window["load_actual_mw"], label="Load", color="tab:gray", alpha=0.6)
    ax.set_ylabel("Renewable generation (MW)")
    ax2.set_ylabel("Load (MW)")
    ax.set_title(f"Largest 3-h renewable ramp in the dataset (ends {t_end})")
    save_figure(fig, RESULTS / "fig_p1_top_ramp")
    plt.close(fig)

    year = df.loc["2019"]
    wind19 = (year["wind_onshore_mw"] + year["wind_offshore_mw"]).sort_values(ascending=False).reset_index(drop=True)
    solar19 = year["solar_mw"].sort_values(ascending=False).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    ax.plot(100 * wind19.index / len(wind19), wind19, label="Wind 2019")
    ax.plot(100 * solar19.index / len(solar19), solar19, label="Solar 2019")
    ax.set_xlabel("Exceedance (%)")
    ax.set_ylabel("Generation (MW)")
    ax.set_title("Renewable duration curves (real OPSD 2019)")
    ax.legend()
    save_figure(fig, RESULTS / "fig_p1_duration_curves")
    plt.close(fig)

    rows = []
    for case in RENEWABLE_SITES:
        rows.append(penetration_summary(case, df, 0.20, 0.10))
    pen = pd.DataFrame(rows)
    pen.to_csv(RESULTS / "penetration_summary.csv", index=False)
    print("[phase1] penetration summary:")
    print(pen.to_string(index=False))

    print("[phase1] done. artifacts in results/phase1/")


if __name__ == "__main__":
    main()
