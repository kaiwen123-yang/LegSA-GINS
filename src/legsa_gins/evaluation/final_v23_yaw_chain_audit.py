"""Audit final_v23 status-yaw generation candidates.

中文说明：本模块只诊断 gnss1/gnss2 status rel_pos 双路相减和候选 yaw convention。
trace 只能 evaluation-only，不能用于 formal 选择 heading offset。
"""

from __future__ import annotations

import math
from typing import Any

from legsa_gins.evaluation.trajectory_metrics import align_by_timestamp, compute_errors, summary_metrics


def wrap_deg360(angle: float) -> float:
    wrapped = angle % 360.0
    return wrapped + 360.0 if wrapped < 0.0 else wrapped


def wrap_deg180(angle: float) -> float:
    wrapped = (angle + 180.0) % 360.0 - 180.0
    if wrapped == 180.0:
        return -180.0
    return wrapped


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = str(value).strip()
    if text == "":
        return default
    try:
        parsed = float(text)
    except ValueError:
        return default
    if math.isnan(parsed):
        return default
    return parsed


def _row_value(row: dict[str, Any], names: list[str]) -> float | None:
    for name in names:
        value = _as_float(row.get(name))
        if value is not None:
            return value
    return None


def _rel_n(row: dict[str, Any]) -> float | None:
    return _row_value(row, ["rel_pos_n", "rel_pos_n_m"])


def _rel_e(row: dict[str, Any]) -> float | None:
    return _row_value(row, ["rel_pos_e", "rel_pos_e_m"])


def _time(row: dict[str, Any]) -> float | None:
    return _row_value(row, ["time", "algo_time_sec", "aligned_time", "tow", "time_unix", "timestamp"])


def _nearest_rows(
    final_rows: list[dict[str, Any]],
    status_rows: list[dict[str, Any]],
    *,
    max_dt: float = 0.2,
) -> list[tuple[dict[str, Any], dict[str, Any], float]]:
    if not final_rows or not status_rows:
        return []
    raw_times = [_time(row) for row in status_rows]
    if any(value is None for value in raw_times):
        return []
    status_times = [float(value) for value in raw_times if value is not None]
    final_times = [float(row["time"]) for row in final_rows]
    offset = 0.0
    if status_times and final_times and abs(status_times[0] - final_times[0]) > max_dt:
        offset = status_times[0] - final_times[0]
    normalized_times = [value - offset for value in status_times]
    pairs: list[tuple[dict[str, Any], dict[str, Any], float]] = []
    status_index = 0
    for final_row in final_rows:
        t = float(final_row["time"])
        while (
            status_index + 1 < len(normalized_times)
            and abs(normalized_times[status_index + 1] - t) <= abs(normalized_times[status_index] - t)
        ):
            status_index += 1
        dt = t - normalized_times[status_index]
        if abs(dt) <= max_dt:
            pairs.append((final_row, status_rows[status_index], dt))
    return pairs


def compute_a1_dual_diff_yaw(gnss1_row: dict[str, Any], gnss2_row: dict[str, Any]) -> dict[str, Any]:
    b_n = (_rel_n(gnss2_row) or 0.0) - (_rel_n(gnss1_row) or 0.0)
    b_e = (_rel_e(gnss2_row) or 0.0) - (_rel_e(gnss1_row) or 0.0)
    yaw_rad = -math.atan2(b_e, b_n)
    return {
        "b_n": b_n,
        "b_e": b_e,
        "yaw_deg": wrap_deg360(math.degrees(yaw_rad)),
        "yaw_formula": "-atan2(be,bn)",
        "source": "A1_dual_diff",
        "diagnostic_only": True,
    }


def _yaw_from_bn_be(b_n: float, b_e: float) -> float:
    return wrap_deg360(-math.degrees(math.atan2(b_e, b_n)))


def compute_yaw_candidates(gnss1_row: dict[str, Any], gnss2_row: dict[str, Any]) -> dict[str, Any]:
    n1 = _rel_n(gnss1_row) or 0.0
    e1 = _rel_e(gnss1_row) or 0.0
    n2 = _rel_n(gnss2_row) or 0.0
    e2 = _rel_e(gnss2_row) or 0.0
    b_n = n2 - n1
    b_e = e2 - e1
    reverse_b_n = n1 - n2
    reverse_b_e = e1 - e2
    a1 = _yaw_from_bn_be(b_n, b_e)
    reverse = _yaw_from_bn_be(reverse_b_n, reverse_b_e)
    heading = wrap_deg360(math.degrees(math.atan2(b_e, b_n)))
    return {
        "a1_dual_diff": a1,
        "a1_dual_diff_plus90": wrap_deg360(a1 + 90.0),
        "a1_dual_diff_minus90": wrap_deg360(a1 - 90.0),
        "reverse_dual_diff": reverse,
        "reverse_plus90": wrap_deg360(reverse + 90.0),
        "reverse_minus90": wrap_deg360(reverse - 90.0),
        "heading_direct_atan2_e_n": heading,
        "yaw_math_candidate": wrap_deg360(90.0 - a1),
        "formal_selection_allowed": False,
        "formal_blocker": "antenna_order_and_process_data_yaw_offset_need_source_confirmation",
        "diagnostic_only": True,
    }


