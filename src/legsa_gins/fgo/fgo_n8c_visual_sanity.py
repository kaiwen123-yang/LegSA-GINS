"""N8C visual sanity checks.

中文说明：这些检查确认 N8C 图像和报告仍保持 no-feedback、非替换边界。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _finite_rows(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        for value in row.values():
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(number):
                return False
    return True


def _time_monotonic(rows: list[dict[str, Any]]) -> bool:
    times = []
    for index, row in enumerate(rows):
        try:
            times.append(float(row.get("time", row.get("timestamp", index))))
        except (TypeError, ValueError):
            times.append(float(index))
    return all(right >= left for left, right in zip(times, times[1:]))


def build_n8c_visual_sanity_report(
    *,
    manifest: dict[str, Any],
    ekf_rows: list[dict[str, Any]],
    rows_by_variant: dict[str, list[dict[str, Any]]],
    ablation_summary: dict[str, Any],
    plot_coverage: dict[str, Any],
    factor_contribution: dict[str, Any],
    figure_manifest: dict[str, Any],
) -> dict[str, Any]:
    variants = {row.get("variant"): row for row in ablation_summary.get("variants", [])}
    weak = variants.get("weak_yaw_smoothness", {})
    yaw_reasonable = float(weak.get("yaw_delta_wrapped_rmse_deg", 999.0) or 999.0) < 2.0
    checks = {
        "no_nan_inf": _finite_rows(ekf_rows) and all(_finite_rows(rows) for rows in rows_by_variant.values()),
        "time_monotonic": _time_monotonic(ekf_rows),
        "weak_yaw_variant_visualized": bool(rows_by_variant.get("weak_yaw_smoothness")),
        "no_feedback_confirmed": bool(manifest.get("no_feedback", False)),
        "output_substitution_false": not bool(manifest.get("output_substitution", True)),
        "yaw_delta_reasonable_after_n8a2": yaw_reasonable,
        "smoothness_not_deleted_final": not bool(weak.get("smoothness_factor_deleted_for_metric", False)),
        "candidate_factors_diagnostic_only": bool(manifest.get("candidate_factors_diagnostic_only", False)),
        "factor_contribution_review_complete": bool(factor_contribution.get("review_complete", False)),
        "required_figures_generated": bool(figure_manifest.get("required_figures_generated", False)),
        "required_figures_nonempty": bool(figure_manifest.get("required_figures_nonempty", False)),
    }
    return {
        "stage": "N8C_no_feedback_fgo_visual_validation",
        **checks,
        "visual_sanity_passed": all(checks.values()) and bool(plot_coverage.get("visual_validation_passed", False)),
        "plot_coverage_passed": bool(plot_coverage.get("visual_validation_passed", False)),
        "paper_performance_claim": False,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
    }


def write_visual_sanity_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
