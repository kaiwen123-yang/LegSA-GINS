"""N7C Go2 horizontal velocity weak-prior policy.

中文说明：N7C 只允许 Go2 horizontal velocity(vn/ve) 作为弱先验进入 EKF；
vertical/yaw/position 不作为有效约束，Go2 velocity 也不是 truth。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


POLICY_NAME = "n7c_go2_horizontal_velocity_weak_prior"
POLICY_FRAME = "go2_velocity_as_body_flu_then_rotate_by_go2_attitude"
STD_VD_DISABLED = 999.0


@dataclass(frozen=True)
class Go2HorizontalVelocityPriorPolicy:
    policy_name: str = POLICY_NAME
    frame: str = POLICY_FRAME
    measurement_components: tuple[str, str] = ("vn", "ve")
    base_horizontal_std_mps: float = 2.0
    vertical_velocity_enabled: bool = False
    vertical_disabled_std_mps: float = STD_VD_DISABLED
    go2_yaw_prior_enabled: bool = False
    go2_position_prior_enabled: bool = False
    fgo_enabled: bool = False
    no_R_shrink: bool = True
    trace_tuning: bool = False
    final_v23_tuning: bool = False
    go2_velocity_truth_claim: bool = False
    paper_performance_claim: bool = False
    no_outperform_final_v23_claim: bool = True


def build_n7c_policy(n7b5_prior_report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = n7b5_prior_report or {}
    std_policy = report.get("std_policy", {}) if isinstance(report.get("std_policy"), dict) else {}
    base = std_policy.get("base_std_mps", report.get("base_horizontal_std_mps", 2.0))
    try:
        base_std = max(2.0, float(base))
    except (TypeError, ValueError):
        base_std = 2.0
    policy = Go2HorizontalVelocityPriorPolicy(base_horizontal_std_mps=base_std)
    data = asdict(policy)
    data.update(
        {
            "stage": "N7C_go2_horizontal_velocity_weak_prior",
            "n7b5_frame_equivalence_required": True,
            "n7b5_frame_equivalence_policy": "use_best_frame_horizontal_only",
            "source_aware_inflation_allowed": True,
            "source_aware_no_R_shrink": True,
            "main_candidate_variant": "go2_horizontal_velocity_weak_prior_main",
            "diagnostic_variants": [
                "go2_horizontal_velocity_probability_weighted",
                "go2_horizontal_velocity_contact_weighted",
                "go2_horizontal_velocity_high_confidence_only",
            ],
        }
    )
    return data


def confidence_bucket_from_quality(quality_flag: str) -> str:
    text = str(quality_flag or "").lower()
    if "high" in text:
        return "high"
    if "medium" in text:
        return "medium"
    return "low"


def validate_n7c_policy(policy: dict[str, Any]) -> tuple[bool, list[str]]:
    blockers: list[str] = []
    if policy.get("policy_name") != POLICY_NAME:
        blockers.append("policy_name_mismatch")
    if tuple(policy.get("measurement_components", ())) != ("vn", "ve"):
        blockers.append("measurement_not_horizontal_2d")
    if policy.get("vertical_velocity_enabled"):
        blockers.append("vertical_velocity_enabled")
    if policy.get("go2_yaw_prior_enabled"):
        blockers.append("go2_yaw_prior_enabled")
    if policy.get("go2_position_prior_enabled"):
        blockers.append("go2_position_prior_enabled")
    if policy.get("fgo_enabled"):
        blockers.append("fgo_enabled")
    if policy.get("trace_tuning") or policy.get("final_v23_tuning"):
        blockers.append("forbidden_tuning_enabled")
    if policy.get("go2_velocity_truth_claim"):
        blockers.append("go2_velocity_truth_claim")
    if policy.get("paper_performance_claim"):
        blockers.append("paper_performance_claim")
    return not blockers, blockers
