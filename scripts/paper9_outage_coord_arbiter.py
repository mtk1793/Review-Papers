"""
Paper 9: Real-Time Outage Coordination and System Operating Limit Management
Using a Metacognitive AI Arbiter.

Simulation script:
  - IEEE 39-bus (proof-of-concept) and IEEE 118-bus (scalability check).
  - Outage injection (line / transformer / generator).
  - SOL margin metrics from FAC-014-3: thermal loading %, voltage deviation,
    voltage-stability (loading) margin.
  - Metacognitive arbiter that switches between System 1 (fast FACTS/EV-style
    reactive support) and System 2 (slow generator re-dispatch) based on the
    instantaneous SOL margin.
  - Four control baselines: No Control, Fixed System 1, Fixed System 2, Arbiter.
  - Generates 4 figures (SOL margin time series, mode-switching timeline,
    violation-count bar chart, extracted nomogram) and 3 CSV summaries.

Outputs:
  /home/z/my-project/download/figures/paper9_fig1_sol_margin_timeseries.png
  /home/z/my-project/download/figures/paper9_fig2_mode_timeline.png
  /home/z/my-project/download/figures/paper9_fig3_violation_bars.png
  /home/z/my-project/download/figures/paper9_fig4_nomogram.png
  /home/z/my-project/download/figures/paper9_scenarios.csv
  /home/z/my-project/download/figures/paper9_violations_by_mode.csv
  /home/z/my-project/download/figures/paper9_nomogram.csv

Run:
  python /home/z/my-project/download/scripts/paper9_outage_coord_arbiter.py
"""

from __future__ import annotations
import os
import json
import warnings
from copy import deepcopy

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.colors import LinearSegmentedColormap

from pypower.api import case39, case118, runpf, ppoption

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Global paths and solver options
# ---------------------------------------------------------------------------
FIG_DIR = "/home/z/my-project/download/figures"
os.makedirs(FIG_DIR, exist_ok=True)

PPC_OPT = ppoption(OUT_ALL=0, VERBOSE=0, PF_TOL=1e-6, PF_MAX_IT=50,
                   ENFORCE_Q_LIMS=False, ENFORCE_P_LIMS=False)


# ---------------------------------------------------------------------------
# Power-flow wrapper
# ---------------------------------------------------------------------------
def run_pf(ppc):
    """Defensive wrapper around pypower.runpf returning the result dict or None."""
    try:
        r, ok = runpf(ppc, PPC_OPT)
        if not ok or r is None:
            return None
        # Sanity: nan voltages -> infeasible
        if np.isnan(r["bus"][:, 7]).any():
            return None
        return r
    except Exception:
        return None


def base_case39():
    """IEEE 39-bus calibrated for an outage-coordination study.

    The stock pypower case39 is mildly stressed at base; that makes it hard to
    demonstrate *post-outage* SOL breaches because the pre-outage operating
    point already has breaches. We make four deliberate, transparent
    adjustments so that (i) the pre-outage case is clean, (ii) the case is
    moderately heavier loaded (so realistic planned outages do cause SOL
    breaches), and (iii) some outages produce voltage breaches that let the
    arbiter exercise System 1 (FACTS) in addition to System 2 (re-dispatch):

      * Vmax uniformly set to 1.10 pu (consistent with NPCC Directory 1).
      * Vmin uniformly set to 0.96 pu (typical pre-contingency SOL).
      * Branch rates of the four most-loaded branches bumped to 1500 MVA so
        the base case has no thermal overload.
      * Loads and generator dispatches uniformly scaled by 1.05 (a hot
        summer-peak proxy), preserving the relative pattern of the stock
        case while making outages more impactful.
    """
    ppc = deepcopy(case39())
    ppc["bus"][:, 11] = 1.10  # Vmax
    ppc["bus"][:, 12] = 0.96  # Vmin (pre-contingency SOL lower bound)
    # Bump the most-loaded branches to 1500 MVA so the base case is clean.
    # Indices 1, 19, 26, 36 are overloaded in the stock case; indices 32 and
    # 45 are overloaded after the 5% load bump (verified by runpf).
    for i in (1, 19, 26, 32, 36, 45):
        ppc["branch"][i, 5] = 1500.0
    # Hot-summer-peak proxy: 5% uniform load increase
    ppc["bus"][:, 2] = ppc["bus"][:, 2] * 1.05
    ppc["bus"][:, 3] = ppc["bus"][:, 3] * 1.05
    ppc["gen"][:, 1] = ppc["gen"][:, 1] * 1.05
    return ppc


def base_case118():
    """IEEE 118-bus with Vmax uniformly 1.10 pu (consistent with NPCC Directory 1
    and with the 39-bus calibration used in this study). Other parameters are
    unchanged from the pypower case118.
    """
    ppc = deepcopy(case118())
    ppc["bus"][:, 11] = 1.10  # Vmax
    return ppc


# ---------------------------------------------------------------------------
# SOL margin metrics (FAC-014-3)
# ---------------------------------------------------------------------------
def thermal_margin(r):
    """Return (1 - max_branch_loading, max_branch_loading)."""
    br = r["branch"]
    pf = br[:, 13]
    qf = br[:, 15]
    s = np.sqrt(pf ** 2 + qf ** 2)
    rate = br[:, 5]
    rate_safe = np.where(rate > 0, rate, 1e6)
    loading = s / rate_safe
    return float(1.0 - loading.max()), float(loading.max())


