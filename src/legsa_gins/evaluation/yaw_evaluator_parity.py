"""Yaw evaluator parity search for official final_v23 case-review reproduction.

中文说明：本模块枚举 yaw convention transforms，只识别 evaluator 定义差异；
不修改 NAV，不调 solver，不做 formal 性能结论。
"""

from __future__ import annotations

import math
from typing import Any

from legsa_gins.evaluation.error_series_parity import compare_error_series
from legsa_gins.evaluation.trajectory_metrics import EARTH_RADIUS_M, align_by_timestamp, summary_metrics
from legsa_gins.evaluation.yaw_convention_transforms import (
    compute_yaw_error,
    generate_yaw_transform_grid,
    wrap_deg180,
)


def _as_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_value(row: dict[str, Any], *names: str) -> float:
    for name in names:
        value = _as_float(row.get(name))
        if value is not None:
            return value
    raise KeyError(f"missing row value from {names}")


def normalize_nav_row(row: dict[str, Any]) -> dict[str, float]:
    """Normalize common NAV/reference row keys for trajectory metric helpers."""

    return {
        "timestamp": _row_value(row, "timestamp", "time", "tow", "algo_time_sec"),
        "lat_deg": _row_value(row, "lat_deg", "lat"),
        "lon_deg": _row_value(row, "lon_deg", "lon"),
        "height_m": _row_value(row, "height_m", "height"),
        "roll_deg": _row_value(row, "roll_deg", "roll"),
        "pitch_deg": _row_value(row, "pitch_deg", "pitch"),
        "yaw_deg": _row_value(row, "yaw_deg", "yaw"),
    }


def normalize_nav_rows(rows: list[dict[str, Any]]) -> list[dict[str, float]]:
    normalized = [normalize_nav_row(row) for row in rows]
    normalized.sort(key=lambda row: row["timestamp"])
    return normalized


def compute_errors_for_transforms(
    est_rows: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    *,
    est_transform: str = "identity",
    ref_transform: str = "identity",
    max_dt: float = 0.05,
) -> list[dict[str, float]]:
    """Compute trajectory errors while applying yaw transforms to est/ref only."""

    est_norm = normalize_nav_rows(est_rows)
    ref_norm = normalize_nav_rows(reference_rows)
    aligned = align_by_timestamp(est_norm, ref_norm, max_dt=max_dt)
    errors: list[dict[str, float]] = []
    for item in aligned:
        est = item["est"]
        ref = item["ref"]
        if not isinstance(est, dict) or not isinstance(ref, dict):
            raise TypeError("aligned row must contain est/ref dictionaries")
        ref_lat_rad = math.radians(ref["lat_deg"])
        dlat_rad = math.radians(est["lat_deg"] - ref["lat_deg"])
        dlon_rad = math.radians(est["lon_deg"] - ref["lon_deg"])
        north = dlat_rad * EARTH_RADIUS_M
        east = dlon_rad * EARTH_RADIUS_M * math.cos(ref_lat_rad)
        up = est["height_m"] - ref["height_m"]
        errors.append(
            {
                "timestamp": est["timestamp"],
                "reference_timestamp": ref["timestamp"],
                "dt": float(item["dt"]),
                "north_error_m": north,
                "east_error_m": east,
                "up_error_m": up,
                "horizontal_error_m": math.hypot(north, east),
                "roll_error_deg": wrap_deg180(est["roll_deg"] - ref["roll_deg"]),
                "pitch_error_deg": wrap_deg180(est["pitch_deg"] - ref["pitch_deg"]),
                "yaw_error_deg": compute_yaw_error(
                    est["yaw_deg"],
                    ref["yaw_deg"],
                    est_transform=est_transform,
                    ref_transform=ref_transform,
                ),
            }
        )
    return errors


def _metric_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return abs(float(a) - float(b))


