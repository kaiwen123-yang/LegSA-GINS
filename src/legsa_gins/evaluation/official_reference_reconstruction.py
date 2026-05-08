"""Reconstruct the official dual_final_v23 evaluation reference.

中文说明：本模块只从 official NAV 与 official error_series 反推出 evaluation-only
reference；不进入 solver input，不删 epoch，不做 output-only correction。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.error_series_parity import load_official_error_series as _load_error_series
from legsa_gins.evaluation.error_series_parity import load_official_summary
from legsa_gins.evaluation.official_case_review_reproduction import parse_kfgins_nav
from legsa_gins.evaluation.trajectory_metrics import EARTH_RADIUS_M, align_by_timestamp, compute_errors, summary_metrics


def wrap_deg180(angle: float) -> float:
    wrapped = (float(angle) + 180.0) % 360.0 - 180.0
    if wrapped == 180.0:
        return -180.0
    return wrapped


def wrap_deg360(angle: float) -> float:
    return float(angle) % 360.0


def load_official_nav(path: str | Path) -> list[dict[str, float]]:
    """Load an official KF_GINS_Navresult.nav file."""

    return parse_kfgins_nav(path)


def load_official_error_series(path: str | Path) -> list[dict[str, Any]]:
    """Load official error_series.csv with schema aliases."""

    return _load_error_series(path)


def _nav_value(row: dict[str, Any], name: str) -> float:
    aliases = {
        "lat_deg": ["lat_deg", "lat"],
        "lon_deg": ["lon_deg", "lon"],
        "height_m": ["height_m", "height"],
        "roll_deg": ["roll_deg", "roll"],
        "pitch_deg": ["pitch_deg", "pitch"],
        "yaw_deg": ["yaw_deg", "yaw"],
    }
    for key in aliases[name]:
        if key in row:
            return float(row[key])
    raise KeyError(name)


def _nearest_nav(nav_rows: list[dict[str, Any]], timestamp: float, start_index: int, tolerance: float) -> tuple[dict[str, Any] | None, int]:
    if not nav_rows:
        return None, start_index
    index = min(max(start_index, 0), len(nav_rows) - 1)
    while index + 1 < len(nav_rows) and abs(float(nav_rows[index + 1]["timestamp"]) - timestamp) <= abs(
        float(nav_rows[index]["timestamp"]) - timestamp
    ):
        index += 1
    row = nav_rows[index]
    return (row if abs(float(row["timestamp"]) - timestamp) <= tolerance else None), index


def _reference_row(est: dict[str, Any], err: dict[str, Any], sign: int) -> dict[str, float]:
    north = float(err.get("north_error_m", 0.0))
    east = float(err.get("east_error_m", 0.0))
    up = float(err.get("up_error_m", 0.0))
    est_lat = _nav_value(est, "lat_deg")
    est_lon = _nav_value(est, "lon_deg")
    est_height = _nav_value(est, "height_m")
    ref_lat = est_lat - sign * math.degrees(north / EARTH_RADIUS_M)
    cos_lat = math.cos(math.radians(ref_lat))
    if abs(cos_lat) < 1.0e-12:
        ref_lon = est_lon
    else:
        ref_lon = est_lon - sign * math.degrees(east / (EARTH_RADIUS_M * cos_lat))
    return {
        "timestamp": float(err["timestamp"]),
        "time": float(err["timestamp"]),
        "lat_deg": ref_lat,
        "lon_deg": ref_lon,
        "height_m": est_height - sign * up,
        "roll_deg": _nav_value(est, "roll_deg") - sign * float(err.get("roll_error_deg", 0.0)),
        "pitch_deg": _nav_value(est, "pitch_deg") - sign * float(err.get("pitch_error_deg", 0.0)),
        "yaw_deg": wrap_deg360(_nav_value(est, "yaw_deg") - sign * float(err.get("yaw_error_deg", 0.0))),
    }


def reconstruct_reference_from_official_errors(
    nav_rows: list[dict[str, Any]],
    error_rows: list[dict[str, Any]],
    *,
    tolerance: float = 0.05,
) -> dict[str, list[dict[str, float]]]:
    """Build reference candidates for both possible official error signs."""

    nav_sorted = sorted(nav_rows, key=lambda row: float(row["timestamp"]))
    errors_sorted = sorted(
        [row for row in error_rows if "timestamp" in row],
        key=lambda row: float(row["timestamp"]),
    )
    candidates = {
        "official_ref_sign_minus": [],
        "official_ref_sign_plus": [],
    }
    nav_index = 0
    for err in errors_sorted:
        est, nav_index = _nearest_nav(nav_sorted, float(err["timestamp"]), nav_index, tolerance)
        if est is None:
            continue
        candidates["official_ref_sign_minus"].append(_reference_row(est, err, +1))
        candidates["official_ref_sign_plus"].append(_reference_row(est, err, -1))
    return candidates


def _summary_diff(official: dict[str, Any], recomputed: dict[str, Any]) -> dict[str, float | None]:
    diff: dict[str, float | None] = {}
    for field in ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]:
        official_value = official.get(field)
        recomputed_value = recomputed.get(field)
        if isinstance(official_value, (int, float)) and isinstance(recomputed_value, (int, float)):
            diff[field] = float(recomputed_value) - float(official_value)
        else:
            diff[field] = None
    return diff


def _score_diff(diff: dict[str, float | None]) -> float:
    weights = {
        "horizontal_rmse_m": 1.0,
        "up_rmse_m": 1.0,
        "yaw_rmse_deg": 1.0,
        "roll_rmse_deg": 0.5,
        "pitch_rmse_deg": 0.5,
    }
    score = 0.0
    for key, weight in weights.items():
        value = diff.get(key)
        score += 1.0e6 if value is None else weight * abs(float(value))
    return score


def _recompute_summary(nav_rows: list[dict[str, Any]], reference_rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors = compute_errors(align_by_timestamp(nav_rows, reference_rows, max_dt=0.05))
    summary = summary_metrics(errors)
    summary["aligned_count"] = summary.get("count")
    summary["trace_solver_input"] = False
    summary["output_only_correction"] = False
    summary["solver_output_changed"] = False
    summary["numerical_performance_claim"] = False
    return summary


def select_reference_sign_by_summary(
    nav_rows: list[dict[str, Any]],
    error_rows: list[dict[str, Any]],
    official_summary: dict[str, Any],
) -> dict[str, Any]:
    """Select the reference sign candidate that best reproduces official summary."""

    candidates = reconstruct_reference_from_official_errors(nav_rows, error_rows)
    candidate_reports: dict[str, dict[str, Any]] = {}
    for name, reference_rows in candidates.items():
        recomputed = _recompute_summary(nav_rows, reference_rows)
        diff = _summary_diff(official_summary, recomputed)
        candidate_reports[name] = {
            "summary": recomputed,
            "summary_diff": diff,
            "score": _score_diff(diff),
            "reference_count": len(reference_rows),
        }
    selected_name = min(
        candidate_reports,
        key=lambda name: (float(candidate_reports[name]["score"]), 0 if name == "official_ref_sign_minus" else 1),
    )
    selected = candidate_reports[selected_name]
    diff = selected["summary_diff"]
    reproduced = bool(
        isinstance(diff.get("horizontal_rmse_m"), (int, float))
        and abs(float(diff["horizontal_rmse_m"])) <= 0.05
        and isinstance(diff.get("up_rmse_m"), (int, float))
        and abs(float(diff["up_rmse_m"])) <= 0.05
        and isinstance(diff.get("yaw_rmse_deg"), (int, float))
        and abs(float(diff["yaw_rmse_deg"])) <= 0.2
    )
    return {
        "phase": "N4H2D",
        "selected_reference_sign": selected_name,
        "selected_reference_profile": {
            "name": selected_name,
            "sign_rule": "ref=est-error" if selected_name == "official_ref_sign_minus" else "ref=est+error",
            "yaw_profile": "direct_identity",
            "reference_source": "dual_official_nav_plus_error_series",
        },
        "reference_candidates": candidates,
        "candidate_reports": candidate_reports,
        "actual_dual_summary_reproduced": reproduced,
        "actual_summary_reproduced": reproduced,
        "actual_summary_reproduced_summary": selected["summary"],
        "summary_diff": diff,
        "evidence_status": "official_reference_reconstructed" if reproduced else "summary_reproduction_failed",
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }


def reconstruct_from_paths(nav_path: str | Path, error_series_path: str | Path, summary_path: str | Path) -> dict[str, Any]:
    """Convenience helper used by scripts/tests."""

    nav_rows = load_official_nav(nav_path)
    error_rows = load_official_error_series(error_series_path)
    official_summary = load_official_summary(summary_path)
    return select_reference_sign_by_summary(nav_rows, error_rows, official_summary)