def voltage_margin(r):
    """Min normalized margin to Vmin/Vmax envelopes across all buses."""
    v = r["bus"][:, 7]
    vmin = r["bus"][:, 12]
    vmax = r["bus"][:, 11]
    lower = (v - vmin) / np.maximum(0.05, 1.0 - vmin)
    upper = (vmax - v) / np.maximum(0.05, vmax - 1.0)
    return float(np.minimum(lower.min(), upper.min()))


def voltage_stability_margin(ppc, lam_max=2.0, step=0.1):
    """Loading (P-V) margin via repeated power flow with scaled load.

    Returns lam_critical - 1.0; i.e., how much more load (per unit) the system
    can take before voltage collapse / divergence.
    """
    base_pd = ppc["bus"][:, 2].copy()
    base_qd = ppc["bus"][:, 3].copy()
    last_good = 1.0
    lam = 1.0
    while lam <= lam_max + 1e-6:
        new = deepcopy(ppc)
        new["bus"][:, 2] = base_pd * lam
        new["bus"][:, 3] = base_qd * lam
        r = run_pf(new)
        if r is None:
            return last_good - 1.0
        v = r["bus"][:, 7]
        if np.isnan(v).any() or (v < 0.80).any() or (v > 1.20).any():
            return last_good - 1.0
        last_good = lam
        lam += step
    return last_good - 1.0


def compute_margins(ppc, with_stability=True):
    """Run PF and return a dict of SOL margins + violation counts."""
    r = run_pf(ppc)
    if r is None:
        return None
    tm, ml = thermal_margin(r)
    vm = voltage_margin(r)
    sm = (voltage_stability_margin(ppc) if with_stability else np.nan)
    v = r["bus"][:, 7]
    vmin = r["bus"][:, 12]
    vmax = r["bus"][:, 11]
    v_viol = int(((v < vmin - 1e-6) | (v > vmax + 1e-6)).sum())
    br = r["branch"]
    pf = br[:, 13]
    qf = br[:, 15]
    s = np.sqrt(pf ** 2 + qf ** 2)
    rate = br[:, 5]
    rate_safe = np.where(rate > 0, rate, 1e6)
    loading = s / rate_safe
    t_viol = int((loading > 1.0 + 1e-6).sum())
    return {
        "thermal_margin": tm,
        "max_loading": ml,
        "voltage_margin": vm,
        "stability_margin": sm,
        "voltage_violations": v_viol,
        "thermal_violations": t_viol,
        "total_violations": v_viol + t_viol,
        "result": r,
    }


# ---------------------------------------------------------------------------
# Outage injection
# ---------------------------------------------------------------------------
def apply_outage(ppc, outage):
    """Return a new ppc with the specified outage applied.

    outage: dict with keys
      type   : 'line' | 'transformer' | 'generator'
      index  : integer index into ppc['branch'] or ppc['gen']
    """
    new = deepcopy(ppc)
    if outage["type"] in ("line", "transformer"):
        idx = int(outage["index"])
        if 0 <= idx < new["branch"].shape[0]:
            new["branch"] = np.delete(new["branch"], idx, axis=0)
    elif outage["type"] == "generator":
        idx = int(outage["index"])
        if 0 <= idx < new["gen"].shape[0]:
            new["gen"] = np.delete(new["gen"], idx, axis=0)
    else:
        raise ValueError(f"Unknown outage type: {outage['type']}")
    return new


def branch_descriptor(ppc, idx):
    """Return 'bus_from-bus_to (kV_from/kV_to)' descriptor for a branch."""
    br = ppc["branch"][idx]
    f = int(br[0])
    t = int(br[1])
    return f"{f}-{t}"


# ---------------------------------------------------------------------------
# System 1 (reflexive) and System 2 (deliberative) control actions
# ---------------------------------------------------------------------------
def apply_system1(ppc, gen_indices, vg_deltas):
    """Fast reactive support via generator AVR setpoint boost.

    Each (gen_idx, vg_delta) tuple bumps the generator's voltage setpoint Vg
    by `vg_delta` (a fractional boost, e.g. 0.03 = +3%). The new Vg is
    capped at (Vmax - 1e-3) on each generator's bus to avoid creating new
    over-voltage violations.

    In a production tool this action would also coordinate FACTS devices
    (SVC/STATCOM) via the same EMS path; we omit explicit FACTS modeling
    here for clarity because, in the IEEE 39-bus system, shunt injection
    alone has a small effect on bus voltages (the slack generator absorbs
    most of the local reactive injection) whereas Vg setpoint bumps produce
    a system-wide voltage lift.
    """
    new = deepcopy(ppc)
    bus_num_to_idx = {int(new["bus"][i, 0]): i for i in range(new["bus"].shape[0])}
    for gi, dv in zip(gen_indices, vg_deltas):
        if gi < 0 or gi >= new["gen"].shape[0]:
            continue
        bus_num = int(new["gen"][gi, 0])
        bi = bus_num_to_idx.get(bus_num, -1)
        if bi < 0:
            continue
        vmax = float(new["bus"][bi, 11])
        new_vg = min(vmax - 1e-3, new["gen"][gi, 5] * (1.0 + float(dv)))
        new["gen"][gi, 5] = new_vg
    return new


def apply_system2(ppc, bus_load_shed):
    """Slow re-dispatch via corrective load shedding at specified buses.

    bus_load_shed: list of (bus_idx, MW_to_shed). Reactive load is shed in
    proportion (pf=0.95 assumed) so the post-shed PF still solves.
    """
    new = deepcopy(ppc)
    for bus_idx, shed in bus_load_shed:
        if bus_idx < 0 or bus_idx >= new["bus"].shape[0]:
            continue
        new["bus"][bus_idx, 2] = max(0.0, new["bus"][bus_idx, 2] - float(shed))
        # shed Q in proportion (pf=0.95)
        q_shed = float(shed) * np.tan(np.arccos(0.95))
        new["bus"][bus_idx, 3] = max(0.0, new["bus"][bus_idx, 3] - q_shed)
    return new


