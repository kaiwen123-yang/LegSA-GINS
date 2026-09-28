"""Shared publication-scale style without importing pyplot in the parent process."""

from __future__ import annotations

from typing import Any

METHOD_COLORS = {
    "Reference": "#111111",
    "RAW01": "#2F6BFF",
    "EXT01": "#2F6BFF",
    "RAW02": "#F28E2B",
    "EXT02": "#F28E2B",
    "RAW03": "#36A165",
    "EXT03": "#36A165",
    "EXT04": "#8C8C8C",
    "LC01": "#7B61FF",
    "GINAV": "#D95F02",
    "LC02": "#D95F02",
    "Hartley": "#009E73",
    "LSE01": "#009E73",
    "F02": "#7A7A7A",
    "F03": "#4C78A8",
    "A04": "#2CA02C",
    "F04": "#D62728",
}

LAYOUT_PIXELS = {
    "normal": (5120, 2880),
    "dense": (7680, 4320),
    "portrait": (4320, 5760),
    "square": (4096, 4096),
    "panel": (4096, 2304),
}

SCOPE_LABELS = {
    "FORMAL C00",
    "NATIVE C00",
    "CANONICAL-541",
    "DIAGNOSTIC ONLY",
    "STRUCTURAL ONLY",
    "MECHANISM ONLY",
    "COVERAGE-AWARE",
}

# Reference-provenance caveats belong in the paper text/caption outside figures.
# The plotting layer intentionally uses only the short display labels Truth or
# Truth Trajectory where a reference series is actually drawn.
REFERENCE_NOTE = ""
BASELINE_NOTE = (
    "Hard-constrained baseline length; not independent accuracy evidence."
)


def pixels_for_layout(
    layout: str,
    *,
    default_width: int = 5120,
    default_height: int = 2880,
    dense_width: int = 7680,
    dense_height: int = 4320,
) -> tuple[int, int]:
    if layout == "normal":
        return default_width, default_height
    if layout == "dense":
        return dense_width, dense_height
    if layout == "portrait":
        return LAYOUT_PIXELS["portrait"]
    if layout == "square":
        return LAYOUT_PIXELS["square"]
    if layout == "panel":
        return LAYOUT_PIXELS["panel"]
    raise ValueError(f"unknown layout: {layout}")


def apply_style(matplotlib_module: Any) -> None:
    """Apply the frozen visual contract after a worker selects the Agg backend."""

    matplotlib_module.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans", "Arial", "Noto Sans"],
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "axes.titlesize": 30,
            "axes.labelsize": 26,
            "xtick.labelsize": 22,
            "ytick.labelsize": 22,
            "legend.fontsize": 22,
            "lines.linewidth": 3.0,
            "lines.markersize": 10,
            "grid.color": "#D8D8D8",
            "grid.alpha": 0.7,
            "grid.linewidth": 1.0,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def color_for(label: str, index: int = 0) -> str:
    upper = label.upper()
    for key, color in METHOD_COLORS.items():
        if key.upper() in upper:
            return color
    fallback = ["#4C78A8", "#F28E2B", "#36A165", "#7B61FF", "#8C8C8C"]
    return fallback[index % len(fallback)]


def add_scope_badge(fig: Any, scope: str) -> None:
    fig.text(
        0.985,
        0.975,
        scope,
        ha="right",
        va="top",
        fontsize=22,
        fontweight="bold",
        color="#202020",
        bbox={"boxstyle": "round,pad=0.35", "fc": "#F1F1F1", "ec": "#777777"},
    )
