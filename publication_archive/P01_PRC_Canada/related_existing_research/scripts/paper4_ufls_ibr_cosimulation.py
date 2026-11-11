"""
paper4_ufls_ibr_cosimulation.py
================================

Co-simulation framework for Underfrequency Load Shedding (UFLS) adequacy
assessment under high Inverter-Based Resource (IBR) penetration, evaluated
against NERC PRC-006-5 and PRC-006-NPCC-2.

Implements
----------
1. Aggregate system frequency model based on the swing equation
   (2H df/dt = P_m - P_e - D*(f - f0)), expressed in Hz.
2. TGOV1 governor-turbine model (servo, turbine lead-lag, reheat).
3. BESS Fast Frequency Response (FFR) model: droop + synthetic inertia,
   with first-order inverter response and current limits.
4. IBR virtual inertia / fast droop contribution (wind and solar).
5. Staged UFLS relay logic with frequency setpoints and time delays,
   evaluated as a discrete state machine co-simulated with the ODE.
6. Two contingency events: loss-of-largest-generator (LLG) and
   loss-of-tie-line-import (LTI).
7. Adequacy metrics: nadir (Hz), RoCoF (Hz/s), settling time (s),
   MW shed, pass/fail against PRC-006-5 and PRC-006-NPCC-2 thresholds.

The script runs without network access. The IEEE 39-bus system is referenced
for the inertia and load bookkeeping, but the dynamics are solved on an
aggregate single-bus equivalent (center-of-inertia frame) following
Undrill (2018) and Eto et al. (2020).

Outputs (PNG, 300 DPI) are written to
    /home/z/my-project/download/figures/paper4_*.png

Author: CAPSM Research Team
Date  : 2026-09-08
"""

from __future__ import annotations

import os
import json
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from dataclasses import dataclass, field
from typing import List, Tuple, Dict

# ---------------------------------------------------------------------------
# Global constants
# ---------------------------------------------------------------------------
F_NOM = 60.0                       # nominal frequency (Hz)
BASE_MVA = 1000.0                  # system base (MVA) for IEEE 39-bus-class systems
FIG_DIR = "/home/z/my-project/download/figures"
os.makedirs(FIG_DIR, exist_ok=True)

# NERC PRC-006-5 and PRC-006-NPCC-2 adequacy thresholds (illustrative).
PRC0065_MIN_NADIR_HZ   = 58.50   # PRC-006-5: regional minimum nadir floor
PRC0065_MAX_ROCOF_HZS = 1.50     # illustrative envelope (Eto et al., 2020)
PRC0065_RECOVERY_HZ   = 59.95    # recovery to within 0.05 Hz of nominal
NPCC2_MIN_NADIR_HZ    = 59.30   # NPCC PRC-006-NPCC-2: more stringent floor
NPCC2_MAX_ROCOF_HZS  = 0.75     # NPCC tight RoCoF envelope
NPCC2_RECOVERY_HZ    = 59.95


# ---------------------------------------------------------------------------
# Component models
# ---------------------------------------------------------------------------
@dataclass
class TGOV1Governor:
    """TGOV1 steam governor-turbine model with three lead-lag stages.

    State (per unit on machine base):
        x1 : servo/gate position
        x2 : first lead-lag (control)
        x3 : turbine/reheat output -> mechanical power P_m
        pm0_ref : AGC secondary-control reference (integral action)

    Reference: IEEE Std 421.5 and Undrill (2018).  Default time constants are
    typical for a large steam unit.  The model is solved on the center-of-
    inertia frame so the input is the per-unit frequency deviation.
    """
    R: float = 0.05          # droop (pu/pu)
    T1: float = 0.10         # lead (s)
    T2: float = 0.20         # lag (s)
    T3: float = 0.30         # turbine lag (s)
    T4: float = 5.00         # reheat lag (s)
    Pm0: float = 1.0         # initial mechanical power (pu)
    K_agc: float = 0.04     # AGC secondary-control gain (pu/Hz/s, slow)
    Pm_max: float = 1.20     # governor over-load cap (pu)

    def __post_init__(self):
        # Steady-state values
        self.x1 = self.Pm0
        self.x2 = self.Pm0
        self.x3 = self.Pm0
        self.pm0_ref = self.Pm0

    def derivatives(self, delta_f_pu: float) -> Tuple[float, float, float, float]:
        """Return derivatives (dx1, dx2, dx3, dpm0_ref) given freq deviation.

        delta_f_pu = (f_nom - f) / f_nom > 0 when frequency droops.
        The speed governor command is delta_f_pu / R + pm0_ref.  A slow
        integral AGC loop on pm0_ref restores frequency to nominal over a
        30-60 s horizon.
        """
        cmd = delta_f_pu / self.R + self.pm0_ref
        cmd = min(self.Pm_max, max(0.0, cmd))
        dx1 = (cmd - self.x1) / (self.T1 + self.T2 + 1e-6)
        dx2 = (self.x1 - self.x2) / self.T2
        dx3 = (self.x2 - self.x3) / self.T4
        # AGC secondary control: ramp pm0_ref to cancel residual freq error
        # delta_f_pu = (60 - f)/60, so when f<60 -> pm0_ref increases
        dpm0 = self.K_agc * delta_f_pu * F_NOM   # pu/s; slow integral
        dpm0 = max(-0.02, min(0.02, dpm0))      # rate-limited
        return dx1, dx2, dx3, dpm0

    def power(self) -> float:
        return self.x3


