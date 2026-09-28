"""Internal full-window Canonical C00 figures."""

from __future__ import annotations

from pathlib import Path

from .common import render_dataset_family
from .loaders import FrozenTable, IdentityMismatch
from .registry import PlotFamily
from .refinements import render_internal

EXPECTED_YAW = {"F02": 2.338, "F03": 1.962, "A04": 1.934, "F04": 1.955}


def render(
    family: PlotFamily,
    table: FrozenTable,
    output_dir: Path,
    **kwargs: object,
) -> list[str]:
    if family.plot_id.startswith("INT") and "case_id" in table.columns:
        cases = {str(row.get("case_id")) for row in table.rows}
        if cases != {"C00_clean_normal"}:
            raise IdentityMismatch(f"internal formal source must be only C00_clean_normal, got {sorted(cases)}")
    if (
        family.plot_id.startswith("INT")
        and "method_id" in table.columns
        and "yaw_rmse_deg" in family.required_fields
    ):
        observed = {str(row.get("method_id")): row.get("yaw_rmse_deg") for row in table.rows}
        for method, expected in EXPECTED_YAW.items():
            value = observed.get(method)
            if not isinstance(value, (int, float)) or abs(float(value) - expected) > 0.25:
                raise IdentityMismatch(f"{method} C00 yaw identity mismatch: {value}")
    if family.plot_id in {
        "INT01_FORMAL_C00_RMSE",
        "INT02_FORMAL_C00_TAIL_METRICS",
        "INT03_FORMAL_C00_COVERAGE_AND_TIME",
        "INT04_C00_HORIZONTAL_AND_3D_ERROR_TIME",
        "INT05_C00_ATTITUDE_ERROR_TIME",
        "INT06_C00_ERROR_ECDF",
    }:
        return render_internal(family, table, output_dir, **kwargs)
    return render_dataset_family(family, table, output_dir, **kwargs)