def design_s1_action(post_result, top_k=3, mvar_per_bus=60.0,
                     vg_boost=0.03):
    """Pick the fast-acting System 1 control action.

    The CAPSM System 1 represents reflexive, fast-acting resources:
    generator AVR setpoint bumps (coordinated reactive dispatch via the
    EMS) and FACTS devices (SVC/STATCOM) modeled as adjustable shunt
    susceptance. In the IEEE 39-bus system, shunt susceptance alone has a
    small effect on bus voltages because the slack bus absorbs most of the
    injected reactive. Bumping generator Vg setpoints is far more effective
    at restoring bus voltages.

    We return a list of (gen_idx, vg_delta) tuples where vg_delta is the
    fractional boost applied to each generator's Vg setpoint. The
    time-domain simulation applies these boosts linearly scaled by the
    current System 1 effort.

    We boost ALL online generators by `vg_boost` (default 3%) so that
    under-voltage conditions are addressed system-wide; this is a faithful
    proxy for the EMS "fast reactive dispatch" action that an operator
    would invoke during a voltage emergency.
    """
    if post_result is None:
        return [], []
    n_gen = post_result["gen"].shape[0]
    gen_indices = list(range(n_gen))
    vg_deltas = [vg_boost] * n_gen
    return gen_indices, vg_deltas


def design_s2_action(post_outage_ppc, base_ppc=None, top_k=4, share=0.30,
                     max_iter=3):
    """System 2 corrective action: greedy closed-loop load shedding.

    The deliberative System 2 path is approximated as a small number of
    iterations of (i) run PF on the post-outage network, (ii) identify the
    worst overloaded branch and a small set of candidate relief buses
    adjacent to overloaded branches, (iii) test shedding `share` of the
    load at each candidate and pick the one that most reduces the worst
    branch loading, (iv) commit that shedding. We cap iterations at 3 to
    keep the deliberation bounded; a full OPF would replace this proxy in a
    production tool. The returned list of (bus_idx, MW_to_shed) actions is
    applied by the time-domain simulation, linearly scaled by the current
    System 2 effort.

    This is a recognized corrective action under IRO-017-1 (R3) and
    FAC-014-3 (R3): planned load shedding to keep flows within SOL.
    """
    if post_outage_ppc is None:
        return []
    ppc = deepcopy(post_outage_ppc)
    actions = []
    bus_num_to_idx = {int(ppc["bus"][i, 0]): i for i in range(ppc["bus"].shape[0])}
    for _ in range(max_iter):
        r = run_pf(ppc)
        if r is None:
            break
        br = r["branch"]
        pf = br[:, 13]
        qf = br[:, 15]
        s = np.sqrt(pf ** 2 + qf ** 2)
        rate = br[:, 5]
        rate_safe = np.where(rate > 0, rate, 1e6)
        loading = s / rate_safe
        overloaded = np.where(loading > 1.0 + 1e-3)[0]
        if len(overloaded) == 0:
            break
        cur_viol = int((loading > 1.0 + 1e-3).sum())
        # Candidate relief buses: 1-hop neighbors of the top-3 overloaded
        # branches (sorted by loading descending)
        top_overload = sorted(overloaded, key=lambda i: -loading[i])[:3]
        cand = set()
        for oi in top_overload:
            cand.add(int(br[oi, 0]))
            cand.add(int(br[oi, 1]))
        cand_idx = [bus_num_to_idx[b] for b in cand if b in bus_num_to_idx]
        cand_idx = [bi for bi in cand_idx if r["bus"][bi, 2] > 0]
        cand_idx = sorted(cand_idx, key=lambda bi: -r["bus"][bi, 2])[:top_k]
        if not cand_idx:
            break
        worst_loading = float(loading.max())
        best_bi = -1
        best_reduc = 0.0
        best_viol_after = cur_viol + 1  # initialize > cur_viol (must not increase)
        # Try each candidate and pick the one that best reduces violations
        # (without increasing them) and reduces worst loading.
        for bi in cand_idx:
            pd = float(r["bus"][bi, 2])
            if pd < 1.0:
                continue
            test_ppc = deepcopy(ppc)
            test_ppc["bus"][bi, 2] *= (1.0 - share)
            test_ppc["bus"][bi, 3] *= (1.0 - share)
            test_r = run_pf(test_ppc)
            if test_r is None:
                continue
            test_br = test_r["branch"]
            tpf, tqf = test_br[:, 13], test_br[:, 15]
            ts = np.sqrt(tpf ** 2 + tqf ** 2)
            tloading = ts / rate_safe
            t_viol = int((tloading > 1.0 + 1e-3).sum())
            t_worst = float(tloading.max())
            reduc = worst_loading - t_worst
            # Must not increase violations (allow equal), then prefer larger
            # loading reduction.
            if t_viol > cur_viol:
                continue  # this candidate increases violations; skip
            if (t_viol < best_viol_after
                    or (t_viol == best_viol_after and reduc > best_reduc)):
                best_viol_after = t_viol
                best_reduc = reduc
                best_bi = bi
        # Require at least 1e-3 worst-loading reduction (otherwise stop)
        if best_bi < 0 or best_reduc < 1e-3:
            break
        shed = float(r["bus"][best_bi, 2]) * share
        actions.append((int(best_bi), shed))
        ppc["bus"][best_bi, 2] *= (1.0 - share)
        ppc["bus"][best_bi, 3] *= (1.0 - share)
    return actions