@dataclass
class BESSFFR:
    """Battery energy storage system Fast Frequency Response model.

    Power command (pu on system base):
        P_cmd = -K_droop * (f - f0)/f0 - K_si * df/dt / f0
    First-order inverter lag and active power saturation are applied.

    Parameters reflect a lithium-ion BESS with grid-forming capability
    (MIGRATE project, 2020).
    """
    P_rated_pu: float = 0.05     # BESS rating in pu on system base (e.g., 5%)
    K_droop: float = 20.0        # FFR droop gain (pu/pu) -> strong
    K_si: float = 5.0            # synthetic inertia gain (s)
    T_inv: float = 0.05          # inverter time constant (s)
    SOC: float = 0.5             # state of charge (kept constant for short event)

    def __post_init__(self):
        self.P_pu = 0.0

    def update(self, f_hz: float, dfdt_hz_per_s: float, dt: float) -> float:
        """Advance one step; return current BESS power output (pu)."""
        delta_f_pu = (f_hz - F_NOM) / F_NOM
        dfdt_pu = dfdt_hz_per_s / F_NOM
        # Command: positive when frequency is low (i.e., discharge BESS)
        cmd = -self.K_droop * delta_f_pu - self.K_si * dfdt_pu
        # Saturation
        cmd = max(-self.P_rated_pu, min(self.P_rated_pu, cmd))
        # First-order inverter response
        self.P_pu += (cmd - self.P_pu) * (dt / max(self.T_inv, 1e-3))
        return self.P_pu


@dataclass
class IBRFFR:
    """Aggregate Inverter-Based Resource (wind + solar) Fast Frequency Response.

    Virtual inertia and fast droop contributed by grid-following and
    grid-forming IBR.  The contribution scales with the IBR fraction of the
    online generation fleet.
    """
    ibr_fraction: float = 0.0
    K_droop_ibr: float = 3.0    # virtual droop (pu/pu) on IBR-rated basis
    K_si_ibr: float = 0.5      # virtual inertia (s)
    ffr_share: float = 0.10     # fraction of IBRs that are FFR-capable
    # Effective rating of IBR fleet in pu on system base
    P_ibr_pu: float = 0.0     # computed externally

    def power(self, delta_f_pu_pos: float, dfdt_pu: float) -> float:
        """Return IBR FFR output (pu on system base).

        Convention:
            delta_f_pu_pos = (F_NOM - f) / F_NOM  -> positive when frequency
            droops, so the IBR command should be POSITIVE (inject power).
            dfdt_pu = df/dt / F_NOM                -> negative when frequency
            droops, so the synthetic-inertia term should also be POSITIVE.
        """
        P_avail_pu = self.P_ibr_pu * self.ffr_share
        # Both terms are positive when frequency droops
        cmd = (self.K_droop_ibr * delta_f_pu_pos
              - self.K_si_ibr * dfdt_pu)  # dfdt_pu<0 -> term positive
        cmd = max(-P_avail_pu, min(P_avail_pu, cmd))
        return cmd


