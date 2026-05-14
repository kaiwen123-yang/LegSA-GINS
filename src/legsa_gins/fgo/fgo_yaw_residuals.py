"""Yaw residual contracts for N8A2.

中文说明：所有 yaw residual 使用 shortest-angle；unwrapped yaw 只允许用于绘图连续性。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_angle_utils import shortest_angle_residual_deg, shortest_angle_residual_rad, wrap_deg, wrap_rad


def dual_yaw_residual_deg(yaw_state_deg: float, yaw_measurement_deg: float) -> float:
    return shortest_angle_residual_deg(yaw_state_deg, yaw_measurement_deg)


def dual_yaw_residual_rad(yaw_state_rad: float, yaw_measurement_rad: float) -> float:
    return shortest_angle_residual_rad(yaw_state_rad, yaw_measurement_rad)


def yaw_smoothness_residual_deg(yaw_prev_deg: float, yaw_next_deg: float, expected_delta_yaw_deg: float = 0.0) -> float:
    return wrap_deg(shortest_angle_residual_deg(yaw_next_deg, yaw_prev_deg) - expected_delta_yaw_deg)


def yaw_smoothness_residual_rad(yaw_prev_rad: float, yaw_next_rad: float, expected_delta_yaw_rad: float = 0.0) -> float:
    return wrap_rad(shortest_angle_residual_rad(yaw_next_rad, yaw_prev_rad) - expected_delta_yaw_rad)


def yaw_rate_between_residual_deg(yaw_prev_deg: float, yaw_next_deg: float, yaw_rate_dps: float, dt_sec: float) -> float:
    return yaw_smoothness_residual_deg(yaw_prev_deg, yaw_next_deg, float(yaw_rate_dps) * float(dt_sec))


def yaw_rate_between_residual_rad(yaw_prev_rad: float, yaw_next_rad: float, yaw_rate_rps: float, dt_sec: float) -> float:
    return yaw_smoothness_residual_rad(yaw_prev_rad, yaw_next_rad, float(yaw_rate_rps) * float(dt_sec))


def build_yaw_residual_contract_report() -> dict[str, Any]:
    dual_example = dual_yaw_residual_deg(1.0, 359.0)
    smooth_example = yaw_smoothness_residual_deg(359.0, 1.0)
    yaw_rate_example = yaw_rate_between_residual_deg(359.0, 1.0, 1.0, 1.0)
    return {
        "stage": "N8A2_fgo_yaw_convention_fix",
        "dual_yaw_residual_formula": "wrap(yaw_state - yaw_measurement)",
        "yaw_smoothness_residual_formula": "wrap((yaw_next - yaw_prev) - expected_delta_yaw)",
        "yaw_rate_between_residual_formula": "wrap((yaw_next - yaw_prev) - yaw_rate * dt)",
        "evaluation_yaw_delta_formula": "wrap(fgo_yaw - ekf_yaw)",
        "unwrapped_yaw_usage": "plotting_only",
        "dual_yaw_wrap": abs(dual_example - 2.0) < 1e-9,
        "smoothness_wrap": abs(smooth_example - 2.0) < 1e-9,
        "yaw_rate_wrap": abs(yaw_rate_example - 1.0) < 1e-9,
        "dual_yaw_example_deg": dual_example,
        "smoothness_example_deg": smooth_example,
        "yaw_rate_example_deg": yaw_rate_example,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_yaw_correction": False,
        "paper_performance_claim": False,
    }


def write_yaw_residual_contract_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
