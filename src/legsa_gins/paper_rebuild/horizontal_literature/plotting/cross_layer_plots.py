"""Registry, comparability, and cross-layer synthesis figures."""

from __future__ import annotations

from pathlib import Path

from .common import render_dataset_family
from .loaders import FrozenTable
from .registry import PlotFamily
from .refinements import render_cross


def render(
    family: PlotFamily,
    table: FrozenTable,
    output_dir: Path,
    **kwargs: object,
) -> list[str]:
    if family.plot_id == "XLYR06_SOLUTION_LEVEL_FORMAL_COMPOSITE":
        return render_cross(family, table, output_dir, **kwargs)
    return render_dataset_family(family, table, output_dir, **kwargs)