@dataclass
class UFLSRelay:
    """Staged Underfrequency Load Shedding relay.

    Each stage trips a specified fraction of system load when the bus
    frequency falls below `f_th` for longer than `delay` seconds.

    Schemes are pre-loaded for PRC-006-5 (NERC continental) and
    PRC-006-NPCC-2 (Northeast), following NPCC Directory 1 and the NERC
    PRC-006-5 standard.
    """
    stages: List[Tuple[float, float, float]] = field(default_factory=list)
    armed_below_time: np.ndarray = field(default_factory=lambda: np.zeros(0))
    tripped: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=bool))

    def reset(self):
        n = len(self.stages)
        self.armed_below_time = np.zeros(n)
        self.tripped = np.zeros(n, dtype=bool)

    def step(self, f_hz: float, dt: float, shed_state: np.ndarray) -> float:
        """Advance discrete UFLS state. Returns MW shed in this step (pu)."""
        # Reset armed time if above threshold
        delta_shed_pu = 0.0
        for i, (f_th, delay, frac) in enumerate(self.stages):
            if self.tripped[i]:
                continue
            if f_hz < f_th:
                self.armed_below_time[i] += dt
                if self.armed_below_time[i] >= delay and not shed_state[i]:
                    # Shed a fraction of the remaining load
                    delta_shed_pu += frac
                    shed_state[i] = True
                    self.tripped[i] = True
            else:
                # Re-arm: relax armed time (single-shot per stage)
                if self.armed_below_time[i] > 0:
                    self.armed_below_time[i] = max(0.0,
                                                   self.armed_below_time[i] - dt)
        return delta_shed_pu


def build_ufls_scheme(scheme: str) -> UFLSRelay:
    """Build the staged UFLS relay for either 'PRC0065' or 'NPCC2'."""
    if scheme.upper() == "PRC0065":
        # Six-stage NERC continental profile (illustrative)
        stages = [
            (59.70, 0.10, 0.07),
            (59.50, 0.10, 0.07),
            (59.30, 0.10, 0.07),
            (59.10, 0.10, 0.07),
            (58.90, 0.10, 0.07),
            (58.70, 0.10, 0.07),
        ]
    elif scheme.upper() == "NPCC2":
        # Eight-stage NPCC profile (Directory 1, illustrative aggregate)
        stages = [
            (59.50, 0.10, 0.10),
            (59.40, 0.10, 0.05),
            (59.30, 0.10, 0.05),
            (59.20, 0.10, 0.05),
            (59.10, 0.10, 0.05),
            (59.00, 0.10, 0.05),
            (58.90, 0.10, 0.05),
            (58.80, 0.10, 0.05),
        ]
    else:
        raise ValueError(f"Unknown scheme: {scheme}")
    relay = UFLSRelay(stages=stages)
    relay.reset()
    return relay


# ---------------------------------------------------------------------------
# System model
# ---------------------------------------------------------------------------
@dataclass
class FrequencySystem:
    """Aggregate center-of-inertia frequency model.

    The synchronous inertia H_total is reduced with the IBR fraction because
    IBRs displace synchronous machines that would otherwise provide inertia.
    """
    ibr_fraction: float = 0.0
    H_sync_base_s: float = 6.5      # base synchronous inertia at 0% IBR (s)
    D_load: float = 1.5             # load damping (pu/pu)
    P_load_pu: float = 1.0          # total system load at t=0 (pu)
    bess_pu: float = 0.0           # BESS rating (pu on system base)
    event_p_loss_pu: float = 0.10   # generation lost in contingency (pu)
    event_type: str = "LLG"         # "LLG" or "LTI"
    scheme: str = "PRC0065"

    def setup(self):
        # Effective inertia: synchronous part drops with IBR, IBR has only
        # synthetic inertia (handled separately in IBRFFR block).
        self.H_eff = self.H_sync_base_s * (1.0 - self.ibr_fraction)
        self.H_eff = max(self.H_eff, 0.5)  # floor
        # IBR fleet effective rating on system base
        self.ibr = IBRFFR(ibr_fraction=self.ibr_fraction,
                          P_ibr_pu=self.ibr_fraction * self.P_load_pu)
        self.gov = TGOV1Governor(Pm0=1.0)
        self.bess = BESSFFR(P_rated_pu=self.bess_pu)
        self.ufls = build_ufls_scheme(self.scheme)
        # shed_state[i] indicates whether stage i has tripped
        self.shed_state = np.zeros(len(self.ufls.stages), dtype=bool)
        self.load_shed_pu = 0.0
        self.P_e_pu = self.P_load_pu

    def event_loss_pu(self) -> float:
        """Return per-unit generation loss for the configured event."""
        if self.event_type == "LLG":
            return self.event_p_loss_pu
        elif self.event_type == "LTI":
            return self.event_p_loss_pu * 1.3  # tie-line import loss, larger
        else:
            raise ValueError(self.event_type)


