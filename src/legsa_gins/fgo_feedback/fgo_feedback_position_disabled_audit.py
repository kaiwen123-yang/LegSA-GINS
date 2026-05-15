"""N8H primary-position-disabled audit.

中文说明：区分 primary position disabled 与 diagnostic PVA position 统计。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_visual_loader import (
    DIAGNOSTIC_PVA_VARIANT,
    PRIMARY_FEEDBACK_VARIANT,
    N8HVisualInputs,
    safe_float,
    stats,
    write_json,
)


def build_position_disabled_audit(bundle: N8HVisualInputs) -> dict[str, Any]:
    primary_summary = bundle.variant_summaries.get(PRIMARY_FEEDBACK_VARIANT, {})
    pva_summary = bundle.variant_summaries.get(DIAGNOSTIC_PVA_VARIANT, {})
    primary_rows = bundle.update_trace_by_variant.get(PRIMARY_FEEDBACK_VARIANT, [])
    pva_rows = bundle.update_trace_by_variant.get(DIAGNOSTIC_PVA_VARIANT, [])

    primary_raw_position = [safe_float(row.get("position_norm_m")) for row in primary_rows]
    primary_applied_position = (
        primary_raw_position if primary_summary.get("position_enabled") is True else [0.0 for _ in primary_rows]
    )
    pva_raw_position = [safe_float(row.get("position_norm_m")) for row in pva_rows]
    pva_applied_position = pva_raw_position if pva_summary.get("position_enabled") is True else [0.0 for _ in pva_rows]
    aggregate_applied = []
    aggregate_includes_pva = False
    for variant_id, rows in bundle.update_trace_by_variant.items():
        enabled = bundle.variant_summaries.get(variant_id, {}).get("position_enabled") is True
        values = [safe_float(row.get("position_norm_m")) for row in rows]
        if enabled:
            aggregate_applied.extend(values)
            if variant_id == DIAGNOSTIC_PVA_VARIANT:
                aggregate_includes_pva = True
        else:
            aggregate_applied.extend(0.0 for _ in rows)

    primary_applied_stats = stats(primary_applied_position)
    violation = primary_summary.get("position_enabled") is False and primary_applied_stats["max"] > 1.0e-9
    if violation:
        status = "position_disabled_violation"
        decision_blocked = True
    elif aggregate_includes_pva:
        status = "aggregate_explained"
        decision_blocked = False
    else:
        status = "primary_position_disabled_confirmed"
        decision_blocked = False

    return {
        "stage": "N8H",
        "status": status,
        "decision_blocked": decision_blocked,
        "primary_variant": PRIMARY_FEEDBACK_VARIANT,
        "diagnostic_pva_variant": DIAGNOSTIC_PVA_VARIANT,
        "primary_position_enabled": bool(primary_summary.get("position_enabled")),
        "diagnostic_pva_position_enabled": bool(pva_summary.get("position_enabled")),
        "primary_position_correction_applied_stats_m": primary_applied_stats,
        "primary_position_residual_proxy_stats_m": stats(primary_raw_position),
        "diagnostic_pva_position_correction_applied_stats_m": stats(pva_applied_position),
        "all_variant_aggregate_position_correction_applied_stats_m": stats(aggregate_applied),
        "aggregate_includes_pva": aggregate_includes_pva,
        "summary_position_stats_may_include_disabled_residual_proxy": True,
        "boundary_explanation": (
            "Primary position feedback is disabled; nonzero primary position norms are residual proxies, "
            "not applied position feedback. Applied aggregate position correction is explained by diagnostic PVA."
        ),
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_position_disabled_audit(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