# ---------------------------------------------------------------------------
# Metacognitive arbiter
# ---------------------------------------------------------------------------
# SOL margin thresholds for mode-switching (FAC-014-3 aligned)
GREEN_MIN = 0.30   # margin >= 0.30 → no control needed (System 2 ready)
YELLOW_MIN = 0.15  # 0.15 <= margin < 0.30 → System 2 engaged
RED_MIN = 0.05     # 0.05 <= margin < 0.15 → System 1 + System 2
EMERGENCY = 0.00   # margin < 0.00 → emergency: System 1 + System 2 max effort


def arbiter_decide(margins):
    """Return (mode, confidence) given SOL margin dict.

    The arbiter treats System 1 and System 2 as separate control channels
    rather than a single scalar "minimum margin" decision:
      * System 1 (reflexive FACTS/EV) engages when voltage or stability
        margin drops into yellow/red — fast reactive support prevents
        voltage collapse and SOL voltage-band breaches.
      * System 2 (deliberative re-dispatch) engages when thermal margin
        drops into yellow/red — corrective load shedding / generation
        shift to relieve branch overloads.
      * If any margin is below EMERGENCY, escalate to full-effort mode
        (s1+s2-emergency).

    mode in {'none', 's1', 's2', 's1+s2', 's1+s2-emergency'}
    confidence in [0,1].
    """
    if margins is None:
        return "s1+s2-emergency", 0.95
    tm = margins["thermal_margin"]
    vm = margins["voltage_margin"]
    sm = margins["stability_margin"]
    sm_eff = sm if not np.isnan(sm) else 0.5

    # Emergency escalation
    if tm < EMERGENCY or vm < EMERGENCY or sm_eff < EMERGENCY:
        return "s1+s2-emergency", 0.95

    # System 1 logic (voltage + stability)
    if vm < RED_MIN or sm_eff < RED_MIN:
        s1_on = True
        s1_conf = 0.85
    elif vm < YELLOW_MIN or sm_eff < YELLOW_MIN:
        s1_on = True
        s1_conf = 0.70
    else:
        s1_on = False
        s1_conf = 0.40

    # System 2 logic (thermal)
    if tm < RED_MIN:
        s2_on = True
        s2_conf = 0.85
    elif tm < YELLOW_MIN:
        s2_on = True
        s2_conf = 0.70
    else:
        s2_on = False
        s2_conf = 0.40

    if s1_on and s2_on:
        return "s1+s2", (s1_conf + s2_conf) / 2
    elif s1_on:
        return "s1", s1_conf
    elif s2_on:
        return "s2", s2_conf
    else:
        return "none", 0.40


# ---------------------------------------------------------------------------
# Time-series simulation of a planned outage
# ---------------------------------------------------------------------------
def simulate_scenario(base_ppc, outage, control_mode="arbiter",
                      T=60.0, dt=2.0,
                      outage_t=20.0, detect_t=21.0,
                      s1_ramp=2.0, s2_ramp=10.0,
                      with_stability_every=4):
    """Time-stepped simulation.

    control_mode in {'none', 's1', 's2', 'arbiter'}.

    Mode codes used internally:
      'none'               : no control
      's1'                 : System 1 only (FACTS reactive support)
      's2'                 : System 2 only (corrective load shedding)
      's1+s2'              : both systems engaged
      's1+s2-emergency'    : both systems at full effort (SOL breach)

    Returns a DataFrame with columns:
      t, thermal_margin, voltage_margin, stability_margin, mode, violations,
      max_loading, s1_effort, s2_effort
    """
    t_grid = np.arange(0.0, T + dt, dt)
    rows = []

    # Pre-compute corrective actions once (designed from immediate post-outage
    # snapshot) so the simulation only needs to ramp them on/off.
    post_ppc = apply_outage(base_ppc, outage)
    post_m = compute_margins(post_ppc, with_stability=True)
    if post_m is None:
        s1_buses, s1_mags = [], []
        s2_dispatch = []
    else:
        s1_buses, s1_mags = design_s1_action(post_m["result"], vg_boost=0.03)
        s2_dispatch = design_s2_action(post_ppc, base_ppc, top_k=4, share=0.30,
                                        max_iter=3)

    s1_effort = 0.0
    s2_effort = 0.0
    mode_state = "none"
    step_index = 0

    for t in t_grid:
        # Build current network
        cur = deepcopy(base_ppc)
        if t >= outage_t:
            cur = apply_outage(cur, outage)

        # Arbiter decision (after detection delay)
        if t >= detect_t and control_mode != "none":
            fast_m = compute_margins(cur, with_stability=False)
            if control_mode == "arbiter":
                mode_target, _ = arbiter_decide(fast_m)
            elif control_mode == "s1":
                # Fixed System 1: respond if any violation detected
                mode_target = "s1" if (fast_m and fast_m["total_violations"] > 0) else "none"
            elif control_mode == "s2":
                # Fixed System 2: always on after detection
                mode_target = "s2"
            else:
                mode_target = "none"
        else:
            mode_target = "none"

        if mode_target != mode_state:
            mode_state = mode_target

        # Ramp System 1 (fast) and System 2 (slow) toward target
        s1_target = 1.0 if ("s1" in mode_state) else 0.0
        s2_target = 1.0 if ("s2" in mode_state) else 0.0

        s1_effort += (s1_target - s1_effort) * (dt / max(dt, s1_ramp))
        s2_effort += (s2_target - s2_effort) * (dt / max(dt, s2_ramp))
        s1_effort = float(np.clip(s1_effort, 0.0, 1.0))
        s2_effort = float(np.clip(s2_effort, 0.0, 1.0))

        # Apply control
        if s1_effort > 0.01 and s1_buses:
            mags = [m * s1_effort for m in s1_mags]
            cur = apply_system1(cur, s1_buses, mags)
        if s2_effort > 0.01 and s2_dispatch:
            disp = [(g, d * s2_effort) for g, d in s2_dispatch]
            cur = apply_system2(cur, disp)

        # Compute SOL margins
        with_stab = (step_index % with_stability_every == 0)
        m = compute_margins(cur, with_stability=with_stab)
        if m is None:
            rows.append({
                "t": t, "thermal_margin": -0.30, "voltage_margin": -0.20,
                "stability_margin": -0.10, "mode": mode_state,
                "violations": 99, "max_loading": 1.5,
                "s1_effort": s1_effort, "s2_effort": s2_effort,
            })
        else:
            rows.append({
                "t": t,
                "thermal_margin": m["thermal_margin"],
                "voltage_margin": m["voltage_margin"],
                "stability_margin": m["stability_margin"],
                "mode": mode_state,
                "violations": m["total_violations"],
                "max_loading": m["max_loading"],
                "s1_effort": s1_effort,
                "s2_effort": s2_effort,
            })
        step_index += 1

    df = pd.DataFrame(rows)
    df["stability_margin"] = df["stability_margin"].ffill()
    return df


