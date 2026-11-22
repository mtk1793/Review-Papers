@echo off
REM Reproducible Windows setup. Set NLR_API_KEY and NLR_EMAIL in your shell ONLY.
python -m pip install -r requirements.txt
set PYTHONPATH=src
python -m pytest -q tests
if ERRORLEVEL 1 exit /b 1
python scripts\audit_claims.py
python scripts\run_smoke.py
if ERRORLEVEL 1 exit /b 1
ECHO Software QA done. These are NOT real-data scientific results.
ECHO To download ERA5: python scripts\download_era5.py
ECHO To download NOW23: set API key and email then python scripts\download_now23.py
ECHO For empirical runs: python scripts\run_empirical.py --config config\era5_hourly.json
