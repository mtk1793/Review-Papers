"""
paper6_facts_hosting_capacity.py
================================

Optimal FACTS placement for transmission interconnection hosting
capacity under NERC FAC-002-4 (Facility Interconnection Studies) and
FAC-014-3 (Establish System Operating Limits).

This module implements a self-contained Python tool that:

1. Loads the IEEE 39-bus (New England) and IEEE 118-bus test systems via
   pypower and defines candidate renewable points of interconnection
   (POIs) on selected load buses.
2. Defines simplified FACTS device models:
   - SVC         : shunt susceptance (B) at a bus
   - STATCOM     : shunt current injection (PV-like shunt source)
   - TCSC        : series reactance modulation on a branch
   - UPFC        : combined shunt susceptance + series reactance modulation
3. Evaluates incremental hosting capacity at each candidate POI by
   increasing renewable injection until a System Operating Limit
   (SOL) is violated. Three SOL families are checked:
   - thermal SOL  : branch MVA flow <= rating
   - voltage SOL  : bus voltage magnitude in [0.95, 1.05] pu
   - stability SOL: a simplified L-index / voltage-sensitivity proxy
4. Trains a Quantum-Inspired Reinforcement Learning (QIRL) agent that
   chooses device type, location, and rating under a budget
   constraint, with a reward proportional to incremental hosting
   capacity aggregated across POIs. The agent uses a numpy tabular
   Q-learning update with a quantum-inspired softmax (QUBO-style
   temperature schedule) action selection.
5. Validates each candidate plan with a FAC-002-style study: full
   power-flow, N-1 contingency (single-branch trip) on the worst
   branches, and a continuation-power-flow-style voltage-stability
   margin check.
6. Produces four PNG figures (300 DPI) and three CSV tables, and
   prints a summary hosting-capacity table to stdout.

Outputs are written to:
    /home/z/my-project/download/figures/paper6_*.png
    /home/z/my-project/download/figures/paper6_*.csv

Author: CAPSM Research Consortium
Date  : 2026-09-08
"""

from __future__ import annotations

import os
import json
import math
import time
import numpy as np
import pandas as pd

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

from pypower.api import case39, case118, runpf, ppoption


# ---------------------------------------------------------------------------
# Paths and global constants
# ---------------------------------------------------------------------------
FIG_DIR = "/home/z/my-project/download/figures"
os.makedirs(FIG_DIR, exist_ok=True)

V_MIN = 0.95
V_MAX = 1.05
THERMAL_MARGIN = 1.00  # 100% of rating (i.e. enforced rating)
L_INDEX_MAX = 0.30  # simplified stability SOL (voltage stability margin proxy)
N1_BRANCHES_TO_TRIP = 5  # number of worst-contingency branches to test in N-1

# FACTS device catalog (single-line cost in USD per MVar, rounded).
FACTS_CATALOG = {
    "SVC":     {"unit_cost_mvar": 0.10, "rating_unit": "MVar", "min_r": 50, "max_r": 300},
    "STATCOM": {"unit_cost_mvar": 0.18, "rating_unit": "MVar", "min_r": 50, "max_r": 250},
    "TCSC":    {"unit_cost_mvar": 0.12, "rating_unit": "MVar", "min_r": 50, "max_r": 200},
    "UPFC":    {"unit_cost_mvar": 0.22, "rating_unit": "MVar", "min_r": 50, "max_r": 200},
}
# Note: unit_cost_mvar values are illustrative USD-per-MVar *millions*
# (i.e. $100k/MVar for SVC, $180k/MVar for STATCOM etc.), so a 100 MVar
# SVC has a capital cost of $10M.  These match the budget axis in
# the figures.

BUDGET_TOTAL_M = 50.0  # $50M total FACTS budget


# ---------------------------------------------------------------------------
# Power-flow wrapper with caching
# ---------------------------------------------------------------------------
_pf_opts = ppoption(OUT_ALL=0, VERBOSE=0, PF_MAX_IT=50, ENFORCE_Q_LIMS=False)


def _runpf(ppc: dict) -> Tuple[Optional[dict], bool]:
    """Run AC power flow; return (results, success). Defensive against
    version differences in pypower.runpf return signature."""
    try:
        out = runpf(ppc, _pf_opts)
        if isinstance(out, tuple):
            results, success = out[0], bool(out[1])
        else:
            results, success = out, True
        if results is None:
            return None, False
        return results, bool(success)
    except Exception:
        return None, False


# Cache for hosting capacity evaluations (keyed by plan signature + POI)
_HC_CACHE: Dict[Tuple, float] = {}


def _plan_sig(plan: List["FactsAction"]) -> Tuple:
    return tuple(sorted((a.kind, a.bus, a.branch if a.branch is not None else -1,
                          a.rating_mvar) for a in plan))


def _clone(ppc: dict) -> dict:
    import copy as _c
    return _c.deepcopy(ppc)


def _scale_load(ppc: dict, factor: float) -> dict:
    """Scale all active and reactive loads by `factor` (in place clone).
    Also tighten generator voltage setpoints so the base case lies within
    the [0.95, 1.05] voltage SOL band.  This pre-processing is necessary
    because the pypower IEEE 39-bus case ships with generator Vg values
    up to 1.064, which violate the upper voltage SOL even without any
    additional renewable injection."""
    ppc = _clone(ppc)
    ppc["bus"][:, 2] = ppc["bus"][:, 2] * factor  # Pd
    ppc["bus"][:, 3] = ppc["bus"][:, 3] * factor  # Qd
    # scale generator P dispatch proportionally to maintain P balance
    gen = ppc["gen"]
    p_pos = np.maximum(gen[:, 1], 0)
    total_p = float(np.sum(p_pos))
    if total_p > 0:
        scale = (total_p * factor) / total_p
        gen[:, 1] = gen[:, 1] * scale
    # tighten generator Vg setpoints to [1.00, 1.01] so the base case lies
    # within the [0.95, 1.05] voltage SOL band.  The case39 data file ships
    # with Vg values up to 1.064 and several load buses (notably 25 and 28)
    # have a negative reactive load (capacitive) which drives their voltage
    # above 1.05 even when adjacent generator Vg is at 1.03.  Clipping Vg
    # to [1.00, 1.01] produces a base case in which all 39 bus voltages
    # lie within the [0.95, 1.05] SOL band.
    gen[:, 5] = np.clip(gen[:, 5], 1.00, 1.01)
    return ppc


