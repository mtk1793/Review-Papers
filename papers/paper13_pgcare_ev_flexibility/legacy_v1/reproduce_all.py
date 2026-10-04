"""Reproduce the complete PG-CARE study and Word manuscript.
Run from the project root with: python reproduce_all.py
"""
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parent
scripts=[
 '01_generate_digital_twin.py',
 '02_train_core_models.py',
 '03_train_modern_baselines.py',
 '04_build_pgcare.py',
 '05_ood_and_statistics.py',
 '07_pgcare_bootstrap.py',
 '08_inference_timing.py',
 '09_make_figures.py',
 '10_build_manuscript.py',
]
for s in scripts:
    print(f'\n=== {s} ===',flush=True)
    subprocess.run([sys.executable,str(ROOT/'code'/s)],check=True,cwd=ROOT)
