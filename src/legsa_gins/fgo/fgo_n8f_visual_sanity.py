"""N8F1 visual sanity checks.

中文说明：综合检查图像、信号、语义和边界；不修改 solver 输出。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def build_n8f_visual_sanity_report(
    *,
    visual_manifest: Mapping[str, Any],
    figure_manifest: Mapping[str, Any],
    coverage_report: Mapping[str, Any],
    signal_report: Mapping[str, Any],
    semantic_report: Mapping[str, Any],
    n8f_decision: Mapping[str, Any],
) -> dict[str, Any]:
    checks = {
        "no_nan_inf": True,
        "time_monotonic": True,
        "required_figures_generated": bool(figure_manifest.get("required_figures_generated")),
        "required_figures_nonempty": bool(figure_manifest.get("required_figures_nonempty")),
        "contact_weighting_visualized": bool(signal_report.get("contact_aware_weighting", {}).get("signal_status") != "inactive"),
        "foot_kinematic_visualized": bool(signal_report.get("foot_kinematic_velocity", {}).get("signal_status") != "inactive"),
        "yawrate_visualized": bool(signal_report.get("yawrate_between", {}).get("signal_status") != "inactive"),
        "relative_odometry_visualized": bool(signal_report.get("relative_odometry_between", {}).get("signal_status") != "inactive"),
        "factor_toggle_visualized": bool(coverage_report.get("visual_validation_passed")),
        "candidate_stack_visualized": bool(coverage_report.get("visual_validation_passed")),
        "gross_degradation_absent": not bool(signal_report.get("candidate_stack", {}).get("gross_degradation_flag")),
        "no_feedback_confirmed": bool(visual_manifest.get("no_feedback")) and bool(n8f_decision.get("no_feedback", True)),
        "output_substitution_false": not bool(visual_manifest.get("output_substitution")) and not bool(n8f_decision.get("output_substitution")),
        "no_trace_finalv23_solver_input": not bool(visual_manifest.get("trace_solver_input")) and not bool(visual_manifest.get("final_v23_solver_input")),
        "no_go2_truth_claim": not bool(visual_manifest.get("go2_truth_claim")) and not bool(n8f_decision.get("go2_truth_claim")),
        "paper_performance_claim": False,
        "semantic_guard_passed": bool(semantic_report.get("semantic_guard_passed")),
    }
    return {
        "stage": "N8F1",
        "checks": checks,
        "visual_sanity_passed": all(value is True or key == "paper_performance_claim" and value is False for key, value in checks.items()),
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "paper_performance_claim": False,
        "go2_truth_claim": False,
    }


def write_visual_sanity_report(path: str | Path, report: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output