def _candidate_error_stats(rows: list[tuple[float, float]]) -> dict[str, Any]:
    if not rows:
        return {"count": 0, "yaw_rmse_deg": None, "yaw_p95_deg": None, "yaw_bias_deg": None}
    errors = [wrap_deg180(candidate - reference) for candidate, reference in rows]
    abs_errors = [abs(value) for value in errors]
    ordered = sorted(abs_errors)
    p95_index = max(0, min(len(ordered) - 1, int(math.ceil(0.95 * len(ordered))) - 1))
    return {
        "count": len(errors),
        "yaw_rmse_deg": math.sqrt(sum(value * value for value in errors) / len(errors)),
        "yaw_p95_deg": ordered[p95_index],
        "yaw_bias_deg": sum(errors) / len(errors),
    }


def compare_final_v23_yaw_column(
    final_gnss_rows: list[dict[str, Any]],
    gnss1_status_rows: list[dict[str, Any]],
    gnss2_status_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    g1_pairs = _nearest_rows(final_gnss_rows, gnss1_status_rows)
    g2_pairs = _nearest_rows(final_gnss_rows, gnss2_status_rows)
    g1_by_time = {id(final_row): status_row for final_row, status_row, _dt in g1_pairs}
    g2_by_time = {id(final_row): status_row for final_row, status_row, _dt in g2_pairs}
    candidate_errors: dict[str, list[tuple[float, float]]] = {}
    candidate_rows: dict[str, list[dict[str, float]]] = {}
    for final_row in final_gnss_rows:
        g1 = g1_by_time.get(id(final_row))
        g2 = g2_by_time.get(id(final_row))
        if g1 is None or g2 is None:
            continue
        candidates = compute_yaw_candidates(g1, g2)
        final_yaw = float(final_row["yaw"])
        for name, value in candidates.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            candidate_errors.setdefault(name, []).append((float(value), final_yaw))
            candidate_rows.setdefault(name, []).append(
                {"timestamp": float(final_row["time"]), "yaw_deg": float(value)}
            )
    stats = {name: _candidate_error_stats(rows) for name, rows in candidate_errors.items()}
    valid = {name: item for name, item in stats.items() if item["count"] > 0 and item["yaw_rmse_deg"] is not None}
    best_name = min(valid, key=lambda name: float(valid[name]["yaw_rmse_deg"])) if valid else None
    a1_rmse = stats.get("a1_dual_diff", {}).get("yaw_rmse_deg")
    a1_match = bool(
        stats.get("a1_dual_diff", {}).get("count", 0) > 0
        and a1_rmse is not None
        and float(a1_rmse) <= 1.0e-3
    )
    return {
        "candidate_errors": stats,
        "candidate_rows": candidate_rows,
        "best_matching_candidate_to_final_gnss_yaw": best_name,
        "yaw_column_source_status": "matched_a1_dual_diff"
        if a1_match
        else ("diagnostic_candidate_matched" if best_name else "evidence_missing"),
        "a1_dual_diff_matches_final_gnss_yaw": a1_match,
        "formal_selection_allowed": False,
        "formal_blocker": "antenna_order_and_process_data_yaw_offset_need_source_confirmation",
        "trace_solver_input": False,
        "final_v23_is_proposed": False,
        "diagnostic_only": True,
    }


def evaluate_yaw_candidate_against_trace(
    candidate_rows: list[dict[str, float]],
    trace_rows: list[dict[str, float]],
) -> dict[str, Any]:
    est_rows = [
        {
            "timestamp": float(row["timestamp"]),
            "lat_deg": 0.0,
            "lon_deg": 0.0,
            "height_m": 0.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "yaw_deg": float(row["yaw_deg"]),
        }
        for row in candidate_rows
    ]
    ref_rows = [
        {
            "timestamp": float(row["timestamp"]),
            "lat_deg": 0.0,
            "lon_deg": 0.0,
            "height_m": 0.0,
            "roll_deg": 0.0,
            "pitch_deg": 0.0,
            "yaw_deg": float(row["yaw_deg"]),
        }
        for row in trace_rows
    ]
    summary = summary_metrics(compute_errors(align_by_timestamp(est_rows, ref_rows, max_dt=0.05)))
    return {
        "count": summary["count"],
        "yaw_rmse_deg": summary["yaw_rmse_deg"],
        "yaw_p95_deg": summary["yaw_p95_deg"],
        "trace_solver_input": False,
        "trace_evaluation_only": True,
        "formal_selection_allowed": False,
        "diagnostic_only": True,
    }