# ---------------------------------------------------------------------------
# Numerical integrator (RK4 with discrete UFLS sampling)
# ---------------------------------------------------------------------------
def simulate(system: FrequencySystem, t_max: float = 30.0,
             dt: float = 0.005) -> Dict[str, np.ndarray]:
    """Run the co-simulation.  Returns a dict of time-series arrays.

    The continuous dynamics are integrated with 4th-order Runge-Kutta at fixed
    step `dt`; the UFLS relay is sampled between steps as a discrete state
    machine (zero-order hold), which is a common co-simulation pattern when
    continuous and discrete subsystems are coupled.
    """
    n = int(t_max / dt)
    t = np.zeros(n + 1)
    f = np.zeros(n + 1)
    f[0] = F_NOM
    p_m = np.zeros(n + 1)
    p_e = np.zeros(n + 1)
    p_bess_arr = np.zeros(n + 1)
    p_ibr_arr = np.zeros(n + 1)
    shed_total = np.zeros(n + 1)
    rocof = np.zeros(n + 1)

    # Discrete event: loss of generation at t_event = 0.5 s
    t_event = 0.5
    loss_pu = system.event_loss_pu()
    shed_remaining = system.P_load_pu  # for tracking remaining load

    def derivatives(t_, f_, gov_x1, gov_x2, gov_x3, pm0_ref):
        """Return (df/dt, dx1/dt, dx2/dt, dx3/dt, dpm0/dt)."""
        # Governor delta_f is per-unit (positive = freq low)
        delta_f_pu = (F_NOM - f_) / F_NOM
        system.gov.pm0_ref = pm0_ref  # so derivatives() uses the candidate value
        dx1, dx2, dx3, dpm0 = system.gov.derivatives(delta_f_pu)
        P_m_gov = gov_x3
        # IBR FFR (needs df/dt)
        dfdt_pu = (P_m_gov - system.P_e_pu) * F_NOM / (2 * system.H_eff) / F_NOM
        P_ibr = system.ibr.power(delta_f_pu, dfdt_pu)
        # Mechanical power after contingency
        if t_ < t_event:
            P_m_total = P_m_gov + P_ibr
        else:
            P_m_total = (P_m_gov - loss_pu) + P_ibr + p_bess_arr_val[0]
        # Power balance -> df/dt
        P_e = (system.P_load_pu - system.load_shed_pu) * \
              (1.0 + system.D_load * (f_ - F_NOM) / F_NOM)
        system.P_e_pu = P_e
        dfdt = (P_m_total - P_e) * F_NOM / (2 * system.H_eff)
        return dfdt, dx1, dx2, dx3, dpm0

    # Use a single mutable container for BESS power during the RK4 substep
    p_bess_arr_val = [0.0]

    for i in range(n):
        ti = t[i]
        fi = f[i]
        x1i = system.gov.x1
        x2i = system.gov.x2
        x3i = system.gov.x3
        pm0i = system.gov.pm0_ref

        # ---- RK4 step for continuous states (now includes AGC) ----
        def F(t_, y):
            f_, x1_, x2_, x3_, pm0_ = y
            delta_f_pu = (F_NOM - f_) / F_NOM
            system.gov.pm0_ref = pm0_
            dx1, dx2, dx3, dpm0 = system.gov.derivatives(delta_f_pu)
            P_m_gov = x3_
            dfdt_pu = (P_m_gov - system.P_e_pu) * F_NOM / (2 * system.H_eff) / F_NOM
            P_ibr = system.ibr.power(delta_f_pu, dfdt_pu)
            P_m_total = P_m_gov + P_ibr if t_ < t_event \
                        else (P_m_gov - loss_pu) + P_ibr + p_bess_arr_val[0]
            P_e = (system.P_load_pu - system.load_shed_pu) * \
                  (1.0 + system.D_load * (f_ - F_NOM) / F_NOM)
            dfdt = (P_m_total - P_e) * F_NOM / (2 * system.H_eff)
            return np.array([dfdt, dx1, dx2, dx3, dpm0])

        y0 = np.array([fi, x1i, x2i, x3i, pm0i])
        k1 = F(ti, y0)
        k2 = F(ti + dt / 2, y0 + dt / 2 * k1)
        k3 = F(ti + dt / 2, y0 + dt / 2 * k2)
        k4 = F(ti + dt, y0 + dt * k3)
        y_new = y0 + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)

        f_new = y_new[0]
        system.gov.x1 = y_new[1]
        system.gov.x2 = y_new[2]
        system.gov.x3 = y_new[3]
        system.gov.pm0_ref = max(0.5, min(1.5, y_new[4]))

        # ---- BESS FFR update (sampled at end of step) ----
        dfdt_step = (f_new - fi) / dt
        p_bess_now = system.bess.update(f_new, dfdt_step, dt)
        p_bess_arr_val[0] = p_bess_now
        p_bess_arr[i + 1] = p_bess_now

        # ---- UFLS discrete update ----
        delta_shed = system.ufls.step(f_new, dt, system.shed_state)
        system.load_shed_pu += delta_shed

        # ---- Store ----
        t[i + 1] = ti + dt
        f[i + 1] = f_new
        p_m[i + 1] = system.gov.power()
        # Re-compute P_e at end of step (post-shed)
        P_e_now = (system.P_load_pu - system.load_shed_pu) * \
                  (1.0 + system.D_load * (f_new - F_NOM) / F_NOM)
        p_e[i + 1] = P_e_now
        p_ibr_arr[i + 1] = system.ibr.power(
            (F_NOM - f_new) / F_NOM, (f_new - fi) / dt / F_NOM)
        shed_total[i + 1] = system.load_shed_pu
        rocof[i + 1] = dfdt_step

    # Compute metrics
    metrics = compute_metrics(t, f, rocof, shed_total, system)
    return {
        "t": t, "f": f, "P_m": p_m, "P_e": p_e, "P_bess": p_bess_arr,
        "P_ibr": p_ibr_arr, "shed_pu": shed_total, "rocof": rocof,
        "ufls_stages": system.ufls.stages, "metrics": metrics,
    }


