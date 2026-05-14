"""Runtime config helpers for C++ EKF feedback interface.

中文说明：这里仅生成 runtime-only feedback 配置，tracked 文件不写本地绝对路径。
"""

from __future__ import annotations

from pathlib import Path

from .feedback_state_types import FeedbackGateThresholds, FeedbackVariantSpec


def append_feedback_config(
    config_path: str | Path,
    *,
    observation_path: str | Path,
    variant: FeedbackVariantSpec,
    thresholds: FeedbackGateThresholds | None = None,
    covariance_scale: float = 1.0,
) -> None:
    limits = thresholds or FeedbackGateThresholds()
    path = Path(config_path)
    lines = [
        "",
        "# N8G FGO feedback EKF foundation; runtime-only observation path.",
        "enable_fgo_feedback: true",
        f"fgo_feedback_path: {Path(observation_path)}",
        "fgo_feedback_mode: pseudo_measurement",
        f"fgo_feedback_position_enabled: {str(variant.position_enabled).lower()}",
        f"fgo_feedback_velocity_enabled: {str(variant.velocity_enabled).lower()}",
        f"fgo_feedback_attitude_enabled: {str(variant.attitude_enabled).lower()}",
        f"fgo_feedback_covariance_scale: {covariance_scale}",
        f"fgo_feedback_max_position_correction_m: {limits.max_position_correction_m}",
        f"fgo_feedback_max_velocity_correction_mps: {limits.max_velocity_correction_mps}",
        f"fgo_feedback_max_attitude_correction_deg: {limits.max_attitude_correction_deg}",
        f"fgo_feedback_min_interval_s: {limits.min_interval_s}",
        "fgo_feedback_no_future_data_required: true",
        "trace_solver_input: false",
        "final_v23_output_solver_input: false",
        "paper_performance_claim: false",
    ]
    path.write_text(path.read_text(encoding="utf-8") + "\n".join(lines) + "\n", encoding="utf-8")


def feedback_interface_contract() -> dict[str, object]:
    return {
        "fgo_feedback_enters_ekf_update": True,
        "fgo_feedback_mode": "pseudo_measurement",
        "output_substitution": False,
        "direct_nav_override": False,
        "state_feedback_required_after_update": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
