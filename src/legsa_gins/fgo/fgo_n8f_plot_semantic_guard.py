"""N8F1 plot semantic guard.

中文说明：防止图像标题/语义把工程诊断信号误写成 truth error 或论文性能。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence


ALLOWED_METRIC_NAMESPACES = [
    "FGO_vs_EKF_delta",
    "residual_proxy",
    "whitened_residual",
    "cross_source_consistency",
    "factor_toggle_delta",
    "diagnostic_engineering_evidence",
]

FORBIDDEN_PHRASES = [
    "truth error",
    "true velocity",
    "truth contact",
    "absolute yaw truth",
    "absolute position truth",
    "EKF output replaced",
    "paper performance",
    "outperform final_v23",
]


def build_n8f_plot_semantic_guard(
    *,
    figure_manifest: Mapping[str, Any],
    semantic_labels: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    blockers = []
    for label in semantic_labels:
        text = " ".join(str(label.get(key, "")) for key in ["figure_name", "title", "metric_namespace", "notes"]).lower()
        for phrase in FORBIDDEN_PHRASES:
            if phrase in text:
                blockers.append({"figure_name": label.get("figure_name"), "forbidden_phrase": phrase})
    namespaces = {str(label.get("metric_namespace")) for label in semantic_labels}
    unknown_namespaces = sorted(namespace for namespace in namespaces if namespace and namespace not in ALLOWED_METRIC_NAMESPACES)
    if unknown_namespaces:
        blockers.append({"figure_name": "metric_namespace", "unknown_namespaces": unknown_namespaces})
    return {
        "stage": "N8F1",
        "semantic_blockers": blockers,
        "semantic_guard_passed": not blockers,
        "metric_namespaces": sorted(namespaces),
        "allowed_metric_namespaces": ALLOWED_METRIC_NAMESPACES,
        "contact_probability_truth_claim": False,
        "foot_kinematic_true_velocity_claim": False,
        "yawrate_absolute_yaw_truth_claim": False,
        "relative_odometry_absolute_position_claim": False,
        "fgo_result_as_ekf_output_claim": False,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "paper_performance_claim": False,
        "go2_truth_claim": False,
        "figures_checked": len(figure_manifest.get("generated_figures", [])),
    }


def write_plot_semantic_guard(path: str | Path, report: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output

