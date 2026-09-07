#!/usr/bin/env python3
"""
Paper 8: Coordinated EV V2G and Undervoltage Load Shedding (UVLS)
for NERC PRC-010-2 Compliance in Weak Transmission Networks.

This script implements:
  1. EV V2G model: reactive power support (Q injection) and active
     power curtailment (P reduction) at user-specified buses with a
     first-order response lag and voltage-droop control law.
  2. UVLS staged relay logic with four voltage thresholds, time
     delays, and per-bus load shed fractions consistent with NERC
     PRC-010-2 / IEEE C37.117 practice.
  3. Voltage stability margin via loading-margin bisection using a
     custom bisection loop (scipy.optimize.bisect is also imported
     and used as a cross-check).
  4. Severe contingency: a line trip combined with a load ramp that
     pushes the system toward voltage collapse.
  5. Quasi-static time-domain simulation of the coupled EV V2G +
     UVLS response.
  6. Four 300-DPI matplotlib figures and three CSV summary tables
     for reproducibility.

Outputs (paths under /home/z/my-project/download/):
  figures/paper8_fig1_voltage_trajectory.png
  figures/paper8_fig2_uvls_mw_vs_ev.png
  figures/paper8_fig3_stability_margin.png
  figures/paper8_fig4_sensitivity_heatmap.png
  figures/paper8_uvls_summary.csv
  figures/paper8_stability_margin.csv
  figures/paper8_sensitivity.csv

Author: Paper 8 subagent (academic producer).
Date: 2026-09-08.
"""

from __future__ import annotations

import copy
import os
import warnings
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.optimize import bisect  # used for stability-margin cross-check

from pypower.api import case39, case118, runpf, ppoption

# Suppress pypower SyntaxWarnings from internal modules
warnings.filterwarnings("ignore", category=SyntaxWarning)

FIG_DIR = "/home/z/my-project/download/figures"
os.makedirs(FIG_DIR, exist_ok=True)

# =============================================================================
# Configuration constants
# =============================================================================

# EV V2G model parameters
EV_Q_PER_EV_KVAR: float = 3.3      # reactive capability per EV (kVAR)
EV_P_PER_EV_KW:   float = 6.6      # active curtailment per EV (kW)
EV_V_REF:         float = 0.95     # voltage reference for V2G droop (pu)
EV_K_Q:           float = 4.0      # reactive droop gain (unitless)
EV_K_P:           float = 1.5      # active droop gain (unitless)

# UVLS staged relay settings: (name, V_threshold_pu, time_delay_s, pct_load_shed)
UVLS_STAGES: List[Tuple[str, float, float, float]] = [
    ("S1", 0.90, 10.0, 0.07),
    ("S2", 0.85,  3.0, 0.10),
    ("S3", 0.80,  1.0, 0.15),
    ("S4", 0.75,  0.5, 0.20),
]

# Severe contingency parameters
SEVERE_BRANCH_TRIP: int = 24       # branch index 24 = line 15-16 in IEEE 39-bus
TRIP_TIME: float = 2.0             # seconds after simulation start
LOAD_RAMP_FINAL: float = 1.20      # 20 % load increase by end of ramp
LOAD_RAMP_START: float = 2.0       # ramp starts at the same time as the line trip
LOAD_RAMP_DURATION: float = 8.0    # ramp duration (s)
SIM_TOTAL_TIME: float = 30.0       # total simulation horizon (s)
SIM_DT: float = 0.2                # time-step (s) — quasi-static power-flow

# EV deployment buses (per task spec: buses 3, 8, 15)
EV_BUSES: List[int] = [3, 8, 15]

# Fleet-size sweep for Figures 2, 3, 4 (vehicles per deployment)
FLEET_SIZES: List[int] = [0, 10_000, 25_000, 50_000, 75_000, 100_000]

# Penetration sweep for Figure 3 (used as a percentage of system peak load)
PENETRATION_PCT: List[float] = [0.0, 5.0, 10.0, 15.0, 20.0, 25.0]

# Response time sweep for Figure 4 (seconds)
RESPONSE_TIMES: List[float] = [0.10, 0.50, 1.00, 2.00, 5.00]
FLEET_HEATMAP: List[int] = [10_000, 25_000, 50_000, 75_000, 100_000]


# =============================================================================
# Power-flow helpers
# =============================================================================

