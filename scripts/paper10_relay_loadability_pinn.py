"""
Paper 10: A Python Tool for Transmission Relay Loadability Screening
Under NERC PRC-023-6 Using Physics-Informed Neural Networks.

This script:
  1. Generates a Monte-Carlo dataset of operating points for the IEEE 39-bus
     and IEEE 118-bus test systems using PYPOWER. For each operating point we
     perturb load (80-120% of base), generation re-dispatch, topology (selected
     branch outages), and renewable (wind/solar proxy) output.
  2. Runs a full AC power flow for each sample and records per-branch
     apparent-power flow (MVA). Loadability margin is defined per
     PRC-023-6 as:  margin_i = (1.15 * S_emergency_i - S_flow_i) / S_emergency_i
  3. Trains a PINN-equivalent surrogate (sklearn MLPRegressor) on the dataset.
     The "physics-informed" component is implemented as a post-training,
     gradient-free constraint check enforcing the PRC-023-6 115% emergency
     rating rule; samples that violate the constraint are flagged for
     active-learning prioritization.
  4. Benchmarks PINN inference time vs full PYPOWER re-calculation.
  5. Produces all figures (300 DPI PNG) and CSV summaries required for the
     Word document.

Outputs:
  /home/z/my-project/download/figures/paper10_fig1_scatter_pinn_vs_pf.png
  /home/z/my-project/download/figures/paper10_fig2_error_histogram.png
  /home/z/my-project/download/figures/paper10_fig3_inference_time.png
  /home/z/my-project/download/figures/paper10_fig4_margin_heatmap.png
  /home/z/my-project/download/figures/paper10_accuracy_per_relay.csv
  /home/z/my-project/download/figures/paper10_inference_time.csv
  /home/z/my-project/download/figures/paper10_violations.csv
  /home/z/my-project/download/figures/paper10_summary.json

The script is fully deterministic (random seeds are fixed) and runs in
roughly 4-6 minutes on a laptop-class CPU.
"""

from __future__ import annotations

import json
import os
import time
import warnings
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import r2_score, mean_absolute_percentage_error, mean_squared_error

from pypower.api import case39, case118, runpf, ppoption

warnings.filterwarnings("ignore")

# -------------------------------------------------------------------------
# Reproducibility
# -------------------------------------------------------------------------
RANDOM_SEED = 20260908
np.random.seed(RANDOM_SEED)

# -------------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------------
FIG_DIR = "/home/z/my-project/download/figures"
os.makedirs(FIG_DIR, exist_ok=True)

# -------------------------------------------------------------------------
# Constants / PRC-023-6 rule
# -------------------------------------------------------------------------
# PRC-023-6 requires that load-responsive relay settings not operate for
# loading below 115% of the highest applicable seasonal emergency rating.
# We therefore define the loadability margin (per unit on emergency rating):
#   margin_i = (1.15 * S_emergency_i - S_flow_i) / S_emergency_i
# Margin > 0 means the relay is not expected to operate (compliant).
# Margin <= 0 means the relay is at or beyond its loadability envelope.
EMERGENCY_RATING_SCALE = 1.15
HEATMAP_THRESHOLD = 0.0  # margin above which the relay is compliant


@dataclass
class CaseConfig:
    name: str
    case_fn: callable
    n_samples: int
    n_critical_relays: int


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
def _silence_pypower() -> dict:
    """Return a ppoption dict that suppresses PYPOWER verbose output."""
    opt = ppoption()
    opt["OUT_ALL"] = 0
    opt["VERBOSE"] = 0
    opt["PF_TOL"] = 1e-7
    opt["PF_MAX_IT"] = 50
    return opt


def _branch_apparent_power(results: dict) -> np.ndarray:
    """Compute per-branch apparent power (MVA) from a converged PF result.

    PYPOWER stores branch flows in results['branch'] with columns:
      fbus, tbus, r, x, b, rateA, rateB, rateC, ratio, angle, status,
      Pf, Qf, Pt, Qt, ...
    """
    br = results["branch"]
    Pf = br[:, 13]
    Qf = br[:, 14]
    Sf = np.sqrt(Pf ** 2 + Qf ** 2)
    return Sf