def compute_metrics(t: np.ndarray, f: np.ndarray, rocof: np.ndarray,
                    shed_pu: np.ndarray, system: FrequencySystem) -> Dict:
    """Compute adequacy metrics: nadir, RoCoF, settling time, MW shed."""
    post_event = t >= 0.5
    f_post = f[post_event]
    t_post = t[post_event]
    rocof_post = rocof[post_event]
    nadir = float(np.min(f_post))
    t_nadir = float(t_post[int(np.argmin(f_post))])
    # Maximum absolute RoCoF over the first 1 second after event
    early = (t >= 0.5) & (t <= 1.5)
    max_rocof = float(np.max(np.abs(rocof[early]))) if np.any(early) else 0.0
    # Recovery time: first time after t_nadir that f returns above 59.95 Hz
    # AND stays within [59.90, 60.05] for at least 1 s.  Falls back to the
    # simulation horizon if recovery is not achieved.
    recovery_hz = 59.95
    band = (f_post >= recovery_hz) & (t_post > t_nadir)
    if np.any(band):
        rec_idx = int(np.argmax(band))
        # Verify sustained: check the next 1 s window
        win_end = t_post[rec_idx] + 1.0
        in_win = (t_post >= t_post[rec_idx]) & (t_post <= win_end)
        if np.all(f_post[in_win] >= recovery_hz - 0.05):
            rec_time = float(t_post[rec_idx] - 0.5)
        else:
            rec_time = float(t_post[-1] - 0.5)
    else:
        rec_time = float(t_post[-1] - 0.5)
    mw_shed = float(shed_pu[-1] * BASE_MVA)

    # Adequacy checks
    if system.scheme.upper() == "PRC0065":
        min_nadir = PRC0065_MIN_NADIR_HZ
        max_rocof_thresh = PRC0065_MAX_ROCOF_HZS
    else:
        min_nadir = NPCC2_MIN_NADIR_HZ
        max_rocof_thresh = NPCC2_MAX_ROCOF_HZS
    pass_nadir = nadir >= min_nadir
    pass_rocof = max_rocof <= max_rocof_thresh
    pass_overall = pass_nadir and pass_rocof

    return {
        "nadir_hz": nadir,
        "t_nadir_s": t_nadir,
        "rocof_hz_s": max_rocof,                # actual measured RoCoF
        "max_rocof_threshold": max_rocof_thresh, # standard limit
        "recovery_s": rec_time,
        "mw_shed": mw_shed,
        "min_nadir_threshold": min_nadir,
        "pass_nadir": bool(pass_nadir),
        "pass_rocof": bool(pass_rocof),
        "pass_overall": bool(pass_overall),
        "scheme": system.scheme,
        "ibr_fraction": system.ibr_fraction,
        "bess_pu": system.bess_pu,
        "event_type": system.event_type,
    }


