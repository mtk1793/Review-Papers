"""CAPSM command-line interface.

Entry point exposed by `pip install capsim-sim` as the `capsim` command.
Provides one-line access to the most common operations without needing
to remember which script to run.

Usage:
    capsim                       # show help
    capsim download              # Phase 0: download OPSD real data
    capsim reproduce             # run phases 1-6 (assumes data is cached)
    capsim run-all               # run phases 0-6 + tests (full pipeline)
    capsim dashboard             # launch the Streamlit dashboard
    capsim test                  # run pytest suite
    capsim phase 4                # run only phase 4 (CNN-LSTM training)
    capsim artifacts             # generate thesis_artifacts/ figures + tables
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _run(script_name: str, *extra: str) -> int:
    """Run a script under capsm_sim/scripts/ as a subprocess with the
    package on PYTHONPATH. Returns the exit code."""
    script = SCRIPTS / script_name
    if not script.exists():
        print(f"error: {script} not found", file=sys.stderr)
        return 2
    cmd = [sys.executable, str(script), *extra]
    return subprocess.call(cmd, cwd=ROOT,
                           env={"PYTHONPATH": str(ROOT),
                                "PATH": "/usr/bin:/bin:/usr/local/bin"})


def _run_module(module: str, *extra: str) -> int:
    """Run a Python module (e.g. `pytest`, `streamlit`) as a subprocess."""
    return subprocess.call([sys.executable, "-m", module, *extra],
                           cwd=ROOT,
                           env={"PYTHONPATH": str(ROOT),
                                "PATH": "/usr/bin:/bin:/usr/local/bin"})


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="capsim",
        description="CAPSM Stage-1 simulation CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("download",    help="Phase 0: download real OPSD data + integrity report")
    sub.add_parser("reproduce",  help="Run phases 1-6 (skips Phase 0, reuses cached OPSD data)")
    sub.add_parser("run-all",    help="Run phases 0-6 + pytest (full pipeline)")
    sub.add_parser("dashboard",  help="Launch the Streamlit dashboard")
    sub.add_parser("test",       help="Run the 52-test pytest suite")
    sub.add_parser("artifacts",  help="Regenerate thesis_artifacts/ figures + tables")

    p_phase = sub.add_parser("phase", help="Run a single phase N (0-6)")
    p_phase.add_argument("n", type=int, choices=[0, 1, 2, 3, 4, 5, 6])

    args = parser.parse_args()

    if args.cmd is None:
        parser.print_help()
        return 0

    if args.cmd == "download":
        return _run("phase0_data.py")
    if args.cmd == "reproduce":
        return _run("run_all.py", "--skip", "0")
    if args.cmd == "run-all":
        return _run("run_all.py", "--test")
    if args.cmd == "dashboard":
        return _run_module("streamlit", "run", str(SCRIPTS / "dashboard.py"))
    if args.cmd == "test":
        return _run_module("pytest", str(ROOT / "tests"), "-q")
    if args.cmd == "artifacts":
        gen_script = SCRIPTS / "generate_thesis_artifacts.py"
        if not gen_script.exists():
            print("error: scripts/generate_thesis_artifacts.py not found — "
                  "commit it from Phase B first", file=sys.stderr)
            return 2
        return subprocess.call([sys.executable, str(gen_script)],
                               cwd=ROOT,
                               env={"PYTHONPATH": str(ROOT),
                                    "PATH": "/usr/bin:/bin:/usr/local/bin"})
    if args.cmd == "phase":
        n = args.n
        script_map = {
            0: "phase0_data.py", 1: "phase1_data.py",
            2: "phase2_grid.py", 3: "phase3_baselines.py",
            4: "phase4_system1.py", 5: "phase5_system2.py",
            6: "phase6_arbiter.py",
        }
        return _run(script_map[n])

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
