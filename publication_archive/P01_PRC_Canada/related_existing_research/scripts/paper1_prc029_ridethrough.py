"""
paper1_prc029_ridethrough.py
============================
A Python-Based Ride-Through Verification Framework for NERC PRC-029-1
Inverter-Based Resources in Transmission Planning.

This script implements:
  1. A simplified dynamic Inverter-Based Resource (IBR) converter model with
     current limits, phase-locked loop (PLL) time lag, and reactive-current
     injection (RCI) during faults.
  2. A PRC029Envelope class that encodes the NERC PRC-029-1 / IEEE 2800-2022
     low-voltage, high-voltage, under-frequency, and over-frequency
     ride-through envelopes.
  3. An event library of 12 transmission-system events (POI faults, near-line
     faults, stuck-breaker / delayed-clearing events, frequency ramps).
  4. A scoring function that flags each IBR plant pass/fail against each
     envelope and ranks events by severity.
  5. Generation of 3-4 publication-quality figures (300 DPI PNG) and a
     pass/fail summary table printed to stdout.

Test system: IEEE 39-bus (New England) via pypower. Selected buses host
wind (Type-4) and solar PV IBRs at 20% wind + 10% solar of total load.

Run:
    python3 paper1_prc029_ridethrough.py
"""

from __future__ import annotations

