"""PAPER10M1R2C2 method-mode yaw semantic checks."""

from __future__ import annotations

from typing import Any


METHODS = [
    "basic_dual_baseline",
    "strong_dual_yaw_baseline",
    "legsa_without_qm",
    "legsa_full_candidate_with_qm",
]


def method_mode_yaw_semantic_row(
    method_mode_id: str,
    mode: dict[str, Any],
    effective_flags: dict[str, bool],
    *,
    yaw_source_path: str,
    yaw_provider_fixed: bool,
) -> dict[str, Any]:
    required_value = mode.get("required_provider_sources", mode.get("required_inputs", ""))
    if isinstance(required_value, list):
        required = ";".join(str(item) for item in required_value)
    else:
        required = str(required_value)
    uses_yaw = "dual_antenna_yaw" in required or bool(effective_flags.get("enable_dual_yaw_update"))
    qm_enabled = bool(effective_flags.get("enable_multi_state_qm"))
    source_aware = bool(effective_flags.get("enable_source_aware"))
    semantic_status = "PASS" if uses_yaw and yaw_provider_fixed else "BLOCKED"
    blocker = "" if semantic_status == "PASS" else "yaw provider body-heading convention not fixed"
    return {
        "method_mode_id": method_mode_id,
        "yaw_source_path": yaw_source_path,
        "yaw_source_role": "solver_visible_provider_dual_antenna_yaw",
        "yaw_unit": "deg",
        "yaw_frame": "NED solver body heading",
        "body_heading_or_baseline_heading": "body_heading",
        "lateral_offset_applied": True,
        "lateral_offset_sign": "baseline_heading_plus_90_equivalent",
        "gnss_order_used": "gnss2_minus_gnss1",
        "wrap_policy": "wrap360",
        "time_alignment_policy": "provider_time_plus_runner_time_offset",
        "yaw_std_source": "provider_fixed_1p5_deg",
        "yaw_std_unit": "deg",
        "source_aware_yaw_scaling_enabled": source_aware,
        "qm_yaw_handling_enabled": qm_enabled,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "legsa_output_solver_input": False,
        "yaw_provider_fixed": yaw_provider_fixed,
        "semantic_status": semantic_status,
        "blocker": blocker,
    }


def common_yaw_convention_pass(rows: list[dict[str, Any]]) -> bool:
    conventions = {
        (
            row.get("yaw_unit"),
            row.get("yaw_frame"),
            row.get("body_heading_or_baseline_heading"),
            row.get("lateral_offset_sign"),
            row.get("gnss_order_used"),
        )
        for row in rows
    }
    return len(conventions) == 1 and all(row.get("semantic_status") == "PASS" for row in rows)