def make_pf_options(enforce_qlims: bool = False) -> dict:
    """Return pypower options dict for fast, silent power flow."""
    return ppoption(OUT_ALL=0, VERBOSE=0, ENFORCE_Q_LIMS=enforce_qlims)


def run_pp(ppc: dict, enforce_qlims: bool = False) -> Tuple[Optional[dict], bool]:
    """Run a Newton-Raphson power flow; return (results, success)."""
    opt = make_pf_options(enforce_qlims)
    try:
        res, succ = runpf(copy.deepcopy(ppc), opt)
        if isinstance(succ, (list, tuple, np.ndarray)):
            succ = bool(succ[0])
        return res, bool(succ)
    except Exception:
        return None, False


def bus_index(ppc: dict, bus_no: int) -> int:
    """Return the 0-based row index of `bus_no` in the bus matrix."""
    bus_ids = ppc['bus'][:, 0].astype(int)
    matches = np.where(bus_ids == bus_no)[0]
    if matches.size == 0:
        raise ValueError(f"bus {bus_no} not found")
    return int(matches[0])


def bus_numbers(ppc: dict) -> List[int]:
    return [int(b) for b in ppc['bus'][:, 0]]


def get_voltages(res: dict) -> np.ndarray:
    """Bus voltage magnitudes (pu) from a pypower results dict."""
    return res['bus'][:, 7].copy()


def total_load_MW(ppc: dict) -> float:
    """Sum of active load (MW) in the case."""
    return float(ppc['bus'][:, 2].sum())


def find_slack_gen_idx(ppc: dict) -> int:
    """Return the row index of the slack generator (gen bus type==3)."""
    for i in range(ppc['gen'].shape[0]):
        gen_bus = int(ppc['gen'][i, 0])
        bidx = bus_index(ppc, gen_bus)
        if int(ppc['bus'][bidx, 1]) == 3:
            return i
    return 0


def scale_load_and_gen(ppc: dict, lam: float) -> dict:
    """Scale all loads and all non-slack generator Pg by lambda."""
    ppc2 = copy.deepcopy(ppc)
    ppc2['bus'][:, 2] = ppc['bus'][:, 2] * lam
    ppc2['bus'][:, 3] = ppc['bus'][:, 3] * lam
    slack_g = find_slack_gen_idx(ppc)
    for g in range(ppc2['gen'].shape[0]):
        if g == slack_g:
            continue
        ppc2['gen'][g, 1] = ppc['gen'][g, 1] * lam
    return ppc2


# =============================================================================
# EV V2G model
# =============================================================================

@dataclass
class EVFleetState:
    """State of a single EV fleet (P_curtail_MW, Q_inject_MVAr)."""
    P: float = 0.0
    Q: float = 0.0


def ev_v2g_command(V_pu: float,
                   n_evs: int,
                   modes: Tuple[str, ...] = ('Q', 'P'),
                   ev_tau: float = 0.3,
                   dt: float = 0.2,
                   prev: Optional[EVFleetState] = None) -> Tuple[float, float, EVFleetState]:
    """Compute V2G P (curtailment, MW) and Q (injection, MVAr) for one timestep.

    Implements a voltage-droop characteristic with a first-order response lag
    so that EV V2G behaves as a controllable negative load that ramps up
    proportionally to the local voltage deviation below a reference.
    """
    if prev is None:
        prev = EVFleetState()

    Q_max_MVAR = n_evs * EV_Q_PER_EV_KVAR / 1e3
    P_max_MW   = n_evs * EV_P_PER_EV_KW   / 1e3

    V_err = EV_V_REF - V_pu
    if V_err <= 0.0 or n_evs == 0:
        Q_target = 0.0
        P_target = 0.0
    else:
        Q_target = min(EV_K_Q * V_err * Q_max_MVAR, Q_max_MVAR) if 'Q' in modes else 0.0
        P_target = min(EV_K_P * V_err * P_max_MW,   P_max_MW)   if 'P' in modes else 0.0

    alpha = dt / (ev_tau + dt)
    P_state = prev.P + alpha * (P_target - prev.P)
    Q_state = prev.Q + alpha * (Q_target - prev.Q)

    return P_state, Q_state, EVFleetState(P=P_state, Q=Q_state)


