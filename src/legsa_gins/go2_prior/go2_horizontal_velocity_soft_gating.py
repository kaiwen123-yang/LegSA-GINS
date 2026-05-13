"""N7C3 soft-gating report for bounded Go2 horizontal velocity prior.

中文说明：本模块报告软门控与跳过计数，低置信度仍以更大但有界的 R 参与更新。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _f(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _is_update(row: dict[str, Any]) -> bool:
    return str(row.get("update_flag", "")).lower() in {"true", "1", "yes"} and str(row.get("source_status", "")).lower() == "active"


def build_go2_horizontal_velocity_soft_gating_report(prior_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize bounded soft-gating rows without treating low confidence as truth."""

    counts = {level: sum(1 for row in prior_rows if row.get("confidence_level") == level) for level in ["high", "medium", "low", "invalid"]}
    update_count = sum(1 for row in prior_rows if _is_update(row))
    skip_count = len(prior_rows) - update_count
    soft_gated_count = sum(1 for row in prior_rows if _is_update(row) and _f(row.get("std_vn"), 0.0) > 1.5)
    hard_skip_count = sum(1 for row in prior_rows if not _is_update(row))
    return {
        "stage": "N7C3_go2_horizontal_velocity_bounded_adaptive_std",
        "policy_name": "n7c3_bounded_adaptive_std_soft_gating",
        "high_count": counts["high"],
        "medium_count": counts["medium"],
        "low_count": counts["low"],
        "invalid_count": counts["invalid"],
        "confidence_counts": counts,
        "row_count": len(prior_rows),
        "update_count_expected": update_count,
        "skip_count": skip_count,
        "hard_skip_count": hard_skip_count,
        "soft_gated_count": soft_gated_count,
        "soft_gating_rule": "high_medium_low_update_with_bounded_std; invalid_skips",
        "hard_gating_rule": "only_invalid_or_update_flag_false_rows_skip",
        "vertical_disabled": True,
        "std_vd": 999.0,
        "max_horizontal_std": max([_f(row.get("std_vn"), 0.0) for row in prior_rows] + [_f(row.get("std_ve"), 0.0) for row in prior_rows], default=0.0),
        "max_std_le_5": all(_f(row.get("std_vn"), 0.0) <= 5.0 and _f(row.get("std_ve"), 0.0) <= 5.0 for row in prior_rows),
        "go2_velocity_truth_claim": False,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "fgo": False,
    }


def write_go2_horizontal_velocity_soft_gating_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
