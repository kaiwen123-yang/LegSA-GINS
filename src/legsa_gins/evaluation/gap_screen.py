"""N4G gap screen for diagnostic trial candidates.

中文说明：gap_screen 只给下一阶段建议，不把候选结果写成正式性能结论。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def make_gap_screen(
    *,
    summary: dict[str, Any],
    gate_report: dict[str, Any],
    event_report: dict[str, Any],
    imu_report: dict[str, Any],
    imu_propagation_mode: str,
    heading_offset_mode: str,
) -> dict[str, Any]:
    severe_h = _gt(summary.get("horizontal_rmse_m"), 50.0)
    severe_up = _gt(summary.get("up_rmse_m"), 10.0)
    severe_yaw = _gt(summary.get("yaw_rmse_deg"), 20.0)
    all_severe = severe_h or severe_up or severe_yaw
    return {
        "event_normalized_time_axis": True,
        "clock_sync_claim": False,
        "physical_time_offset_claim": False,
        "go2_time_domain": event_report.get("go2_time_domain"),
        "gnss_time_domain": event_report.get("gnss_time_domain"),
        "imu_propagation_mode": imu_propagation_mode,
        "accel_contains_gravity": imu_report.get("accel_contains_gravity", True),
        "heading_offset_mode": heading_offset_mode,
        "possible_time_domain_issue": event_report.get("evidence_status") != "common_window_ready",
        "possible_imu_semantics_issue": imu_report.get("quaternion_rpy_consistency_status")
        not in {"passed", None},
        "possible_heading_mounting_issue": heading_offset_mode == "no_offset",
        "possible_full_mechanization_missing_issue": True,
        "severe_horizontal_error": severe_h,
        "severe_vertical_error": severe_up,
        "severe_yaw_error": severe_yaw,
        "target_gate_pass": gate_report.get("target_gate_pass", False),
        "ready_for_factor_stacking": gate_report.get("ready_for_factor_stacking", False),
        "recommended_next_stage": "N4H_full_kf_gins_style_ekf_reconstruction"
        if all_severe or not gate_report.get("ready_for_factor_stacking", False)
        else "manual_review_before_factor_stacking",
        "numerical_performance_claim": False,
        "trace_solver_input": False,
        "trace_used_for_alignment": False,
    }


def _gt(value: Any, threshold: float) -> bool:
    return isinstance(value, (int, float)) and float(value) > threshold


def write_gap_screen(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