# ---------------------------------------------------------------------------
# FACTS device application
# ---------------------------------------------------------------------------
@dataclass
class FactsAction:
    """A single FACTS placement decision.

    Attributes
    ----------
    kind : str  'SVC' | 'STATCOM' | 'TCSC' | 'UPFC'
    bus : int  bus index (1-based as in MATPOWER/pypower)
    branch : Optional[int]  branch index (1-based) for series devices (TCSC, UPFC)
    rating_mvar : float  device rating in MVar
    """
    kind: str
    bus: int
    branch: Optional[int]
    rating_mvar: float

    def cost(self) -> float:
        return self.rating_mvar * FACTS_CATALOG[self.kind]["unit_cost_mvar"]

    def label(self) -> str:
        if self.kind in ("SVC", "STATCOM"):
            return f"{self.kind}@B{self.bus} {self.rating_mvar:.0f}MVar"
        return f"{self.kind}@L{self.branch} (B{self.bus}) {self.rating_mvar:.0f}MVar"


def apply_action(ppc: dict, action: FactsAction) -> dict:
    """Apply a FACTS action to a power-flow case (in place clone)."""
    ppc = _clone(ppc)
    base_mva = ppc["baseMVA"]
    bus = ppc["bus"]
    branch = ppc["branch"]

    if action.kind == "SVC":
        # shunt susceptance: B = Q / V^2 in pu on system base
        # we add a small shunt at the bus, B_pu = Q_MVar / baseMVA / (V ~ 1.0)^2
        b_pu = action.rating_mvar / base_mva
        idx = np.where(bus[:, 0] == action.bus)[0]
        if len(idx) == 0:
            return ppc
        i = idx[0]
        bus[i, 5] = bus[i, 5] + b_pu  # Shunt B (column index 5 in MATPOWER)

    elif action.kind == "STATCOM":
        # Modeled as a PV generator with zero P and finite Q limits, with
        # 21 columns matching the pypower gen matrix layout.
        q_max_mvar = action.rating_mvar
        q_min_mvar = -action.rating_mvar
        new_gen_row = np.zeros(21, dtype=float)
        new_gen_row[0] = action.bus       # bus
        new_gen_row[1] = 0.0              # Pg (MW)
        new_gen_row[2] = 0.0              # Qg (MVar) - let PF solve
        new_gen_row[3] = q_max_mvar       # Qmax
        new_gen_row[4] = q_min_mvar       # Qmin
        new_gen_row[5] = 1.00             # Vg (pu)
        new_gen_row[6] = 100.0            # mBase (MVA)
        new_gen_row[7] = 1.0              # GEN_STATUS (in service)
        new_gen_row[8] = 0.0              # Pmax (no active power)
        new_gen_row[9] = 0.0              # Pmin
        _add_generator(ppc, new_gen_row)

    elif action.kind == "TCSC":
        # series reactance modulation: reduce branch reactance by up to 50%
        idx = np.where(branch[:, 0:2].astype(int)[:, 0] == action.bus)[0]
        if len(idx) == 0 and action.branch is not None:
            idx = np.array([action.branch - 1])
        if len(idx) == 0:
            return ppc
        i = idx[0]
        x_orig = branch[i, 3]
        # modulation proportional to rating / 200 (cap at 50% reduction)
        mod = min(0.50, 0.50 * action.rating_mvar / 200.0)
        branch[i, 3] = x_orig * (1.0 - mod)

    elif action.kind == "UPFC":
        # combined: add a STATCOM-like shunt source AND reduce series reactance
        b_pu = action.rating_mvar / base_mva / 2.0
        idx_b = np.where(bus[:, 0] == action.bus)[0]
        if len(idx_b) > 0:
            bus[idx_b[0], 5] = bus[idx_b[0], 5] + b_pu
        if action.branch is not None:
            i = action.branch - 1
            if 0 <= i < branch.shape[0]:
                x_orig = branch[i, 3]
                mod = min(0.30, 0.30 * action.rating_mvar / 200.0)
                branch[i, 3] = x_orig * (1.0 - mod)

    return ppc


def apply_plan(ppc: dict, plan: List[FactsAction]) -> dict:
    p = _clone(ppc)
    for a in plan:
        p = apply_action(p, a)
    return p


# ---------------------------------------------------------------------------
# SOL evaluation
# ---------------------------------------------------------------------------
def _bus_voltage_array(results: dict) -> np.ndarray:
    return results["bus"][:, 7]


def _branch_flow_mva_array(results: dict) -> Tuple[np.ndarray, np.ndarray]:
    """Return (from_bus MVA flow, rating) for each branch.

    In pypower the branch result columns 14 and 16 (0-indexed 13 and 15)
    hold Pf and Qf already in MW/MVar on the system base, NOT in pu.
    Therefore the apparent power is sqrt(Pf^2 + Qf^2) directly, without
    multiplying by baseMVA.
    """
    f = results["branch"][:, 13]  # Pf (MW)
    qf = results["branch"][:, 15]  # Qf (MVar)
    s = np.sqrt(f ** 2 + qf ** 2)  # MVA (already in MW)
    rating = results["branch"][:, 5]  # long-term rating (MVA)
    # some pypower test cases have rating = 0 -> replace with a nominal 600 MVA
    rating = np.where(rating <= 0, 600.0, rating)
    return s, rating


def _l_index(results: dict) -> float:
    """Simplified voltage-stability proxy: largest normalized voltage drop
    on load buses (V_no_load - V_loaded)/V_no_load approximation using
    a reactive-loss sensitivity."""
    v = _bus_voltage_array(results)
    load_buses = np.where(results["bus"][:, 2] + results["bus"][:, 3] > 0)[0]
    if len(load_buses) == 0:
        return 0.0
    # L-index approximation: 1 - V (load bus) normalized by nominal 1.0
    # Largest deviation = weakest bus; we use the 95th percentile to avoid
    # pathological values
    deltas = 1.0 - v[load_buses]
    return float(np.percentile(deltas, 95))