# ---------------------------------------------------------------------------
# Figure 1: Frequency trajectory after loss of largest generator
# ---------------------------------------------------------------------------
def figure_1_trajectory():
    ibr_levels = [0.0, 0.20, 0.40, 0.60]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    for ibr, c in zip(ibr_levels, colors):
        sys = FrequencySystem(ibr_fraction=ibr, event_p_loss_pu=0.12,
                              event_type="LLG", scheme="PRC0065",
                              bess_pu=0.02)
        sys.setup()
        out = simulate(sys, t_max=60.0, dt=0.01)
        ax.plot(out["t"], out["f"], color=c, lw=1.6,
                label=f"{int(ibr*100)}% IBR")
        # mark nadir
        idx = int(np.argmin(out["f"]))
        ax.scatter(out["t"][idx], out["f"][idx], color=c, zorder=5, s=30)
    ax.axhline(58.5, ls="--", color="gray", lw=1.0,
               label="PRC-006-5 minimum nadir (58.5 Hz)")
    ax.axvline(0.5, ls=":", color="black", lw=1.0, label="Loss-of-gen event")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("Figure 1. System frequency trajectory after loss of the "
                 "largest generator\nfor 0/20/40/60% IBR penetration with "
                 "staged UFLS and 20 MW BESS FFR")
    ax.set_xlim(0, 60)
    ax.set_ylim(57.8, 60.2)
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.4)
    plt.tight_layout()
    fp = os.path.join(FIG_DIR, "paper4_fig1_frequency_trajectory.png")
    plt.savefig(fp, dpi=300)
    plt.close()
    print(f"Saved: {fp}")
    return fp


# ---------------------------------------------------------------------------
# Figure 2: Nadir vs IBR penetration
# ---------------------------------------------------------------------------
def figure_2_nadir_vs_ibr():
    ibr_levels = np.arange(0.0, 0.71, 0.05)
    nadirs_no_bess = []
    nadirs_bess = []
    for ibr in ibr_levels:
        # Without BESS
        sys = FrequencySystem(ibr_fraction=ibr, event_p_loss_pu=0.12,
                              event_type="LLG", scheme="PRC0065",
                              bess_pu=0.0)
        sys.setup()
        out = simulate(sys, t_max=60.0, dt=0.01)
        nadirs_no_bess.append(out["metrics"]["nadir_hz"])
        # With 50 MW BESS
        sys = FrequencySystem(ibr_fraction=ibr, event_p_loss_pu=0.12,
                              event_type="LLG", scheme="PRC0065",
                              bess_pu=0.05)
        sys.setup()
        out = simulate(sys, t_max=60.0, dt=0.01)
        nadirs_bess.append(out["metrics"]["nadir_hz"])

    ibr_levels_pct = ibr_levels * 100
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.plot(ibr_levels_pct, nadirs_no_bess, "o-", color="#d62728",
            label="No BESS FFR", lw=1.8, ms=6)
    ax.plot(ibr_levels_pct, nadirs_bess, "s-", color="#2ca02c",
            label="50 MW BESS FFR", lw=1.8, ms=6)
    ax.axhline(PRC0065_MIN_NADIR_HZ, ls="--", color="#1f77b4", lw=1.4,
               label=f"PRC-006-5 floor ({PRC0065_MIN_NADIR_HZ} Hz)")
    ax.axhline(NPCC2_MIN_NADIR_HZ, ls="--", color="#ff7f0e", lw=1.4,
               label=f"PRC-006-NPCC-2 floor ({NPCC2_MIN_NADIR_HZ} Hz)")
    ax.fill_between(ibr_levels_pct, PRC0065_MIN_NADIR_HZ, 57.5,
                    color="red", alpha=0.07)
    ax.set_xlabel("IBR penetration (%)")
    ax.set_ylabel("Frequency nadir (Hz)")
    ax.set_title("Figure 2. Frequency nadir versus IBR penetration after "
                 "loss of the largest generator")
    ax.set_xlim(0, 70)
    ax.set_ylim(57.5, 60.2)
    ax.legend(loc="lower left", fontsize=9)
    ax.grid(True, alpha=0.4)
    plt.tight_layout()
    fp = os.path.join(FIG_DIR, "paper4_fig2_nadir_vs_ibr.png")
    plt.savefig(fp, dpi=300)
    plt.close()
    print(f"Saved: {fp}")
    return fp