# =============================================================================
# UVLS staged relay logic
# =============================================================================

@dataclass
class UVLSRelay:
    """Per-bus staged UVLS relay implementing PRC-010-2 staged tripping."""
    timers: List[float] = field(default_factory=lambda: [0.0] * len(UVLS_STAGES))
    fired:  List[bool]  = field(default_factory=lambda: [False] * len(UVLS_STAGES))
    shed_MW: float = 0.0
    shed_MVAr: float = 0.0

    def update(self, V_pu: float, dt: float, orig_load_MW: float) -> List[Tuple[str, float]]:
        """Advance the relay by one timestep. Returns list of (stage_name, shed_MW)."""
        actions: List[Tuple[str, float]] = []
        for s_idx, (name, V_th, T_delay, pct) in enumerate(UVLS_STAGES):
            if self.fired[s_idx]:
                continue
            if V_pu < V_th:
                self.timers[s_idx] += dt
                if self.timers[s_idx] >= T_delay:
                    shed = pct * orig_load_MW
                    self.shed_MW += shed
                    self.shed_MVAr += shed * 0.484  # assume pf=0.9 for shed load
                    self.fired[s_idx] = True
                    actions.append((name, shed))
            else:
                # Reset the timer if voltage recovers above threshold
                self.timers[s_idx] = 0.0
        return actions


# =============================================================================
# Severe contingency: line trip + load ramp
# =============================================================================

def load_ramp_function(t: float,
                       start: float = LOAD_RAMP_START,
                       duration: float = LOAD_RAMP_DURATION,
                       final: float = LOAD_RAMP_FINAL) -> float:
    """Piecewise-linear load scale: 1.0 -> final over [start, start+duration]."""
    if t <= start:
        return 1.0
    if t >= start + duration:
        return final
    return 1.0 + (final - 1.0) * (t - start) / duration


# =============================================================================
# Quasi-static time-domain simulation
# =============================================================================