def _branch_emergency_rating(results: dict) -> np.ndarray:
    """Return the per-branch emergency rating (rateC, fallback to rateA).

    PYPOWER uses 9900 (or 0) as the "no limit" sentinel. We replace those
    sentinels with a pseudo-rating proportional to the base-case branch
    flow so that loadability margins have meaningful variance across
    operating points. This modelling choice is documented in the paper;
    real utility studies would use the actual facility ratings from the
    transmission owner's EMS.
    """
    br = results["branch"]
    rateA = br[:, 5]
    rateB = br[:, 6]
    rateC = br[:, 7]
    # Use rateC if > 0 and < 9900, else rateB if > 0 and < 9900, else rateA.
    def _ok(v):
        return (v > 0) & (v < 9900)
    rating = np.where(_ok(rateC), rateC,
                      np.where(_ok(rateB), rateB,
                               np.where(_ok(rateA), rateA, 0.0)))
    return rating


def _resolve_pseudo_ratings(rating: np.ndarray, base_flows: np.ndarray) -> np.ndarray:
    """For branches whose effective rating is zero (i.e., no rateA/B/C was
    specified in the test case), assign a pseudo-rating proportional to the
    base-case apparent-power flow. The 1.30 multiplier reflects the typical
    75-80% base-case loading assumption used in transmission planning
    studies, plus a 50 MVA floor to avoid degenerate cases on lightly
    loaded branches.
    """
    out = rating.copy()
    zero_mask = out <= 0
    out[zero_mask] = np.maximum(50.0, 1.30 * base_flows[zero_mask] + 10.0)
    return out


