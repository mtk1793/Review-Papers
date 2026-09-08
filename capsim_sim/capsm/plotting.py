"""Shared plotting style for all CAPSM figures.

Goals:
- One place to set the visual identity of every figure that goes into the thesis.
- All figures exported at 300 dpi as both PNG (slides / Word) and PDF (vector, LaTeX).
- `constrained_layout=True` everywhere; never call `tight_layout()` or
  `bbox_inches='tight'` because they fight `constrained_layout`.
- Predictable font fallback (Noto Sans SC for CJK glyphs, DejaVu Sans for math symbols).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt

# --- Public configuration knobs ------------------------------------------------
DPI = 300
DEFAULT_FMT = ("png", "pdf")

PALETTE = [
    "#0072B2",  # blue
    "#D55E00",  # vermillion
    "#009E73",  # bluish green
    "#CC79A7",  # reddish purple
    "#E69F00",  # orange
    "#56B4E9",  # sky blue
    "#F0E442",  # yellow
    "#000000",  # black
]


def _register_fonts() -> None:
    candidates = [
        "/usr/share/fonts/truetype/chinese/NotoSansSC-Regular.ttf",
        "/usr/share/fonts/truetype/noto-serif-sc/NotoSerifSC-Regular.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            fm.fontManager.addfont(path)
        except (FileNotFoundError, RuntimeError):
            pass


def set_style() -> None:
    _register_fonts()
    matplotlib.use("Agg")
    plt.rcParams.update({
        "font.sans-serif": ["Noto Sans SC", "DejaVu Sans", "Arial", "Helvetica"],
        "font.family": "sans-serif",
        "font.size": 11,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.labelsize": 11,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "grid.linestyle": "--",
        "grid.linewidth": 0.5,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "legend.frameon": False,
        "axes.unicode_minus": False,
        "savefig.dpi": DPI,
        "figure.dpi": 100,
        "figure.autolayout": False,
        "axes.prop_cycle": plt.cycler(color=PALETTE),
    })


def save_figure(fig, base_path: str | Path, formats=DEFAULT_FMT) -> list[Path]:
    base = Path(base_path)
    written: list[Path] = []
    for fmt in formats:
        out = base.with_suffix(f".{fmt}")
        fig.savefig(out, dpi=DPI, format=fmt)
        written.append(out)
    return written
