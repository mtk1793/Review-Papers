#!/usr/bin/env bash
set -euo pipefail
python -m pip install -r requirements.txt
export PYTHONPATH=src
python -m pytest -q tests
python scripts/audit_claims.py
python scripts/run_smoke.py
echo 'QA passed; real empirical evaluation still needs downloaded data.'
