"""N8I feedback policy grid definitions.

中文说明：N8I 只定义 solver 可见的 feedback 策略消融网格，不读取 trace 或
final_v23 输出调 gate/covariance。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .feedback_state_types import FeedbackGateThresholds, FeedbackVariantSpec
from .fgo_feedback_visual_loader import write_json


FEEDBACK_MODE_DIMENSION = [
    "horizontal_velocity_attitude_primary",
    "velocity_attitude",
    "velocity_only",
    "attitude_only",
    "PVA_diagnostic",
    "reject_all_sanity",
]

COVARIANCE_INFLATION_DIMENSION = [
    "inflation_x1",
    "inflation_x2",
    "inflation_x4",
    "inflation_auto_from_residual_proxy",
]

GATE_POLICY_DIMENSION = [
    "default_gate",
    "attitude_max_3deg",
    "attitude_max_4deg",
    "velocity_max_0p3mps",
    "velocity_max_0p5mps",
    "combined_conservative_gate",
]

WINDOW_POLICY_DIMENSION = [
    "window_3s_stride_1s",
    "window_5s_stride_1s",
    "window_10s_stride_1s",
    "window_5s_stride_2s",
]

POSITION_POLICY_DIMENSION = [
    "position_disabled_primary",
    "PVA_diagnostic_only",
]


@dataclass(frozen=True)
class FeedbackPolicySpec:
    policy_id: str
    mode_id: str
    feedback_mode: str
    position_enabled: bool
    velocity_enabled: bool
    attitude_enabled: bool
    covariance_policy: str = "inflation_auto_from_residual_proxy"
    covariance_inflation: float = 2.0
    covariance_scale: float = 1.0
    gate_policy: str = "default_gate"
    window_duration_s: float = 5.0
    feedback_stride_s: float = 1.0
    reject_all: bool = False
    diagnostic_only: bool = False
    run_feedback: bool = True

    def thresholds(self) -> FeedbackGateThresholds:
        return thresholds_for_gate_policy(self.gate_policy)

    def variant_spec(self) -> FeedbackVariantSpec:
        return FeedbackVariantSpec(
            self.policy_id,
            self.feedback_mode,
            position_enabled=self.position_enabled,
            velocity_enabled=self.velocity_enabled,
            attitude_enabled=self.attitude_enabled,
            reject_all=self.reject_all,
            diagnostic_only=self.diagnostic_only,
        )

    def to_report_dict(self) -> dict[str, Any]:
        limits = self.thresholds()
        return {
            "policy_id": self.policy_id,
            "mode_id": self.mode_id,
            "feedback_mode": self.feedback_mode,
            "position_enabled": self.position_enabled,
            "velocity_enabled": self.velocity_enabled,
            "attitude_enabled": self.attitude_enabled,
            "covariance_policy": self.covariance_policy,
            "covariance_inflation": self.covariance_inflation,
            "covariance_scale": self.covariance_scale,
            "gate_policy": self.gate_policy,
            "gate_thresholds": {
                "max_position_correction_m": limits.max_position_correction_m,
                "max_velocity_correction_mps": limits.max_velocity_correction_mps,
                "max_attitude_correction_deg": limits.max_attitude_correction_deg,
                "max_yaw_correction_deg": limits.max_yaw_correction_deg,
                "min_window_epoch_count": limits.min_window_epoch_count,
                "min_interval_s": limits.min_interval_s,
            },
            "window_duration_s": self.window_duration_s,
            "feedback_stride_s": self.feedback_stride_s,
            "position_policy": "PVA_diagnostic_only" if self.position_enabled else "position_disabled_primary",
            "reject_all": self.reject_all,
            "diagnostic_only": self.diagnostic_only,
            "run_feedback": self.run_feedback,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "paper_performance_claim": False,
        }


def thresholds_for_gate_policy(policy_id: str) -> FeedbackGateThresholds:
    if policy_id == "attitude_max_3deg":
        return FeedbackGateThresholds(max_attitude_correction_deg=3.0, max_yaw_correction_deg=3.0)
    if policy_id == "attitude_max_4deg":
        return FeedbackGateThresholds(max_attitude_correction_deg=4.0, max_yaw_correction_deg=4.0)
    if policy_id == "velocity_max_0p3mps":
        return FeedbackGateThresholds(max_velocity_correction_mps=0.3)
    if policy_id == "velocity_max_0p5mps":
        return FeedbackGateThresholds(max_velocity_correction_mps=0.5)
    if policy_id == "combined_conservative_gate":
        return FeedbackGateThresholds(
            max_velocity_correction_mps=0.5,
            max_attitude_correction_deg=4.0,
            max_yaw_correction_deg=4.0,
        )
    return FeedbackGateThresholds()


def covariance_inflation_for_policy(policy_id: str) -> float:
    if policy_id == "inflation_x1":
        return 1.0
    if policy_id == "inflation_x4":
        return 4.0
    if policy_id == "inflation_auto_from_residual_proxy":
        return 2.0
    return 2.0


def build_feedback_policy_grid() -> dict[str, Any]:
    curated_specs = build_mode_ablation_specs() + build_gate_sweep_specs() + build_covariance_sweep_specs() + build_window_policy_specs()
    unique: dict[str, FeedbackPolicySpec] = {spec.policy_id: spec for spec in curated_specs}
    full_factorial_count = (
        len(FEEDBACK_MODE_DIMENSION)
        * len(COVARIANCE_INFLATION_DIMENSION)
        * len(GATE_POLICY_DIMENSION)
        * len(WINDOW_POLICY_DIMENSION)
    )
    return {
        "stage": "N8I",
        "dimensions": {
            "feedback_mode": FEEDBACK_MODE_DIMENSION,
            "covariance_inflation": COVARIANCE_INFLATION_DIMENSION,
            "gate_policy": GATE_POLICY_DIMENSION,
            "window_policy": WINDOW_POLICY_DIMENSION,
            "position_policy": POSITION_POLICY_DIMENSION,
        },
        "full_factorial_policy_count": full_factorial_count,
        "runtime_curated_policy_count": len(unique),
        "runtime_curated_policies": [spec.to_report_dict() for spec in unique.values()],
        "selection_basis": [
            "correction_norm",
            "accepted_rejected",
            "finite_output",
            "gross_degradation",
            "feedback_residual",
            "no_future_data",
            "no_substitution",
            "solver_visible_diagnostics",
        ],
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def baseline_policy_spec() -> FeedbackPolicySpec:
    return FeedbackPolicySpec(
        "baseline_no_feedback",
        "baseline_no_feedback",
        "no_feedback_baseline",
        position_enabled=False,
        velocity_enabled=False,
        attitude_enabled=False,
        run_feedback=False,
        covariance_policy="none",
        covariance_inflation=1.0,
        gate_policy="none",
    )


def build_mode_ablation_specs() -> list[FeedbackPolicySpec]:
    return [
        baseline_policy_spec(),
        _policy("primary_horizontal_velocity_attitude_default", "horizontal_velocity_attitude_primary"),
        _policy("primary_hv_att_conservative_gate", "horizontal_velocity_attitude_primary", gate_policy="combined_conservative_gate"),
        _policy("primary_hv_att_cov_x4", "horizontal_velocity_attitude_primary", covariance_policy="inflation_x4"),
        _policy("velocity_only", "velocity_only"),
        _policy("attitude_only", "attitude_only"),
        _policy("velocity_attitude", "velocity_attitude"),
        _policy("diagnostic_PVA", "PVA_diagnostic", diagnostic_only=True),
        _policy("reject_all_sanity", "reject_all_sanity", reject_all=True),
    ]


def build_gate_sweep_specs() -> list[FeedbackPolicySpec]:
    return [
        _policy("gate_default_primary", "horizontal_velocity_attitude_primary", gate_policy="default_gate"),
        _policy("gate_attitude_max_4deg", "horizontal_velocity_attitude_primary", gate_policy="attitude_max_4deg"),
        _policy("gate_attitude_max_3deg", "horizontal_velocity_attitude_primary", gate_policy="attitude_max_3deg"),
        _policy("gate_combined_conservative", "horizontal_velocity_attitude_primary", gate_policy="combined_conservative_gate"),
    ]


def build_covariance_sweep_specs() -> list[FeedbackPolicySpec]:
    return [
        _policy("cov_inflation_x1", "horizontal_velocity_attitude_primary", covariance_policy="inflation_x1"),
        _policy("cov_inflation_x2", "horizontal_velocity_attitude_primary", covariance_policy="inflation_x2"),
        _policy("cov_inflation_x4", "horizontal_velocity_attitude_primary", covariance_policy="inflation_x4"),
        _policy("cov_auto_residual_proxy", "horizontal_velocity_attitude_primary", covariance_policy="inflation_auto_from_residual_proxy"),
        _policy("cov_velocity_x2_attitude_x4", "horizontal_velocity_attitude_primary", covariance_policy="block_velocity_x2_attitude_x4"),
        _policy("cov_attitude_x6_diagnostic", "horizontal_velocity_attitude_primary", covariance_policy="block_attitude_x6_diagnostic", diagnostic_only=True),
    ]


def build_window_policy_specs() -> list[FeedbackPolicySpec]:
    return [
        _policy("window_3s_stride_1s", "horizontal_velocity_attitude_primary", window_duration_s=3.0, feedback_stride_s=1.0),
        _policy("window_5s_stride_1s", "horizontal_velocity_attitude_primary", window_duration_s=5.0, feedback_stride_s=1.0),
        _policy("window_10s_stride_1s", "horizontal_velocity_attitude_primary", window_duration_s=10.0, feedback_stride_s=1.0),
        _policy("window_5s_stride_2s", "horizontal_velocity_attitude_primary", window_duration_s=5.0, feedback_stride_s=2.0),
    ]


def _policy(
    policy_id: str,
    mode_id: str,
    *,
    covariance_policy: str = "inflation_auto_from_residual_proxy",
    gate_policy: str = "default_gate",
    window_duration_s: float = 5.0,
    feedback_stride_s: float = 1.0,
    reject_all: bool = False,
    diagnostic_only: bool = False,
) -> FeedbackPolicySpec:
    mode = _mode_payload(mode_id)
    return FeedbackPolicySpec(
        policy_id=policy_id,
        mode_id=mode_id,
        feedback_mode=mode["feedback_mode"],
        position_enabled=mode["position_enabled"],
        velocity_enabled=mode["velocity_enabled"],
        attitude_enabled=mode["attitude_enabled"],
        covariance_policy=covariance_policy,
        covariance_inflation=covariance_inflation_for_policy(covariance_policy),
        gate_policy=gate_policy,
        window_duration_s=window_duration_s,
        feedback_stride_s=feedback_stride_s,
        reject_all=reject_all or mode_id == "reject_all_sanity",
        diagnostic_only=diagnostic_only or mode_id == "PVA_diagnostic",
    )


def _mode_payload(mode_id: str) -> dict[str, Any]:
    if mode_id == "velocity_attitude":
        return {"feedback_mode": "velocity_attitude_feedback", "position_enabled": False, "velocity_enabled": True, "attitude_enabled": True}
    if mode_id == "velocity_only":
        return {"feedback_mode": "velocity_only_feedback", "position_enabled": False, "velocity_enabled": True, "attitude_enabled": False}
    if mode_id == "attitude_only":
        return {"feedback_mode": "attitude_only_feedback", "position_enabled": False, "velocity_enabled": False, "attitude_enabled": True}
    if mode_id == "PVA_diagnostic":
        return {"feedback_mode": "position_velocity_attitude_feedback", "position_enabled": True, "velocity_enabled": True, "attitude_enabled": True}
    if mode_id == "reject_all_sanity":
        return {"feedback_mode": "velocity_attitude_feedback", "position_enabled": False, "velocity_enabled": True, "attitude_enabled": True}
    return {"feedback_mode": "horizontal_velocity_attitude_feedback", "position_enabled": False, "velocity_enabled": True, "attitude_enabled": True}


def write_policy_grid(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
