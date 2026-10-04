#!/usr/bin/env python3
"""Reproduce the leak-free PG-CARE v2 study from the package root.

External measured-data adapters are deliberately excluded from the default run.
The current manuscript does not claim that external validation has been executed.
"""
from __future__ import annotations
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STAGES = [
    (11, "generate leak-free digital twin", ROOT / "code_v2" / "11_generate_leakfree_twin.py"),
    (12, "train/calibrate PG-CARE v2", ROOT / "code_v2" / "12_train_leakfree_pgcare.py"),
    (13, "generalization and feature ablations", ROOT / "code_v2" / "13_generalization_ablation.py"),
    (14, "IEEE 33-bus QSTS + RBR", ROOT / "code_v2" / "14_ieee33_qsts.py"),
    (15, "block bootstrap + leak invariant", ROOT / "code_v2" / "15_block_bootstrap_and_tests.py"),
    (16, "figures", ROOT / "code_v2" / "16_make_v2_figures.py"),
    (17, "Word manuscript", ROOT / "code_v2" / "17_build_v2_manuscript.py"),
    (18, "IEEEtran LaTeX source", ROOT / "code_v2" / "18_build_v2_latex.py"),
]


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=ROOT, check=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-stage", type=int, default=11, choices=range(11, 19))
    ap.add_argument("--through-stage", type=int, default=18, choices=range(11, 19))
    ap.add_argument("--compile-pdf", action="store_true", help="After stage 18, run pdflatex twice if available.")
    args = ap.parse_args()
    if args.from_stage > args.through_stage:
        ap.error("--from-stage must be <= --through-stage")
    for n, desc, script in STAGES:
        if args.from_stage <= n <= args.through_stage:
            if not script.exists():
                raise FileNotFoundError(script)
            print(f"\n=== Stage {n}: {desc} ===", flush=True)
            run([sys.executable, str(script)])
    if args.compile_pdf and args.through_stage >= 18:
        texdir = ROOT / "manuscript_v2"
        tex = texdir / "PG_CARE_Leakage_Free_IEEE_Transactions_Manuscript.tex"
        for _ in range(2):
            run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex.name])
    print("\nReproduction pipeline completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
