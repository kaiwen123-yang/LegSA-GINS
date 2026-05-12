"""N7B2A Go2 attitude-prior standard-deviation policy review.

中文说明：5 deg 是 Go2 roll/pitch weak-prior measurement uncertainty，不是
gate threshold；RPY/quaternion 一致性只说明 Go2 内部格式一致，不证明绝对精度。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _num(value: Any, fallback: float | None = None) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def review_go2_attitude_prior_std_policy(n7a_reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    build = n7a_reports.get("weak_prior_build", {})
    quat = n7a_reports.get("quaternion_rpy", {})
    comparison = n7a_reports.get("comparison", {})
    std_policy = build.get("std_policy", {}) if isinstance(build.get("std_policy"), dict) else {}
    current_std = _num(std_policy.get("std_roll_deg"), 5.0) or 5.0
    std_screen = comparison.get("std_screen_summaries", [])
    if not isinstance(std_screen, list):
        std_screen = []
    quaternion_status = str(quat.get("rpy_consistency_status", "unknown"))
    quaternion_delta = _num(quat.get("max_quat_rpy_delta_rad"))
    return {
        "stage": "N7B2A_go2_metric_contact_visual_audit",
        "current_roll_pitch_std_deg": current_std,
        "current_pitch_std_deg": _num(std_policy.get("std_pitch_deg"), current_std) or current_std,
        "is_gate_or_threshold": False,
        "is_measurement_std": True,
        "reason_for_weak_prior": (
            "Go2 roll/pitch are robot internal attitude signals, useful only as a conservative weak prior after "
            "source, time, frame, and quaternion/RPY checks."
        ),
        "quaternion_rpy_internal_consistency": {
            "status": quaternion_status,
            "max_delta_rad": quaternion_delta,
            "activation_allowed_for_attitude_prior": bool(quat.get("activation_allowed_for_attitude_prior")),
            "internal_consistency_not_absolute_truth": True,
        },
        "absolute_truth_available": False,
        "go2_attitude_not_truth": True,
        "suggested_future_std_screen": [1.0, 1.6, 3.0, 5.0],
        "existing_n7a_std_screen": [
            {"std_deg": row.get("std_deg"), "diagnostic_only": True, "summary": row.get("summary", {})}
            for row in std_screen
            if isinstance(row, dict)
        ],
        "recommended_policy": [
            "keep_5deg_for_N7A_safety",
            "review_1p6_or_3deg_in_future_N7C_if_activation_needed",
        ],
        "std_policy_status": "clear",
        "no_trace_tuning": True,
        "no_paper_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_position_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "fgo": False,
    }


def write_go2_attitude_prior_std_policy_review(
    n7a_reports: dict[str, dict[str, Any]],
    output_dir: str | Path,
) -> tuple[Path, dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = review_go2_attitude_prior_std_policy(n7a_reports)
    path = out / "GO2_ATTITUDE_PRIOR_STD_POLICY_REVIEW.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, report
