"""N8A2 real FGO rerun helpers with yaw-wrap-fixed residuals.

中文说明：本模块只重跑 no-feedback FGO yaw wrap 修复，不回写 EKF。
"""

from __future__ import annotations

import math
from typing import Any

from legsa_gins.fgo.fgo_angle_utils import shortest_angle_residual_deg
from legsa_gins.fgo.fgo_evaluator import evaluate_no_feedback_fgo
from legsa_gins.fgo.fgo_no_feedback_smoother import run_no_feedback_smoother
from legsa_gins.fgo.fgo_state_types import FGOState, FGOStateDataset


STATE_FIELDS = ["lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn_mps", "ve_mps", "vd_mps"]


def _f(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def rows_to_dataset(rows: list[dict[str, Any]]) -> FGOStateDataset:
    states = [
        FGOState(
            index=int(_f(row.get("index"), float(index))),
            time=_f(row.get("time", row.get("timestamp")), float(index)),
            lat_deg=_f(row.get("lat_deg")),
            lon_deg=_f(row.get("lon_deg")),
            height_m=_f(row.get("height_m")),
            roll_deg=_f(row.get("roll_deg")),
            pitch_deg=_f(row.get("pitch_deg")),
            yaw_deg=_f(row.get("yaw_deg")),
            vn_mps=_f(row.get("vn_mps", row.get("vn"))),
            ve_mps=_f(row.get("ve_mps", row.get("ve"))),
            vd_mps=_f(row.get("vd_mps", row.get("vd"))),
        )
        for index, row in enumerate(rows)
    ]
    return FGOStateDataset(states)


def horizontal_delta_rmse_m(ekf_rows: list[dict[str, Any]], fgo_rows: list[dict[str, Any]]) -> float:
    values: list[float] = []
    for ekf, fgo in zip(ekf_rows, fgo_rows):
        lat0 = math.radians(_f(ekf.get("lat_deg")))
        north = (_f(fgo.get("lat_deg")) - _f(ekf.get("lat_deg"))) * 111_320.0
        east = (_f(fgo.get("lon_deg")) - _f(ekf.get("lon_deg"))) * 111_320.0 * math.cos(lat0)
        values.append(math.sqrt(north * north + east * east))
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else 0.0


def yaw_delta_metrics(ekf_rows: list[dict[str, Any]], fgo_rows: list[dict[str, Any]]) -> dict[str, float]:
    raw: list[float] = []
    wrapped: list[float] = []
    for ekf, fgo in zip(ekf_rows, fgo_rows):
        ekf_yaw = _f(ekf.get("yaw_deg"))
        fgo_yaw = _f(fgo.get("yaw_deg"))
        raw.append(fgo_yaw - ekf_yaw)
        wrapped.append(shortest_angle_residual_deg(fgo_yaw, ekf_yaw))
    raw_rmse = math.sqrt(sum(value * value for value in raw) / len(raw)) if raw else 0.0
    wrapped_rmse = math.sqrt(sum(value * value for value in wrapped) / len(wrapped)) if wrapped else 0.0
    return {"yaw_delta_raw_rmse_deg": raw_rmse, "yaw_delta_wrapped_rmse_deg": wrapped_rmse}


def summarize_variant(
    *,
    variant: str,
    ekf_rows: list[dict[str, Any]],
    fgo_rows: list[dict[str, Any]],
    smoother_report: dict[str, Any],
    real_solver_rerun: bool,
    notes: str,
) -> dict[str, Any]:
    metrics = yaw_delta_metrics(ekf_rows, fgo_rows)
    return {
        "variant": variant,
        "solve_status": smoother_report.get("solve_status", "reference_existing_n8a"),
        "finite_output": bool(smoother_report.get("finite_output", True)),
        "horizontal_delta_rmse_m": horizontal_delta_rmse_m(ekf_rows, fgo_rows),
        "residual_proxy_p95": smoother_report.get("residual_proxy_p95", 0.0),
        "iteration_count": smoother_report.get("iteration_count", 0),
        "final_cost": smoother_report.get("final_cost", 0.0),
        "real_solver_rerun": real_solver_rerun,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_yaw_correction": False,
        "paper_performance_claim": False,
        "notes": notes,
        **metrics,
    }


def run_yaw_wrap_fixed_variant(dataset: FGOStateDataset, *, variant: str, smoothness_weight: float, notes: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    rows, report = run_no_feedback_smoother(
        dataset,
        smoothness_weight=smoothness_weight,
        stage="N8A2_fgo_yaw_convention_fix",
        variant=variant,
    )
    summary = summarize_variant(
        variant=variant,
        ekf_rows=dataset.to_rows(),
        fgo_rows=rows,
        smoother_report=report,
        real_solver_rerun=True,
        notes=notes,
    )
    return rows, report, summary
