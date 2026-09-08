"""CAPSM Stage-1 interactive dashboard.

Run with:
    streamlit run scripts/dashboard.py
or via the capsim CLI after `pip install -e .`:
    capsim dashboard
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from capsm.agents.baselines import BASELINES, NoControl, run_controller  # noqa: E402
from capsm.data.opsd import SPLITS, load_opsd  # noqa: E402
from capsm.grid.environment import QSTSEnvironment  # noqa: E402

try:
    from capsm.agents.system1 import CNNLSTM, StateEncoder, System1Controller  # noqa: E402
    from capsm.agents.system2 import QIRLController  # noqa: E402
    from capsm.agents.arbiter import MetacognitiveArbiter  # noqa: E402
    from capsm.agents.trainer import collect_demos, train_behavior_cloning  # noqa: E402
    _AI_AVAILABLE = True
except Exception as e:
    st.error(f"Could not import AI controllers: {e}")
    _AI_AVAILABLE = False

import plotly.graph_objects as go  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402


@st.cache_data(show_spinner=False)
def get_opspan() -> tuple[pd.Timestamp, pd.Timestamp]:
    df = load_opsd()
    return df.index.min(), df.index.max()


@st.cache_data(show_spinner=False)
def get_profile_slice(start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    return load_opsd(start=start.isoformat(), end=end.isoformat())


@st.cache_resource(show_spinner="Training System 1 (CNN-LSTM, ~30 s) ...")
def get_system1() -> "System1Controller | None":
    if not _AI_AVAILABLE:
        return None
    profiles = load_opsd(start="2019-01-01", end="2019-01-31")
    env = QSTSEnvironment("case39", profiles)
    encoder = StateEncoder(env)
    trajs, _ = collect_demos("case39", profiles, n_episodes=4, steps_per_episode=168)
    model = train_behavior_cloning(trajs, encoder.n_features, 9,
                                   epochs=50, batch_size=128, lr=1e-3,
                                   verbose=False)
    return System1Controller(model, encoder)


def sidebar_controls(opspan: tuple[pd.Timestamp, pd.Timestamp]) -> dict:
    st.sidebar.title("CAPSM Stage-1 dashboard")
    st.sidebar.markdown(
        "Live QSTS on real OPSD data (DOI "
        "[10.25832/time_series/2020-10-06](https://doi.org/10.25832/time_series/2020-10-06)). "
        "Every run is real measured load + wind + solar; nothing is synthesised."
    )

    st.sidebar.markdown("### Renewable penetration")
    wind_pen = st.sidebar.slider("Wind penetration (% of mean load)", 0, 40, 20, step=1) / 100.0
    solar_pen = st.sidebar.slider("Solar penetration (% of mean load)", 0, 20, 10, step=1) / 100.0

    st.sidebar.markdown("### Date window (real OPSD data)")
    start = st.sidebar.date_input("Start date", value=pd.Timestamp("2019-01-01").date(),
                                  min_value=opspan[0].date(), max_value=opspan[1].date())
    end = st.sidebar.date_input("End date", value=pd.Timestamp("2019-01-08").date(),
                                min_value=opspan[0].date(), max_value=opspan[1].date())
    if end <= start:
        st.sidebar.error("End date must be after start date.")
        st.stop()

    st.sidebar.markdown("### Controller")
    controller = st.sidebar.selectbox(
        "Pick a controller",
        ["NoControl", "RuleBased", "PID", "System 1 (CNN-LSTM)",
         "System 2 (QIRL)", "CAPSM (Arbiter)"], index=0,
    )

    st.sidebar.markdown("### IEEE test system")
    case = st.sidebar.selectbox("Case", ["case9", "case14", "case39", "case118"], index=2,
                                help="case39 is the thesis primary system. FACTS + EV V2G only exist on case39.")
    if case != "case39" and controller != "NoControl":
        st.sidebar.warning("FACTS + EV V2G models are only defined on case39. "
                           "Controllers other than NoControl will be a no-op on this case.")

    run_btn = st.sidebar.button("Run QSTS", type="primary")
    return {"wind_pen": wind_pen, "solar_pen": solar_pen,
            "start": pd.Timestamp(start, tz="UTC"),
            "end": pd.Timestamp(end, tz="UTC") + pd.Timedelta(days=1) - pd.Timedelta(hours=1),
            "controller": controller, "case": case, "run": run_btn}


def build_controller(name: str, env: QSTSEnvironment):
    if name == "NoControl":
        return NoControl()
    if name == "RuleBased":
        return BASELINES[1]()
    if name == "PID":
        return BASELINES[2]()
    if name == "System 1 (CNN-LSTM)":
        s1 = get_system1()
        if s1 is None:
            st.error("System 1 unavailable (AI modules not loaded).")
            st.stop()
        return s1
    if name == "System 2 (QIRL)":
        return QIRLController(n_candidates=32, seed=42)
    if name == "CAPSM (Arbiter)":
        s1 = get_system1()
        if s1 is None:
            st.error("CAPSM unavailable (System 1 modules not loaded).")
            st.stop()
        s2 = QIRLController(n_candidates=32, seed=42)
        return MetacognitiveArbiter(s1, s2, threshold=0.03)
    raise ValueError(f"Unknown controller: {name}")


def run_scenario(opts: dict):
    profiles = get_profile_slice(opts["start"], opts["end"])
    if len(profiles) < 24:
        st.error(f"Profile window has only {len(profiles)} hours; need at least 24.")
        st.stop()
    env = QSTSEnvironment(opts["case"], profiles,
                          wind_penetration=opts["wind_pen"],
                          solar_penetration=opts["solar_pen"])
    controller = build_controller(opts["controller"], env)
    df = run_controller(env, controller, start=opts["start"].isoformat())
    return df, env


def plot_trajectory(df: pd.DataFrame, controller_name: str) -> go.Figure:
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                       subplot_titles=("Total load (MW)", "Losses (MW)", "min/max voltage (p.u.)"))
    fig.add_trace(go.Scatter(x=df.index, y=df["total_load_mw"], name="Load",
                             line=dict(color="#6c757d", width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["losses_mw"], name="Losses",
                             line=dict(color="#dc3545", width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["vm_min"], name="min Vm",
                             line=dict(color="#0072B2", width=1.5)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["vm_max"], name="max Vm",
                             line=dict(color="#E69F00", width=1.5)), row=3, col=1)
    fig.add_hline(y=0.95, line_dash="dash", line_color="black", line_width=1, row=3, col=1)
    fig.add_hline(y=1.05, line_dash="dash", line_color="black", line_width=1, row=3, col=1)
    fig.update_layout(height=720, template="plotly_white",
                      title_text=f"CAPSM QSTS — {controller_name}, {df.index[0]} → {df.index[-1]}")
    fig.update_xaxes(title_text="Time (UTC)", row=3, col=1)
    return fig


def plot_summary_bars(df: pd.DataFrame, controller_name: str, nocontrol_viol: int) -> go.Figure:
    metrics = {
        "Voltage violations (bus-h)": int(df["n_voltage_violations"].sum()),
        "Mean losses (MW)": float(df["losses_mw"].mean()),
        "Mean |V−1| (p.u.)": float(df["voltage_deviation_pu"].mean()),
        "Min Vm (p.u.)": float(df["vm_min"].min()),
    }
    fig = go.Figure()
    colors = ["#dc3545", "#fd7e14", "#56B4E9", "#0072B2"]
    for (label, val), color in zip(metrics.items(), colors):
        fig.add_trace(go.Bar(x=[label], y=[val], name=label, marker_color=color,
                             text=[f"{val:.4g}"], textposition="outside"))
    fig.update_layout(height=320, template="plotly_white",
                      title_text=f"Headline metrics — {controller_name}", showlegend=False)
    if controller_name != "NoControl" and nocontrol_viol > 0:
        delta = metrics["Voltage violations (bus-h)"] - nocontrol_viol
        pct = 100 * delta / nocontrol_viol
        fig.add_annotation(x=0, y=1.1, xref="paper", yref="paper",
                           text=f"vs NoControl: {delta:+d} bus-h ({pct:+.2f}%)",
                           showarrow=False,
                           font=dict(size=14, color="#dc3545" if delta < 0 else "#198754"))
    return fig


def main() -> None:
    st.set_page_config(page_title="CAPSM Stage-1 dashboard", page_icon="⚡", layout="wide")
    opspan = get_opspan()
    opts = sidebar_controls(opspan)

    st.title("⚡ CAPSM Stage-1 — live demo")
    st.markdown(f"Real OPSD data coverage: **{opspan[0]} → {opspan[1]}**. "
                f"You picked: **{opts['controller']}** on **{opts['case']}**, "
                f"wind {opts['wind_pen']*100:.0f}%, solar {opts['solar_pen']*100:.0f}%, "
                f"window {opts['start']} → {opts['end']}.")

    if not opts["run"]:
        st.info("Click **Run QSTS** in the sidebar to start a simulation.")
        st.markdown("### Headline result (Jan 2019, case39, 721 h, pre-computed)")
        st.markdown("| Controller | Violations | Δ vs NoControl | Inference (ms/step) |\n"
                    "|---|---:|---:|---:|\n"
                    "| NoControl | 2847 | — | 8.7 |\n"
                    "| RuleBased | 2846 | −1 (−0.04%) | 8.7 |\n"
                    "| PID | 2842 | −5 (−0.18%) | 8.7 |\n"
                    "| System 1 (CNN-LSTM) | 2824 | −23 (−0.81%) | 10.3 |\n"
                    "| System 2 (QIRL) | 2810 | −37 (−1.30%) | 9.2 |\n"
                    "| **CAPSM (Arbiter)** | 2815 | **−32 (−1.12%)** | 10.8 |")
        st.caption("Source: results/phase6/phase6_summary.json (auto-generated by `capsim run-all`).")
        return

    with st.spinner("Running live QSTS on real OPSD data ..."):
        df, env = run_scenario(opts)

    with st.spinner("Running NoControl baseline for comparison ..."):
        df0, _ = run_scenario({**opts, "controller": "NoControl"})
        nocontrol_viol = int(df0["n_voltage_violations"].sum())

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Hours simulated", f"{len(df)}")
    col2.metric("Converged steps", f"{int(df['converged'].sum())}/{len(df)}")
    col3.metric("Voltage violations (bus-h)", f"{int(df['n_voltage_violations'].sum())}",
                delta=f"{int(df['n_voltage_violations'].sum()) - nocontrol_viol:+d} vs NoControl")
    col4.metric("Renewable curtailment (h)", f"{env.curtailment_hours}")

    st.plotly_chart(plot_trajectory(df, opts["controller"]), use_container_width=True)
    st.plotly_chart(plot_summary_bars(df, opts["controller"], nocontrol_viol),
                    use_container_width=True)

    with st.expander("Show raw metrics table"):
        st.dataframe(df[["total_load_mw", "losses_mw", "vm_min", "vm_max",
                         "voltage_deviation_pu", "n_voltage_violations",
                         "converged"]].head(200), use_container_width=True)

    st.caption("Dashboard built with Streamlit + Plotly. Reuses "
               "capsm.grid.QSTSEnvironment and capsm.agents.{baselines,system1,system2,arbiter}. "
               "QSTS powered by PYPOWER.")


if __name__ == "__main__":
    main()