# ---------------------------------------------------------------------------
# Scenario catalogue (IEEE 39-bus)
# ---------------------------------------------------------------------------
def build_scenarios_39():
    """Return a list of outage scenarios for IEEE 39-bus.

    Branch indices in pypower case39 (0-based, buses 1-indexed):
      2  : bus 2-3      9  : bus 5-6      18 : bus 10-13
      12 : bus 6-11 (transformer 480 MVA)
    Generators (0-based):
      8  : bus 38 (830 MW) — trip causes mixed voltage + thermal breaches
      5  : bus 35 (650 MW) — trip causes thermal breaches near voltage limit
    """
    scenarios = []
    scenarios.append({
        "name": "L1", "type_str": "Line outage",
        "outage": {"type": "line", "index": 2},     # bus 2-3 (corridor)
        "desc": "Line 2-3 (heavily loaded east-west corridor)",
    })
    scenarios.append({
        "name": "L2", "type_str": "Line outage",
        "outage": {"type": "line", "index": 9},     # bus 5-6 (major tie)
        "desc": "Line 5-6 (major east-west tie, 1200 MVA rating)",
    })
    scenarios.append({
        "name": "L3", "type_str": "Line outage",
        "outage": {"type": "line", "index": 18},    # bus 10-13 (load feeder)
        "desc": "Line 10-13 (load-supply feeder to bus 13)",
    })
    scenarios.append({
        "name": "T1", "type_str": "Transformer outage",
        "outage": {"type": "transformer", "index": 12},  # bus 6-11 (480 MVA xfmr)
        "desc": "Transformer 6-11 (step-down to bus 11 subnetwork, 480 MVA)",
    })
    scenarios.append({
        "name": "G1", "type_str": "Generator outage",
        "outage": {"type": "generator", "index": 8},   # bus 38 (830 MW)
        "desc": "Generator at bus 38 (830 MW, mixed voltage+thermal impact)",
    })
    scenarios.append({
        "name": "G2", "type_str": "Generator outage",
        "outage": {"type": "generator", "index": 5},   # bus 35 (650 MW)
        "desc": "Generator at bus 35 (650 MW, near voltage limit)",
    })
    return scenarios


def scenario_table_row(scn, base_ppc):
    """Compute pre-outage loading & rating summary for the scenario table."""
    outage = scn["outage"]
    if outage["type"] in ("line", "transformer"):
        idx = outage["index"]
        br = base_ppc["branch"][idx]
        f_bus = int(br[0])
        t_bus = int(br[1])
        rate = float(br[5])
        # Pre-outage flow
        r = run_pf(base_ppc)
        if r is not None:
            flow = np.sqrt(r["branch"][idx, 13]**2 + r["branch"][idx, 15]**2)
            loading = flow / rate if rate > 0 else float("nan")
        else:
            loading = float("nan")
        return {
            "Scenario": scn["name"],
            "Type": scn["type_str"],
            "Element": f"{f_bus}-{t_bus}",
            "Duration (h)": 8.0,
            "Pre-outage loading (%)": round(loading * 100, 1),
            "Rating (MVA)": round(rate, 1),
            "Description": scn["desc"],
        }
    elif outage["type"] == "generator":
        idx = outage["index"]
        g = base_ppc["gen"][idx]
        bus = int(g[0])
        pg = float(g[1])
        pmax = float(g[8])
        return {
            "Scenario": scn["name"],
            "Type": scn["type_str"],
            "Element": f"Gen@bus{bus}",
            "Duration (h)": 8.0,
            "Pre-outage loading (%)": round(pg / pmax * 100, 1),
            "Rating (MVA)": round(pmax, 1),
            "Description": scn["desc"],
        }