def quasi_static_sim(ppc0: dict,
                     line_trip_idx: Optional[int] = SEVERE_BRANCH_TRIP,
                     trip_time: float = TRIP_TIME,
                     load_ramp: Optional[Callable[[float], float]] = None,
                     ev_fleet: Optional[Dict[int, int]] = None,
                     ev_modes: Tuple[str, ...] = ('Q', 'P'),
                     ev_tau: float = 0.3,
                     total_time: float = SIM_TOTAL_TIME,
                     dt: float = SIM_DT,
                     scale_gens: bool = False) -> dict:
    """Run a quasi-static time-domain simulation of EV V2G + UVLS coordination.

    The simulation alternates between (a) building a stressed case with the
    line trip, the load ramp, and EV V2G injections, (b) running a Newton
    power flow, and (c) advancing the UVLS staged relay at every load bus.

    By default (`scale_gens=False`), only loads are scaled by the load ramp
    and the slack generator picks up the imbalance — this mirrors the
    seconds-to-minutes emergency response timeframe of UVLS, before AGC and
    economic dispatch have had time to re-dispatch the unit commitment.
    Setting `scale_gens=True` mirrors a long-term planning CPF scenario in
    which generators are also re-dispatched proportionally.
    """
    if load_ramp is None:
        load_ramp = load_ramp_function
    if ev_fleet is None:
        ev_fleet = {}

    n_steps = int(total_time / dt)
    times = np.arange(n_steps + 1) * dt

    ppc = copy.deepcopy(ppc0)
    n_bus = ppc['bus'].shape[0]
    b_nums = bus_numbers(ppc)
    b_to_i = {b: i for i, b in enumerate(b_nums)}

    # Initial power flow to record pre-contingency voltages
    res, succ = run_pp(ppc)
    if not succ:
        raise RuntimeError("initial power flow did not converge")

    V_hist = np.zeros((n_steps + 1, n_bus))
    V_hist[0, :] = get_voltages(res)

    # Original loads (per bus_no, MW and MVAr)
    orig_P = {b: float(ppc0['bus'][b_to_i[b], 2]) for b in b_nums}
    orig_Q = {b: float(ppc0['bus'][b_to_i[b], 3]) for b in b_nums}

    # Per-bus UVLS relays
    relays: Dict[int, UVLSRelay] = {b: UVLSRelay() for b in b_nums}
    ev_state: Dict[int, EVFleetState] = {b: EVFleetState() for b in ev_fleet}
    ev_keys = list(ev_fleet.keys())
    ev_P_hist = np.zeros((n_steps + 1, len(ev_keys)))
    ev_Q_hist = np.zeros((n_steps + 1, len(ev_keys)))
    uvls_log: List[dict] = []
    total_shed_hist = np.zeros(n_steps + 1)

    for k in range(1, n_steps + 1):
        t = times[k]

        # Contingency: trip the line
        if line_trip_idx is not None and t >= trip_time:
            ppc['branch'][line_trip_idx, 10] = 0

        load_scale = load_ramp(t)

        # Compute EV V2G injections from previous voltage
        ev_inj: Dict[int, Tuple[float, float]] = {}
        for j, b in enumerate(ev_keys):
            i = b_to_i[b]
            V_prev = V_hist[k - 1, i]
            P, Q, new_state = ev_v2g_command(
                V_prev, ev_fleet[b], modes=ev_modes,
                ev_tau=ev_tau, dt=dt, prev=ev_state[b]
            )
            ev_state[b] = new_state
            ev_P_hist[k, j] = P
            ev_Q_hist[k, j] = Q
            ev_inj[b] = (P, Q)

        # Build the step case
        if scale_gens:
            ppc_step = scale_load_and_gen(ppc, load_scale)
        else:
            ppc_step = copy.deepcopy(ppc)
            ppc_step['bus'][:, 2] = ppc['bus'][:, 2] * load_scale
            ppc_step['bus'][:, 3] = ppc['bus'][:, 3] * load_scale
        for i in range(n_bus):
            b = b_nums[i]
            P_load = orig_P[b] * load_scale
            Q_load = orig_Q[b] * load_scale
            # Subtract already-shed load
            P_load -= relays[b].shed_MW
            Q_load -= relays[b].shed_MVAr
            # EV V2G injection reduces net load
            if b in ev_inj:
                P_load = max(0.0, P_load - ev_inj[b][0])
                Q_load -= ev_inj[b][1]
            ppc_step['bus'][i, 2] = P_load
            ppc_step['bus'][i, 3] = Q_load

        res, succ = run_pp(ppc_step)
        if not succ:
            # Hold voltages; do not advance relays (conservative)
            V_hist[k, :] = V_hist[k - 1, :]
            total_shed_hist[k] = total_shed_hist[k - 1]
            continue
        V = get_voltages(res)
        V_hist[k, :] = V

        # UVLS relay update
        for i in range(n_bus):
            b = b_nums[i]
            actions = relays[b].update(V[i], dt, orig_P[b] * load_scale)
            for name, shed in actions:
                uvls_log.append({
                    'time_s': t, 'bus': b, 'stage': name,
                    'V_pu': float(V[i]), 'shed_MW': float(shed)
                })
        total_shed_hist[k] = sum(r.shed_MW for r in relays.values())

    total_shed = float(sum(r.shed_MW for r in relays.values()))
    return {
        't': times,
        'V': V_hist,
        'total_shed_hist': total_shed_hist,
        'ev_P_hist': ev_P_hist,
        'ev_Q_hist': ev_Q_hist,
        'ev_keys': ev_keys,
        'total_shed_MW': total_shed,
        'uvls_log': uvls_log,
        'bus_numbers': b_nums,
        'V0': V_hist[0, :],
    }


# =============================================================================
# Voltage stability margin via loading-margin bisection
# =============================================================================

def pf_converges_at_lambda(ppc: dict, lam: float,
                           ev_fleet: Optional[Dict[int, int]] = None,
                           ev_modes: Tuple[str, ...] = ('Q', 'P'),
                           full_capability: bool = True) -> bool:
    """Return True if the power flow converges at load scaling `lam`."""
    ppc_lam = scale_load_and_gen(ppc, lam)
    if ev_fleet:
        for b, n_evs in ev_fleet.items():
            if n_evs <= 0:
                continue
            i = bus_index(ppc, b)
            if 'Q' in ev_modes and full_capability:
                Q_inj = n_evs * EV_Q_PER_EV_KVAR / 1e3
                ppc_lam['bus'][i, 3] -= Q_inj
            if 'P' in ev_modes and full_capability:
                P_inj = n_evs * EV_P_PER_EV_KW / 1e3
                ppc_lam['bus'][i, 2] = max(0.0, ppc_lam['bus'][i, 2] - P_inj)
    res, succ = run_pp(ppc_lam)
    return bool(succ)


