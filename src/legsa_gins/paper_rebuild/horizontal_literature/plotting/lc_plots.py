"""Frozen LC01 and coverage-aware GINav plot families."""

from __future__ import annotations

from pathlib import Path

from .common import render_dataset_family
from .loaders import FrozenTable, IdentityMismatch
from .registry import PlotFamily
from .refinements import render_cross, render_lc, render_lc_extra

REFINED = {
    "LC01_FORMAL_C00_COVERAGE",
    "LC02_FORMAL_POSITION_METRICS",
    "LC03_FORMAL_ATTITUDE_METRICS",
    "LC04_FORMAL_TAIL_METRICS",
    "LC07_GINAV_STATUS_TIMELINE",
    "LC10_COMMON_SUPPORT_77_DIAGNOSTIC",
}


def render(
    family: PlotFamily,
    table: FrozenTable,
    output_dir: Path,
    **kwargs: object,
) -> list[str]:
    if "GINAV" in family.plot_id and family.allow_gap_fill:
        raise IdentityMismatch("GINav alignment/pre-alignment gaps cannot be filled")
    if family.plot_id == "LC10_COMMON_SUPPORT_77_DIAGNOSTIC" and family.scope_label != "DIAGNOSTIC ONLY":
        raise IdentityMismatch("77-epoch common support is diagnostic only")
    if family.plot_id in REFINED:
        return render_lc(family, table, output_dir, **kwargs)
    if family.plot_id in {
        "LC05_TIME_SUPPORT_GAPS_SEGMENTS",
        "LC06_INITIALIZATION_AND_UPDATE_FUNNEL",
        "LC08_GINAV_LC_UPDATE_VS_INS_ONLY",
    }:
        return render_lc_extra(family, table, output_dir, **kwargs)
    if family.plot_id == "XLYR06_SOLUTION_LEVEL_FORMAL_COMPOSITE":
        return render_cross(family, table, output_dir, **kwargs)
    return render_dataset_family(family, table, output_dir, **kwargs)