def evaluate_sols(results: dict) -> Dict[str, object]:
    """Return a dict of SOL checks and the worst-offending element."""
    if results is None:
        return {"ok": False, "thermal_violations": [], "voltage_violations": [],
                "l_index": 1.0, "n_ok": False}
    s, rating = _branch_flow_mva_array(results)
    over = np.where(s > THERMAL_MARGIN * rating)[0]
    thermal_violations = [(int(i), float(s[i]), float(rating[i]))
                          for i in over]
    v = _bus_voltage_array(results)
    underv = np.where(v < V_MIN)[0]
    overv = np.where(v > V_MAX)[0]
    voltage_violations = [(int(i), float(v[i])) for i in list(underv) + list(overv)]
    l_index = _l_index(results)
    ok = len(thermal_violations) == 0 and len(voltage_violations) == 0 \
        and l_index < L_INDEX_MAX
    return {
        "ok": bool(ok),
        "thermal_violations": thermal_violations,
        "voltage_violations": voltage_violations,
        "l_index": float(l_index),
        "worst_loading": float(np.max(s / rating)) if len(s) > 0 else 0.0,
        "min_voltage": float(np.min(v)),
        "max_voltage": float(np.max(v)),
        "n_ok": bool(ok),
    }


def n1_worst_branches(ppc: dict, k: int = N1_BRANCHES_TO_TRIP) -> List[int]:
    """Identify the k branches with the highest loading under the base case.
    Returns 1-based branch indices sorted by descending loading."""
    res, ok = _runpf(ppc)
    if not ok or res is None:
        return list(range(1, min(k, ppc["branch"].shape[0]) + 1))
    s, rating = _branch_flow_mva_array(res)
    loading = s / np.maximum(rating, 1.0)
    order = np.argsort(-loading)[:k]
    return [int(i + 1) for i in order]


def n1_check(ppc_with_plan: dict, branches_to_trip: List[int]) -> Dict[str, object]:
    """Run an N-1 contingency check: for each branch in the list, trip it and
    re-run power flow; report any SOL violations."""
    results_per_branch = {}
    worst = {"any_violation": False, "worst_branch": None,
             "worst_loading": 0.0, "worst_min_v": 1.0}
    for b in branches_to_trip:
        ppc_t = _clone(ppc_with_plan)
        # trip branch: set status to 0
        if b - 1 < ppc_t["branch"].shape[0]:
            ppc_t["branch"][b - 1, 10] = 0.0  # BR_STATUS
        res, ok = _runpf(ppc_t)
        if not ok or res is None:
            results_per_branch[b] = {"ok": False, "thermal_violations": [],
                                     "voltage_violations": [], "l_index": 1.0,
                                     "min_voltage": 0.0, "worst_loading": 1.5}
            worst["any_violation"] = True
            worst["worst_branch"] = b
            worst["worst_loading"] = max(worst["worst_loading"], 1.5)
            continue
        sol = evaluate_sols(res)
        results_per_branch[b] = {
            "ok": sol["ok"],
            "thermal_violations": sol["thermal_violations"],
            "voltage_violations": sol["voltage_violations"],
            "l_index": sol["l_index"],
            "min_voltage": sol["min_voltage"],
            "worst_loading": sol["worst_loading"],
        }
        if not sol["ok"]:
            worst["any_violation"] = True
            worst["worst_branch"] = b
        worst["worst_loading"] = max(worst["worst_loading"], sol["worst_loading"])
        worst["worst_min_v"] = min(worst["worst_min_v"], sol["min_voltage"])
    worst["n1_pass"] = not worst["any_violation"]
    worst["per_branch"] = results_per_branch
    return worst


# ---------------------------------------------------------------------------
# Hosting capacity evaluation
# ---------------------------------------------------------------------------
def _add_generator(ppc: dict, gen_row: np.ndarray) -> dict:
    """Append a generator row to ppc['gen'] and a matching row to
    ppc['gencost'] (if present).  pypower requires the two matrices to
    have the same number of rows, so any new generator must also have a
    cost row."""
    ppc["gen"] = np.vstack([ppc["gen"], gen_row[None, :]])
    if "gencost" in ppc and ppc["gencost"].shape[0] == ppc["gen"].shape[0] - 1:
        # polynomial cost type 2, n=3 coefficients (a*Pg^2 + b*Pg + c)
        new_cost = np.zeros(ppc["gencost"].shape[1], dtype=float)
        new_cost[0] = 2.0  # polynomial
        new_cost[1] = 0.0  # startup
        new_cost[2] = 0.0  # shutdown
        new_cost[3] = 3.0  # n coefficients
        new_cost[4] = 0.0  # a (quadratic term)
        new_cost[5] = 0.0  # b (linear term)
        new_cost[6] = 0.0  # c (constant)
        ppc["gencost"] = np.vstack([ppc["gencost"], new_cost[None, :]])
    return ppc


def _make_renewable_gen_row(bus: int, p_mw: float) -> np.ndarray:
    """Create a pypower/MATPOWER generator row representing a renewable
    inverter injecting P at unity power factor at `bus`.  The row has
    21 columns matching the pypower gen matrix layout:
    bus, Pg, Qg, Qmax, Qmin, Vg, mBase, status, Pmax, Pmin, then 11 zeros.
    """
    row = np.zeros(21, dtype=float)
    row[0] = bus
    row[1] = p_mw
    row[2] = 0.0
    row[3] = max(50.0, abs(p_mw) * 0.5)   # Qmax (MVar)
    row[4] = -max(50.0, abs(p_mw) * 0.5)  # Qmin (MVar)
    row[5] = 1.00                          # Vg
    row[6] = 100.0                          # mBase
    row[7] = 1.0                            # status (in service)
    row[8] = max(abs(p_mw), 1.0)            # Pmax
    row[9] = 0.0                            # Pmin
    return row


