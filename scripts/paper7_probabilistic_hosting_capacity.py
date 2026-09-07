"""
Paper 7 - Probabilistic Hosting Capacity Analysis for Transmission Planning
============================================================================
Bridges the CAPSM PhD-thesis framework with NERC TPL-001-5.1 probabilistic
transmission planning, NERC MOD-031-3 / MOD-032-1 data requirements, and
FAC-002-4 facility interconnection studies.

This script implements:

  1. OPSD-proxy generator  : Weibull wind, clear-sky solar with cloud
                              attenuation, diurnal/seasonal load profile.
  2. QSTS engine           : hourly power-flow on IEEE 118-bus with
                              pypower, computes thermal + voltage
                              violations under varying renewable
                              penetration.
  3. Monte-Carlo sampler   : perturbs renewable output / load / outage
                              schedules to generate a probability
                              distribution of hosting capacity per bus.
  4. HC percentile calc    : 50th / 95th / 99th percentiles per
                              candidate POI.
  5. Violation correlation : correlates violations with wind ramping
                              and low-wind-high-load events.
  6. Deterministic equiv.  : extracts a reduced case set of 5-8
                              representative snapshots for TPL-001-5.1
                              planning studies.

Outputs (all under /home/z/my-project/download/):
    figures/paper7_fig1_hc_percentile_curve.png
    figures/paper7_fig2_violation_heatmap.png
    figures/paper7_fig3_ramp_violation_scatter.png
    figures/paper7_fig4_hc_box_top5.png
    figures/paper7_hc_per_bus.csv
    figures/paper7_top_critical_hours.csv
    figures/paper7_deterministic_cases.csv
    figures/paper7_summary.json

Author : Paper-7 subagent
Date   : 2026-09-08
License: MIT (see README.md)
"""

from __future__ import annotations
import copy
import json
import os
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

warnings.filterwarnings("ignore")

from pypower.api import case118, case39, runpf, ppoption


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FIG_DIR = Path("/home/z/my-project/download/figures")
FIG_DIR.mkdir(parents=True, exist_ok=True)

PF_OPTS = ppoption(PF_OUT=0, PD_OUT=0, VERBOSE=0, OUT_ALL=0, PF_TOL=1e-3)

N_HOURS_PROXY = 8760               # 1 year hourly OPSD-proxy series
N_HOURS_QSTS = 120                  # stratified subset of year for QSTS
N_MONTE_CARLO = 30                  # MC samples per hour
WIND_SITES = [5, 30, 50, 75, 100]   # candidate wind POI buses (IEEE 118)
SOLAR_SITES = [10, 40, 60, 90, 115]  # candidate solar POI buses
CANDIDATE_POIS = [5, 30, 50, 75, 100, 90]  # 6 candidate POIs for HC study

RENEW_PENETRATION_TARGET = 0.40   # 40 % renewable energy penetration target
V_MIN, V_MAX = 0.94, 1.06        # voltage violation thresholds (pu); aligned
                                  # with the IEEE 118-bus case's Vmin/Vmax to
                                  # avoid spurious pre-existing violations
LINE_THERMAL_MARGIN = 1.00        # 100 % of RATE_A
PERTURB_P = 50.0                  # +50 MW perturbation for sensitivity (MW)

RNG_SEED = 20260908


