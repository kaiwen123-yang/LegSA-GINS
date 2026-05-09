"""Over-close audit for N4H4R3B.

中文说明：metric gate 通过但明显优于 external clean / dual official reference 时，
只能生成 over-close warning，不能写成 outperform 或论文性能 claim。
"""

from __future__ import annotations

from typing import Any


EXTERNAL_CLEAN_SUMMARY = {
    "horizontal_rmse_m": 0.3460851160719829,
    "up_rmse_m": 0.7940342899951961,
    "yaw_rmse_deg": 1.979182806966782,
    "roll_rmse_deg": 1.0200759961634018,
    "pitch_rmse_deg": 1.522164831263277,
}

DUAL_OFFICIAL_SUMMARY = {
    "horizontal_rmse_m": 0.3527090758847838,
    "up_rmse_m": 0.8178104428183638,
    "yaw_rmse_deg": 1.813898158169119,
    "roll_rmse_deg": 1.024555363681649,
    "pitch_rmse_deg": 1.5238205432000829,
}


def _metric(summary: dict[str, Any], key: str) -> float | None:
    value = summary.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def _delta(summary: dict[str, Any], reference: dict[str, float]) -> dict[str, float | None]:
    return {key: (None if _metric(summary, key) is None else _metric(summary, key) - ref) for key, ref in reference.items()}


def _gate_pass(summary: dict[str, Any]) -> bool:
    h = _metric(summary, "horizontal_rmse_m")
    up = _metric(summary, "up_rmse_m")
    yaw = _metric(summary, "yaw_rmse_deg")
    roll = _metric(summary, "roll_rmse_deg")
    pitch = _metric(summary, "pitch_rmse_deg")
    return bool(
        h is not None
        and up is not None
        and yaw is not None
        and roll is not None
        and pitch is not None
        and h <= 2.0
        and up <= 3.0
        and yaw <= 2.0
        and roll <= 1.6
        and pitch <= 1.6
    )


def _external_closeness_failed(deltas: dict[str, float | None]) -> bool:
    return bool(
        deltas.get("horizontal_rmse_m") is None
        or abs(float(deltas["horizontal_rmse_m"])) > 0.5
        or deltas.get("up_rmse_m") is None
        or abs(float(deltas["up_rmse_m"])) > 0.8
        or deltas.get("yaw_rmse_deg") is None
        or abs(float(deltas["yaw_rmse_deg"])) > 0.5
    )


def _too_good(deltas: dict[str, float | None]) -> bool:
    thresholds = {
        "horizontal_rmse_m": -0.2,
        "up_rmse_m": -0.4,
        "yaw_rmse_deg": -0.5,
        "roll_rmse_deg": -0.4,
        "pitch_rmse_deg": -0.4,
    }
    return any(deltas.get(key) is not None and float(deltas[key]) <= threshold for key, threshold in thresholds.items())


def analyze_overclose(
    summary: dict[str, Any],
    external_clean_summary: dict[str, float] | None = None,
    dual_official_summary: dict[str, float] | None = None,
) -> dict[str, Any]:
    external = external_clean_summary or EXTERNAL_CLEAN_SUMMARY
    dual = dual_official_summary or DUAL_OFFICIAL_SUMMARY
    deltas_external = _delta(summary, external)
    deltas_dual = _delta(summary, dual)
    metric_gate_passed = _gate_pass(summary)
    external_failed = _external_closeness_failed(deltas_external)
    too_good_external = _too_good(deltas_external)
    too_good_dual = _too_good(deltas_dual)
    reason_categories: list[str] = []
    if metric_gate_passed and external_failed:
        reason_categories.append("metric_gate_pass_external_closeness_failed")
    if too_good_external:
        reason_categories.append("too_good_relative_to_external_clean")
    if too_good_dual:
        reason_categories.append("too_good_relative_to_dual_official")
    return {
        "phase": "N4H4R3B",
        "metric_gate_passed": metric_gate_passed,
        "external_closeness_failed": external_failed,
        "overclose_warning": bool(metric_gate_passed and (external_failed or too_good_external or too_good_dual)),
        "overclose_to_reference_suspect": False,
        "overclose_to_measurement_suspect": False,
        "too_good_relative_to_external_clean": too_good_external,
        "too_good_relative_to_dual_official": too_good_dual,
        "delta_vs_external_clean": deltas_external,
        "delta_vs_dual_official": deltas_dual,
        "reason_categories": reason_categories,
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
