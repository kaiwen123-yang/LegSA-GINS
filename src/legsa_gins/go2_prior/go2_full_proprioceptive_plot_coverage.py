"""N7C5A plot data coverage checks.

中文说明：coverage 只描述 N7C5 图像复核数据是否足够画图，不用作调参反馈。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _f(value: Any, fallback: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _finite_count(rows: list[dict[str, Any]], keys: list[str]) -> int:
    count = 0
    for row in rows:
        if any(math.isfinite(_f(row.get(key), math.nan)) for key in keys):
            count += 1
    return count


def build_n7c5a_plot_data_coverage(inputs: dict[str, Any]) -> dict[str, Any]:
    foot_rows = inputs.get("foot_rows", [])
    contact_rows = inputs.get("contact_rows", [])
    phase_rows = inputs.get("phase_rows", [])
    ranking = inputs.get("ranking_report", {})
    figures = inputs.get("figure_manifest", {})
    return {
        "stage": "N7C5A_go2_full_proprioceptive_visual_review",
        "field_inventory_available": bool(inputs.get("inventory_report")),
        "contact_row_count": len(contact_rows),
        "contact_rows_summary_only": bool(inputs.get("contact_rows_summary_only")),
        "contact_finite_rows": _finite_count(contact_rows, [f"foot_{foot}_contact_probability" for foot in range(4)]),
        "foot_kinematic_row_count": len(foot_rows),
        "foot_kinematic_finite_rows": _finite_count(foot_rows, ["candidate_vn", "candidate_ve", "residual_to_receiver", "residual_to_raw"]),
        "mode_gait_phase_row_count": len(phase_rows),
        "phase_label_count": sum(1 for row in phase_rows if row.get("phase")),
        "yawrate_report_available": bool(inputs.get("yawrate_report")),
        "relative_odometry_report_available": bool(inputs.get("relative_report")),
        "ranking_candidate_count": len(ranking.get("candidates", [])) if isinstance(ranking, dict) else 0,
        "figure_count_total": figures.get("figure_count_total", 0) if isinstance(figures, dict) else 0,
        "required_figures_generated": bool(figures.get("required_figures_generated")) if isinstance(figures, dict) else False,
        "required_figures_nonempty": bool(figures.get("required_figures_nonempty")) if isinstance(figures, dict) else False,
        "no_truth_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def write_n7c5a_plot_data_coverage(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
