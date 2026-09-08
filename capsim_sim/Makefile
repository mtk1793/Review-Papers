# CAPSM Stage-1 simulation — Makefile
#
# Common entry points:
#   make all          # run phases 0..6 + tests
#   make reproduce    # run phases 1..6 (reuse cached OPSD data, skip download)
#   make phaseN       # run only phase N (0..6)
#   make test         # run pytest suite
#   make summary      # just regenerate results/SUMMARY.md
#   make clean-data    # delete downloaded OPSD CSVs (~242 MB) and the parquet cache
#   make clean-results # delete everything under results/
#   make clean        # clean-data + clean-results
#   make install       # pip install -e . (editable)
#   make deps          # pip install -r requirements.txt + CPU torch
#   make dashboard     # launch the Streamlit dashboard

PY      ?= python
SCRIPTS  = scripts
PYTHONPATH := .

.DEFAULT_GOAL := all

.PHONY: all reproduce test summary clean clean-data clean-results install deps \
        phase0 phase1 phase2 phase3 phase4 phase5 phase6 dashboard

all: deps
	$(PY) $(SCRIPTS)/run_all.py --test

reproduce: deps
	$(PY) $(SCRIPTS)/run_all.py --skip 0 --test

phase0:
	$(PY) $(SCRIPTS)/phase0_data.py
phase1:
	$(PY) $(SCRIPTS)/phase1_data.py
phase2:
	$(PY) $(SCRIPTS)/phase2_grid.py
phase3:
	$(PY) $(SCRIPTS)/phase3_baselines.py
phase4:
	$(PY) $(SCRIPTS)/phase4_system1.py
phase5:
	$(PY) $(SCRIPTS)/phase5_system2.py
phase6:
	$(PY) $(SCRIPTS)/phase6_arbiter.py

test:
	$(PY) -m pytest tests -q

summary:
	$(PY) -c "from scripts.run_all import write_summary_md; import json; from pathlib import Path; write_summary_md([{'phase': n, 'ok': True, 'runtime_s': 0, 'desc': ''} for n in range(7)])"

dashboard:
	$(PY) -m streamlit run $(SCRIPTS)/dashboard.py

install:
	$(PY) -m pip install -e .

deps:
	$(PY) -m pip install -r requirements.txt
	@$(PY) -c "import torch; assert '+cpu' in torch.__version__ or torch.cuda.is_available()" 2>/dev/null \
		|| $(PY) -m pip install torch --index-url https://download.pytorch.org/whl/cpu

clean-data:
	rm -rf data/raw/time_series_*.csv data/processed

clean-results:
	rm -rf results/phase*/ results/SUMMARY.md thesis_artifacts

clean: clean-data clean-results
