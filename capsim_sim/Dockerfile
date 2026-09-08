# CAPSM Stage-1 simulation — Dockerfile
#
# Build a self-contained image that can:
#   - reproduce every figure in the thesis (capsim run-all)
#   - launch the interactive dashboard (capsim dashboard)
#   - run the test suite (capsim test)
#
# Image size: ~1.2 GB (CPU-only torch + pandas + scipy + scikit-learn +
# streamlit + plotly). No CUDA / GPU support — that's a deliberate choice
# to keep the image portable; the CNN-LSTM inference is small enough that
# CPU is fine for thesis-scale validation.
#
# Build:
#   docker build -t capsim-sim:1.0.0 .
#
# Run (one-shot reproduce, writes everything to /app/results/):
#   docker run --rm -v "$PWD/results:/app/results" -v "$PWD/thesis_artifacts:/app/thesis_artifacts" capsim-sim:1.0.0 capsim run-all
#
# Run (dashboard, then visit http://localhost:8501):
#   docker run --rm -p 8501:8501 -v "$PWD/results:/app/results" capsim-sim:1.0.0 capsim dashboard
#
# Run (interactive shell):
#   docker run --rm -it -v "$PWD/results:/app/results" capsim-sim:1.0.0 bash
#
# The /app/data/raw volume is shared between containers via a named
# volume `capsim-opspd-data` so the 242 MB OPSD download only happens once.

FROM python:3.12-slim AS base

# --- System deps for PYPOWER (pandas/numpy/scipy need libgomp + libstdc++) ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgomp1 \
        libstdc++6 \
        fonts-noto-core \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# --- Create non-root user (so files written to mounted volumes are
#     ownable by the host user, and we're not running as root in prod) ---
RUN useradd --create-home --uid 1000 capsim
WORKDIR /app
RUN chown capsim:capsim /app

USER capsim
ENV PATH="/home/capsim/.local/bin:${PATH}" \
    PYTHONPATH="/app" \
    MPLBACKEND="Agg" \
    PYTHONDONTWRITEBYTECODE=1

# --- Install Python deps first (cached layer; rebuild only when
#     requirements.txt changes) ---
COPY --chown=capsim:capsim capsim_sim/requirements.txt /tmp/requirements.txt
RUN pip install --user --no-cache-dir -r /tmp/requirements.txt
# CPU-only torch (smaller than the default CUDA build)
RUN pip install --user --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.14.0
# Optional dashboard deps (streamlit + plotly)
RUN pip install --user --no-cache-dir streamlit plotly

# --- Copy the capsm package + scripts + tests ---
COPY --chown=capsim:capsim capsim_sim /app/capsim_sim
WORKDIR /app/capsim_sim

# Install the package itself (so the `capsim` CLI is on PATH)
RUN pip install --user --no-cache-dir -e .

# --- Default command: print help ---
CMD ["capsim", "--help"]

# --- Image metadata ---
LABEL org.opencontainers.image.title="capsim-sim" \
      org.opencontainers.image.description="CAPSM Stage-1 — Cognitive Adaptive Power System Management, offline Python validation on real OPSD data" \
      org.opencontainers.image.authors="Mahmoud Kiasari <mahmoud.kiasari@dal.ca>" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.url="https://github.com/mtk1793/PhD-Thesis" \
      org.opencontainers.image.source="https://github.com/mtk1793/PhD-Thesis"