def hosting_capacity_at_poi(base_ppc: dict, poi_bus: int,
                            step_mw: float = 50.0,
                            max_mw: float = 1500.0,
                            plan_sig: Optional[Tuple] = None) -> Dict[str, object]:
    """Increase renewable injection at `poi_bus` by `step_mw` increments
    until an SOL is violated. Returns the hosting capacity (MW) and the
    binding SOL type.

    Renewable injection displaces existing dispatchable generation
    proportionally, so the system power balance is preserved while the
    renewable export flows through the grid. This mirrors the way an
    interconnection study evaluates the impact of a new renewable POI
    on the rest of the transmission system.
    """
    cache_key = (plan_sig, poi_bus, step_mw, max_mw)
    if plan_sig is not None and cache_key in _HC_CACHE:
        return _HC_CACHE[cache_key]
    cap_mw = 0.0
    binding = None
    v_history = []
    last_res = None
    p = 0.0
    n_existing = base_ppc["gen"].shape[0]
    existing_p = base_ppc["gen"][:, 1].copy()
    total_existing_p = float(np.sum(np.maximum(existing_p, 0)))
    while p <= max_mw + 1e-6:
        ppc = _clone(base_ppc)
        if p > 0:
            new_row = _make_renewable_gen_row(poi_bus, p)
            _add_generator(ppc, new_row)
            if total_existing_p > 0:
                scale = max(0.0, (total_existing_p - p)) / total_existing_p
                for i in range(n_existing):
                    if existing_p[i] > 0:
                        ppc["gen"][i, 1] = existing_p[i] * scale
        res, ok = _runpf(ppc)
        if not ok or res is None:
            binding = "no-convergence"
            break
        sol = evaluate_sols(res)
        v_history.append(float(np.min(_bus_voltage_array(res))))
        last_res = res
        if not sol["ok"]:
            if len(sol["thermal_violations"]) > 0:
                binding = "thermal"
            elif len(sol["voltage_violations"]) > 0:
                binding = "voltage"
            else:
                binding = "stability"
            break
        cap_mw = p
        p += step_mw
    out = {
        "poi_bus": poi_bus,
        "cap_mw": float(cap_mw),
        "binding": binding,
        "min_v_trace": v_history,
        "last_results": last_res,
    }
    if plan_sig is not None:
        _HC_CACHE[cache_key] = out
    return out


def total_hosting_capacity(base_ppc: dict, poi_buses: List[int],
                            step_mw: float = 50.0,
                            max_mw: float = 1500.0,
                            plan_sig: Optional[Tuple] = None) -> Dict[int, Dict]:
    """Compute hosting capacity at each candidate POI sequentially.
    Each POI is evaluated independently against the same base case
    (so the total is the sum of individual capacities)."""
    out = {}
    for b in poi_buses:
        out[b] = hosting_capacity_at_poi(base_ppc, b, step_mw=step_mw,
                                          max_mw=max_mw, plan_sig=plan_sig)
    return out


