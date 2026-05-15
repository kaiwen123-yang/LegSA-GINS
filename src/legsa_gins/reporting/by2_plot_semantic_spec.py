"""Semantic filename contracts for BY2 formal ablation figures."""

# 中文说明：N8K4 明确文件名对应的图像语义，避免只靠 hash 去判定图是否正确。

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlotSemanticSpec:
    category: str
    filename: str
    expected_semantic_role: str
    required_title_keywords: tuple[str, ...] = ()
    forbidden_title_keywords: tuple[str, ...] = ()
    documented_not_applicable_allowed: bool = False
    not_applicable_reason_allowed: str = ""


SEMANTIC_SPECS: dict[tuple[str, str], PlotSemanticSpec] = {
    ("04_attitude", "yaw_residual_time.png"): PlotSemanticSpec(
        category="04_attitude",
        filename="yaw_residual_time.png",
        expected_semantic_role="yaw_residual_time_series",
        required_title_keywords=("yaw", "residual"),
        forbidden_title_keywords=("wrap consistency", "reject-all", "sanity"),
    ),
    ("04_attitude", "yaw_wrap_check.png"): PlotSemanticSpec(
        category="04_attitude",
        filename="yaw_wrap_check.png",
        expected_semantic_role="yaw_wrap_consistency_check",
        required_title_keywords=("wrap",),
    ),
    ("07_compare", "compare_horizontal_error.png"): PlotSemanticSpec(
        category="07_compare",
        filename="compare_horizontal_error.png",
        expected_semantic_role="horizontal_error_comparison",
        required_title_keywords=("horizontal",),
        forbidden_title_keywords=("reject-all sanity", "not-applicable only"),
    ),
    ("07_compare", "reject_all_sanity_compare.png"): PlotSemanticSpec(
        category="07_compare",
        filename="reject_all_sanity_compare.png",
        expected_semantic_role="reject_all_sanity_compare",
        required_title_keywords=("reject-all",),
        documented_not_applicable_allowed=True,
        not_applicable_reason_allowed="reject-all sanity only applies to feedback variants / no feedback rows",
    ),
    ("11_feedback", "feedback_accept_reject_timeline.png"): PlotSemanticSpec(
        category="11_feedback",
        filename="feedback_accept_reject_timeline.png",
        expected_semantic_role="feedback_accept_reject_timeline",
        required_title_keywords=("accept", "reject"),
        forbidden_title_keywords=("reject-all sanity",),
        documented_not_applicable_allowed=True,
        not_applicable_reason_allowed="feedback disabled for this variant / no feedback rows",
    ),
    ("11_feedback", "reject_all_sanity.png"): PlotSemanticSpec(
        category="11_feedback",
        filename="reject_all_sanity.png",
        expected_semantic_role="feedback_reject_all_sanity",
        required_title_keywords=("reject-all",),
        documented_not_applicable_allowed=True,
        not_applicable_reason_allowed="no reject-all comparison rows for this variant / no feedback rows",
    ),
    ("03_velocity", "velocity_residual_time.png"): PlotSemanticSpec(
        category="03_velocity",
        filename="velocity_residual_time.png",
        expected_semantic_role="velocity_residual_time_series",
        required_title_keywords=("velocity", "residual"),
    ),
    ("07_compare", "compare_velocity_error.png"): PlotSemanticSpec(
        category="07_compare",
        filename="compare_velocity_error.png",
        expected_semantic_role="velocity_error_comparison",
        required_title_keywords=("velocity",),
        forbidden_title_keywords=("velocity residual time series",),
        documented_not_applicable_allowed=True,
        not_applicable_reason_allowed="velocity comparison unavailable / no comparable velocity rows",
    ),
    ("06_observation_quality", "feedback_accept_reject_time.png"): PlotSemanticSpec(
        category="06_observation_quality",
        filename="feedback_accept_reject_time.png",
        expected_semantic_role="feedback_observation_quality_timeline",
        required_title_keywords=("feedback",),
        documented_not_applicable_allowed=True,
        not_applicable_reason_allowed="no feedback rows / feedback disabled for this variant",
    ),
    ("07_compare", "compare_feedback_delta.png"): PlotSemanticSpec(
        category="07_compare",
        filename="compare_feedback_delta.png",
        expected_semantic_role="feedback_delta_comparison",
        required_title_keywords=("feedback",),
        forbidden_title_keywords=("accept/reject timeline",),
        documented_not_applicable_allowed=True,
        not_applicable_reason_allowed="feedback delta comparison only applies to feedback variants / no feedback rows",
    ),
}


SEMANTIC_TARGETS: tuple[tuple[str, str], ...] = tuple(SEMANTIC_SPECS)
DERIVED_DATA_SOURCE = "derived_from_n8k_metrics_and_baseline_nav"