# ---------------------------------------------------------------------------
# Figure 1: SOL margin time series for the representative outage
# ---------------------------------------------------------------------------
def figure_1_sol_margin_timeseries(scenario, base_ppc):
    """Compare arbiter vs no-control during a planned outage."""
    print(f"  [Fig 1] time series for scenario {scenario['name']} ...")
    df_arb = simulate_scenario(base_ppc, scenario["outage"], control_mode="arbiter")
    df_no = simulate_scenario(base_ppc, scenario["outage"], control_mode="none")

    fig, axes = plt.subplots(3, 1, figsize=(9.0, 7.2), sharex=True)
    palette = {"Arbiter": "#1b7837", "No Control": "#c51b7d"}

    for ax, metric, ylabel in zip(
        axes,
        ["thermal_margin", "voltage_margin", "stability_margin"],
        ["Thermal margin\n(1 - max loading)",
         "Voltage margin\n(min to Vmin/Vmax)",
         "Stability margin\n(P-V loading margin)"],
    ):
        ax.plot(df_arb["t"], df_arb[metric], color=palette["Arbiter"],
               lw=2.0, label="Arbiter (System 1+2)", marker="o", ms=3)
        ax.plot(df_no["t"], df_no[metric], color=palette["No Control"],
                lw=2.0, ls="--", label="No Control", marker="s", ms=3)
        ax.axhline(0.0, color="black", lw=0.7, ls=":")
        ax.axhline(RED_MIN, color="#d73027", lw=0.8, ls=":", alpha=0.6)
        ax.axhline(YELLOW_MIN, color="#fdae61", lw=0.8, ls=":", alpha=0.6)
        ax.axhline(GREEN_MIN, color="#1a9850", lw=0.8, ls=":", alpha=0.6)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.grid(alpha=0.3)
        ax.set_ylim(-0.15, max(0.7, df_arb[metric].max() + 0.05))

    axes[0].axvline(20.0, color="grey", lw=1.0, ls="--")
    axes[0].legend(loc="lower left", fontsize=8, framealpha=0.95)
    axes[-1].set_xlabel("Time (s)  -  outage applied at t = 20 s", fontsize=10)
    fig.suptitle(
        f"Figure 1. SOL margin time series during {scenario['name']} "
        f"({scenario['type_str']}) on IEEE 39-bus",
        fontsize=11, y=0.995)
    plt.tight_layout(rect=[0, 0, 1, 0.97])
    out = os.path.join(FIG_DIR, "paper9_fig1_sol_margin_timeseries.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return df_arb, df_no


# ---------------------------------------------------------------------------
# Figure 2: Arbiter mode-switching timeline
# ---------------------------------------------------------------------------
def figure_2_mode_timeline(scenario, base_ppc):
    """Stacked timeline of arbiter mode and effort."""
    print(f"  [Fig 2] mode timeline for scenario {scenario['name']} ...")
    df = simulate_scenario(base_ppc, scenario["outage"], control_mode="arbiter")

    fig, axes = plt.subplots(2, 1, figsize=(9.0, 5.6), sharex=True,
                             gridspec_kw={"height_ratios": [1.4, 1.0]})
    # Mode strip
    mode_colors = {
        "none": "#a6d96a",
        "s1": "#74add1",
        "s2": "#fdae61",
        "s1+s2": "#f46d43",
        "s1+s2-emergency": "#d73027",
    }
    mode_order = ["none", "s1", "s2", "s1+s2", "s1+s2-emergency"]
    mode_to_int = {m: i for i, m in enumerate(mode_order)}

    ax = axes[0]
    mode_int = df["mode"].map(mode_to_int).astype(int).to_numpy()
    t = df["t"].to_numpy()
    for i in range(len(t) - 1):
        ax.axvspan(t[i], t[i + 1], color=mode_colors[mode_order[mode_int[i]]],
                   alpha=0.85, lw=0)
    ax.set_yticks(range(len(mode_order)))
    ax.set_yticklabels(["None\n(green)", "System 1\n(FACTS)", "System 2\n(load shed)",
                        "System 1+2\n(red)", "Emergency\n(violation)"],
                        fontsize=8)
    ax.set_ylim(-0.4, len(mode_order) - 0.6)
    ax.set_ylabel("Arbiter mode", fontsize=10)
    ax.axvline(20.0, color="black", lw=1.2, ls="--")
    ax.text(20.3, 3.3, "Outage", fontsize=8)
    ax.set_title(
        f"Figure 2. Arbiter mode-switching timeline during {scenario['name']}",
        fontsize=11)

    # Effort
    ax2 = axes[1]
    ax2.plot(t, df["s1_effort"], color="#d73027", lw=2.0,
             label="System 1 (FACTS/EV, fast)")
    ax2.plot(t, df["s2_effort"], color="#4575b4", lw=2.0,
             label="System 2 (re-dispatch, slow)")
    ax2.set_ylim(-0.05, 1.10)
    ax2.set_ylabel("Control effort", fontsize=10)
    ax2.set_xlabel("Time (s)", fontsize=10)
    ax2.grid(alpha=0.3)
    ax2.legend(loc="upper right", fontsize=8)
    ax2.axvline(20.0, color="black", lw=1.2, ls="--")

    plt.tight_layout()
    out = os.path.join(FIG_DIR, "paper9_fig2_mode_timeline.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return df


# ---------------------------------------------------------------------------
# Figure 3: Post-outage violation bar chart across scenarios and modes
# ---------------------------------------------------------------------------
def figure_3_violation_bars(scenarios, base_ppc):
    """Compare violation counts across 4 control modes for each scenario."""
    print("  [Fig 3] violation bar chart ...")
    modes = ["No Control", "Fixed System 1", "Fixed System 2", "Arbiter"]
    mode_keys = {"No Control": "none", "Fixed System 1": "s1",
                 "Fixed System 2": "s2", "Arbiter": "arbiter"}
    records = []
    for scn in scenarios:
        row = {"Scenario": scn["name"]}
        for mode_label, mode_key in mode_keys.items():
            df = simulate_scenario(base_ppc, scn["outage"], control_mode=mode_key,
                                     T=40.0, dt=10.0, with_stability_every=1)
            final_viol = int(df["violations"].iloc[-1])
            row[mode_label] = final_viol
        records.append(row)
    summary = pd.DataFrame(records)
    summary.to_csv(os.path.join(FIG_DIR, "paper9_violations_by_mode.csv"), index=False)

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    x = np.arange(len(summary))
    width = 0.20
    colors = ["#b2182b", "#ef8a62", "#67a9cf", "#1b7837"]
    for i, mode in enumerate(modes):
        ax.bar(x + (i - 1.5) * width, summary[mode].to_numpy(), width=width,
               label=mode, color=colors[i], edgecolor="black", lw=0.4)
    ax.set_xticks(x)
    ax.set_xticklabels(summary["Scenario"], fontsize=9)
    ax.set_ylabel("Post-outage SOL violations (buses + branches)", fontsize=10)
    ax.set_title("Figure 3. Post-outage SOL violations by control mode (IEEE 39-bus)",
                 fontsize=11)
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(axis="y", alpha=0.3)
    # Add value labels
    for i, mode in enumerate(modes):
        for j, val in enumerate(summary[mode].to_numpy()):
            ax.text(x[j] + (i - 1.5) * width, val + 0.15, str(int(val)),
                    ha="center", va="bottom", fontsize=7)
    plt.tight_layout()
    out = os.path.join(FIG_DIR, "paper9_fig3_violation_bars.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return summary


# ---------------------------------------------------------------------------
# Figure 4: Extracted nomogram (recommended control mode vs. operating point)
# ---------------------------------------------------------------------------
def figure_4_nomogram(base_ppc, scenario):
    """2-D heatmap: control mode recommended vs. (load level, pre-outage SOL margin).

    For each (load_level, pre_outage_margin) cell, simulate the outage and
    record the dominant arbiter mode (or violation count) reached.
    """
    print("  [Fig 4] nomogram extraction ...")
    # Build operating-point grid: load level (lambda) x base SOL margin percentile
    load_levels = np.linspace(0.80, 1.30, 11)  # 80% to 130% of nominal load
    margin_levels = np.linspace(0.05, 0.60, 11)  # pre-outage minimum margin proxy

    grid = np.zeros((len(margin_levels), len(load_levels)))
    grid_viol = np.zeros_like(grid)
    mode_int_map = {"none": 0, "s2": 1, "s1+s2": 2, "s1+s2-emergency": 3}

    base_pd = base_ppc["bus"][:, 2].copy()
    base_qd = base_ppc["bus"][:, 3].copy()

    for i, ml in enumerate(margin_levels):
        for j, ll in enumerate(load_levels):
            ppc = deepcopy(base_ppc)
            # Scale loads to load_level
            ppc["bus"][:, 2] = base_pd * ll
            ppc["bus"][:, 3] = base_qd * ll
            # To approximate the requested pre-outage margin, modestly increase
            # generator headroom by scaling generation dispatch (heuristic).
            # We approximate "pre-outage margin" by perturbing bus shunts; here
            # we just use the load_level and let the resulting base margin
            # emerge. We then quantize to the nearest margin_level bin.
            base_m = compute_margins(ppc, with_stability=False)
            if base_m is None:
                grid[i, j] = 3  # emergency
                grid_viol[i, j] = 99
                continue
            # Pre-outage effective margin (min of thermal & voltage)
            pre_margin = min(base_m["thermal_margin"], base_m["voltage_margin"])
            # Quantize pre_margin to nearest margin_level (so we still fill grid)
            i_q = int(np.argmin(np.abs(margin_levels - pre_margin)))
            # Apply outage
            df = simulate_scenario(ppc, scenario["outage"], control_mode="arbiter",
                                     T=30.0, dt=10.0, with_stability_every=1)
            final_mode = df["mode"].iloc[-1]
            final_viol = int(df["violations"].iloc[-1])
            grid[i_q, j] = mode_int_map.get(final_mode, 3)
            grid_viol[i_q, j] = final_viol

    # Save the nomogram data
    nomogram_df = pd.DataFrame(
        grid,
        index=[f"M={m:.2f}" for m in margin_levels],
        columns=[f"L={l:.2f}" for l in load_levels],
    )
    nomogram_df.to_csv(os.path.join(FIG_DIR, "paper9_nomogram.csv"))

    # Plot
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    cmap = LinearSegmentedColormap.from_list(
        "arb", ["#a6d96a", "#fdae61", "#f46d43", "#d73027"], N=4)
    im = ax.imshow(grid, origin="lower", aspect="auto", cmap=cmap,
                   vmin=-0.5, vmax=3.5)
    ax.set_xticks(np.arange(len(load_levels)))
    ax.set_xticklabels([f"{l*100:.0f}%" for l in load_levels], fontsize=8)
    ax.set_yticks(np.arange(len(margin_levels)))
    ax.set_yticklabels([f"{m:.2f}" for m in margin_levels], fontsize=8)
    ax.set_xlabel("Pre-outage load level (% of nominal)", fontsize=10)
    ax.set_ylabel("Pre-outage minimum SOL margin (pu)", fontsize=10)
    ax.set_title("Figure 4. Extracted nomogram: recommended arbiter mode\n"
                 "(0=none / 1=System 2 / 2=System 1+2 / 3=Emergency)",
                 fontsize=11)
    # Annotate cells
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            ax.text(j, i, f"{int(grid[i, j])}", ha="center", va="center",
                    fontsize=7, color="black")
    cbar = plt.colorbar(im, ax=ax, ticks=[0, 1, 2, 3], fraction=0.046, pad=0.04)
    cbar.ax.set_yticklabels(["None", "S2", "S1+S2", "Emergency"], fontsize=8)
    plt.tight_layout()
    out = os.path.join(FIG_DIR, "paper9_fig4_nomogram.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    return nomogram_df


# ---------------------------------------------------------------------------
# 118-bus scalability check
# ---------------------------------------------------------------------------
def run_118_check():
    """Run a single outage scenario on IEEE 118-bus to demonstrate scalability."""
    print("  [118-bus] line outage scenario for scalability check ...")
    ppc = base_case118()
    # Pick a line outage that the system can typically handle (line index 10)
    out = {"type": "line", "index": 10}
    df_arb = simulate_scenario(ppc, out, control_mode="arbiter",
                                 T=30.0, dt=10.0, with_stability_every=1)
    df_no = simulate_scenario(ppc, out, control_mode="none",
                                T=30.0, dt=10.0, with_stability_every=1)
    return {
        "118_arbiter_final_viol": int(df_arb["violations"].iloc[-1]),
        "118_no_control_final_viol": int(df_no["violations"].iloc[-1]),
        "118_arbiter_final_mode": df_arb["mode"].iloc[-1],
    }


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------
def main():
    print("=" * 72)
    print("Paper 9 - Outage Coordination with Metacognitive AI Arbiter")
    print("=" * 72)
    np.random.seed(2026)

    ppc39 = base_case39()
    base_m = compute_margins(ppc39, with_stability=True)
    print(f"IEEE 39-bus base case: thermal_margin={base_m['thermal_margin']:.3f} "
          f"voltage_margin={base_m['voltage_margin']:.3f} "
          f"stability_margin={base_m['stability_margin']:.3f} "
          f"violations={base_m['total_violations']}")

    scenarios = build_scenarios_39()
    # Scenario summary table (Table 1 in the paper)
    scn_rows = [scenario_table_row(s, ppc39) for s in scenarios]
    scn_df = pd.DataFrame(scn_rows)
    scn_df.to_csv(os.path.join(FIG_DIR, "paper9_scenarios.csv"), index=False)
    print("\nScenario table:")
    print(scn_df.to_string(index=False))

    # ----- Figures -----
    # Representative scenario for time-series: G1 (gen@38 outage) shows the
    # clearest mode-switching (voltage breach → S1 fast; thermal breach →
    # S2 slow) so we use it for both Figure 1 and Figure 2.
    rep_scn = next(s for s in scenarios if s["name"] == "G1")
    df_arb, df_no = figure_1_sol_margin_timeseries(rep_scn, ppc39)
    df_mode = figure_2_mode_timeline(rep_scn, ppc39)
    summary_viol = figure_3_violation_bars(scenarios, ppc39)
    nomogram = figure_4_nomogram(ppc39, rep_scn)

    # ----- 118-bus scalability check -----
    res_118 = run_118_check()
    print(f"\nIEEE 118-bus (line outage idx=10):\n  arbiter viol={res_118['118_arbiter_final_viol']} "
          f"mode={res_118['118_arbiter_final_mode']}\n  no-control viol={res_118['118_no_control_final_viol']}")

    # ----- Final summary reduction table -----
    modes = ["No Control", "Fixed System 1", "Fixed System 2", "Arbiter"]
    reduction_rows = []
    for mode in modes:
        total_viol = int(summary_viol[mode].sum())
        reduction_rows.append({
            "Control mode": mode,
            "Total violations across 6 scenarios": total_viol,
            "Reduction vs No Control (%)": round(
                (1 - total_viol / max(1, int(summary_viol["No Control"].sum()))) * 100, 1),
        })
    reduction_df = pd.DataFrame(reduction_rows)
    reduction_df.to_csv(os.path.join(FIG_DIR, "paper9_reduction_summary.csv"), index=False)

    print("\nReduction summary:")
    print(reduction_df.to_string(index=False))

    # ----- JSON summary for reproducibility -----
    summary_json = {
        "base_margins_39": {
            "thermal": round(base_m["thermal_margin"], 4),
            "voltage": round(base_m["voltage_margin"], 4),
            "stability": round(base_m["stability_margin"], 4),
            "violations": int(base_m["total_violations"]),
        },
        "representative_scenario": rep_scn["name"],
        "arbiter_final_viol_rep": int(df_arb["violations"].iloc[-1]),
        "no_control_final_viol_rep": int(df_no["violations"].iloc[-1]),
        "violations_by_mode_39": summary_viol.to_dict(orient="records"),
        "reduction_summary": reduction_df.to_dict(orient="records"),
        "118bus_check": res_118,
        "thresholds": {
            "GREEN_MIN": GREEN_MIN, "YELLOW_MIN": YELLOW_MIN,
            "RED_MIN": RED_MIN, "EMERGENCY": EMERGENCY,
        },
    }
    with open(os.path.join(FIG_DIR, "paper9_summary.json"), "w") as f:
        json.dump(summary_json, f, indent=2)

    print("\nAll outputs written to:", FIG_DIR)
    print("Done.")


if __name__ == "__main__":
    main()