def loading_margin_lambda(ppc: dict,
                          ev_fleet: Optional[Dict[int, int]] = None,
                          ev_modes: Tuple[str, ...] = ('Q', 'P'),
                          max_lambda: float = 2.5,
                          tol: float = 0.005) -> float:
    """Bisect to find the largest load scaling factor at which PF converges."""
    if pf_converges_at_lambda(ppc, max_lambda, ev_fleet, ev_modes):
        return max_lambda
    if not pf_converges_at_lambda(ppc, 1.0, ev_fleet, ev_modes):
        return 1.0

    lo, hi = 1.0, max_lambda
    # First, find an upper bound that fails
    while pf_converges_at_lambda(ppc, hi, ev_fleet, ev_modes) and hi - lo > 1e-3:
        lo = hi
        hi = min(hi * 1.5, max_lambda)
    if pf_converges_at_lambda(ppc, hi, ev_fleet, ev_modes):
        return hi  # converged up to max_lambda

    # Custom bisection (more robust than scipy.optimize.bisect when the
    # boundary function is not perfectly monotonic due to PF solver quirks)
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        if pf_converges_at_lambda(ppc, mid, ev_fleet, ev_modes):
            lo = mid
        else:
            hi = mid
    return lo


def loading_margin_MW(ppc: dict,
                      ev_fleet: Optional[Dict[int, int]] = None,
                      ev_modes: Tuple[str, ...] = ('Q', 'P'),
                      max_lambda: float = 2.5,
                      tol: float = 0.005) -> Tuple[float, float]:
    """Return (lambda_max, margin_MW) where margin_MW is extra load capacity."""
    lam_max = loading_margin_lambda(ppc, ev_fleet, ev_modes, max_lambda, tol)
    base_load = total_load_MW(ppc)
    margin_MW = (lam_max - 1.0) * base_load
    return lam_max, margin_MW


def loading_margin_bisect_scipy(ppc: dict,
                                ev_fleet: Optional[Dict[int, int]] = None,
                                ev_modes: Tuple[str, ...] = ('Q', 'P'),
                                max_lambda: float = 2.5,
                                tol: float = 0.005) -> float:
    """Cross-check using scipy.optimize.bisect (used for reproducibility)."""
    def f(lam: float) -> float:
        return 1.0 if pf_converges_at_lambda(ppc, lam, ev_fleet, ev_modes) else -1.0

    if f(max_lambda) > 0:
        return max_lambda
    if f(1.0) < 0:
        return 1.0
    # Search an upper bracket that fails
    lo, hi = 1.0, max_lambda
    while f(hi) > 0:
        lo = hi
        hi = min(hi * 1.5, max_lambda)
        if hi - lo < 1e-3:
            break
    try:
        return bisect(f, lo, hi, xtol=tol)
    except ValueError:
        return lo


# =============================================================================
# Figure 1: Voltage trajectory at the critical bus during severe contingency
# =============================================================================