def _candidate_score(
    summary: dict[str, Any],
    official_summary: dict[str, Any] | None,
    error_parity: dict[str, Any] | None,
) -> float:
    score = 0.0
    if official_summary:
        yaw_diff = _metric_diff(summary.get("yaw_rmse_deg"), official_summary.get("yaw_rmse_deg"))
        horizontal_diff = _metric_diff(summary.get("horizontal_rmse_m"), official_summary.get("horizontal_rmse_m"))
        up_diff = _metric_diff(summary.get("up_rmse_m"), official_summary.get("up_rmse_m"))
        score += 1000.0 if yaw_diff is None else yaw_diff * 10.0
        score += 100.0 if horizontal_diff is None else horizontal_diff
        score += 100.0 if up_diff is None else up_diff
    else:
        score += 1000.0
    if error_parity:
        yaw_series = _as_float(error_parity.get("yaw_error_series_rmse_diff"))
        score += 1000.0 if yaw_series is None else yaw_series * 2.0
    return score


def _candidate_priority(item: dict[str, Any]) -> tuple[int, int, int]:
    est = item["est_transform"]
    ref = item["ref_transform"]
    est_priority = {
        "identity": 0,
        "neg": 1,
        "plus90": 2,
        "minus90": 3,
        "plus180": 4,
        "heading_reverse": 4,
    }.get(est, 5)
    ref_priority = {
        "identity": 0,
        "heading_to_math_yaw": 1,
        "trace_yaw_as_math": 2,
        "math_to_heading_yaw": 3,
        "neg_plus90": 4,
        "trace_yaw_neg_plus90": 5,
        "neg_minus90": 6,
    }.get(ref, 7)
    changed_count = int(est != "identity") + int(ref != "identity")
    return changed_count, est_priority, ref_priority


def evaluate_yaw_transform_grid(
    est_rows: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    *,
    official_summary: dict[str, Any] | None = None,
    official_error_rows: list[dict[str, Any]] | None = None,
    max_dt: float = 0.05,
) -> dict[str, Any]:
    """Run every yaw transform pair and choose the best official-parity candidate."""

    candidates: list[dict[str, Any]] = []
    for candidate in generate_yaw_transform_grid():
        errors = compute_errors_for_transforms(
            est_rows,
            reference_rows,
            est_transform=candidate["est_transform"],
            ref_transform=candidate["ref_transform"],
            max_dt=max_dt,
        )
        summary = summary_metrics(errors)
        error_parity = (
            compare_error_series(official_error_rows, errors)
            if official_error_rows
            else {"yaw_error_series_parity_status": "evidence_missing"}
        )
        item = {
            **candidate,
            "summary": summary,
            "official_summary_yaw_diff_deg": _metric_diff(
                summary.get("yaw_rmse_deg"),
                official_summary.get("yaw_rmse_deg") if official_summary else None,
            ),
            "official_error_series_yaw_rmse_diff": error_parity.get("yaw_error_series_rmse_diff"),
            "official_error_series_yaw_parity_status": error_parity.get("yaw_error_series_parity_status"),
            "score": _candidate_score(summary, official_summary, error_parity),
        }
        candidates.append(item)
    candidates.sort(
        key=lambda item: (
            round(float(item["score"]), 9),
            _candidate_priority(item),
            item["candidate_id"],
        )
    )
    best = candidates[0] if candidates else None
    direct = next(
        (
            item
            for item in candidates
            if item["est_transform"] == "identity" and item["ref_transform"] == "identity"
        ),
        None,
    )
    official_yaw = official_summary.get("yaw_rmse_deg") if official_summary else None
    best_yaw_diff = best.get("official_summary_yaw_diff_deg") if best else None
    direct_yaw_diff = direct.get("official_summary_yaw_diff_deg") if direct else None
    return {
        "candidate_count": len(candidates),
        "direct_candidate": direct,
        "best_yaw_transform_candidate": best,
        "top_candidates": candidates[:10],
        "evaluator_direct_parity_passed": bool(direct_yaw_diff is not None and direct_yaw_diff < 0.1),
        "evaluator_yaw_transform_needed": bool(
            direct_yaw_diff is not None
            and direct_yaw_diff >= 0.1
            and best_yaw_diff is not None
            and best_yaw_diff < 0.1
        ),
        "evaluator_reference_source_mismatch": bool(best_yaw_diff is None or best_yaw_diff >= 0.1),
        "official_yaw_error_definition_identified": bool(
            best
            and best.get("official_error_series_yaw_parity_status") == "passed"
            and best.get("official_error_series_yaw_rmse_diff") is not None
            and float(best["official_error_series_yaw_rmse_diff"]) < 0.1
        ),
        "official_summary_yaw_rmse_deg": official_yaw,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
