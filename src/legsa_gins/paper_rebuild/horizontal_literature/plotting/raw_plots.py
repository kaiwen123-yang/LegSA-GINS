"""Raw dual-antenna and EXT04 mechanism plot families."""

from __future__ import annotations

from pathlib import Path

from .common import render_dataset_family
from .loaders import FrozenTable, IdentityMismatch
from .registry import PlotFamily
from .refinements import render_ext04


def render(
    family: PlotFamily,
    table: FrozenTable,
    output_dir: Path,
    **kwargs: object,
) -> list[str]:
    text = f"{family.title} {family.caption}".lower()
    method_tokens = {
        token.strip().lower()
        for token in family.method_layer.replace("/", " ").split()
        if token.strip()
    }
    if method_tokens <= {"ext01", "raw01"} and method_tokens:
        if "fix success" in text or "correct ambiguity" in text:
            raise IdentityMismatch("EXT01 must be labelled global optimum certified integer solutions")
    if method_tokens <= {"ext02", "raw02"} and method_tokens:
        if "ambiguity correctness" not in text and "accepted wrapped" in text:
            raise IdentityMismatch("EXT02 accepted wrapped solution requires ambiguity-correctness caveat")
    if family.plot_id == "RAW12_YANG_MODE_STATE_GRID":
        modes = {
            (
                str(row.get("system_mode")),
                str(row.get("constraint_mode")),
                str(row.get("baseline_sigma_m")),
            )
            for row in table.rows
        }
        if len(modes) != 10:
            raise IdentityMismatch(f"EXT03 registry requires all 10 modes, observed {len(modes)}")
    if family.plot_id.startswith("EXT04") and "mechanism only" not in family.scope_label.lower():
        raise IdentityMismatch("EXT04 must remain MECHANISM ONLY")
    if family.plot_id in {
        "EXT04_01_FAR_PAR_INVALID_FLOW",
        "EXT04_02_POLICY_MODE_STATE_HEATMAP",
        "EXT04_03_AMBIGUITY_QC_BASELINE_FUNNEL",
        "EXT04_04_POLICY_MODE_RUNTIME",
    }:
        return render_ext04(family, table, output_dir, **kwargs)
    return render_dataset_family(family, table, output_dir, **kwargs)