# ---------------------------------------------------------------------------
# Figure 3: UFLS stages activation timeline (worst-case event)
# ---------------------------------------------------------------------------
def figure_3_ufls_timeline():
    # Worst-case: 60% IBR + loss of tie-line import
    sys = FrequencySystem(ibr_fraction=0.60, event_p_loss_pu=0.15,
                          event_type="LTI", scheme="NPCC2",
                          bess_pu=0.05)
    sys.setup()
    out = simulate(sys, t_max=30.0, dt=0.005)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(out["t"], out["f"], color="black", lw=1.8,
            label="System frequency")
    # Detect stage trip times
    shed_state_traj = np.zeros((len(out["shed_pu"]), len(sys.ufls.stages)))
    # Recompute stage trip times by re-running relay tracking
    sys2 = FrequencySystem(ibr_fraction=0.60, event_p_loss_pu=0.15,
                           event_type="LTI", scheme="NPCC2", bess_pu=0.05)
    sys2.setup()
    # Simple stage tracking alongside the trajectory
    armed = np.zeros(len(sys2.ufls.stages))
    tripped = np.zeros(len(sys2.ufls.stages), dtype=bool)
    trip_times = [None] * len(sys2.ufls.stages)
    dt_run = 0.005
    for i in range(1, len(out["t"])):
        f_now = out["f"][i]
        for k, (f_th, delay, _) in enumerate(sys2.ufls.stages):
            if tripped[k]:
                continue
            if f_now < f_th:
                armed[k] += dt_run
                if armed[k] >= delay:
                    tripped[k] = True
                    trip_times[k] = out["t"][i]
            else:
                armed[k] = max(0.0, armed[k] - dt_run)
    for k, (f_th, delay, frac) in enumerate(sys2.ufls.stages):
        if trip_times[k] is not None:
            ax.axvline(trip_times[k], color="C%d" % (k % 9), ls="--", lw=1.0,
                       alpha=0.7)
            ax.scatter([trip_times[k]], [f_th], s=80, color="C%d" % (k % 9),
                       zorder=6, edgecolor="black")
            ax.annotate(f"Stage {k+1}\n{int(frac*100)}% @ {f_th:.2f} Hz",
                        xy=(trip_times[k], f_th),
                        xytext=(trip_times[k] + 0.3, f_th + 0.05),
                        fontsize=7)
    ax.axhline(NPCC2_MIN_NADIR_HZ, ls=":", color="red", lw=1.0,
               label=f"NPCC-2 floor ({NPCC2_MIN_NADIR_HZ} Hz)")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("Figure 3. UFLS stage activation timeline for a worst-case "
                 "contingency\n(60% IBR, loss-of-tie-line-import, NPCC PRC-006-NPCC-2)")
    ax.set_xlim(0, 30)
    ax.set_ylim(58.0, 60.2)
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.4)
    plt.tight_layout()
    fp = os.path.join(FIG_DIR, "paper4_fig3_ufls_timeline.png")
    plt.savefig(fp, dpi=300)
    plt.close()
    print(f"Saved: {fp}")
    return fp