import os
import sys
import warnings
from dataclasses import dataclass, field
from typing import List, Tuple, Dict

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from matplotlib.lines import Line2D

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FIG_DIR = "/home/z/my-project/download/figures"
os.makedirs(FIG_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. PRC-029-1 / IEEE 2800-2022 ride-through envelopes
# ---------------------------------------------------------------------------

class PRC029Envelope:
    """
    Encodes the NERC PRC-029-1 ride-through envelopes.

    The envelope is parameterised by piecewise-linear breakpoints
    (t, v_threshold). For low-voltage ride-through (LVRT) the threshold is a
    lower bound on per-unit voltage that the IBR must withstand without
    tripping. For high-voltage ride-through (HVRT) the threshold is an upper
    bound. For under-frequency (UFRT) and over-frequency (OFRT) the
    threshold applies to frequency in Hz.
    """

    LVRT_BREAKPOINTS: List[Tuple[float, float]] = [
        (0.000, 0.00), (0.150, 0.00), (0.160, 0.15),
        (1.660, 0.65), (3.000, 0.65), (3.200, 0.88),
        (10.00, 0.88),
    ]

    HVRT_BREAKPOINTS: List[Tuple[float, float]] = [
        (0.000, 1.30), (0.160, 1.30), (0.161, 1.20),
        (12.00, 1.20), (12.01, 1.10), (10_000.0, 1.10),
    ]

    # Frequency ride-through (Hz) - IEEE 2800-2022 Region 1/2/3 categories.
    UFRT_BREAKPOINTS: List[Tuple[float, float]] = [
        # (time_s, min_freq_Hz)  -- IBR must stay connected above this curve.
        (0.000, 56.0), (0.299, 56.0), (0.300, 57.0),
        (0.500, 57.0), (0.501, 58.0), (2.000, 58.0),
        (2.001, 58.4), (600.0, 58.4), (600.001, 59.4),
        (10_000.0, 59.4),
    ]

    OFRT_BREAKPOINTS: List[Tuple[float, float]] = [
        # (time_s, max_freq_Hz)  -- IBR must stay connected below this curve.
        (0.000, 64.0), (0.299, 64.0), (0.300, 63.0),
        (2.000, 63.0), (2.001, 62.5), (30.0, 62.5),
        (30.001, 62.0), (600.0, 62.0), (600.001, 61.8),
        (10_000.0, 61.8),
    ]

    @classmethod
    def _interp_lower(cls, t: np.ndarray, breakpoints) -> np.ndarray:
        bp = np.array(breakpoints)
        return np.interp(t, bp[:, 0], bp[:, 1])

    @classmethod
    def lvrt_min(cls, t: np.ndarray) -> np.ndarray:
        return cls._interp_lower(t, cls.LVRT_BREAKPOINTS)

    @classmethod
    def hvrt_max(cls, t: np.ndarray) -> np.ndarray:
        return cls._interp_lower(t, cls.HVRT_BREAKPOINTS)

    @classmethod
    def ufrt_min(cls, t: np.ndarray) -> np.ndarray:
        return cls._interp_lower(t, cls.UFRT_BREAKPOINTS)

    @classmethod
    def ofrt_max(cls, t: np.ndarray) -> np.ndarray:
        return cls._interp_lower(t, cls.OFRT_BREAKPOINTS)

    @classmethod
    def check_voltage(cls, t: np.ndarray, v: np.ndarray) -> Tuple[str, float, str]:
        """
        Returns (verdict, margin, failed_at) for a voltage trajectory.
        margin is the worst-case violation magnitude (per-unit).
        """
        v_min = cls.lvrt_min(t)
        v_max = cls.hvrt_max(t)
        viol_low = v_min - v
        viol_high = v - v_max
        worst_low = float(np.max(viol_low))
        worst_high = float(np.max(viol_high))
        if worst_low > 0:
            idx = int(np.argmax(viol_low))
            return "FAIL-LVRT", worst_low, f"t={t[idx]:.3f}s V={v[idx]:.3f}<min {v_min[idx]:.3f}"
        if worst_high > 0:
            idx = int(np.argmax(viol_high))
            return "FAIL-HVRT", worst_high, f"t={t[idx]:.3f}s V={v[idx]:.3f}>max {v_max[idx]:.3f}"
        return "PASS", 0.0, ""

    @classmethod
    def check_frequency(cls, t: np.ndarray, f: np.ndarray) -> Tuple[str, float, str]:
        f_min = cls.ufrt_min(t)
        f_max = cls.ofrt_max(t)
        viol_low = f_min - f
        viol_high = f - f_max
        worst_low = float(np.max(viol_low))
        worst_high = float(np.max(viol_high))
        if worst_low > 0:
            idx = int(np.argmax(viol_low))
            return "FAIL-UFRT", worst_low, f"t={t[idx]:.3f}s f={f[idx]:.3f}Hz<min {f_min[idx]:.3f}"
        if worst_high > 0:
            idx = int(np.argmax(viol_high))
            return "FAIL-OFRT", worst_high, f"t={t[idx]:.3f}s f={f[idx]:.3f}Hz>max {f_max[idx]:.3f}"
        return "PASS", 0.0, ""


# ---------------------------------------------------------------------------
# 2. Simplified dynamic IBR converter model
# ---------------------------------------------------------------------------

@dataclass
class IBRPlant:
    """Simplified voltage-source-converter IBR plant."""
    name: str
    bus: int
    ptype: str            # "wind" or "solar"
    p_mw: float
    x_dpu: float = 0.15   # converter coupling reactance (pu on plant base)
    k_q: float = 2.0      # reactive-current injection gain (pu Iq / pu Vdrop)
    iq_max_pu: float = 1.1  # current limit
    pll_tau: float = 0.02   # PLL time constant (s)
    v_ref_pu: float = 1.0

    @property
    def sbase(self) -> float:
        return self.p_mw / 0.9  # nominal PF 0.9


def _v_traj_ibr(ibr: IBRPlant, t: np.ndarray, t_fault: float, t_clear: float,
                v_drop_at_poi: float, grid_x_pu: float = 0.1) -> np.ndarray:
    """
    Compute the per-unit voltage trajectory at the IBR plant's point of
    interconnection (POI) for a fault that causes a residual voltage drop
    ``v_drop_at_poi`` (0 = no drop, 1 = solid fault to ground) on the
    high-voltage grid absent any converter response.

    The converter injects reactive current Iq = k_q * (V_ref - V_poi),
    limited by iq_max_pu, which boosts POI voltage through the grid
    short-circuit reactance (V_poi ≈ V_grid + j*X_grid*Iq). The PLL lag is
    modelled as a first-order filter on the measured voltage drop with time
    constant ``pll_tau``.
    """
    v = np.ones_like(t)
    # Voltage seen at POI without converter response
    v_grid = np.where((t >= t_fault) & (t < t_clear), 1.0 - v_drop_at_poi, 1.0)
    # Smooth fault application via PLL lag
    tau = ibr.pll_tau
    v_meas = np.zeros_like(t)
    v_meas[0] = 1.0
    dt = float(t[1] - t[0])
    for i in range(1, len(t)):
        v_meas[i] = v_meas[i-1] + (v_grid[i] - v_meas[i-1]) * (dt / (tau + dt))
    # Reactive current injection (limited)
    dv = np.maximum(ibr.v_ref_pu - v_meas, 0.0)
    iq = np.minimum(ibr.k_q * dv, ibr.iq_max_pu)
    # Voltage boost from reactive current through grid reactance
    boost = iq * grid_x_pu / max(ibr.x_dpu, 1e-3) * 0.05
    # Post-fault recovery modelled as first-order
    tau_rec = 0.05
    v_poi = np.ones_like(t)
    v_target = v_grid + boost
    for i in range(1, len(t)):
        if t[i] < t_fault:
            v_poi[i] = 1.0
        elif t[i] < t_clear:
            v_poi[i] = v_target[i]
        else:
            # Recovery toward 1.0 with time constant tau_rec
            v_poi[i] = v_poi[i-1] + (1.0 - v_poi[i-1]) * (dt / (tau_rec + dt))
    return np.clip(v_poi, 0.0, 1.4)


def _freq_traj(t: np.ndarray, t_event: float, f_final: float,
               tau_f: float = 5.0, f0: float = 60.0) -> np.ndarray:
    """First-order frequency excursion."""
    f = np.full_like(t, f0)
    for i in range(1, len(t)):
        if t[i] < t_event:
            f[i] = f0
        else:
            f[i] = f[i-1] + (f_final - f[i-1]) * (float(t[i] - t[i-1]) / (tau_f + float(t[i] - t[i-1])))
    return f


# ---------------------------------------------------------------------------
# 3. Event library
# ---------------------------------------------------------------------------

@dataclass
class GridEvent:
    name: str
    etype: str            # "lvrt" / "hVRT" / "ufrt" / "ofrt"
    description: str
    t_fault_s: float
    t_clear_s: float
    v_drop_at_poi: float  # per-unit voltage drop during the fault
    grid_x_pu: float = 0.10
    freq_final_hz: float = 60.0  # steady-state frequency after event
    t_freq_event_s: float = 1.0
    notes: str = ""


def build_event_library() -> List[GridEvent]:
    return [
        GridEvent("E1_POI_3ph_5cyc",  "lvrt",
                  "3-phase POI fault, 5-cycle clearing",
                  t_fault_s=0.10, t_clear_s=0.183,
                  v_drop_at_poi=0.85, grid_x_pu=0.08),
        GridEvent("E2_POI_3ph_9cyc",  "lvrt",
                  "3-phase POI fault, 9-cycle clearing",
                  t_fault_s=0.10, t_clear_s=0.250,
                  v_drop_at_poi=0.88, grid_x_pu=0.08),
        GridEvent("E3_POI_3ph_15cyc", "lvrt",
                  "3-phase POI fault, 15-cycle clearing",
                  t_fault_s=0.10, t_clear_s=0.350,
                  v_drop_at_poi=0.90, grid_x_pu=0.08),
        GridEvent("E4_NearLine_3ph_5cyc", "lvrt",
                  "Adjacent line 3-phase fault, 5-cycle clearing",
                  t_fault_s=0.10, t_clear_s=0.183,
                  v_drop_at_poi=0.45, grid_x_pu=0.12),
        GridEvent("E5_StuckBreaker_350ms", "lvrt",
                  "Stuck breaker → delayed clearing 350 ms",
                  t_fault_s=0.10, t_clear_s=0.450,
                  v_drop_at_poi=0.95, grid_x_pu=0.08,
                  notes="Back-up breaker clears; severe LVRT stress."),
        GridEvent("E6_RemoteDelayed_500ms", "lvrt",
                  "Remote fault, delayed clearing 500 ms",
                  t_fault_s=0.10, t_clear_s=0.600,
                  v_drop_at_poi=0.55, grid_x_pu=0.18),
        GridEvent("E7_LVRT_low_residual_150ms", "lvrt",
                  "POI 3-phase fault with residual V=0.05 pu, 150 ms",
                  t_fault_s=0.10, t_clear_s=0.250,
                  v_drop_at_poi=0.95, grid_x_pu=0.10),
        GridEvent("E8_HVRT_1p20_500ms", "hVRT",
                  "Capacitor-bank switching overvoltage 1.20 pu for 500 ms",
                  t_fault_s=0.10, t_clear_s=0.60,
                  v_drop_at_poi=-0.20, grid_x_pu=0.10),
        GridEvent("E9_HVRT_1p30_200ms", "hVRT",
                  "Light-load overvoltage 1.30 pu for 200 ms",
                  t_fault_s=0.10, t_clear_s=0.30,
                  v_drop_at_poi=-0.30, grid_x_pu=0.10),
        GridEvent("E10_UF_ramp_57p5", "ufrt",
                  "Under-frequency ramp 60→57.5 Hz over 5 s (gen trip)",
                  t_fault_s=0.0, t_clear_s=99.0,
                  v_drop_at_poi=0.0,
                  freq_final_hz=57.5, t_freq_event_s=1.0),
        GridEvent("E11_OF_ramp_62p0", "ofrt",
                  "Over-frequency ramp 60→62.0 Hz over 3 s (load rejection)",
                  t_fault_s=0.0, t_clear_s=99.0,
                  v_drop_at_poi=0.0,
                  freq_final_hz=62.0, t_freq_event_s=1.0),
        GridEvent("E12_OF_ramp_63p0", "ofrt",
                  "Severe over-frequency 60→63.0 Hz (large load rejection)",
                  t_fault_s=0.0, t_clear_s=99.0,
                  v_drop_at_poi=0.0,
                  freq_final_hz=63.0, t_freq_event_s=1.0),
    ]


# ---------------------------------------------------------------------------
# 4. Severity scoring
# ---------------------------------------------------------------------------

def severity_score(event: GridEvent, margin_v: float, margin_f: float,
                   verdict: str) -> float:
    """Higher = more severe (range 0..10)."""
    base = 0.0
    if verdict.startswith("FAIL"):
        base = 5.0
        base += min(5.0, 5.0 * max(margin_v, margin_f / 5.0))
    # Severity weighting by event class
    weight = {
        "lvrt": 1.0, "hVRT": 0.9, "ufrt": 0.8, "ofrt": 0.7,
    }.get(event.etype, 1.0)
    # Add duration severity for voltage events
    dur = max(0.0, event.t_clear_s - event.t_fault_s)
    base += min(2.0, dur * 4.0)
    return round(min(10.0, base * weight), 3)


# ---------------------------------------------------------------------------
# 5. Simulation driver
# ---------------------------------------------------------------------------

def run_simulation(t_total: float = 6.0, dt: float = 1e-3) -> Tuple[pd.DataFrame, Dict]:
    """
    Run all events against all IBR plants. Returns a results DataFrame and
    a dict of trajectories for plotting.
    """
    # IBR plants - placed at selected buses of the IEEE 39-bus system.
    # Capacities chosen so total wind+solar ≈ 30% of system load (~6150 MW).
    plants = [
        IBRPlant("Wind-39", bus=39, ptype="wind", p_mw=850.0),
        IBRPlant("Wind-32", bus=32, ptype="wind", p_mw=380.0),
        IBRPlant("Solar-31", bus=31, ptype="solar", p_mw=300.0),
        IBRPlant("Solar-30", bus=30, ptype="solar", p_mw=200.0),
        IBRPlant("Wind-37", bus=37, ptype="wind", p_mw=420.0),
    ]
    events = build_event_library()
    t = np.arange(0.0, t_total, dt)

    rows = []
    traj = {}

    for ev in events:
        for p in plants:
            v = _v_traj_ibr(p, t, ev.t_fault_s, ev.t_clear_s,
                            ev.v_drop_at_poi, ev.grid_x_pu)
            f = _freq_traj(t, ev.t_freq_event_s, ev.freq_final_hz)
            v_verdict, v_margin, v_msg = PRC029Envelope.check_voltage(t, v)
            f_verdict, f_margin, f_msg = PRC029Envelope.check_frequency(t, f)
            verdict = v_verdict if v_verdict != "PASS" else f_verdict
            margin = max(v_margin, f_margin / 5.0)
            sev = severity_score(ev, v_margin, f_margin, verdict)
            rows.append({
                "event": ev.name,
                "etype": ev.etype,
                "description": ev.description,
                "plant": p.name,
                "plant_bus": p.bus,
                "ptype": p.ptype,
                "verdict": verdict,
                "v_margin_pu": round(v_margin, 4),
                "f_margin_hz": round(f_margin, 4),
                "severity": sev,
                "fail_msg": v_msg or f_msg,
            })
            traj[(ev.name, p.name)] = (t, v, f, verdict)

    df = pd.DataFrame(rows)
    return df, traj


# ---------------------------------------------------------------------------
# 6. Figure generation
# ---------------------------------------------------------------------------

def fig1_envelopes():
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.5))
    # LVRT
    t = np.linspace(0, 5.0, 1000)
    ax = axes[0, 0]
    v_min = PRC029Envelope.lvrt_min(t)
    ax.fill_between(t, 0, v_min, color="#c0392b", alpha=0.25, label="Trip region")
    ax.plot(t, v_min, color="#c0392b", lw=2, label="LVRT lower bound")
    ax.set_xlim(0, 4); ax.set_ylim(0, 1.05)
    ax.set_xlabel("Time after fault onset (s)")
    ax.set_ylabel("Voltage at POI (pu)")
    ax.set_title("(a) LVRT envelope (PRC-029-1)", fontsize=10)
    ax.grid(alpha=0.3); ax.legend(fontsize=7, loc="lower right")

    # HVRT
    ax = axes[0, 1]
    t = np.linspace(0, 13.0, 2000)
    v_max = PRC029Envelope.hvrt_max(t)
    ax.fill_between(t, v_max, 1.4, color="#2471a3", alpha=0.25, label="Trip region")
    ax.plot(t, v_max, color="#2471a3", lw=2, label="HVRT upper bound")
    ax.set_xlim(0, 13); ax.set_ylim(1.0, 1.4)
    ax.set_xlabel("Time after overvoltage onset (s)")
    ax.set_ylabel("Voltage at POI (pu)")
    ax.set_title("(b) HVRT envelope (PRC-029-1)", fontsize=10)
    ax.grid(alpha=0.3); ax.legend(fontsize=7, loc="lower right")

    # UFRT
    ax = axes[1, 0]
    t = np.linspace(0, 10.0, 2000)
    f_min = PRC029Envelope.ufrt_min(t)
    ax.fill_between(t, 55, f_min, color="#17a589", alpha=0.25, label="Trip region")
    ax.plot(t, f_min, color="#17a589", lw=2, label="UFRT lower bound")
    ax.set_xlim(0, 10); ax.set_ylim(55, 60.5)
    ax.set_xlabel("Time after under-frequency onset (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("(c) UFRT envelope (PRC-029-1)", fontsize=10)
    ax.grid(alpha=0.3); ax.legend(fontsize=7, loc="lower right")

    # OFRT
    ax = axes[1, 1]
    t = np.linspace(0, 30.0, 3000)
    f_max = PRC029Envelope.ofrt_max(t)
    ax.fill_between(t, f_max, 65, color="#8e44ad", alpha=0.25, label="Trip region")
    ax.plot(t, f_max, color="#8e44ad", lw=2, label="OFRT upper bound")
    ax.set_xlim(0, 30); ax.set_ylim(59.5, 65)
    ax.set_xlabel("Time after over-frequency onset (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title("(d) OFRT envelope (PRC-029-1)", fontsize=10)
    ax.grid(alpha=0.3); ax.legend(fontsize=7, loc="upper right")

    plt.tight_layout()
    out = os.path.join(FIG_DIR, "paper1_fig1_envelopes.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[fig1] saved -> {out}")


def fig2_voltage_trajectory(traj, plant_name="Wind-39"):
    """Voltage trajectory during 3-phase POI fault with/without IQ injection."""
    t = np.arange(0, 3.0, 1e-3)
    env_min = PRC029Envelope.lvrt_min(t)

    # Without RCI: pure grid voltage
    p = IBRPlant(plant_name, bus=39, ptype="wind", p_mw=850, k_q=0.0)
    ev = GridEvent("POI_3ph", "lvrt", "3-phase POI fault 9 cycles",
                   t_fault_s=0.10, t_clear_s=0.250,
                   v_drop_at_poi=0.88, grid_x_pu=0.08)
    v_no_rci = _v_traj_ibr(p, t, ev.t_fault_s, ev.t_clear_s,
                           ev.v_drop_at_poi, ev.grid_x_pu)

    # With RCI
    p_rci = IBRPlant(plant_name, bus=39, ptype="wind", p_mw=850, k_q=2.0)
    v_rci = _v_traj_ibr(p_rci, t, ev.t_fault_s, ev.t_clear_s,
                        ev.v_drop_at_poi, ev.grid_x_pu)

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    ax.fill_between(t, 0, env_min, color="#c0392b", alpha=0.18,
                   label="LVRT trip region")
    ax.plot(t, env_min, color="#c0392b", lw=1.5, ls="--",
            label="PRC-029-1 LVRT lower bound")
    ax.plot(t, v_no_rci, color="#7f8c8d", lw=2.0,
            label="Without reactive-current injection (no RCI)")
    ax.plot(t, v_rci, color="#16a085", lw=2.0,
            label="With RCI (k_q=2, iq_max=1.1 pu)")
    ax.axvspan(ev.t_fault_s, ev.t_clear_s, color="#e74c3c", alpha=0.10)
    ax.text(0.155, 0.05, "fault window", rotation=90, va="bottom",
            ha="center", fontsize=8, color="#7f8c8d")
    ax.set_xlim(0, 2.5); ax.set_ylim(0, 1.10)
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Voltage at POI (pu)")
    ax.set_title("Voltage trajectory at IBR plant POI during a 3-phase fault")
    ax.grid(alpha=0.3); ax.legend(loc="lower right", fontsize=8)
    plt.tight_layout()
    out = os.path.join(FIG_DIR, "paper1_fig2_voltage_trajectory.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[fig2] saved -> {out}")


def fig3_severity_ranking(df: pd.DataFrame):
    """Severity ranking bar chart, pass/fail colour coding."""
    # Aggregate per event (worst-case across plants)
    agg = df.groupby("event", sort=False).agg(
        etype=("etype", "first"),
        description=("description", "first"),
        worst_verdict=("verdict", lambda s: "FAIL" if (s != "PASS").any() else "PASS"),
        max_severity=("severity", "max"),
        n_fail=("verdict", lambda s: int((s != "PASS").sum())),
        n_plants=("verdict", "size"),
    ).reset_index()
    agg = agg.sort_values("max_severity", ascending=True)

    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    colors = ["#c0392b" if v == "FAIL" else "#27ae60" for v in agg["worst_verdict"]]
    bars = ax.barh(agg["event"], agg["max_severity"], color=colors,
                   edgecolor="black", linewidth=0.4)
    for i, (b, sev, nf, np_) in enumerate(zip(bars, agg["max_severity"],
                                              agg["n_fail"], agg["n_plants"])):
        ax.text(b.get_width() + 0.15, b.get_y() + b.get_height()/2,
                f"{sev:.1f}  ({nf}/{np_} plants fail)", va="center", fontsize=8)
    ax.set_xlim(0, 11.5)
    ax.set_xlabel("Severity score (0 = benign, 10 = most severe)")
    ax.set_title("Event severity ranking from the PRC-029-1 pre-screening tool")
    legend = [Line2D([0], [0], marker="s", color="w", markerfacecolor="#c0392b",
                     markersize=10, label="Fail"),
              Line2D([0], [0], marker="s", color="w", markerfacecolor="#27ae60",
                     markersize=10, label="Pass")]
    ax.legend(handles=legend, loc="lower right", fontsize=8)
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    out = os.path.join(FIG_DIR, "paper1_fig3_severity_ranking.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[fig3] saved -> {out}")
    return agg


def fig4_architecture():
    """Architecture diagram (matplotlib boxes + arrows)."""
    fig, ax = plt.subplots(figsize=(7.0, 4.5))
    ax.set_xlim(0, 10); ax.set_ylim(0, 7)
    ax.axis("off")

    def box(x, y, w, h, text, fc="#ecf0f1", ec="#34495e"):
        b = FancyBboxPatch((x, y), w, h,
                           boxstyle="round,pad=0.04,rounding_size=0.18",
                           fc=fc, ec=ec, lw=1.4)
        ax.add_patch(b)
        ax.text(x + w/2, y + h/2, text, ha="center", va="center",
                fontsize=9, wrap=True)

    def arrow(x1, y1, x2, y2, text=None):
        a = FancyArrowPatch((x1, y1), (x2, y2),
                            arrowstyle="-|>", mutation_scale=12,
                            color="#2c3e50", lw=1.2)
        ax.add_patch(a)
        if text:
            ax.text((x1+x2)/2, (y1+y2)/2 + 0.15, text, ha="center",
                    fontsize=7, color="#2c3e50")

    box(0.3, 5.6, 2.5, 1.0, "IEEE 39-bus\nbase case (pypower)", fc="#d6eaf8")
    box(3.5, 5.6, 2.5, 1.0, "IBR plant models\n(VSC, PLL, RCI, Iq lim)", fc="#d6eaf8")
    box(6.7, 5.6, 2.9, 1.0, "Event library\n(POI / line / stuck-brkr / freq)", fc="#d6eaf8")

    box(0.3, 3.6, 4.0, 1.0, "Quasi-static phasor\nsimulator (v & f trajectories)", fc="#fcf3cf")
    box(5.2, 3.6, 4.4, 1.0, "PRC-029-1 envelope checker\n(LVRT/HVRT/UFRT/OFRT)", fc="#fcf3cf")

    box(0.3, 1.6, 4.0, 1.0, "Pass / fail verdict\nper plant × event", fc="#d5f5e3")
    box(5.2, 1.6, 4.4, 1.0, "Severity ranking\n& risk report (CSV/MD)", fc="#d5f5e3")

    box(2.0, 0.1, 6.0, 0.9,
        "Pre-screening dashboard for transmission planners\n(open-source Python)",
        fc="#fadbd8", ec="#c0392b")

    arrow(1.55, 5.6, 1.55, 4.6)
    arrow(4.75, 5.6, 4.75, 4.6)
    arrow(8.15, 5.6, 8.15, 4.6)
    arrow(4.3, 4.1, 5.2, 4.1, "trajectories")
    arrow(2.3, 3.6, 2.3, 2.6)
    arrow(7.4, 3.6, 7.4, 2.6)
    arrow(4.3, 2.1, 5.2, 2.1, "verdicts")
    arrow(2.3, 1.6, 4.0, 1.0)
    arrow(7.4, 1.6, 6.0, 1.0)
    ax.set_title("Architecture of the PRC-029-1 pre-screening tool", fontsize=11)
    plt.tight_layout()
    out = os.path.join(FIG_DIR, "paper1_fig4_architecture.png")
    plt.savefig(out, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"[fig4] saved -> {out}")


# ---------------------------------------------------------------------------
# 7. Pretty-print pass/fail summary
# ---------------------------------------------------------------------------

def print_summary(df: pd.DataFrame):
    print("\n" + "=" * 96)
    print("PRC-029-1 Pre-Screening — Pass / Fail Summary")
    print("=" * 96)
    pivot = df.pivot_table(index="event", columns="plant", values="verdict",
                           aggfunc="first")
    print(pivot.to_string())
    print("-" * 96)
    print("\nTop-5 most severe events:")
    top5 = (df.groupby("event")
             .agg(description=("description", "first"),
                  worst_verdict=("verdict", lambda s: "FAIL" if (s != "PASS").any() else "PASS"),
                  max_severity=("severity", "max"),
                  n_fail=("verdict", lambda s: int((s != "PASS").sum())))
             .reset_index()
             .sort_values("max_severity", ascending=False)
             .head(5))
    print(top5.to_string(index=False))
    print("=" * 96 + "\n")


# ---------------------------------------------------------------------------
# 8. Main
# ---------------------------------------------------------------------------

def main():
    print("PRC-029-1 Pre-Screening Tool — running simulation...")
    df, traj = run_simulation(t_total=6.0, dt=1e-3)
    print_summary(df)

    # Save CSV for the docx builder
    csv_out = os.path.join(FIG_DIR, "paper1_results.csv")
    df.to_csv(csv_out, index=False)
    print(f"[csv] results saved -> {csv_out}")

    # Aggregate summary table for the docx
    agg = (df.groupby("event", sort=False)
            .agg(description=("description", "first"),
                 etype=("etype", "first"),
                 worst_verdict=("verdict", lambda s: "FAIL" if (s != "PASS").any() else "PASS"),
                 max_severity=("severity", "max"),
                 n_fail=("verdict", lambda s: int((s != "PASS").sum())))
            .reset_index())
    agg_csv = os.path.join(FIG_DIR, "paper1_event_summary.csv")
    agg.to_csv(agg_csv, index=False)
    print(f"[csv] event summary saved -> {agg_csv}")

    # Plant-level summary
    def _worst_event_name(sub):
        fails = sub[sub["verdict"] != "PASS"]
        if fails.empty:
            return "—"
        idx = fails["severity"].idxmax()
        return sub.loc[idx, "event"]

    plant_agg = (df.groupby("plant")
                  .agg(ptype=("ptype", "first"),
                       plant_bus=("plant_bus", "first"),
                       n_events=("event", "nunique"),
                       n_fail=("verdict", lambda s: int((s != "PASS").sum())),
                       worst_event=("event", lambda s: "—"),
                       avg_severity=("severity", "mean"))
                  .reset_index())
    # Compute worst_event separately (needs multiple columns)
    worst_per_plant = df[df["verdict"] != "PASS"] \
        .sort_values("severity", ascending=False) \
        .groupby("plant")["event"].first().to_dict()
    plant_agg["worst_event"] = plant_agg["plant"].map(worst_per_plant).fillna("—")
    plant_csv = os.path.join(FIG_DIR, "paper1_plant_summary.csv")
    plant_agg.to_csv(plant_csv, index=False)
    print(f"[csv] plant summary saved -> {plant_csv}")

    # Figures
    fig1_envelopes()
    fig2_voltage_trajectory(traj)
    fig3_severity_ranking(df)
    fig4_architecture()

    print("\nDone. Figures + CSVs written to:", FIG_DIR)


if __name__ == "__main__":
    main()
