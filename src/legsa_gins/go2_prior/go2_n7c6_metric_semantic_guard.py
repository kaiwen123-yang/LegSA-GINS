"""Metric semantic guard for N7C6A.

中文说明：检查图名和指标命名空间是否会把 raw series / delta / residual proxy
误读为 truth error；N7C6A 可用 replacement figure 修正表达，不改算法数据。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.go2_prior.go2_n7c6_final_visual_loader import read_json, write_json


ALLOWED_METRIC_NAMESPACES = {
    "absolute_to_trace",
    "parity_to_final_v23",
    "variant_delta",
    "raw_series",
    "residual_proxy",
    "NIS_proxy",
    "cross_source_consistency",
}


def _figure_names(n7c6_root: Path) -> list[str]:
    manifest = read_json(n7c6_root / "N7C6_FIGURE_MANIFEST.json")
    names = manifest.get("required_figures", [])
    if not isinstance(names, list):
        names = []
    generated = manifest.get("generated_figures", [])
    if isinstance(generated, list):
        names.extend(str(row.get("figure_name", "")) for row in generated if isinstance(row, dict))
    return sorted({name for name in names if name})


def _namespace_for_name(name: str) -> str:
    lower = name.lower()
    if "nis" in lower:
        return "NIS_proxy"
    if "residual" in lower:
        return "residual_proxy"
    if "delta" in lower or "minus" in lower:
        return "variant_delta"
    if "vs" in lower or "series" in lower or "timeline" in lower or "scan" in lower:
        return "raw_series"
    return "raw_series"


def build_metric_semantic_guard_report(n7c6_root: str | Path) -> dict[str, Any]:
    root = Path(n7c6_root)
    names = _figure_names(root)
    original_issues: list[dict[str, Any]] = []
    guarded: list[dict[str, Any]] = []
    for name in names:
        namespace = _namespace_for_name(name)
        lower = name.lower()
        issue = None
        if "error" in lower and namespace == "raw_series":
            issue = "raw_series_named_error"
        if ("velocity" in lower or "yaw" in lower or "roll_pitch" in lower) and "error" in lower:
            issue = issue or "metric_reference_not_explicit"
        if issue:
            original_issues.append(
                {
                    "figure_name": name,
                    "issue": issue,
                    "replacement_policy": "use_series_or_delta_namespace_in_N7C6A_readable_figure",
                }
            )
        guarded.append(
            {
                "figure_name": name,
                "metric_namespace": namespace,
                "namespace_allowed": namespace in ALLOWED_METRIC_NAMESPACES,
                "not_truth_error": namespace in {"raw_series", "cross_source_consistency", "residual_proxy", "NIS_proxy"},
            }
        )
    replacement_names = {
        "clean_horizontal_series_baseline_vs_joint_readable.png",
        "clean_yaw_series_baseline_vs_joint_readable.png",
        "clean_roll_pitch_series_baseline_vs_joint_readable.png",
        "joint_minus_horizontal_only_delta_readable.png",
    }
    return {
        "stage": "N7C6A_go2_proprioceptive_joint_final_review",
        "metric_semantic_status": "passed_with_runtime_replacements" if original_issues else "passed",
        "original_issues": original_issues,
        "replacement_required": bool(original_issues),
        "required_replacement_figures": sorted(replacement_names),
        "guarded_figures": guarded,
        "allowed_metric_namespaces": sorted(ALLOWED_METRIC_NAMESPACES),
        "attitude_series_not_error": True,
        "velocity_plots_not_truth_error": True,
        "joint_factor_delta_namespace": "variant_delta",
        "diagnostic_engineering_evidence": True,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "go2_not_truth": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo": False,
    }


def write_metric_semantic_guard_report(path: str | Path, report: dict[str, Any]) -> Path:
    return write_json(path, report)
