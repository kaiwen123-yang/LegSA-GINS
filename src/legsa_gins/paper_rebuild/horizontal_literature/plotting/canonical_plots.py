"""Canonical-541 aggregates, never substituted for normal C00."""

from __future__ import annotations

from pathlib import Path

from .common import render_dataset_family
from .loaders import FrozenTable, IdentityMismatch
from .registry import PlotFamily
from .refinements import render_canonical


def render(
    family: PlotFamily,
    table: FrozenTable,
    output_dir: Path,
    **kwargs: object,
) -> list[str]:
    if family.source_root != "canonical" or family.scope_label != "CANONICAL-541":
        raise IdentityMismatch("Canonical-541 family must use canonical aggregate source and scope")
    if "/14_FULL_PLOTTING/" in str(table.source).replace("\\", "/"):
        raise IdentityMismatch("prior Canonical plotting output is not evidence")
    if family.plot_id in {
        "C541_06_A04_F04_PAIRED_DELTA_DISTRIBUTION",
        "C541_07_A04_F04_PAIRED_SCATTER",
        "C541_08_WIN_TIE_LOSS_BY_FAMILY",
    }:
        return render_canonical(family, table, output_dir, **kwargs)
    return render_dataset_family(family, table, output_dir, **kwargs)