def make_fig1_voltage_trajectory(ppc0: dict, critical_bus: int = 15) -> str:
    """Voltage trajectory at `critical_bus` for the severe contingency,
    with and without coordinated EV V2G (50,000 EVs)."""
    print("[Fig 1] voltage trajectory at bus", critical_bus)
    # Scenario A: no V2G
    simA = quasi_static_sim(ppc0, ev_fleet={}, ev_modes=('Q', 'P'),
                            ev_tau=0.3)
    # Scenario B: 50k EVs, Q + P
    fleetB = {b: 50_000 for b in EV_BUSES}
    simB = quasi_static_sim(ppc0, ev_fleet=fleetB, ev_modes=('Q', 'P'),
                            ev_tau=0.3)
    # Scenario C: 50k EVs, Q only (sensitivity)
    simC = quasi_static_sim(ppc0, ev_fleet=fleetB, ev_modes=('Q',),
                            ev_tau=0.3)

    bidx = bus_index(ppc0, critical_bus)
    tA = simA['t']
    vA = simA['V'][:, bidx]
    vB = simB['V'][:, bidx]
    vC = simC['V'][:, bidx]

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.plot(tA, vA, color='#d62728', lw=2.0, label='No V2G (UVLS only)')
    ax.plot(tA, vB, color='#2ca02c', lw=2.0, label='V2G: Q + P (50k EVs)')
    ax.plot(tA, vC, color='#1f77b4', lw=2.0, ls='--',
            label='V2G: Q-only (50k EVs)')

    # UVLS stage thresholds
    for name, V_th, T_d, _ in UVLS_STAGES:
        ax.axhline(V_th, color='grey', lw=0.7, ls=':')
        ax.text(tA[-1] + 0.2, V_th, f' {name}={V_th:.2f}',
                fontsize=8, color='grey', va='center')
    # Line trip marker
    ax.axvline(TRIP_TIME, color='black', lw=0.8, ls='--', alpha=0.6)
    ax.text(TRIP_TIME + 0.1, 1.06, 'Line 15-16 trip + load ramp',
            fontsize=8, rotation=0, va='bottom')

    ax.set_xlim(0, tA[-1] + 2.0)
    ax.set_ylim(0.65, 1.10)
    ax.set_xlabel('Time (s)', fontsize=11)
    ax.set_ylabel(f'Voltage at bus {critical_bus} (pu)', fontsize=11)
    ax.set_title('Figure 1. Voltage trajectory at the critical bus during a '
                 'severe contingency', fontsize=11)
    ax.grid(alpha=0.3)
    ax.legend(loc='lower left', fontsize=9, framealpha=0.95)
    fig.tight_layout()

    out = os.path.join(FIG_DIR, 'paper8_fig1_voltage_trajectory.png')
    fig.savefig(out, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return out


# =============================================================================
# Figure 2: UVLS MW shed vs EV fleet size
# =============================================================================

def make_fig2_uvls_vs_fleet(ppc0: dict) -> str:
    """Total UVLS MW shed as a function of EV fleet size for the severe
    contingency, for three V2G modes."""
    print("[Fig 2] UVLS MW vs EV fleet size")
    results = []
    for n in FLEET_SIZES:
        fleet = {b: n for b in EV_BUSES} if n > 0 else {}
        for mode_label, modes in [('Q+P', ('Q', 'P')),
                                   ('Q-only', ('Q',)),
                                   ('P-only', ('P',))]:
            sim = quasi_static_sim(ppc0, ev_fleet=fleet, ev_modes=modes,
                                  ev_tau=0.3)
            results.append({
                'fleet_size': n,
                'mode': mode_label,
                'total_shed_MW': sim['total_shed_MW'],
                'n_uvls_events': len(sim['uvls_log']),
            })
            print(f"  fleet={n:>6d} mode={mode_label:7s} "
                  f"shed={sim['total_shed_MW']:7.2f} MW events={len(sim['uvls_log'])}")
    df = pd.DataFrame(results)
    df.to_csv(os.path.join(FIG_DIR, 'paper8_uvls_summary.csv'), index=False)

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    palette = {'Q+P': '#2ca02c', 'Q-only': '#1f77b4', 'P-only': '#ff7f0e'}
    for mode in ['Q+P', 'Q-only', 'P-only']:
        sub = df[df['mode'] == mode].sort_values('fleet_size')
        ax.plot(sub['fleet_size'] / 1000, sub['total_shed_MW'],
                marker='o', lw=2.0, color=palette[mode], label=f'V2G: {mode}')
    # Baseline (no V2G) reference line
    base = df[(df['mode'] == 'Q+P') & (df['fleet_size'] == 0)]['total_shed_MW'].iloc[0]
    ax.axhline(base, color='#d62728', ls='--', lw=1.2,
               label=f'Baseline (no V2G): {base:.1f} MW')
    ax.set_xlabel('EV fleet size (thousand vehicles, split across buses 3, 8, 15)',
                  fontsize=11)
    ax.set_ylabel('Total UVLS load shed (MW)', fontsize=11)
    ax.set_title('Figure 2. UVLS MW shed vs EV fleet size for the severe '
                 'contingency', fontsize=11)
    ax.grid(alpha=0.3)
    ax.legend(loc='upper right', fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIG_DIR, 'paper8_fig2_uvls_mw_vs_ev.png')
    fig.savefig(out, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return out, df


# =============================================================================
# Figure 3: Voltage stability margin improvement vs EV penetration
# =============================================================================

def make_fig3_stability_margin(ppc0: dict) -> str:
    """Voltage stability margin (MW) vs EV penetration by V2G mode."""
    print("[Fig 3] Voltage stability margin vs EV penetration")
    base_load = total_load_MW(ppc0)
    rows = []
    for pct in PENETRATION_PCT:
        # Compute fleet size from penetration:
        # penetration = total EV charging power / base load
        ev_total_MW = pct / 100.0 * base_load
        n_evs = int(ev_total_MW * 1e3 / EV_P_PER_EV_KW)
        fleet = {b: n_evs for b in EV_BUSES} if n_evs > 0 else {}
        # Baseline margin (no V2G)
        _, margin_no = loading_margin_MW(ppc0, ev_fleet={}, ev_modes=('Q', 'P'))
        # With V2G: three modes
        for mode_label, modes in [('Q+P', ('Q', 'P')),
                                   ('Q-only', ('Q',)),
                                   ('P-only', ('P',))]:
            lam, margin = loading_margin_MW(ppc0, ev_fleet=fleet, ev_modes=modes)
            rows.append({
                'penetration_pct': pct,
                'fleet_size': n_evs,
                'mode': mode_label,
                'lambda_max': lam,
                'margin_MW': margin,
                'margin_gain_MW': margin - margin_no,
            })
            print(f"  pct={pct:5.1f}% n={n_evs:>7d} mode={mode_label:7s} "
                  f"lambda={lam:.3f} margin={margin:7.2f} MW "
                  f"(gain {margin-margin_no:6.2f} MW)")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(FIG_DIR, 'paper8_stability_margin.csv'), index=False)

    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    palette = {'Q+P': '#2ca02c', 'Q-only': '#1f77b4', 'P-only': '#ff7f0e'}
    # Baseline (no V2G) margin is the same across penetrations
    baseline_margin = df[df['mode'] == 'Q+P'].assign(
        margin_MW=df[df['mode'] == 'Q+P'].apply(
            lambda r: loading_margin_MW(ppc0, ev_fleet={}, ev_modes=('Q', 'P'))[1],
            axis=1))['margin_MW'].iloc[0]
    # Simpler: compute baseline once
    _, baseline_margin = loading_margin_MW(ppc0, ev_fleet={}, ev_modes=('Q', 'P'))
    ax.axhline(baseline_margin, color='#d62728', ls='--', lw=1.2,
               label=f'Baseline (no V2G): {baseline_margin:.0f} MW')
    for mode in ['Q+P', 'Q-only', 'P-only']:
        sub = df[df['mode'] == mode].sort_values('penetration_pct')
        ax.plot(sub['penetration_pct'], sub['margin_MW'],
                marker='s', lw=2.0, color=palette[mode], label=f'V2G: {mode}')

    ax.set_xlabel('EV penetration (% of system peak load, split across buses 3, 8, 15)',
                  fontsize=11)
    ax.set_ylabel('Voltage stability loading margin (MW)', fontsize=11)
    ax.set_title('Figure 3. Voltage stability margin vs EV penetration by V2G mode',
                 fontsize=11)
    ax.grid(alpha=0.3)
    ax.legend(loc='upper left', fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIG_DIR, 'paper8_fig3_stability_margin.png')
    fig.savefig(out, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return out, df


# =============================================================================
# Figure 4: Sensitivity heatmap — UVLS reduction vs response time × fleet size
# =============================================================================

def make_fig4_sensitivity_heatmap(ppc0: dict) -> str:
    """Heatmap of UVLS MW reduction achieved by V2G, swept over response
    time (rows) and fleet size (columns)."""
    print("[Fig 4] sensitivity heatmap")
    # Baseline (no V2G)
    sim_base = quasi_static_sim(ppc0, ev_fleet={}, ev_modes=('Q', 'P'),
                                ev_tau=0.3)
    base_shed = sim_base['total_shed_MW']
    print(f"  baseline UVLS shed: {base_shed:.2f} MW")

    rows = []
    matrix = np.zeros((len(RESPONSE_TIMES), len(FLEET_HEATMAP)))
    for i, tau in enumerate(RESPONSE_TIMES):
        for j, n in enumerate(FLEET_HEATMAP):
            fleet = {b: n for b in EV_BUSES}
            sim = quasi_static_sim(ppc0, ev_fleet=fleet, ev_modes=('Q', 'P'),
                                   ev_tau=tau)
            shed = sim['total_shed_MW']
            reduction = base_shed - shed
            matrix[i, j] = reduction
            rows.append({
                'response_time_s': tau,
                'fleet_size': n,
                'shed_MW': shed,
                'reduction_MW': reduction,
                'n_uvls_events': len(sim['uvls_log']),
            })
            print(f"  tau={tau:4.2f}s n={n:>6d} shed={shed:7.2f} "
                  f"reduction={reduction:7.2f} MW")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(FIG_DIR, 'paper8_sensitivity.csv'), index=False)

    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    im = ax.imshow(matrix, aspect='auto', cmap='YlGn', origin='lower')
    ax.set_xticks(np.arange(len(FLEET_HEATMAP)))
    ax.set_xticklabels([f"{n//1000}k" for n in FLEET_HEATMAP])
    ax.set_yticks(np.arange(len(RESPONSE_TIMES)))
    ax.set_yticklabels([f"{t:.2f}" for t in RESPONSE_TIMES])
    ax.set_xlabel('EV fleet size per bus (thousand vehicles)', fontsize=11)
    ax.set_ylabel('EV V2G response time constant (s)', fontsize=11)
    ax.set_title('Figure 4. UVLS MW reduction achieved by V2G\n'
                 '(rows = response time, cols = fleet size)',
                 fontsize=11)
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label('UVLS MW reduction vs baseline (MW)', fontsize=10)

    # Annotate cells
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            val = matrix[i, j]
            color = 'black' if val > -1e-3 else 'white'
            ax.text(j, i, f"{val:.1f}", ha='center', va='center',
                    color=color, fontsize=9)
    fig.tight_layout()
    out = os.path.join(FIG_DIR, 'paper8_fig4_sensitivity_heatmap.png')
    fig.savefig(out, dpi=300, bbox_inches='tight')
    plt.close(fig)
    return out, df


# =============================================================================
# Main driver
# =============================================================================

def main() -> None:
    print("=" * 78)
    print("Paper 8: Coordinated EV V2G and UVLS for PRC-010-2 Compliance")
    print("=" * 78)

    ppc0 = case39()

    # Sanity: baseline loading margin (no V2G)
    lam0, margin0 = loading_margin_MW(ppc0, ev_fleet={})
    print(f"Baseline IEEE 39-bus: total load = {total_load_MW(ppc0):.1f} MW, "
          f"lambda_max = {lam0:.3f}, margin = {margin0:.1f} MW")

    # Cross-check with scipy.optimize.bisect
    lam_bisect = loading_margin_bisect_scipy(ppc0, ev_fleet={})
    print(f"Cross-check (scipy.optimize.bisect): lambda_max = {lam_bisect:.3f}")

    # Generate the four figures
    fig1_path = make_fig1_voltage_trajectory(ppc0, critical_bus=15)
    print(f"  -> {fig1_path}")
    fig2_path, df2 = make_fig2_uvls_vs_fleet(ppc0)
    print(f"  -> {fig2_path}")
    fig3_path, df3 = make_fig3_stability_margin(ppc0)
    print(f"  -> {fig3_path}")
    fig4_path, df4 = make_fig4_sensitivity_heatmap(ppc0)
    print(f"  -> {fig4_path}")

    # Summary table printed to stdout (Table 3 in the paper)
    print("\n=== Table 3: UVLS MW shed reduction by V2G coordination ===")
    print(df2.to_string(index=False))
    print("\n=== Table 2: Voltage stability margin improvement ===")
    print(df3.to_string(index=False))
    print("\n=== Table 4: Sensitivity (response time × fleet size) ===")
    print(df4.to_string(index=False))

    # Build a compact MW-shed reduction table for the Word doc
    pivot = df2.pivot(index='fleet_size', columns='mode', values='total_shed_MW')
    base = float(pivot.loc[0, 'Q+P'])
    pivot_red = (base - pivot).clip(lower=0.0)
    pivot_red.to_csv(os.path.join(FIG_DIR, 'paper8_reduction_table.csv'))
    print("\nUVLS MW reduction (vs baseline) by fleet size and mode:")
    print(pivot_red.to_string())

    print("\nPaper 8 script complete.")


if __name__ == "__main__":
    main()
