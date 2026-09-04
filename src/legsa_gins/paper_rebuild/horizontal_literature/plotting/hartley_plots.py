"""Hartley gauge, observability, contact-topology, and NIS figures only."""

from __future__ import annotations

from pathlib import Path

from .common import render_dataset_family
from .loaders import FrozenTable, IdentityMismatch
from .registry import PlotFamily
from .refinements import render_hartley

FORBIDDEN = ("absolute_position_rmse", "absolute_yaw_rmse")


def render(
    family: PlotFamily,
    table: FrozenTable,
    output_dir: Path,
    **kwargs: object,
) -> list[str]:
    identity = " ".join((family.title, family.caption, *family.y_fields, *family.required_fields)).lower()
    if any(field in identity for field in FORBIDDEN):
        raise IdentityMismatch("Hartley absolute position/yaw RMSE is forbidden")
    if family.plot_id in {
        "HAR06_GAUGE_EQUIVALENCE_QUANTILES",
        "HAR07_GAUGE_TOLERANCE_NORMALIZED",
        "HAR08_OBSERVABILITY_RANK_NULLITY",
        "HAR09_NONGAUGE_SINGULAR_AND_WEAK_DIRECTIONS",
        "HAR10_TOPOLOGY_NIS_CHI_SQUARE",
    }:
        return render_hartley(family, table, output_dir, **kwargs)
    return render_dataset_family(family, table, output_dir, **kwargs)