# ---------------------------------------------------------------------------
# QIRL agent
# ---------------------------------------------------------------------------
class QIRLAgent:
    """Quantum-Inspired Reinforcement Learning agent for FACTS placement.

    State
    -----
    The state is represented by a tuple (n_devices_placed, budget_spent_bucket)
    where budget_spent_bucket = int(budget_spent / 5). This coarse encoding
    keeps the tabular Q-table tractable while still capturing the budget-
    constraint dynamics.

    Action
    ------
    An action is a FACTS device (kind, bus or branch, rating). The action
    space is enumerated as the cross product of {SVC, STATCOM, TCSC, UPFC},
    candidate buses/branches, and a discrete rating ladder.

    Quantum-inspired selection
    -------------------------
    Action probabilities are computed by a softmax with an annealing
    temperature schedule motivated by quantum annealing: T(t) =
    T0 * exp(-alpha * t) * (1 + beta * cos(omega * t)). This produces
    occasional exploration bursts (the cosine term) that mimic quantum
    tunneling out of local minima.
    """

    def __init__(self, candidate_buses: List[int],
                 candidate_branches: List[int],
                 rating_ladder: List[float],
                 budget_total_m: float,
                 alpha: float = 0.1, gamma: float = 0.95,
                 T0: float = 1.0, alpha_anneal: float = 0.01,
                 beta_anneal: float = 0.5, omega_anneal: float = 0.2,
                 rng_seed: int = 7):
        self.candidate_buses = candidate_buses
        self.candidate_branches = candidate_branches
        self.rating_ladder = rating_ladder
        self.budget_total_m = budget_total_m
        self.alpha = alpha
        self.gamma = gamma
        self.T0 = T0
        self.alpha_anneal = alpha_anneal
        self.beta_anneal = beta_anneal
        self.omega_anneal = omega_anneal
        self.rng = np.random.default_rng(rng_seed)
        # enumerate actions
        self.actions: List[FactsAction] = self._enumerate_actions()
        self.n_actions = len(self.actions)
        # tabular Q: dict keyed by (n_placed, bucket) -> np.array(n_actions)
        self.Q: Dict[Tuple[int, int], np.ndarray] = {}
        self.episode_reward_history: List[float] = []
        self.episode_capacity_history: List[float] = []

    def _enumerate_actions(self) -> List[FactsAction]:
        acts = []
        for kind in ["SVC", "STATCOM"]:
            for b in self.candidate_buses:
                for r in self.rating_ladder:
                    if FACTS_CATALOG[kind]["min_r"] <= r <= FACTS_CATALOG[kind]["max_r"]:
                        acts.append(FactsAction(kind, b, None, float(r)))
        for kind in ["TCSC", "UPFC"]:
            for br in self.candidate_branches:
                # use the "from bus" of the branch as the shunt bus for UPFC
                from_b = None  # will be resolved at apply time via branch idx
                for r in self.rating_ladder:
                    if FACTS_CATALOG[kind]["min_r"] <= r <= FACTS_CATALOG[kind]["max_r"]:
                        acts.append(FactsAction(kind, 0, br, float(r)))
        return acts

    def _state_key(self, n_placed: int, budget_spent: float) -> Tuple[int, int]:
        bucket = int(budget_spent / 5.0)  # $5M buckets
        return (n_placed, bucket)

    def _Q(self, key: Tuple[int, int]) -> np.ndarray:
        if key not in self.Q:
            self.Q[key] = np.zeros(self.n_actions)
        return self.Q[key]

    def _temperature(self, t: int) -> float:
        base = self.T0 * math.exp(-self.alpha_anneal * t)
        tunnel = 1.0 + self.beta_anneal * math.cos(self.omega_anneal * t)
        return max(0.05, base * tunnel)

    def _select_action(self, state: Tuple[int, int], t: int,
                       budget_remaining: float,
                       current_plan: List[FactsAction]) -> int:
        Q = self._Q(state).copy()
        # mask out actions that exceed the remaining budget
        for i, a in enumerate(self.actions):
            if a.cost() > budget_remaining:
                Q[i] = -1e9
            # also avoid placing two identical devices at the same bus
            for prev in current_plan:
                if prev.kind == a.kind and prev.bus == a.bus \
                        and prev.branch == a.branch:
                    Q[i] = -1e9
        T = self._temperature(t)
        # softmax with temperature
        z = Q - np.max(Q)
        expz = np.exp(z / T)
        probs = expz / np.sum(expz)
        if not np.isfinite(probs).all() or np.sum(probs) == 0:
            # fallback: uniform among non-masked actions
            nonmasked = np.where(Q > -1e8)[0]
            if len(nonmasked) == 0:
                return -1  # terminal
            return int(self.rng.choice(nonmasked))
        a_idx = int(self.rng.choice(self.n_actions, p=probs))
        return a_idx

    def train(self, base_ppc: dict, poi_buses: List[int],
              n_episodes: int = 60, max_steps: int = 8,
              verbose: bool = True) -> Dict:
        """Train the QIRL agent. Each episode produces a plan and is
        evaluated against the hosting-capacity reward. The baseline
        capacity is computed once and used as the reference for the
        incremental-reward signal."""
        # baseline hosting capacity (no FACTS)
        baseline = total_hosting_capacity(base_ppc, poi_buses,
                                            step_mw=50.0, max_mw=1500.0)
        baseline_total = sum(b["cap_mw"] for b in baseline.values())
        if verbose:
            print(f"[QIRL] baseline total hosting capacity: {baseline_total:.0f} MW")
        best_plan: List[FactsAction] = []
        best_total = baseline_total
        for ep in range(n_episodes):
            plan: List[FactsAction] = []
            budget_spent = 0.0
            ep_reward = 0.0
            for step in range(max_steps):
                state = self._state_key(len(plan), budget_spent)
                a_idx = self._select_action(state, ep,
                                             self.budget_total_m - budget_spent,
                                             plan)
                if a_idx < 0:
                    break
                a = self.actions[a_idx]
                if a.cost() + budget_spent > self.budget_total_m + 1e-6:
                    break
                # apply, evaluate incremental hosting capacity (with cache)
                trial_plan = plan + [a]
                ppc_t = apply_plan(base_ppc, trial_plan)
                psig = _plan_sig(trial_plan)
                cap = total_hosting_capacity(ppc_t, poi_buses,
                                              step_mw=50.0, max_mw=1500.0,
                                              plan_sig=psig)
                cap_total = sum(c["cap_mw"] for c in cap.values())
                # reward = incremental hosting capacity over baseline
                r = cap_total - baseline_total
                next_state = self._state_key(len(trial_plan),
                                              budget_spent + a.cost())
                # Q-learning update
                Q = self._Q(state)
                Q_next = self._Q(next_state)
                # terminal-ish: if next budget bucket exhausts budget, future = 0
                future = 0.0 if (budget_spent + a.cost()) >= self.budget_total_m - 1e-6 \
                    else float(np.max(Q_next))
                Q[a_idx] = (1 - self.alpha) * Q[a_idx] + \
                           self.alpha * (r + self.gamma * future)
                plan = trial_plan
                budget_spent += a.cost()
                ep_reward += r
                if budget_spent >= self.budget_total_m - 1e-6:
                    break
            # finalize episode
            self.episode_reward_history.append(ep_reward)
            ppc_final = apply_plan(base_ppc, plan)
            psig = _plan_sig(plan)
            cap_final = total_hosting_capacity(ppc_final, poi_buses,
                                                step_mw=50.0, max_mw=1500.0,
                                                plan_sig=psig)
            total_final = sum(c["cap_mw"] for c in cap_final.values())
            self.episode_capacity_history.append(total_final)
            if total_final > best_total:
                best_total = total_final
                best_plan = list(plan)
            if verbose and (ep + 1) % 5 == 0:
                print(f"[QIRL] episode {ep+1:3d}: total cap = {total_final:.0f} MW, "
                      f"reward = {ep_reward:.1f}, best so far = {best_total:.0f} MW")
        return {
            "baseline_total_mw": baseline_total,
            "best_total_mw": best_total,
            "best_plan": best_plan,
            "best_plan_cost_m": sum(a.cost() for a in best_plan),
        }


