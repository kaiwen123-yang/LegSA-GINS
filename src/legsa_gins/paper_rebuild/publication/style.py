"""Publication figure style for the paper (AGENTS sections 13 and 14).

Rules encoded here: double-column width about 174 mm, panel labels only (no machine
title, no scope badge), units on the axes, grayscale-safe palette with distinct line
styles, PNG at least 4096 px wide plus PDF and SVG, no absolute paths in any text.
"""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

DOUBLE_COLUMN_MM = 174.0
SINGLE_COLUMN_MM = 88.9
MIN_PNG_WIDTH_PX = 4096
BASE_FONT_PT = 8.0

METHOD_ORDER = ["F01", "F02", "F03", "A04", "F04"]
# Okabe-Ito colour-blind-safe palette; every method also has its own line style and marker
COLORS = {
    "F01": "#4D4D4D",  # Single: dark grey (luminance 0.30)
    "F02": "#E69F00",  # Dual-basic: orange (0.69)
    "F03": "#56B4E9",  # Backbone: sky blue (0.66)
    "A04": "#0072B2",  # Core: blue (0.41)
    "F04": "#D55E00",  # Full: vermillion (0.49)
    "neutral": "#4D4D4D",
    "light": "#BFBFBF",
    "window": "#D9D9D9",
    "recovery": "#EFEFEF",
}
LINESTYLES = {"F01": (0, (1, 1)), "F02": (0, (5, 2)), "F03": (0, (4, 1, 1, 1, 1, 1)), "A04": "-", "F04": (0, (6, 2, 1, 2))}
MARKERS = {"F01": "x", "F02": "s", "F03": "o", "A04": "^", "F04": "D"}
LINEWIDTHS = {"F01": 0.9, "F02": 0.9, "F03": 1.0, "A04": 1.2, "F04": 1.0}
HATCH_SECONDARY = "////"   # second series of grouped bars, so bars stay distinguishable in grayscale
MIN_TEXT_PT = 7.0          # IEEE: nothing below about 7 pt at final size


def apply_rcparams() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
        "font.size": BASE_FONT_PT,
        "axes.titlesize": BASE_FONT_PT,
        "axes.labelsize": BASE_FONT_PT,
        "xtick.labelsize": MIN_TEXT_PT,
        "ytick.labelsize": MIN_TEXT_PT,
        "legend.fontsize": MIN_TEXT_PT,
        "hatch.linewidth": 0.4,
        "legend.frameon": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.6,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "lines.linewidth": 1.0,
        "grid.linewidth": 0.4,
        "grid.color": "#DDDDDD",
        "axes.grid": False,
        "figure.dpi": 100,
        "savefig.dpi": 600,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "mathtext.default": "regular",
    })


def width_inches(kind: str = "double") -> float:
    mm = DOUBLE_COLUMN_MM if kind == "double" else SINGLE_COLUMN_MM
    return mm / 25.4


def new_figure(nrows: int, ncols: int, height_in: float, kind: str = "double", **gridspec_kw):
    apply_rcparams()
    fig, axes = plt.subplots(nrows, ncols, figsize=(width_inches(kind), height_in), squeeze=False, gridspec_kw=gridspec_kw)
    return fig, axes


def new_gridspec_figure(height_in: float, nrows: int, ncols: int, kind: str = "double", **gridspec_kw):
    """Figure plus GridSpec for layouts that mix full-width and half-width panels."""
    apply_rcparams()
    fig = plt.figure(figsize=(width_inches(kind), height_in))
    gs = fig.add_gridspec(nrows, ncols, **gridspec_kw)
    return fig, gs


def panel_label(ax, letter: str, x: float = -0.16, y: float = 1.04) -> None:
    """(a), (b), ... in the top-left corner outside the axes, bold, 9 pt."""
    ax.text(x, y, f"({letter})", transform=ax.transAxes, fontsize=BASE_FONT_PT + 1, fontweight="bold",
            ha="left", va="bottom")


def png_dpi(fig: Figure) -> int:
    return int(math.ceil(MIN_PNG_WIDTH_PX / fig.get_figwidth())) + 1


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def save_figure(fig: Figure, out_dir: Path, figure_id: str) -> dict:
    """Write PNG (>= 4096 px wide), PDF and SVG; return paths, pixel width and hashes."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    from PIL import Image

    dpi = png_dpi(fig)
    paths = {}
    for ext in ("pdf", "svg"):
        p = out_dir / f"{figure_id}.{ext}"
        fig.savefig(p, bbox_inches="tight", pad_inches=0.02, facecolor="white")
        paths[ext] = p
    png = out_dir / f"{figure_id}.png"
    for _ in range(4):  # tight bbox crops the canvas; raise dpi until the PNG is wide enough
        fig.savefig(png, dpi=dpi, bbox_inches="tight", pad_inches=0.02, facecolor="white")
        with Image.open(png) as im:
            width_px, height_px = im.size
        if width_px >= MIN_PNG_WIDTH_PX:
            break
        dpi = int(math.ceil(dpi * MIN_PNG_WIDTH_PX / width_px * 1.02))
    paths["png"] = png
    return {
        "figure_id": figure_id,
        "png": str(paths["png"]), "pdf": str(paths["pdf"]), "svg": str(paths["svg"]),
        "png_dpi": dpi, "png_width_px": width_px, "png_height_px": height_px,
        "png_sha256": sha256_of(paths["png"]), "pdf_sha256": sha256_of(paths["pdf"]), "svg_sha256": sha256_of(paths["svg"]),
    }
