"""Evaluation namespace for N8A no-feedback FGO."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _rmse(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else 0.0


def evaluate_no_feedback_fgo(*, ekf_states: list[dict[str, Any]], fgo_states: list[dict[str, Any]]) -> dict[str, Any]:
    """中文说明：只评价 FGO 与 EKF diagnostic delta，不把 FGO 输出替换 EKF。"""
    count = min(len(ekf_states), len(fgo_states))
    deltas = []
    for index in range(count):
        ekf = ekf_states[index]
        fgo = fgo_states[index]
        deltas.append(float(fgo.get("yaw_deg", 0.0)) - float(ekf.get("yaw_deg", 0.0)))
    return {
        "stage": "N8A_no_feedback_fgo_foundation",
        "metric_namespace": "FGO_vs_EKF_delta",
        "aligned_state_count": count,
        "yaw_delta_rmse_deg": _rmse(deltas),
        "evaluation_only_reference": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "fgo_output_feedback_to_ekf": False,
        "fgo_output_replaces_ekf_nav": False,
        "paper_performance_claim": False,
    }


def write_evaluation_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