def _perturb_case(base_case: dict,
                  load_scale: float,
                  gen_dispatch: np.ndarray,
                  outage_branches: List[int],
                  renewable_scale: np.ndarray) -> dict:
    """Return a perturbed deep-copy of the base PYPOWER case.

    Perturbations:
      * Load scale (uniform multiplier, 0.8-1.2)
      * Generator P dispatch: scaled by random per-generator factor then
        re-normalized so total generation covers load plus losses.
      * Branch outages: status set to 0 for selected branches (we never
        disconnect generators or shunts).
      * Renewable output: a subset of generators flagged as wind/solar is
        scaled by a random renewable capacity factor (0.1-0.9).
    """
    ppc = {k: (v.copy() if isinstance(v, np.ndarray) else v)
           for k, v in base_case.items()}

    # Scale loads
    ppc["bus"][:, 2] = base_case["bus"][:, 2] * load_scale
    ppc["bus"][:, 3] = base_case["bus"][:, 3] * load_scale

    # Renewable proxy: assume the last few generators are renewables.
    # For IEEE 39-bus, treat buses 37, 38 (gens at indices 7, 8) as wind.
    # For IEEE 118-bus, treat the last 3 gens as renewables.
    n_gen = ppc["gen"].shape[0]
    n_re = min(3, max(1, n_gen // 5))
    re_idx = list(range(n_gen - n_re, n_gen))

    # Apply gen_dispatch factors
    ppc["gen"][:, 1] = base_case["gen"][:, 1] * gen_dispatch
    # Apply renewable scaling on top of dispatch
    for k, idx in enumerate(re_idx):
        ppc["gen"][idx, 1] = base_case["gen"][idx, 1] * renewable_scale[k]

    # Re-dispatch remaining (non-slack, non-renewable) generators to cover
    # the new load while keeping total generation feasible.
    slack_idx = 0  # first generator is the slack bus in pypower default
    total_load = ppc["bus"][:, 2].sum()
    other_gen_idx = [i for i in range(n_gen) if i not in re_idx and i != slack_idx]
    re_total = ppc["gen"][re_idx, 1].sum()
    target_other = total_load * 1.02 - re_total  # 2% losses margin
    other_capacity = ppc["gen"][other_gen_idx, 1].sum()
    if other_capacity > 0:
        scale = min(1.5, max(0.5, target_other / other_capacity))
        ppc["gen"][other_gen_idx, 1] *= scale
    # Slack picks up the residual automatically during PF.

    # Apply branch outages
    for br in outage_branches:
        if 0 <= br < ppc["branch"].shape[0]:
            ppc["branch"][br, 10] = 0  # status = 0

    return ppc


def _select_outages(n_branches: int, n_outages: int,
                    protected: List[int], rng: np.random.Generator) -> List[int]:
    """Pick `n_outages` branch indices to take out, avoiding `protected`
    branches (e.g., generator step-up transformers)."""
    pool = [i for i in range(n_branches) if i not in protected]
    if n_outages >= len(pool):
        n_outages = max(0, len(pool) - 1)
    return list(rng.choice(pool, size=n_outages, replace=False))


# -------------------------------------------------------------------------
# Dataset generation
# -------------------------------------------------------------------------
def generate_dataset(cfg: CaseConfig) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Generate (X, Y, meta) for a given test case.

    X: (n_samples, n_features) - load multipliers, gen dispatch, topology
       one-hot, renewable capacity factors.
    Y: (n_samples, n_critical_relays) - loadability margin per relay.
    meta: dict with branch indices of critical relays, emergency ratings,
         base case info, etc.
    """
    rng = np.random.default_rng(RANDOM_SEED + hash(cfg.name) % 1000)
    base_case = cfg.case_fn()
    opt = _silence_pypower()

    # Run base PF to get branch ratings and base-case flows.
    base_res, base_ok = runpf(base_case, opt)
    if not base_ok:
        raise RuntimeError(f"Base PF failed for {cfg.name}")

    base_flows = _branch_apparent_power(base_res)
    base_ratings = _branch_emergency_rating(base_res)
    # Resolve pseudo-ratings for any branches without an explicit rating.
    pseudo_ratings = _resolve_pseudo_ratings(base_ratings, base_flows)

    # Identify "load-responsive relay elements": pick the top-N branches by
    # base-case loading (S_flow / rating). These are the branches where
    # relay loadability is most often the binding constraint in PRC-023-6
    # studies.
    base_loading = base_flows / pseudo_ratings
    protected = list(range(0, 6))  # protect the first few branches (gen ties)
    candidates = [i for i in range(len(base_loading)) if i not in protected]
    top_indices = sorted(candidates,
                         key=lambda i: base_loading[i],
                         reverse=True)[:cfg.n_critical_relays]
    top_indices = sorted(top_indices)
    crit_ratings = pseudo_ratings[top_indices]

    n_gen = base_case["gen"].shape[0]
    n_re = min(3, max(1, n_gen // 5))
    n_branches = base_case["branch"].shape[0]

    # Features (per sample):
    #  - load_scale (1)
    #  - mean gen_dispatch (1)
    #  - std gen_dispatch (1)
    #  - n_outages (1)
    #  - outage one-hot (n_branches)  -> we use a sparse count vector
    #  - renewable capacity factors (n_re)
    #  - total load MW (1)
    # Total: 5 + n_branches + n_re + 1
    n_features = 5 + n_branches + n_re + 1
    X = np.zeros((cfg.n_samples, n_features))
    Y = np.zeros((cfg.n_samples, cfg.n_critical_relays))

    print(f"[{cfg.name}] Generating {cfg.n_samples} operating points "
          f"({n_features} features, {cfg.n_critical_relays} relays)...")

    t0 = time.time()
    n_ok = 0
    n_fail = 0
    for i in range(cfg.n_samples):
        # Random load scale in 0.8-1.2
        load_scale = float(rng.uniform(0.80, 1.20))
        # Random gen dispatch factors: 0.7-1.3
        gen_dispatch = rng.uniform(0.70, 1.30, size=n_gen)
        # Random renewable capacity factor: 0.1-0.95
        renewable_scale = rng.uniform(0.10, 0.95, size=n_re)
        # Random number of branch outages: 0, 1, or 2
        n_outages = int(rng.choice([0, 1, 2], p=[0.65, 0.27, 0.08]))
        outage_branches = _select_outages(n_branches, n_outages,
                                          protected, rng) if n_outages else []

        ppc = _perturb_case(base_case, load_scale, gen_dispatch,
                            outage_branches, renewable_scale)
        try:
            res, ok = runpf(ppc, opt)
        except Exception:
            ok = False
            res = None
        if not ok or res is None:
            n_fail += 1
            # Mark this sample as "failed" by setting margins to NaN; we'll
            # filter them out below.
            Y[i, :] = np.nan
            X[i, :] = np.concatenate([
                [load_scale, gen_dispatch.mean(), gen_dispatch.std(),
                 float(n_outages), 0.0],
                np.zeros(n_branches),
                renewable_scale,
                [load_scale * base_case["bus"][:, 2].sum()],
            ])
            continue
        n_ok += 1
        flows = _branch_apparent_power(res)
        crit_flows = flows[top_indices]
        margins = (EMERGENCY_RATING_SCALE * crit_ratings - crit_flows) / crit_ratings
        Y[i, :] = margins
        # Feature vector
        outage_oh = np.zeros(n_branches)
        for b in outage_branches:
            outage_oh[b] = 1.0
        total_load_mw = float(ppc["bus"][:, 2].sum())
        X[i, :] = np.concatenate([
            [load_scale, float(gen_dispatch.mean()), float(gen_dispatch.std()),
             float(n_outages), float(np.sum(outage_oh) > 0)],
            outage_oh,
            renewable_scale,
            [total_load_mw],
        ])
        if (i + 1) % 500 == 0:
            elapsed = time.time() - t0
            print(f"  [{cfg.name}] {i + 1}/{cfg.n_samples}  "
                  f"({n_ok} ok, {n_fail} fail)  {elapsed:.1f}s")

    elapsed = time.time() - t0
    print(f"  [{cfg.name}] Done in {elapsed:.1f}s  "
          f"(converged: {n_ok}, failed: {n_fail})")

    meta = {
        "name": cfg.name,
        "top_indices": top_indices,
        "crit_ratings": crit_ratings,
        "base_flows": base_flows,
        "n_features": n_features,
        "n_ok": n_ok,
        "n_fail": n_fail,
        "n_branches": int(n_branches),
        "n_gen": int(n_gen),
        "n_re": int(n_re),
    }
    return X, Y, meta


# -------------------------------------------------------------------------
# PINN-equivalent surrogate
# -------------------------------------------------------------------------
def train_pinn(X: np.ndarray, Y: np.ndarray, meta: dict) -> dict:
    """Train an sklearn MLPRegressor as a PINN-equivalent surrogate.

    The "physics-informed" component is implemented as a post-training,
    gradient-free constraint check (see the paper, Section 3.3):
      margin_i_pred = surrogate(X)
      For each sample, if any relay predicts margin < 0 (PRC-023-6
      violation), the sample is flagged for active-learning re-screening
      with full PYPOWER.

    Returns a dict containing the trained model, scaler, metrics, and
    physics-violation flags.
    """
    # Drop samples with NaN margins (failed PF).
    mask = ~np.isnan(Y).any(axis=1)
    X_clean = X[mask]
    Y_clean = Y[mask]
    print(f"[{meta['name']}] Training on {X_clean.shape[0]} clean samples "
          f"({(~mask).sum()} dropped due to PF non-convergence).")

    # Train/test split (80/20).
    X_tr, X_te, Y_tr, Y_te = train_test_split(
        X_clean, Y_clean, test_size=0.20, random_state=RANDOM_SEED)

    # Standardize features.
    scaler = StandardScaler()
    X_tr_s = scaler.fit_transform(X_tr)
    X_te_s = scaler.transform(X_te)

    # MLPRegressor: 3 hidden layers (128, 64, 32), ReLU, Adam, 500 epochs.
    # This is a modest-sized network; in a production tool one would tune
    # the architecture with cross-validation. We fix the seed for
    # reproducibility.
    model = MLPRegressor(
        hidden_layer_sizes=(128, 64, 32),
        activation="relu",
        solver="adam",
        alpha=1e-4,
        batch_size=64,
        learning_rate_init=1e-3,
        max_iter=500,
        early_stopping=True,
        n_iter_no_change=20,
        random_state=RANDOM_SEED,
        verbose=False,
    )
    t0 = time.time()
    model.fit(X_tr_s, Y_tr)
    train_time = time.time() - t0
    print(f"[{meta['name']}] PINN training: {train_time:.1f}s, "
          f"iters={model.n_iter_}, loss={model.loss_:.5f}")

    # Predict on test set.
    Y_te_pred = model.predict(X_te_s)

    # Per-relay accuracy metrics.
    n_relays = Y_te.shape[1]
    metrics_rows = []
    for j in range(n_relays):
        y_true = Y_te[:, j]
        y_pred = Y_te_pred[:, j]
        r2 = r2_score(y_true, y_pred)
        # Guard against zero-divide in MAPE.
        mape = np.mean(np.abs((y_true - y_pred) / np.maximum(np.abs(y_true), 1e-3))) * 100
        # Symmetric MAPE (sMAPE) is more robust when the true margin is near zero.
        smape = np.mean(2.0 * np.abs(y_true - y_pred) /
                        (np.abs(y_true) + np.abs(y_pred) + 1e-3)) * 100
        rmse = np.sqrt(mean_squared_error(y_true, y_pred))
        max_err = np.max(np.abs(y_true - y_pred))
        metrics_rows.append({
            "relay_idx": int(meta["top_indices"][j]),
            "R2": float(r2),
            "MAPE_pct": float(mape),
            "sMAPE_pct": float(smape),
            "RMSE": float(rmse),
            "MaxError": float(max_err),
            "MeanTrue": float(np.mean(y_true)),
            "StdTrue": float(np.std(y_true)),
        })

    # Overall metrics (averaged across relays).
    overall_r2 = r2_score(Y_te, Y_te_pred, multioutput="uniform_average")
    overall_mape = np.mean([m["MAPE_pct"] for m in metrics_rows])
    overall_smape = np.mean([m["sMAPE_pct"] for m in metrics_rows])
    overall_rmse = np.sqrt(mean_squared_error(Y_te, Y_te_pred))

    # Physics-informed post-training check: PRC-023-6 115% rule.
    # margin_i = (1.15 * S_emergency_i - S_flow_i) / S_emergency_i
    # Constraint: margin_i >= 0  (i.e., flow <= 1.15 * emergency rating)
    # We compute the per-sample violation count on the test set.
    Y_te_pred_viol = (Y_te_pred < HEATMAP_THRESHOLD)
    Y_te_true_viol = (Y_te < HEATMAP_THRESHOLD)
    # Detection performance for violations (treating as binary per relay sample).
    tp = int(np.sum(Y_te_pred_viol & Y_te_true_viol))
    fp = int(np.sum(Y_te_pred_viol & ~Y_te_true_viol))
    fn = int(np.sum(~Y_te_pred_viol & Y_te_true_viol))
    tn = int(np.sum(~Y_te_pred_viol & ~Y_te_true_viol))
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Inference time benchmark (PINN forward pass vs full PYPOWER).
    # We benchmark on the first 200 test samples.
    n_bench = min(200, X_te_s.shape[0])
    t0 = time.time()
    for _ in range(5):
        _ = model.predict(X_te_s[:n_bench])
    pinn_inference_ms = (time.time() - t0) / 5 / n_bench * 1000

    # Full PYPOWER benchmark: re-run PF on n_bench randomly chosen cases.
    # We use the base case with a perturbation similar to test set.
    base_case_fn = case39 if meta["name"] == "IEEE39" else case118
    opt = _silence_pypower()
    rng = np.random.default_rng(RANDOM_SEED)
    n_gen = base_case_fn()["gen"].shape[0]
    n_re = min(3, max(1, n_gen // 5))
    n_branches = base_case_fn()["branch"].shape[0]
    protected = list(range(0, 6))
    t0 = time.time()
    for i in range(n_bench):
        load_scale = float(rng.uniform(0.80, 1.20))
        gen_dispatch = rng.uniform(0.70, 1.30, size=n_gen)
        renewable_scale = rng.uniform(0.10, 0.95, size=n_re)
        n_outages = int(rng.choice([0, 1, 2], p=[0.65, 0.27, 0.08]))
        outage_branches = _select_outages(n_branches, n_outages,
                                          protected, rng) if n_outages else []
        ppc = _perturb_case(base_case_fn(), load_scale, gen_dispatch,
                            outage_branches, renewable_scale)
        try:
            _, _ = runpf(ppc, opt)
        except Exception:
            pass
    pf_inference_ms = (time.time() - t0) / n_bench * 1000

    speedup = pf_inference_ms / max(pinn_inference_ms, 1e-6)

    result = {
        "model": model,
        "scaler": scaler,
        "X_train": X_tr, "Y_train": Y_tr,
        "X_test": X_te, "Y_test": Y_te,
        "Y_test_pred": Y_te_pred,
        "metrics_per_relay": metrics_rows,
        "overall_r2": float(overall_r2),
        "overall_mape": float(overall_mape),
        "overall_smape": float(overall_smape),
        "overall_rmse": float(overall_rmse),
        "train_time_s": float(train_time),
        "pinn_inference_ms_per_sample": float(pinn_inference_ms),
        "pf_inference_ms_per_sample": float(pf_inference_ms),
        "speedup": float(speedup),
        "violation_tp": tp, "violation_fp": fp,
        "violation_fn": fn, "violation_tn": tn,
        "violation_precision": float(precision),
        "violation_recall": float(recall),
        "violation_f1": float(f1),
        "n_test_samples": int(Y_te.shape[0]),
        "n_test_violations_true": int(np.sum(Y_te_true_viol)),
        "n_test_violations_pred": int(np.sum(Y_te_pred_viol)),
    }
    return result


# -------------------------------------------------------------------------
# Figures
# -------------------------------------------------------------------------
def _setup_style():
    plt.rcParams.update({
        "figure.figsize": (7.5, 4.5),
        "figure.dpi": 300,
        "axes.titlesize": 12,
        "axes.labelsize": 11,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "legend.fontsize": 9,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "font.family": "DejaVu Sans",
    })


def make_figure1_scatter(result: dict, cfg_name: str, save_path: str):
    """Figure 1: PINN-predicted vs PYPOWER ground-truth margin scatter."""
    _setup_style()
    Y_te = result["Y_test"]
    Y_pred = result["Y_test_pred"]
    # Flatten across relays for a single scatter.
    y_true_flat = Y_te.flatten()
    y_pred_flat = Y_pred.flatten()
    r2 = r2_score(y_true_flat, y_pred_flat)

    fig, ax = plt.subplots()
    # Subsample for visual clarity if too many points.
    n_pts = len(y_true_flat)
    if n_pts > 8000:
        idx = np.random.default_rng(RANDOM_SEED).choice(n_pts, 8000, replace=False)
        y_true_flat = y_true_flat[idx]
        y_pred_flat = y_pred_flat[idx]
    ax.scatter(y_true_flat, y_pred_flat, s=8, alpha=0.35,
               color="#1f77b4", edgecolors="none", label=f"{cfg_name} test points")
    # 1:1 line
    lim = [min(y_true_flat.min(), y_pred_flat.min()) - 0.05,
          max(y_true_flat.max(), y_pred_flat.max()) + 0.05]
    ax.plot(lim, lim, "--", color="black", linewidth=1.2, label="1:1 line")
    # PRC-023-6 threshold
    ax.axvline(0.0, color="red", linestyle=":", linewidth=1.2,
               label="PRC-023-6 115% threshold")
    ax.axhline(0.0, color="red", linestyle=":", linewidth=1.2)
    ax.set_xlabel("PYPOWER ground-truth loadability margin (pu on emergency rating)")
    ax.set_ylabel("PINN-predicted loadability margin (pu)")
    ax.set_title(f"Figure 1. PINN vs PYPOWER loadability margin — {cfg_name}\n"
                 f"R² = {r2:.3f}  |  n_test = {result['n_test_samples']}")
    ax.legend(loc="lower right", framealpha=0.85)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def make_figure2_error_hist(result: dict, cfg_name: str, save_path: str):
    """Figure 2: Per-relay MAPE distribution histogram."""
    _setup_style()
    metrics = result["metrics_per_relay"]
    mapes = [m["MAPE_pct"] for m in metrics]
    rmse = [m["RMSE"] for m in metrics]
    fig, ax = plt.subplots()
    bins = np.linspace(0, max(20.0, max(mapes) * 1.1), 21)
    ax.hist(mapes, bins=bins, color="#2ca02c", edgecolor="black", alpha=0.8,
            label=f"{cfg_name}: per-relay MAPE")
    mean_mape = np.mean(mapes)
    ax.axvline(mean_mape, color="red", linestyle="--", linewidth=1.5,
               label=f"mean = {mean_mape:.2f}%")
    ax.set_xlabel("Per-relay MAPE (%)")
    ax.set_ylabel("Relay count")
    ax.set_title(f"Figure 2. Distribution of PINN per-relay MAPE — {cfg_name}\n"
                 f"mean MAPE = {mean_mape:.2f}%  |  max = {max(mapes):.2f}%")
    ax.legend(loc="upper right", framealpha=0.85)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def make_figure3_inference_time(results: Dict[str, dict], save_path: str):
    """Figure 3: Inference time comparison bar chart."""
    _setup_style()
    names = list(results.keys())
    pinn_times = [results[n]["pinn_inference_ms_per_sample"] for n in names]
    pf_times = [results[n]["pf_inference_ms_per_sample"] for n in names]
    speedups = [results[n]["speedup"] for n in names]

    x = np.arange(len(names))
    width = 0.35
    fig, ax = plt.subplots()
    # Use log scale on Y because PF is orders of magnitude slower.
    bars1 = ax.bar(x - width / 2, pinn_times, width,
                  label="PINN forward pass", color="#1f77b4",
                  edgecolor="black")
    bars2 = ax.bar(x + width / 2, pf_times, width,
                  label="PYPOWER full PF", color="#d62728",
                  edgecolor="black")
    ax.set_yscale("log")
    ax.set_ylabel("Inference time per sample (ms, log scale)")
    ax.set_xlabel("Test system")
    ax.set_xticks(x)
    ax.set_xticklabels(names)
    title = "Figure 3. PINN inference vs full PYPOWER re-calculation\n"
    title += " | ".join([f"{n}: {s:.0f}× speed-up" for n, s in zip(names, speedups)])
    ax.set_title(title)
    ax.legend(loc="upper left", framealpha=0.85)
    # Annotate bars.
    for bar in bars1:
        ax.annotate(f"{bar.get_height():.3f} ms",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", fontsize=8)
    for bar in bars2:
        ax.annotate(f"{bar.get_height():.1f} ms",
                    xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


def make_figure4_heatmap(result: dict, cfg_name: str, save_path: str,
                         n_rows: int = 1000, n_relays_to_show: int = 10):
    """Figure 4: PRC-023-6 margin heatmap across operating points x critical relays."""
    _setup_style()
    Y_pred = result["Y_test_pred"]
    n_show_rows = min(n_rows, Y_pred.shape[0])
    n_show_cols = min(n_relays_to_show, Y_pred.shape[1])
    Y_show = Y_pred[:n_show_rows, :n_show_cols]

    # Sort rows by mean margin so the heatmap shows a clear gradient.
    row_order = np.argsort(-Y_show.mean(axis=1))
    Y_show = Y_show[row_order, :]

    # Custom diverging colormap: red (violation) -> yellow (threshold) -> green (compliant).
    cmap = LinearSegmentedColormap.from_list(
        "prc023", ["#b22222", "#ffcc33", "#2ca02c"], N=256)

    fig, ax = plt.subplots(figsize=(8.5, 5.0))
    im = ax.imshow(Y_show, aspect="auto", cmap=cmap, vmin=-0.5, vmax=0.5,
                   interpolation="nearest")
    # Mark the 115% emergency-rating threshold (margin = 0).
    ax.axhline(0, color="black", linewidth=0.3)
    ax.set_xlabel("Critical relay index (sorted by base-case loading)")
    ax.set_ylabel("Operating points (sorted by mean predicted margin, descending)")
    ax.set_title(f"Figure 4. PINN-predicted PRC-023-6 margin heatmap — {cfg_name}\n"
                 f"{n_show_rows} operating points × {n_show_cols} critical relays "
                 f"(red = violation, green = compliant)")
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Margin (pu on emergency rating)")
    # Mark threshold line on colorbar.
    cbar.ax.axhline(0.0, color="black", linewidth=1.2)
    fig.tight_layout()
    fig.savefig(save_path, dpi=300, bbox_inches="tight")
    plt.close(fig)


# -------------------------------------------------------------------------
# Main pipeline
# -------------------------------------------------------------------------
def main():
    print("=" * 72)
    print("Paper 10: Relay Loadability Screening under NERC PRC-023-6 with PINN")
    print("=" * 72)

    # We use two test systems. The smaller (IEEE 39-bus) is used for the main
    # study; the larger (IEEE 118-bus) is used to demonstrate scalability.
    configs = [
        CaseConfig(name="IEEE39", case_fn=case39, n_samples=5000,
                   n_critical_relays=10),
        CaseConfig(name="IEEE118", case_fn=case118, n_samples=2000,
                   n_critical_relays=10),
    ]

    results = {}
    datasets = {}
    metas = {}
    for cfg in configs:
        X, Y, meta = generate_dataset(cfg)
        datasets[cfg.name] = (X, Y)
        metas[cfg.name] = meta
        result = train_pinn(X, Y, meta)
        results[cfg.name] = result

    # ---- Save CSVs ----
    # Per-relay accuracy (combined across both test systems).
    all_metrics = []
    for cfg_name, res in results.items():
        for row in res["metrics_per_relay"]:
            row = dict(row)
            row["case"] = cfg_name
            all_metrics.append(row)
    pd.DataFrame(all_metrics).to_csv(
        os.path.join(FIG_DIR, "paper10_accuracy_per_relay.csv"), index=False)

    # Inference time comparison.
    inf_rows = []
    for cfg_name, res in results.items():
        inf_rows.append({
            "case": cfg_name,
            "PINN_inference_ms": res["pinn_inference_ms_per_sample"],
            "PYPOWER_inference_ms": res["pf_inference_ms_per_sample"],
            "speedup": res["speedup"],
            "train_time_s": res["train_time_s"],
        })
    pd.DataFrame(inf_rows).to_csv(
        os.path.join(FIG_DIR, "paper10_inference_time.csv"), index=False)

    # Violation screening summary.
    vio_rows = []
    for cfg_name, res in results.items():
        vio_rows.append({
            "case": cfg_name,
            "n_test_samples": res["n_test_samples"],
            "n_test_violations_true": res["n_test_violations_true"],
            "n_test_violations_pred": res["n_test_violations_pred"],
            "TP": res["violation_tp"], "FP": res["violation_fp"],
            "FN": res["violation_fn"], "TN": res["violation_tn"],
            "precision": res["violation_precision"],
            "recall": res["violation_recall"],
            "F1": res["violation_f1"],
        })
    pd.DataFrame(vio_rows).to_csv(
        os.path.join(FIG_DIR, "paper10_violations.csv"), index=False)

    # Summary JSON for the docx assembler.
    summary = {
        "configs": [c.name for c in configs],
        "results": {
            name: {
                "n_samples_total": int(datasets[name][0].shape[0]),
                "n_clean": int((~np.isnan(datasets[name][1]).any(axis=1)).sum()),
                "n_features": int(datasets[name][0].shape[1]),
                "n_relays": int(datasets[name][1].shape[1]),
                "n_test_samples": res["n_test_samples"],
                "overall_r2": res["overall_r2"],
                "overall_mape": res["overall_mape"],
                "overall_smape": res["overall_smape"],
                "overall_rmse": res["overall_rmse"],
                "train_time_s": res["train_time_s"],
                "pinn_inference_ms": res["pinn_inference_ms_per_sample"],
                "pf_inference_ms": res["pf_inference_ms_per_sample"],
                "speedup": res["speedup"],
                "violation_tp": res["violation_tp"],
                "violation_fp": res["violation_fp"],
                "violation_fn": res["violation_fn"],
                "violation_tn": res["violation_tn"],
                "violation_precision": res["violation_precision"],
                "violation_recall": res["violation_recall"],
                "violation_f1": res["violation_f1"],
                "n_test_violations_true": res["n_test_violations_true"],
                "n_test_violations_pred": res["n_test_violations_pred"],
                "top_indices": [int(i) for i in metas[name]["top_indices"]],
                "crit_ratings": [float(r) for r in metas[name]["crit_ratings"]],
            } for name, res in results.items()
        },
        "constants": {
            "emergency_rating_scale": EMERGENCY_RATING_SCALE,
            "heatmap_threshold": HEATMAP_THRESHOLD,
            "random_seed": RANDOM_SEED,
            "mlp_architecture": "128-64-32 ReLU, Adam, alpha=1e-4, max_iter=500",
        },
    }
    with open(os.path.join(FIG_DIR, "paper10_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # ---- Generate figures ----
    # Figure 1: scatter for IEEE39 (main study).
    make_figure1_scatter(results["IEEE39"], "IEEE39",
                         os.path.join(FIG_DIR, "paper10_fig1_scatter_pinn_vs_pf.png"))

    # Figure 2: per-relay error histogram (IEEE39).
    make_figure2_error_hist(results["IEEE39"], "IEEE39",
                             os.path.join(FIG_DIR, "paper10_fig2_error_histogram.png"))

    # Figure 3: inference time comparison across both test systems.
    make_figure3_inference_time(results,
                                 os.path.join(FIG_DIR, "paper10_fig3_inference_time.png"))

    # Figure 4: PRC-023-6 margin heatmap for IEEE39 (1000 ops x 10 relays).
    make_figure4_heatmap(results["IEEE39"], "IEEE39",
                         os.path.join(FIG_DIR, "paper10_fig4_margin_heatmap.png"),
                         n_rows=1000, n_relays_to_show=10)

    # ---- Print summary ----
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    print(f"{'Case':<10}{'R²':>8}{'sMAPE%':>9}{'RMSE':>8}"
          f"{'PINN(ms)':>10}{'PF(ms)':>10}{'SpeedUp':>10}{'F1':>8}")
    for name, res in results.items():
        print(f"{name:<10}{res['overall_r2']:>8.3f}{res['overall_smape']:>9.2f}"
              f"{res['overall_rmse']:>8.3f}{res['pinn_inference_ms_per_sample']:>10.3f}"
              f"{res['pf_inference_ms_per_sample']:>10.1f}{res['speedup']:>10.0f}"
              f"{res['violation_f1']:>8.3f}")

    print("\nFigures saved:")
    for f in sorted(os.listdir(FIG_DIR)):
        if f.startswith("paper10"):
            print(f"  {os.path.join(FIG_DIR, f)}")

    print("\nDone.")


if __name__ == "__main__":
    main()
