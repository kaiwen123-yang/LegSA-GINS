"""Machine QA for publication figures (AGENTS section 13 visual contract).

Checks run on the matplotlib Figure before saving and on the rendered PNG after:
forbidden text (machine titles, badges, verdicts, paths), panel labels on every
data axes when the figure has more than one, a unit on every non-empty axis label,
minimum pixel width, non-blank raster, and perceptual-hash duplicates across the
figures of one run (the legacy "same plot under many names" failure).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from matplotlib.figure import Figure
from matplotlib.text import Text

FORBIDDEN_TOKENS = ("DIAGNOSTIC", "ONLY", "PASS", "FAIL", "/mnt/", "RUN_", ".csv", "attempt", "scope", "coverage panel", "\\\\")
PANEL_LABEL_RE = re.compile(r"^\([a-z]\)$")
UNIT_RE = re.compile(r"\((m|°|deg|s|%|count|cases|ratio|fraction|m/s)\)")
MIN_PNG_WIDTH_PX = 4096
BLANK_STD_THRESHOLD = 4.0
DUPLICATE_HAMMING_MAX = 8


def figure_texts(fig: Figure) -> list[str]:
    return [t.get_text() for t in fig.findobj(Text) if t.get_text().strip()]


def check_figure(fig: Figure, figure_id: str) -> list[dict]:
    """Return a list of check rows; every row has figure_id, check, pass, detail."""
    rows: list[dict] = []
    texts = figure_texts(fig)
    hits = sorted({tok for tok in FORBIDDEN_TOKENS for t in texts if tok in t})
    rows.append({"figure_id": figure_id, "check": "no_forbidden_text", "pass": not hits, "detail": ",".join(hits)})
    rows.append({"figure_id": figure_id, "check": "no_suptitle", "pass": not (fig._suptitle and fig._suptitle.get_text().strip()), "detail": ""})
    data_axes = [ax for ax in fig.axes if ax.get_visible() and ax.get_label() != "<colorbar>" and (ax.lines or ax.patches or ax.collections or ax.images)]
    if len(data_axes) > 1:
        missing = []
        for ax in data_axes:
            labels = [t.get_text() for t in ax.texts if PANEL_LABEL_RE.match(t.get_text().strip())]
            if not labels:
                missing.append(ax.get_ylabel() or ax.get_title() or "unnamed axes")
        rows.append({"figure_id": figure_id, "check": "panel_labels", "pass": not missing, "detail": ";".join(missing)})
    unitless = []
    for ax in data_axes:
        for lab in (ax.get_xlabel(), ax.get_ylabel()):
            if lab.strip() and not UNIT_RE.search(lab) and not re.search(r"\b(ECDF|method|family|type|degradation|configuration)\b", lab, re.I):
                unitless.append(lab)
    rows.append({"figure_id": figure_id, "check": "axis_units", "pass": not unitless, "detail": ";".join(unitless)})
    return rows


def average_hash(png_path: Path, size: int = 16) -> np.ndarray:
    from PIL import Image

    with Image.open(png_path) as im:
        g = np.asarray(im.convert("L").resize((size, size), Image.Resampling.LANCZOS), dtype=float)
    return (g > g.mean()).astype(np.uint8).ravel()


def check_png(png_path: Path, figure_id: str) -> list[dict]:
    from PIL import Image

    rows: list[dict] = []
    with Image.open(png_path) as im:
        width = im.size[0]
        gray = np.asarray(im.convert("L"), dtype=float)
    rows.append({"figure_id": figure_id, "check": "png_min_width", "pass": width >= MIN_PNG_WIDTH_PX, "detail": f"{width}px"})
    rows.append({"figure_id": figure_id, "check": "png_not_blank", "pass": gray.std() > BLANK_STD_THRESHOLD, "detail": f"std={gray.std():.1f}"})
    rows.append({"figure_id": figure_id, "check": "png_file_size", "pass": png_path.stat().st_size > 20_000, "detail": f"{png_path.stat().st_size} bytes"})
    return rows


def duplicate_pairs(hashes: dict[str, np.ndarray], max_hamming: int = DUPLICATE_HAMMING_MAX) -> list[tuple[str, str, int]]:
    ids = sorted(hashes)
    pairs = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            d = int(np.count_nonzero(hashes[a] != hashes[b]))
            if d <= max_hamming:
                pairs.append((a, b, d))
    return pairs