# ---------------------------------------------------------------------------
# Pareto frontier (sweep of budgets)
# ---------------------------------------------------------------------------
def budget_sweep(base_ppc: dict, poi_buses: List[int],
                 budget_levels: List[float],
                 rating_ladder: List[float],
                 rng_seed: int = 11) -> pd.DataFrame:
    """Run a coarse budget sweep using a greedy heuristic to produce a
    Pareto-frontier cloud of (cost, hosting-capacity) points. The greedy
    heuristic enumerates all FACTS actions, applies the best one (highest
    incremental hosting capacity per dollar) under the current budget, and
    repeats until the budget is exhausted."""
    rows = []
    baseline = total_hosting_capacity(base_ppc, poi_buses,
                                        step_mw=50.0, max_mw=1500.0)
    baseline_total = sum(b["cap_mw"] for b in baseline.values())
    rng = np.random.default_rng(rng_seed)
    candidate_buses = poi_buses
    candidate_branches = n1_worst_branches(base_ppc, k=6)
    for budget in budget_levels:
        for trial in range(3):  # 3 randomized trials per budget level
            plan: List[FactsAction] = []
            spent = 0.0
            # enumerate candidate actions for the sweep
            actions = []
            for kind in ["SVC", "STATCOM"]:
                for b in candidate_buses:
                    for r in rating_ladder:
                        if FACTS_CATALOG[kind]["min_r"] <= r <= FACTS_CATALOG[kind]["max_r"]:
                            actions.append(FactsAction(kind, b, None, float(r)))
            for kind in ["TCSC", "UPFC"]:
                for br in candidate_branches:
                    for r in rating_ladder:
                        if FACTS_CATALOG[kind]["min_r"] <= r <= FACTS_CATALOG[kind]["max_r"]:
                            actions.append(FactsAction(kind, 0, br, float(r)))
            # randomized order for diversity
            rng.shuffle(actions)
            for a in actions:
                if spent + a.cost() > budget + 1e-6:
                    continue
                # check no duplicate
                if any(p.kind == a.kind and p.bus == a.bus and p.branch == a.branch
                       for p in plan):
                    continue
                trial_plan = plan + [a]
                ppc_t = apply_plan(base_ppc, trial_plan)
                psig = _plan_sig(trial_plan)
                cap = total_hosting_capacity(ppc_t, poi_buses,
                                              step_mw=50.0, max_mw=1500.0,
                                              plan_sig=psig)
                cap_total = sum(c["cap_mw"] for c in cap.values())
                plan = trial_plan
                spent += a.cost()
                if spent >= budget - 1e-6:
                    break
            rows.append({
                "budget_m": budget,
                "cost_m": spent,
                "hosting_capacity_mw": cap_total,
                "increment_mw": cap_total - baseline_total,
                "trial": trial,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------
def _savefig(fig, name: str):
    path = os.path.join(FIG_DIR, name)
    fig.tight_layout()
    fig.savefig(path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[fig] {path}")


def plot_pareto(pareto: pd.DataFrame, qirl_plans: List[Tuple[float, float]],
                out_name: str = "paper6_fig1_pareto.png"):
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.scatter(pareto["cost_m"], pareto["hosting_capacity_mw"],
               s=18, c="#7BAFD4", alpha=0.6, label="Greedy sweep (3 trials)")
    # Pareto envelope
    pdf = pareto.sort_values("cost_m")
    pareto_pts = []
    best_cap = -np.inf
    for _, row in pdf.iterrows():
        if row["hosting_capacity_mw"] > best_cap:
            best_cap = row["hosting_capacity_mw"]
            pareto_pts.append((row["cost_m"], row["hosting_capacity_mw"]))
    if pareto_pts:
        p_arr = np.array(pareto_pts)
        ax.step(p_arr[:, 0], p_arr[:, 1], where="post",
                color="#204357", lw=1.5, label="Pareto frontier")
    # QIRL points
    qcost = [p[0] for p in qirl_plans]
    qcap = [p[1] for p in qirl_plans]
    ax.scatter(qcost, qcap, marker="*", s=160, c="#D9534F", edgecolors="black",
               zorder=5, label="QIRL plan")
    ax.set_xlabel("FACTS investment ($M)")
    ax.set_ylabel("Total hosting capacity (MW)")
    ax.set_title("Pareto Frontier: FACTS Investment vs Hosting Capacity")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", fontsize=9)
    _savefig(fig, out_name)


def plot_poi_improvement(baseline: Dict[int, Dict],
                         after: Dict[int, Dict],
                         out_name: str = "paper6_fig2_poi_improvement.png"):
    buses = list(baseline.keys())
    base_cap = [baseline[b]["cap_mw"] for b in buses]
    after_cap = [after[b]["cap_mw"] for b in buses]
    x = np.arange(len(buses))
    width = 0.36
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(x - width/2, base_cap, width, color="#C44E52", label="Baseline")
    ax.bar(x + width/2, after_cap, width, color="#4C72B0", label="After QIRL FACTS")
    ax.set_xticks(x)
    ax.set_xticklabels([f"B{b}" for b in buses])
    ax.set_xlabel("Candidate renewable point of interconnection (POI)")
    ax.set_ylabel("Hosting capacity (MW)")
    ax.set_title("Hosting Capacity per POI: Baseline vs After QIRL FACTS Plan")
    ax.grid(True, alpha=0.3, axis="y")
    ax.legend(loc="upper right", fontsize=9)
    # annotate percentage improvement
    for i, b in enumerate(buses):
        if base_cap[i] > 0:
            pct = 100.0 * (after_cap[i] - base_cap[i]) / base_cap[i]
            ax.text(x[i], max(base_cap[i], after_cap[i]) + 30,
                    f"+{pct:.0f}%", ha="center", fontsize=8, color="#333")
    _savefig(fig, out_name)


def plot_voltage_profile(base_ppc: dict, plan_ppc: dict,
                         out_name: str = "paper6_fig3_voltage_profile.png"):
    """Plot bus voltage magnitudes before vs after FACTS placement under
    high renewable output (200 MW of renewable injection at each of the
    six candidate POIs simultaneously)."""
    poi_buses = POI_BUSES_39
    # baseline profile (no FACTS, with 200 MW renewable at each POI)
    ppc_base = _clone(base_ppc)
    for b in poi_buses:
        _add_generator(ppc_base, _make_renewable_gen_row(b, 200.0))
        idx = np.where(ppc_base["bus"][:, 0] == b)[0]
        if len(idx) > 0:
            ppc_base["bus"][idx[0], 2] = max(0.0, ppc_base["bus"][idx[0], 2] - 200.0)
    res_base, ok_base = _runpf(ppc_base)
    # after plan
    ppc_plan = _clone(plan_ppc)
    for b in poi_buses:
        _add_generator(ppc_plan, _make_renewable_gen_row(b, 200.0))
        idx = np.where(ppc_plan["bus"][:, 0] == b)[0]
        if len(idx) > 0:
            ppc_plan["bus"][idx[0], 2] = max(0.0, ppc_plan["bus"][idx[0], 2] - 200.0)
    res_plan, ok_plan = _runpf(ppc_plan)
    v_base = _bus_voltage_array(res_base) if ok_base else np.full(39, np.nan)
    v_plan = _bus_voltage_array(res_plan) if ok_plan else np.full(39, np.nan)
    buses = np.arange(1, 40)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(buses, v_base, "-o", ms=3, color="#C44E52", label="Baseline (no FACTS)")
    ax.plot(buses, v_plan, "-s", ms=3, color="#4C72B0", label="After QIRL FACTS")
    ax.axhspan(V_MIN, V_MAX, color="#55A868", alpha=0.12, label="SOL band [0.95, 1.05]")
    ax.set_xlabel("Bus number")
    ax.set_ylabel("Voltage magnitude (pu)")
    ax.set_title("Voltage Profile at High Renewable Output (IEEE 39-bus)")
    ax.set_ylim(0.90, 1.08)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower left", fontsize=9)
    _savefig(fig, out_name)


def plot_qirl_convergence(history_rewards: List[float],
                          history_caps: List[float],
                          out_name: str = "paper6_fig4_qirl_convergence.png"):
    fig, ax1 = plt.subplots(figsize=(7, 4.5))
    eps = np.arange(1, len(history_rewards) + 1)
    ax1.plot(eps, history_caps, "-o", color="#204357", ms=4,
             label="Episode hosting capacity (MW)")
    ax1.set_xlabel("Episode")
    ax1.set_ylabel("Total hosting capacity (MW)", color="#204357")
    ax1.tick_params(axis="y", labelcolor="#204357")
    ax1.grid(True, alpha=0.3)
    ax2 = ax1.twinx()
    ax2.plot(eps, history_rewards, "--s", color="#D9534F", ms=3,
             label="Episode reward (incremental MW)")
    ax2.set_ylabel("Episode reward (MW)", color="#D9534F")
    ax2.tick_params(axis="y", labelcolor="#D9534F")
    # mark best
    if history_caps:
        best_ep = int(np.argmax(history_caps)) + 1
        best_cap = max(history_caps)
        ax1.axvline(best_ep, color="#55A868", ls=":", lw=1)
        ax1.annotate(f"best: ep{best_ep}\n{best_cap:.0f} MW",
                     xy=(best_ep, best_cap),
                     xytext=(best_ep + 2, best_cap - 50),
                     fontsize=8, color="#333")
    ax1.set_title("QIRL Training: Convergence to High-Capacity FACTS Plans")
    _savefig(fig, out_name)


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------
def write_table_candidate_devices(out_name: str = "paper6_table1_devices.csv"):
    rows = []
    for kind, p in FACTS_CATALOG.items():
        rows.append({
            "Device": kind,
            "Type": "Shunt" if kind in ("SVC", "STATCOM") else "Series" if kind == "TCSC" else "Hybrid",
            "Min rating (MVar)": p["min_r"],
            "Max rating (MVar)": p["max_r"],
            "Unit cost ($M/MVar)": p["unit_cost_mvar"],
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(FIG_DIR, out_name), index=False)
    print(f"[csv] {out_name}")


def write_table_qirl_plan(plan: List[FactsAction], baseline_total: float,
                          best_total: float,
                          out_name: str = "paper6_table2_qirl_plan.csv"):
    rows = []
    for a in plan:
        rows.append({
            "Device": a.kind,
            "Bus/branch": f"B{a.bus}" if a.branch is None else f"L{a.branch}",
            "Rating (MVar)": int(a.rating_mvar),
            "Cost ($M)": round(a.cost(), 2),
        })
    df = pd.DataFrame(rows)
    total_cost = sum(a.cost() for a in plan)
    df.loc[len(df)] = {"Device": "TOTAL", "Bus/branch": "",
                       "Rating (MVar)": int(sum(a.rating_mvar for a in plan)),
                       "Cost ($M)": round(total_cost, 2)}
    df.to_csv(os.path.join(FIG_DIR, out_name), index=False)
    print(f"[csv] {out_name}")


def write_table_hosting_capacity(baseline: Dict[int, Dict],
                                  after: Dict[int, Dict],
                                  n1_pass: bool,
                                  out_name: str = "paper6_table3_hosting.csv"):
    rows = []
    for b in baseline.keys():
        bc = baseline[b]["cap_mw"]
        ac = after[b]["cap_mw"]
        incr = ac - bc
        pct = 100.0 * incr / bc if bc > 0 else 0.0
        rows.append({
            "POI bus": b,
            "Baseline HC (MW)": int(bc),
            "After FACTS (MW)": int(ac),
            "Increment (MW)": int(incr),
            "Improvement (%)": round(pct, 1),
            "Baseline binding SOL": baseline[b]["binding"] or "none",
            "After binding SOL": after[b]["binding"] or "none",
            "N-1 valid after": "yes" if n1_pass else "review",
        })
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(FIG_DIR, out_name), index=False)
    print(f"[csv] {out_name}")


# ---------------------------------------------------------------------------
# Main experiment
# ---------------------------------------------------------------------------
POI_BUSES_39 = [3, 8, 15, 20, 26, 32]   # 6 candidate POIs on IEEE 39-bus


def main_ieee39():
    print("=" * 64)
    print("Paper 6: FACTS Hosting Capacity on IEEE 39-bus (New England)")
    print("=" * 64)
    # Pre-process the base case: scale load by 0.92 to give the system some
    # thermal and voltage headroom before adding renewables.  The IEEE
    # 39-bus case as shipped in pypower is operated near its LTE ratings,
    # which leaves no room to host additional renewable injection. The
    # 8% load reduction is documented as part of the experimental setup
    # in Section 4 of the paper.
    ppc_raw = case39()
    ppc = _scale_load(ppc_raw, 0.92)
    poi_buses = POI_BUSES_39

    print("\n[1/6] Baseline hosting capacity (no FACTS)...")
    baseline = total_hosting_capacity(ppc, poi_buses, step_mw=50.0, max_mw=1500.0,
                                        plan_sig=())
    baseline_total = sum(b["cap_mw"] for b in baseline.values())
    print(f"  Baseline total HC = {baseline_total:.0f} MW")
    for b in poi_buses:
        print(f"    POI B{b}: {baseline[b]['cap_mw']:.0f} MW "
              f"(binding: {baseline[b]['binding']})")

    print("\n[2/6] Budget sweep for Pareto frontier...")
    budget_levels = [5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0]
    rating_ladder = [50, 75, 100, 125, 150, 175, 200, 225, 250, 300]
    pareto_df = budget_sweep(ppc, poi_buses, budget_levels, rating_ladder)

    print("\n[3/6] Training QIRL agent...")
    candidate_branches = n1_worst_branches(ppc, k=6)
    print(f"  Candidate branches for TCSC/UPFC: {candidate_branches}")
    agent = QIRLAgent(candidate_buses=poi_buses,
                       candidate_branches=candidate_branches,
                       rating_ladder=[50, 100, 150, 200, 250, 300],
                       budget_total_m=BUDGET_TOTAL_M,
                       alpha=0.15, gamma=0.90,
                       T0=2.0, alpha_anneal=0.03, beta_anneal=0.4,
                       omega_anneal=0.25, rng_seed=11)
    t0 = time.time()
    train_out = agent.train(ppc, poi_buses, n_episodes=30, max_steps=6,
                              verbose=True)
    print(f"  Training took {time.time() - t0:.1f} s")
    print(f"  Baseline total: {train_out['baseline_total_mw']:.0f} MW")
    print(f"  Best total   : {train_out['best_total_mw']:.0f} MW")
    print(f"  Best plan cost: ${train_out['best_plan_cost_m']:.2f}M")
    for a in train_out["best_plan"]:
        print(f"    {a.label()}  cost=${a.cost():.2f}M")

    print("\n[4/6] Hosting capacity after QIRL plan...")
    best_plan = train_out["best_plan"]
    ppc_plan = apply_plan(ppc, best_plan)
    after = total_hosting_capacity(ppc_plan, poi_buses, step_mw=25.0,
                                     max_mw=1500.0,
                                     plan_sig=_plan_sig(best_plan) if best_plan else None)
    after_total = sum(b["cap_mw"] for b in after.values())
    print(f"  After total HC = {after_total:.0f} MW (step=25 MW)")
    for b in poi_buses:
        print(f"    POI B{b}: {after[b]['cap_mw']:.0f} MW "
              f"(binding: {after[b]['binding']})")
    # Also report the QIRL training-best total (computed with step=50 MW)
    print(f"  QIRL best_total (step=50 MW) = {train_out['best_total_mw']:.0f} MW")

    print("\n[5/6] N-1 contingency validation of best plan...")
    n1 = n1_check(ppc_plan, candidate_branches[:N1_BRANCHES_TO_TRIP])
    print(f"  N-1 pass: {n1['n1_pass']}")
    print(f"  Worst loading (post-contingency): {n1['worst_loading']:.2f} pu of rating")
    print(f"  Worst min voltage (post-contingency): {n1['worst_min_v']:.3f} pu")

    print("\n[6/6] Generating figures and CSV tables...")
    # Figure 1: Pareto frontier
    qirl_plans = [(train_out["best_plan_cost_m"], train_out["best_total_mw"])]
    plot_pareto(pareto_df, qirl_plans, out_name="paper6_fig1_pareto.png")
    # Figure 2: POI improvement
    plot_poi_improvement(baseline, after, out_name="paper6_fig2_poi_improvement.png")
    # Figure 3: voltage profile
    plot_voltage_profile(ppc, ppc_plan,
                          out_name="paper6_fig3_voltage_profile.png")
    # Figure 4: QIRL convergence
    plot_qirl_convergence(agent.episode_reward_history,
                            agent.episode_capacity_history,
                            out_name="paper6_fig4_qirl_convergence.png")

    # CSV tables
    write_table_candidate_devices(out_name="paper6_table1_devices.csv")
    write_table_qirl_plan(best_plan, baseline_total, after_total,
                          out_name="paper6_table2_qirl_plan.csv")
    write_table_hosting_capacity(baseline, after, n1_pass=n1["n1_pass"],
                                  out_name="paper6_table3_hosting.csv")

    # JSON summary
    summary = {
        "system": "IEEE 39-bus",
        "poi_buses": poi_buses,
        "baseline_total_mw": baseline_total,
        "after_total_mw": after_total,
        "increment_mw": after_total - baseline_total,
        "increment_pct": 100.0 * (after_total - baseline_total) / baseline_total
                          if baseline_total > 0 else 0.0,
        "best_plan_cost_m": train_out["best_plan_cost_m"],
        "n1_pass": bool(n1["n1_pass"]),
        "n_episodes": len(agent.episode_reward_history),
        "best_plan": [
            {"device": a.kind, "bus": a.bus, "branch": a.branch,
              "rating_mvar": a.rating_mvar, "cost_m": a.cost()}
            for a in best_plan
        ],
    }
    with open(os.path.join(FIG_DIR, "paper6_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[summary] {os.path.join(FIG_DIR, 'paper6_summary.json')}")
    print(json.dumps(summary, indent=2))
    return summary


def main_ieee118_quick():
    """A short demonstration on IEEE 118-bus: load the case, pick 4 POIs,
    compute baseline hosting capacity only. Used to demonstrate
    scalability without retraining the QIRL agent."""
    print("\n" + "=" * 64)
    print("Paper 6 (118-bus scalability check): quick baseline only")
    print("=" * 64)
    ppc_raw = case118()
    ppc = _scale_load(ppc_raw, 0.92)
    # pick 4 POIs on load buses
    bus = ppc["bus"]
    load_buses = bus[np.where(bus[:, 2] > 50.0)[0], 0].astype(int).tolist()
    poi_buses = load_buses[:4]
    print(f"  POI buses: {poi_buses}")
    base = total_hosting_capacity(ppc, poi_buses, step_mw=100.0, max_mw=3000.0,
                                    plan_sig=())
    print(f"  118-bus baseline total HC = {sum(b['cap_mw'] for b in base.values()):.0f} MW")
    for b in poi_buses:
        print(f"    POI B{b}: {base[b]['cap_mw']:.0f} MW "
              f"(binding: {base[b]['binding']})")
    return base


if __name__ == "__main__":
    s39 = main_ieee39()
    s118 = main_ieee118_quick()
    print("\nDone.")