# ---------------------------------------------------------------------------
# Figure 4: BESS FFR effect (nadir vs BESS rating)
# ---------------------------------------------------------------------------
def figure_4_bess_effect():
    bess_mw_levels = np.arange(0, 121, 10)
    nadirs_40_ibr = []
    nadirs_60_ibr = []
    for bmw in bess_mw_levels:
        bpu = bmw / BASE_MVA
        for ibr, lst in [(0.40, nadirs_40_ibr), (0.60, nadirs_60_ibr)]:
            sys = FrequencySystem(ibr_fraction=ibr, event_p_loss_pu=0.12,
                                  event_type="LLG", scheme="PRC0065",
                                  bess_pu=bpu)
            sys.setup()
            out = simulate(sys, t_max=60.0, dt=0.01)
            lst.append(out["metrics"]["nadir_hz"])

    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.plot(bess_mw_levels, nadirs_40_ibr, "o-", color="#1f77b4",
            label="40% IBR", lw=1.8, ms=6)
    ax.plot(bess_mw_levels, nadirs_60_ibr, "s-", color="#d62728",
            label="60% IBR", lw=1.8, ms=6)
    ax.axhline(PRC0065_MIN_NADIR_HZ, ls="--", color="black", lw=1.2,
               label=f"PRC-006-5 floor ({PRC0065_MIN_NADIR_HZ} Hz)")
    ax.fill_between(bess_mw_levels, PRC0065_MIN_NADIR_HZ, 57.5,
                    color="red", alpha=0.07)
    ax.set_xlabel("BESS FFR power rating (MW)")
    ax.set_ylabel("Frequency nadir (Hz)")
    ax.set_title("Figure 4. Frequency nadir improvement as a function of "
                 "BESS FFR power rating\n(loss of largest generator)")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, alpha=0.4)
    plt.tight_layout()
    fp = os.path.join(FIG_DIR, "paper4_fig4_bess_effect.png")
    plt.savefig(fp, dpi=300)
    plt.close()
    print(f"Saved: {fp}")
    return fp


# ---------------------------------------------------------------------------
# Adequacy comparison table
# ---------------------------------------------------------------------------
def build_adequacy_table():
    """Build a comparison table across IBR levels, schemes and events."""
    rows = []
    scenarios = []
    for ibr in [0.0, 0.20, 0.40, 0.60, 0.70]:
        for scheme in ["PRC0065", "NPCC2"]:
            for event in ["LLG", "LTI"]:
                for bess in [0.0, 0.05]:
                    sys = FrequencySystem(
                        ibr_fraction=ibr,
                        event_p_loss_pu=0.12 if event == "LLG" else 0.15,
                        event_type=event,
                        scheme=scheme,
                        bess_pu=bess,
                    )
                    sys.setup()
                    out = simulate(sys, t_max=60.0, dt=0.01)
                    m = out["metrics"]
                    rows.append({
                        "IBR %": f"{int(ibr*100)}",
                        "Event": event,
                        "Scheme": scheme,
                        "BESS (MW)": f"{int(bess*BASE_MVA)}",
                        "Nadir (Hz)": f"{m['nadir_hz']:.3f}",
                        "RoCoF (Hz/s)": f"{m['rocof_hz_s']:.3f}",
                        "Recovery (s)": f"{m['recovery_s']:.2f}",
                        "MW shed": f"{m['mw_shed']:.1f}",
                        "Pass": "Y" if m["pass_overall"] else "N",
                    })
    df = pd.DataFrame(rows)
    return df


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------
def main():
    print("=" * 70)
    print("Paper 4: UFLS Adequacy with High IBR Penetration")
    print("Co-simulation driver (CAPSM x NERC PRC-006-5 / PRC-006-NPCC-2)")
    print("=" * 70)

    # Generate figures
    print("\n[1/5] Generating Figure 1 (frequency trajectories) ...")
    figure_1_trajectory()
    print("[2/5] Generating Figure 2 (nadir vs IBR) ...")
    figure_2_nadir_vs_ibr()
    print("[3/5] Generating Figure 3 (UFLS timeline) ...")
    figure_3_ufls_timeline()
    print("[4/5] Generating Figure 4 (BESS effect) ...")
    figure_4_bess_effect()

    # Build summary table
    print("[5/5] Building adequacy summary table ...")
    df = build_adequacy_table()
    print("\nUFLS Adequacy Summary Table:")
    print(df.to_string(index=False))
    df.to_csv(os.path.join(FIG_DIR, "paper4_adequacy_table.csv"), index=False)

    # Save summary JSON
    summary = {
        "figures": [
            "paper4_fig1_frequency_trajectory.png",
            "paper4_fig2_nadir_vs_ibr.png",
            "paper4_fig3_ufls_timeline.png",
            "paper4_fig4_bess_effect.png",
        ],
        "scenarios_run": len(df),
        "pass_rate": float((df["Pass"] == "Y").mean()),
    }
    with open(os.path.join(FIG_DIR, "paper4_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nPass rate across all {len(df)} scenarios: {summary['pass_rate']*100:.1f}%")
    print("Done.")


if __name__ == "__main__":
    main()