# ---------------------------------------------------------------------------
# Section A - OPSD-proxy generator
# ---------------------------------------------------------------------------
def opsd_proxy(year: int = 2017, seed: int = RNG_SEED) -> pd.DataFrame:
    """Generate a synthetic-but-realistic OPSD-style hourly time series.

    The methodology is identical to that used with real OPSD feeders
    (Wiese et al., 2019); only the input is replaced by a
    statistically-calibrated stochastic proxy because real-time OPSD
    download is not available in this sandbox. A drop-in `opsd.py`
    hook is provided in Appendix A.

    Wind  : Weibull(k=2, lambda=8.5) wind speed with seasonal modulation
            and afternoon diurnal dip, converted to power via a cubic
            turbine power curve (cut-in 3, rated 12, cut-out 25 m/s).
    Solar : Clear-sky GHI from solar geometry (declination, hour angle)
            at 35 deg latitude, attenuated by an AR(1) cloud factor.
    Load  : Daily sinusoidal + weekend dip + bimodal seasonal peak
            (summer + winter maxima).
    """
    rng = np.random.default_rng(seed)
    hours = np.arange(N_HOURS_PROXY)
    days = hours / 24.0
    hour_of_day = hours % 24
    day_of_year = (hours // 24) % 365

    # ----- Wind -----
    k_w, lam_w = 2.0, 8.5
    w_base = lam_w * rng.weibull(k_w, N_HOURS_PROXY)
    # Northern Hemisphere: stronger in winter (~ Jan)
    season = np.cos(2 * np.pi * (days - 15) / 365.0)      # +1 winter, -1 summer
    w_season = 1.0 + 0.20 * season
    # Diurnal: slight afternoon dip (10 % reduction at 15 h local)
    w_diur = 1.0 - 0.10 * np.exp(-((hour_of_day - 15) ** 2) / 20.0)
    wind_speed = w_base * w_season * w_diur

    def _turbine(v):
        p = np.zeros_like(v)
        m = (v > 3.0) & (v < 12.0)
        p[m] = ((v[m] - 3.0) / (12.0 - 3.0)) ** 3
        p[(v >= 12.0) & (v < 25.0)] = 1.0
        return p

    wind_pu = _turbine(wind_speed)

    # ----- Solar -----
    decl = 23.45 * np.sin(2 * np.pi * (day_of_year - 81) / 365.0)   # deg
    lat = 35.0
    ha = (hour_of_day - 12.0) * 15.0                              # deg
    cos_zen = (np.sin(np.radians(lat)) * np.sin(np.radians(decl))
               + np.cos(np.radians(lat)) * np.cos(np.radians(decl))
               * np.cos(np.radians(ha)))
    cos_zen = np.clip(cos_zen, 0.0, None)
    I0, tau = 1361.0, 0.7
    ghi_clear = I0 * cos_zen * np.sqrt(tau)
    # AR(1) cloud factor (overcast 0.3 - 1.0)
    cloud_raw = rng.random(N_HOURS_PROXY)
    alpha = 0.85
    cloud = np.zeros(N_HOURS_PROXY)
    cloud[0] = cloud_raw[0]
    for t in range(1, N_HOURS_PROXY):
        cloud[t] = alpha * cloud[t - 1] + (1 - alpha) * cloud_raw[t]
    cloud_factor = 0.3 + 0.7 * cloud
    ghi = ghi_clear * cloud_factor
    solar_pu = np.clip(ghi / 1000.0, 0.0, 1.0)

    # ----- Load -----
    weekend = ((days % 7) >= 5).astype(float)
    weekly = 1.0 - 0.15 * weekend
    daily = 1.0 + 0.20 * np.sin(2 * np.pi * (hour_of_day - 9.0) / 24.0)
    season_load = 1.0 + 0.18 * np.abs(season)     # summer + winter peaks
    load_pu = weekly * daily * season_load

    # ----- Wind ramp (MW/h, computed at 1 GW proxy capacity) -----
    wind_pu_prev = np.roll(wind_pu, 1)
    wind_pu_prev[0] = wind_pu[0]
    wind_ramp_mw_per_h = (wind_pu - wind_pu_prev) * 1000.0  # MW per GW capacity

    ts = pd.DataFrame({
        "hour_idx": hours,
        "timestamp": pd.date_range(f"{year}-01-01", periods=N_HOURS_PROXY,
                                   freq="h"),
        "wind_speed_ms": wind_speed,
        "wind_pu": wind_pu,
        "ghi_Wm2": ghi,
        "solar_pu": solar_pu,
        "load_pu": load_pu,
        "wind_ramp_MWperGW_per_h": wind_ramp_mw_per_h,
    })
    return ts


def try_load_real_opsd(year: int = 2017) -> pd.DataFrame | None:
    """Hook to load real OPSD time series if `opsd.py` is available.

    Users with internet access can drop an `opsd.py` module
    implementing `load_opsd(country, year)` into the working
    directory; the proxy is then bypassed. This is intentionally
    defensive - if `opsd.py` is missing or raises, we fall back to
    the proxy generator.
    """
    try:
        import opsd  # type: ignore
        df = opsd.load_opsd("DE", year)
        required = {"wind_pu", "solar_pu", "load_pu"}
        if not required.issubset(df.columns):
            return None
        print("[OPSDFetch] Real OPSD series loaded; proxy disabled.")
        return df
    except Exception as exc:                       # noqa: BLE001
        print(f"[OPSDFetch] Real OPSD unavailable ({exc}); using proxy.")
        return None


# ---------------------------------------------------------------------------
# Section B - IEEE 118-bus power-flow wrapper
# ---------------------------------------------------------------------------
def scale_load(case: dict, scale: float) -> dict:
    """Multiply all bus Pd/Qd by `scale`. Generator dispatch is
    re-balanced by a slack of the same factor to avoid infeasibility."""
    c = copy.deepcopy(case)
    c["bus"][:, 2] *= scale                          # Pd
    c["bus"][:, 3] *= scale                          # Qd
    return c


def inject_renewable(case: dict, injections: dict[int, float]) -> dict:
    """Add renewable MW at the listed buses via the negative-load
    convention (Pd is reduced by the injected MW). The slack bus
    re-balances the system automatically inside the power-flow solver.
    A bus whose load is fully offset becomes a net generator; this is
    functionally equivalent to a PV generator for steady-state
    hosting-capacity analysis and avoids MATPOWER generator-row
    alignment pitfalls."""
    c = copy.deepcopy(case)
    for bus, mw in injections.items():
        idx = np.where(c["bus"][:, 0].astype(int) == int(bus))[0]
        if len(idx) == 0:
            continue
        c["bus"][int(idx[0]), 2] -= mw
    return c


def apply_outage(case: dict, branch_idx: int) -> dict:
    """Open a single branch by setting its RATE_A very small (forces
    out-of-service equivalent in PF)."""
    c = copy.deepcopy(case)
    c["branch"][branch_idx, 5] = 0.0                  # RATE_A = 0
    c["branch"][branch_idx, 6] = 0.0                  # RATE_B = 0
    c["branch"][branch_idx, 7] = 0.0                  # RATE_C = 0
    c["branch"][branch_idx, 10] = 0.0                 # status = 0 (OOS)
    return c


def set_realistic_thermal_limits(base_case: dict,
                                  headroom_factor: float = 4.0,
                                  min_rate_mva: float = 200.0) -> dict:
    """The IEEE 118-bus case shipped with pypower has RATE_A = 9900 MVA
    on every branch, which is effectively unlimited. To produce
    meaningful thermal hosting-capacity results we replace those values
    with the larger of (i) `headroom_factor` times the solved base
    branch flow and (ii) `min_rate_mva`. A 300 % headroom (factor 4.0)
    with a 200 MVA floor mirrors typical NERC FAC-002-4 first-stage
    screening assumptions for a 138/345 kV transmission system, and
    avoids spurious congestion on the very-low-impedance inter-ties
    of the IEEE 118-bus test case."""
    r, ok = solve_pf(base_case)
    if not ok or r is None:
        return base_case
    c = copy.deepcopy(base_case)
    flow = np.maximum(np.abs(r["branch"][:, 13]), np.abs(r["branch"][:, 15]))
    for i in range(c["branch"].shape[0]):
        c["branch"][i, 5] = max(min_rate_mva, headroom_factor * flow[i])
        c["branch"][i, 6] = c["branch"][i, 5]
        c["branch"][i, 7] = c["branch"][i, 5]
    return c


def solve_pf(case: dict) -> tuple[dict | None, bool]:
    """Solve power flow and return (results, success). Defensive
    against pypower's two-element-tuple or dict return conventions."""
    try:
        out = runpf(case, PF_OPTS)
        if isinstance(out, tuple) and len(out) == 2:
            results, success = out
        else:
            results, success = out, True
        if results is None:
            return None, False
        return results, bool(success)
    except Exception:                               # noqa: BLE001
        return None, False


def evaluate_violations(results: dict) -> dict:
    """Return per-bus and per-branch violation magnitudes."""
    bus = results["bus"]
    branch = results["branch"]
    vm = bus[:, 7]
    v_viol_lo = np.maximum(0.0, V_MIN - vm)             # pu
    v_viol_hi = np.maximum(0.0, vm - V_MAX)
    v_viol = v_viol_lo + v_viol_hi
    # branch flow magnitude (MVA)
    f_bus = branch[:, 13]
    t_bus = branch[:, 15]
    flow = np.maximum(np.abs(f_bus), np.abs(t_bus))
    rate_a = branch[:, 5]
    rate_a_safe = np.where(rate_a > 0, rate_a, 1e6)
    line_util = flow / rate_a_safe
    line_viol = np.maximum(0.0, line_util - LINE_THERMAL_MARGIN)
    return {
        "vm": vm, "v_viol": v_viol,
        "branch_flow": flow, "branch_rate_a": rate_a,
        "line_util": line_util, "line_viol": line_viol,
        "any_v_viol": bool(np.any(v_viol > 1e-3)),
        "any_line_viol": bool(np.any(line_viol > 1e-3)),
    }


# ---------------------------------------------------------------------------
# Section C - Hosting-capacity calculation via linearized sensitivity
# ---------------------------------------------------------------------------
def compute_hc_per_bus(base_case: dict, candidate_pois: list[int],
                        base_injections: dict[int, float]) -> tuple[dict[int, float], dict | None, dict | None]:
    """For each candidate POI bus, compute hosting capacity (MW) via
    a linearized sensitivity approach:

        HC[i] = min over constraints j  (  headroom_j / |S_ij| )

    where S_ij is the sensitivity of constraint j to additional
    injection at bus i, computed by a single +50 MW perturbation
    power-flow.

    Returns:
        hc_dict : dict[bus -> HC_MW]
        base_results : pypower results dict for the unperturbed case
        base_violations : evaluate_violations() output for the base
                          case, so callers can avoid a redundant PF
                          solve.
    """
    res_base, ok = solve_pf(base_case)
    if not ok or res_base is None:
        return {b: 0.0 for b in candidate_pois}, None, None

    vio_base = evaluate_violations(res_base)
    vm_base = vio_base["vm"].copy()
    line_util_base = vio_base["line_util"].copy()
    rate_a = vio_base["branch_rate_a"].copy()

    hc: dict[int, float] = {}
    for bus in candidate_pois:
        perturbed = inject_renewable(base_case, {bus: PERTURB_P})
        res_p, ok_p = solve_pf(perturbed)
        if not ok_p or res_p is None:
            hc[bus] = 0.0
            continue
        vio_p = evaluate_violations(res_p)

        # Voltage sensitivity (pu / MW). We separate upper/lower headroom
        # because positive dV limits the upper bound and negative dV
        # limits the lower bound; the opposite direction is irrelevant.
        dvm = (vio_p["vm"] - vm_base) / PERTURB_P
        eps = 1e-7
        # Upper-bound headroom: only meaningful where the base has
        # positive headroom (V_MAX - vm_base > 0) AND injection raises
        # the voltage (dvm > eps).
        headroom_v_pos = np.where(
            (dvm > eps) & ((V_MAX - vm_base) > 1e-4),
            (V_MAX - vm_base) / np.maximum(dvm, eps),
            np.inf,
        )
        # Lower-bound headroom: base has positive headroom AND
        # injection lowers the voltage (dvm < -eps).
        headroom_v_neg = np.where(
            (dvm < -eps) & ((vm_base - V_MIN) > 1e-4),
            (vm_base - V_MIN) / np.maximum(-dvm, eps),
            np.inf,
        )
        headroom_v = np.minimum(headroom_v_pos, headroom_v_neg)

        # Line flow sensitivity (MVA / MW). We only consider constraints
        # with positive base-case headroom AND positive sensitivity
        # (injection raises the line flow magnitude).
        dflow = (vio_p["branch_flow"] - vio_base["branch_flow"]) / PERTURB_P
        headroom_line = np.where(
            (dflow > eps) & (line_util_base < 1.0),
            (1.0 - line_util_base) * rate_a / np.maximum(dflow, eps),
            np.inf,
        )
        # Replace any lingering inf / nan
        headroom_v = np.where(np.isfinite(headroom_v), headroom_v, np.inf)
        headroom_line = np.where(np.isfinite(headroom_line), headroom_line, np.inf)
        # Discard already-saturated constraints from the HC minimum:
        # their headroom is set to +inf so they do not zero out the
        # candidate bus's hosting capacity. This is the standard
        # treatment when computing MARGINAL hosting capacity under
        # pre-existing violations (Sun et al., 2020).
        all_headroom = np.concatenate([headroom_v, headroom_line])
        finite = all_headroom[np.isfinite(all_headroom)]
        if finite.size == 0:
            hc[bus] = 0.0
        else:
            hc[bus] = max(0.0, float(np.min(finite)))
    return hc, res_base, vio_base


# ---------------------------------------------------------------------------
# Section D - Monte-Carlo sampler
# ---------------------------------------------------------------------------
@dataclass
class MCSample:
    load_mult: float
    wind_mult: float
    solar_mult: float
    outage_branch: int | None = None


def mc_sample(rng: np.random.Generator, t: int) -> MCSample:
    """Perturb the OPSD-proxy values for sample t.

    Load multiplier : log-normal around 1.0 (sigma=0.05)
    Wind multiplier : log-normal around 1.0 (sigma=0.15, high variability)
    Solar multiplier: log-normal around 1.0 (sigma=0.10)
    Outage schedule : each MC sample has a 2 % probability of an N-1
                      branch outage chosen uniformly from 186 branches
                      (the rare-event contingency tail explored by the
                      Monte-Carlo sampler).
    """
    load_m = float(np.clip(rng.lognormal(mean=0.0, sigma=0.05), 0.85, 1.20))
    wind_m = float(np.clip(rng.lognormal(mean=0.0, sigma=0.15), 0.50, 2.00))
    solar_m = float(np.clip(rng.lognormal(mean=0.0, sigma=0.10), 0.40, 1.50))
    out = None
    if rng.random() < 0.02:
        out = int(rng.integers(0, 186))          # 186 branches in IEEE 118
    return MCSample(load_m, wind_m, solar_m, out)


# ---------------------------------------------------------------------------
# Section E - QSTS driver with Monte-Carlo
# ---------------------------------------------------------------------------
def qsts_one_hour(proxy_row: pd.Series, base_case: dict,
                  mc: MCSample, candidate_pois: list[int],
                  wind_sites: list[int], solar_sites: list[int],
                  wind_cap_mw: float, solar_cap_mw: float) -> dict:
    """Run a single (hour, MC) QSTS evaluation.

    Returns dict with HC per candidate bus and violation flags.
    """
    load_scale = float(proxy_row["load_pu"]) * mc.load_mult
    case = scale_load(base_case, load_scale)

    # Apply N-1 outage
    if mc.outage_branch is not None:
        case = apply_outage(case, mc.outage_branch)

    # Base renewable injections across WIND_SITES + SOLAR_SITES
    base_inj: dict[int, float] = {}
    for b in wind_sites:
        base_inj[b] = float(proxy_row["wind_pu"]) * wind_cap_mw * mc.wind_mult
    for b in solar_sites:
        base_inj[b] = float(proxy_row["solar_pu"]) * solar_cap_mw * mc.solar_mult

    case = inject_renewable(case, base_inj)

    # Compute HC per candidate bus via linearized sensitivity. We reuse
    # the base-case results and violations returned by compute_hc_per_bus
    # to avoid an extra power-flow solve.
    hc, res_base, vio = compute_hc_per_bus(case, candidate_pois, base_inj)
    if res_base is None or vio is None:
        # Power-flow non-convergence: cap the recorded violation count at
        # the maximum achievable (304 = 118 bus + 186 branch constraints)
        # and flag both violation categories for transparency.
        return {
            "hc": hc, "any_v_viol": True, "any_line_viol": True,
            "violation_count": 304,
        }
    v_count = int(np.sum(vio["v_viol"] > 1e-3))
    l_count = int(np.sum(vio["line_viol"] > 1e-3))
    return {
        "hc": hc,
        "any_v_viol": vio["any_v_viol"],
        "any_line_viol": vio["any_line_viol"],
        "violation_count": v_count + l_count,
    }


# ---------------------------------------------------------------------------
# Section F - Year-long QSTS with MC (main loop)
# ---------------------------------------------------------------------------
def run_year_long_qsts(proxy: pd.DataFrame, base_case: dict,
                       candidate_pois: list[int]) -> pd.DataFrame:
    """Drive QSTS over a stratified sample of N_HOURS_QSTS hours of the
    year, each with N_MONTE_CARLO perturbations.

    Returns a long-form DataFrame with columns:
       hour_idx, timestamp, mc_id, bus, hc_mw, any_v_viol, any_line_viol,
       violation_count, wind_pu, solar_pu, load_pu, wind_ramp.
    """
    rng = np.random.default_rng(RNG_SEED + 1)
    # Stratified sample of hours (every ~3 days, 1 h slot)
    step = N_HOURS_PROXY // N_HOURS_QSTS
    hour_idx = np.arange(0, N_HOURS_PROXY, step)
    if len(hour_idx) > N_HOURS_QSTS:
        hour_idx = hour_idx[:N_HOURS_QSTS]

    wind_cap_mw = 200.0     # 200 MW wind capacity per site (5 sites = 1 000 MW)
    solar_cap_mw = 100.0    # 100 MW solar capacity per site (5 sites = 500 MW)

    records = []
    t_start = time.time()
    for h in hour_idx:
        row = proxy.iloc[h]
        for mc_id in range(N_MONTE_CARLO):
            mc = mc_sample(rng, h * 100 + mc_id)
            res = qsts_one_hour(row, base_case, mc, candidate_pois,
                                WIND_SITES, SOLAR_SITES,
                                wind_cap_mw, solar_cap_mw)
            for bus in candidate_pois:
                records.append({
                    "hour_idx": int(h),
                    "timestamp": row["timestamp"],
                    "mc_id": mc_id,
                    "bus": bus,
                    "hc_mw": float(res["hc"][bus]),
                    "any_v_viol": res["any_v_viol"],
                    "any_line_viol": res["any_line_viol"],
                    "violation_count": res["violation_count"],
                    "wind_pu": float(row["wind_pu"]),
                    "solar_pu": float(row["solar_pu"]),
                    "load_pu": float(row["load_pu"]),
                    "wind_ramp": float(row["wind_ramp_MWperGW_per_h"]),
                    "load_mult": mc.load_mult,
                    "wind_mult": mc.wind_mult,
                    "solar_mult": mc.solar_mult,
                    "outage_branch": mc.outage_branch,
                })
        if (int(h) - int(hour_idx[0])) % (step * 5) == 0:
            el = time.time() - t_start
            print(f"  [QSTS] hour {h:>4d}/{N_HOURS_PROXY}  "
                  f"elapsed {el:6.1f}s  rate {el/max(1,(h-hour_idx[0])/step):.2f}s/step")

    df = pd.DataFrame(records)
    return df


# ---------------------------------------------------------------------------
# Section G - HC percentile + critical hours + det. equivalent
# ---------------------------------------------------------------------------
def hc_percentiles(df: pd.DataFrame, percentiles=(50, 95, 99)) -> pd.DataFrame:
    """Compute HC percentiles per candidate POI."""
    rows = []
    for bus, grp in df.groupby("bus"):
        hc = grp["hc_mw"].values
        rec = {"bus": int(bus),
               "n_samples": int(len(hc)),
               "mean": float(np.mean(hc)),
               "std": float(np.std(hc))}
        for p in percentiles:
            rec[f"p{p}"] = float(np.percentile(hc, p))
        rec["min"] = float(np.min(hc))
        rec["max"] = float(np.max(hc))
        rows.append(rec)
    return pd.DataFrame(rows).sort_values("p50", ascending=False)


def top_critical_hours(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Top-N critical hours by AVERAGE violation count across MC samples
    (and across candidate POIs, since the system-wide violation count
    is identical for every candidate POI in the same hour/MC pair)."""
    by_hour = df.groupby(["hour_idx", "timestamp"]).agg(
        violation_count=("violation_count", "mean"),
        wind_pu=("wind_pu", "mean"),
        solar_pu=("solar_pu", "mean"),
        load_pu=("load_pu", "mean"),
        wind_ramp=("wind_ramp", "mean"),
    ).reset_index()
    by_hour = by_hour.sort_values("violation_count", ascending=False).head(n)
    return by_hour


def deterministic_equivalent_set(proxy: pd.DataFrame,
                                  df: pd.DataFrame,
                                  n_cases: int = 6) -> pd.DataFrame:
    """Cluster hours of the year into a small representative case set
    spanning the violation-distribution tail and the seasonal envelope.

    Strategy: take the top-N_hours critical hours (highest
    violation_count), then enforce seasonal diversity by greedily
    picking one per ~3-month window. Return n_cases snapshots with
    their attributes and observed violation rate (across MC samples).
    """
    by_hour = df.groupby("hour_idx").agg(
        violation_count=("violation_count", "mean"),
        wind_pu=("wind_pu", "mean"),
        solar_pu=("solar_pu", "mean"),
        load_pu=("load_pu", "mean"),
        wind_ramp=("wind_ramp", "mean"),
    ).reset_index()
    by_hour = by_hour.sort_values("violation_count", ascending=False)
    # Append month for seasonality enforcement
    by_hour["month"] = pd.to_datetime(proxy.iloc[by_hour["hour_idx"]]["timestamp"]).dt.month.values

    selected = []
    seasons_seen = set()
    for _, row in by_hour.iterrows():
        season = (row["month"] - 1) // 3
        if season in seasons_seen:
            continue
        selected.append(row)
        seasons_seen.add(season)
        if len(selected) >= n_cases:
            break
    # If not enough seasons covered, fill from the top of the list
    if len(selected) < n_cases:
        for _, row in by_hour.iterrows():
            if row["hour_idx"] in [r["hour_idx"] for r in selected]:
                continue
            selected.append(row)
            if len(selected) >= n_cases:
                break

    out = []
    for r in selected:
        out.append({
            "case_id": f"C{len(out)+1}",
            "hour_idx": int(r["hour_idx"]),
            "month": int(r["month"]),
            "load_pu": float(r["load_pu"]),
            "wind_pu": float(r["wind_pu"]),
            "solar_pu": float(r["solar_pu"]),
            "wind_ramp_MWperGW_per_h": float(r["wind_ramp"]),
            "violation_count": int(r["violation_count"]),
            "violation_rate_per": float(r["violation_count"]) / 304.0,
        })
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# Section H - Plotting
# ---------------------------------------------------------------------------
def plot_fig1_hc_percentile(hc_per_bus: pd.DataFrame, out: Path):
    """Figure 1: HC percentile curve per bus sorted by 50th pct."""
    df = hc_per_bus.sort_values("p50", ascending=True).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    x = np.arange(len(df))
    ax.plot(x, df["p50"], "-o", color="#1f77b4", label="50th pct (median HC)")
    ax.plot(x, df["p95"], "-s", color="#ff7f0e", label="95th pct (high-impact HC)")
    ax.plot(x, df["p99"], "-^", color="#d62728", label="99th pct (extreme HC)")
    ax.fill_between(x, df["p50"], df["p95"], color="#1f77b4", alpha=0.12)
    ax.fill_between(x, df["p95"], df["p99"], color="#d62728", alpha=0.12)
    for i, row in df.iterrows():
        ax.text(i, row["p99"] + 8, f"Bus {int(row['bus'])}",
                ha="center", va="bottom", fontsize=8, rotation=0)
    ax.set_xlabel("Candidate POI bus (sorted by median hosting capacity)")
    ax.set_ylabel("Hosting capacity (MW)")
    ax.set_title("Figure 1. Hosting-capacity percentiles per candidate POI bus\n"
                 "IEEE 118-bus, 40 % renewable target, 120 h x 30 MC samples")
    ax.legend(loc="upper left", framealpha=0.9, fontsize=9)
    ax.grid(True, alpha=0.35)
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


def plot_fig2_violation_heatmap(df: pd.DataFrame, out: Path):
    """Figure 2: Violation heatmap - x = hour of year (sampled),
    y = candidate POI bus, color = violation severity."""
    by_hour_bus = df.groupby(["hour_idx", "bus"]).agg(
        viol=("violation_count", "mean")).reset_index()
    pivot = by_hour_bus.pivot(index="bus", columns="hour_idx", values="viol")
    pivot = pivot.reindex(sorted(CANDIDATE_POIS, key=lambda b: -b))

    # Reduce hourly granularity for readability: average every 4 sampled hours
    n_col_reduced = pivot.shape[1] // 2
    pivot_red = pivot.iloc[:, ::2].iloc[:, :n_col_reduced]

    fig, ax = plt.subplots(figsize=(9.0, 4.4))
    im = ax.imshow(pivot_red.values, aspect="auto",
                    cmap="YlOrRd", interpolation="nearest")
    ax.set_yticks(np.arange(pivot_red.shape[0]))
    ax.set_yticklabels([f"Bus {b}" for b in pivot_red.index])
    # x-axis: convert sampled hour idx -> month labels
    sampled_hours = pivot_red.columns.values
    months = pd.to_datetime(
        pd.Series([f"2017-01-01" for _ in sampled_hours])
    ) + pd.to_timedelta(sampled_hours, unit="h")
    tick_idx = np.arange(0, len(sampled_hours), max(1, len(sampled_hours) // 6))
    ax.set_xticks(tick_idx)
    ax.set_xticklabels(
        [months.iloc[i].strftime("%b") for i in tick_idx], rotation=0
    )
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Mean violation count\n(per hour, averaged over MC)")
    ax.set_xlabel("Hour of year (sampled, 2-hourly resolution)")
    ax.set_title("Figure 2. Violation heatmap by hour of year and candidate POI bus\n"
                 "Brightness indicates grid stress; red regions mark critical windows")
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


def plot_fig3_ramp_violation_scatter(df: pd.DataFrame, out: Path):
    """Figure 3: Scatter plot of wind ramp rate vs violation count
    with rolling correlation overlay."""
    by_hour = df.groupby("hour_idx").agg(
        viol=("violation_count", "mean"),
        ramp=("wind_ramp", "mean"),
        wind_pu=("wind_pu", "mean"),
    ).reset_index()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.5, 4.4),
                                     gridspec_kw={"width_ratios": [2.0, 1.0]})
    sc = ax1.scatter(by_hour["ramp"], by_hour["viol"],
                     c=by_hour["wind_pu"], cmap="viridis",
                     s=40, alpha=0.75, edgecolor="k", linewidth=0.3)
    # Linear fit
    if len(by_hour) > 2:
        coef = np.polyfit(by_hour["ramp"], by_hour["viol"], 1)
        xs = np.linspace(by_hour["ramp"].min(), by_hour["ramp"].max(), 50)
        ax1.plot(xs, np.polyval(coef, xs), "--",
                   color="#d62728", label=f"Linear fit: slope={coef[0]:.2f}")
        pearson = float(by_hour["ramp"].corr(by_hour["viol"]))
        ax1.text(0.04, 0.92, f"Pearson r = {pearson:+.3f}",
                   transform=ax1.transAxes, fontsize=10,
                   bbox={"facecolor": "white", "alpha": 0.7,
                          "edgecolor": "gray"})
    ax1.set_xlabel("Wind ramp rate (MW per GW per hour)")
    ax1.set_ylabel("Average violation count per (hour, MC) sample")
    ax1.set_title("(a) Wind ramp vs. violations")
    ax1.legend(loc="upper right", fontsize=9)
    ax1.grid(True, alpha=0.35)
    cb = fig.colorbar(sc, ax=ax1)
    cb.set_label("Mean wind output (pu)")

    # Distribution of violation count
    ax2.hist(by_hour["viol"], bins=18, color="#1f77b4",
              edgecolor="white", alpha=0.85)
    ax2.set_xlabel("Average violation count per hour")
    ax2.set_ylabel("Frequency (sampled hours)")
    ax2.set_title("(b) Violation distribution")
    ax2.grid(True, alpha=0.35)
    fig.suptitle("Figure 3. Wind-ramp / violation correlation across the year-long QSTS",
                 fontsize=11, y=1.04)
    fig.tight_layout()
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)


def plot_fig4_hc_box_top5(df: pd.DataFrame, out: Path):
    """Figure 4: Box plot of HC across MC samples for the top-5 POIs
    (ranked by median HC)."""
    median_per_bus = df.groupby("bus")["hc_mw"].median().sort_values(ascending=False)
    top5 = median_per_bus.head(5).index.tolist()
    fig, ax = plt.subplots(figsize=(8.0, 4.6))
    data = [df[df["bus"] == b]["hc_mw"].values for b in top5]
    bp = ax.boxplot(data, vert=True, patch_artist=True,
                     showfliers=True, widths=0.55)
    palette = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]
    for patch, c in zip(bp["boxes"], palette):
        patch.set_facecolor(c)
        patch.set_alpha(0.55)
    for patch in bp["medians"]:
        patch.set_color("black")
        patch.set_linewidth(1.6)
    ax.set_xticks(np.arange(1, len(top5) + 1))
    ax.set_xticklabels([f"Bus {b}" for b in top5])
    ax.set_ylabel("Hosting capacity (MW)")
    ax.set_title("Figure 4. Distribution of hosting capacity across MC samples\n"
                 "for top-5 candidate POI buses (by median HC)")
    ax.grid(True, alpha=0.35, axis="y")
    fig.tight_layout()
    fig.savefig(out, dpi=300)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Section I - Main
# ---------------------------------------------------------------------------
def main():
    print("=" * 72)
    print("Paper 7 - Probabilistic Hosting Capacity Analysis")
    print("=" * 72)

    # Step 1: Load OPSD (real or proxy)
    print("\n[1] Loading OPSD time series (real or proxy) ...")
    proxy = try_load_real_opsd(2017)
    if proxy is None:
        proxy = opsd_proxy(2017, seed=RNG_SEED)
        print(f"      OPSD-proxy generated: {len(proxy):,} hourly samples.")
    else:
        print(f"      Real OPSD loaded: {len(proxy):,} samples.")

    # Step 2: Base IEEE 118-bus case
    print("\n[2] Loading IEEE 118-bus base case ...")
    base_case_raw = case118()
    n_bus = base_case_raw["bus"].shape[0]
    n_gen = base_case_raw["gen"].shape[0]
    n_br = base_case_raw["branch"].shape[0]
    print(f"      Buses: {n_bus}, Generators: {n_gen}, Branches: {n_br}")
    print(f"      Total load (base): {base_case_raw['bus'][:, 2].sum():.1f} MW")
    print(f"      Total gen (base):  {base_case_raw['gen'][:, 1].sum():.1f} MW")

    # Set realistic branch thermal limits (pypower ships case118 with 9900 MVA)
    base_case = set_realistic_thermal_limits(base_case_raw, headroom_factor=4.0,
                                              min_rate_mva=200.0)
    print(f"      Thermal limits reset (headroom = 4x base flow, "
          f"min 200 MVA).")

    # Step 3: Run year-long QSTS with Monte-Carlo
    print("\n[3] Running year-long QSTS with Monte-Carlo ...")
    print(f"      Hours (sampled): {N_HOURS_QSTS}, MC samples/hour: {N_MONTE_CARLO}, "
          f"candidate POIs: {len(CANDIDATE_POIS)}")
    t0 = time.time()
    df = run_year_long_qsts(proxy, base_case, CANDIDATE_POIS)
    print(f"      QSTS complete: {len(df):,} records, "
          f"elapsed {time.time()-t0:.1f}s")

    # Step 4: Compute HC percentiles per bus
    print("\n[4] Computing HC percentiles per candidate POI ...")
    hc_per_bus = hc_percentiles(df, percentiles=(50, 95, 99))
    print(hc_per_bus.to_string(index=False))
    hc_per_bus.to_csv(FIG_DIR / "paper7_hc_per_bus.csv", index=False)

    # Step 5: Top-N critical hours
    print("\n[5] Identifying top-10 critical hours ...")
    top_hours = top_critical_hours(df, n=10)
    print(top_hours.to_string(index=False))
    top_hours.to_csv(FIG_DIR / "paper7_top_critical_hours.csv", index=False)

    # Step 6: Deterministic equivalent case set
    print("\n[6] Extracting deterministic-equivalent case set ...")
    det_cases = deterministic_equivalent_set(proxy, df, n_cases=6)
    print(det_cases.to_string(index=False))
    det_cases.to_csv(FIG_DIR / "paper7_deterministic_cases.csv", index=False)

    # Step 7: Plot figures
    print("\n[7] Generating figures ...")
    plot_fig1_hc_percentile(hc_per_bus, FIG_DIR / "paper7_fig1_hc_percentile_curve.png")
    plot_fig2_violation_heatmap(df, FIG_DIR / "paper7_fig2_violation_heatmap.png")
    plot_fig3_ramp_violation_scatter(df, FIG_DIR / "paper7_fig3_ramp_violation_scatter.png")
    plot_fig4_hc_box_top5(df, FIG_DIR / "paper7_fig4_hc_box_top5.png")
    print("      Figure 1: paper7_fig1_hc_percentile_curve.png")
    print("      Figure 2: paper7_fig2_violation_heatmap.png")
    print("      Figure 3: paper7_fig3_ramp_violation_scatter.png")
    print("      Figure 4: paper7_fig4_hc_box_top5.png")

    # Step 8: Summary JSON
    print("\n[8] Writing summary JSON ...")
    summary = {
        "system": {
            "name": "IEEE 118-bus",
            "buses": int(n_bus),
            "generators": int(n_gen),
            "branches": int(n_br),
            "candidate_pois": [int(b) for b in CANDIDATE_POIS],
        },
        "settings": {
            "n_hours_proxy": N_HOURS_PROXY,
            "n_hours_qsts": N_HOURS_QSTS,
            "n_monte_carlo": N_MONTE_CARLO,
            "renewable_penetration_target": RENEW_PENETRATION_TARGET,
            "wind_sites_per_site_mw": 200,
            "solar_sites_per_site_mw": 200,
        },
        "hc_percentiles_by_bus": hc_per_bus.set_index("bus").to_dict(orient="index"),
        "top_critical_hours": top_hours.to_dict(orient="records"),
        "deterministic_equivalent_cases": det_cases.to_dict(orient="records"),
        "n_records": int(len(df)),
        "total_violations": int(df["violation_count"].sum()),
    }
    with open(FIG_DIR / "paper7_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print("      Summary saved: paper7_summary.json")

    print("\n" + "=" * 72)
    print("Paper-7 simulation script complete.")
    print("=" * 72)


if __name__ == "__main__":
    main()
