"""N7B4 Go2 velocity-frame internal/external scoring.

中文说明：内部评分来自 Go2 position/yaw 自洽，外部评分来自 receiver-native
velocity 与 raw Doppler velocity 的 cross-source consistency；不使用 trace 或
final_v23 output，也不把任一速度源当 truth。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .go2_contact_state import _f, _time_value
from .go2_velocity_frame_review import transform_go2_velocity_for_frame
from .go2_velocity_quality import _corr, _nearest_from_index, _norm, _rmse


FRAME_CANDIDATES = [
    "go2_velocity_as_world_enu_or_ned_direct",
    "go2_velocity_as_body_flu_then_rotate_by_go2_attitude",
    "go2_velocity_flu_to_frd_then_rotate",
    "yaw_only_rotation_diagnostic_only",
    "sign_flip_y",
    "sign_flip_z",
    "xy_swap_diagnostic_only",
    "sign_flip_x_diagnostic_only",
    "sign_flip_xy_diagnostic_only",
]


def _go2_velocity(row: dict[str, Any]) -> list[float]:
    return [_f(row.get(f"go2_velocity_{axis}")) for axis in range(3)]


def _candidate_velocity(row: dict[str, Any], frame_name: str) -> list[float]:
    if frame_name == "sign_flip_x_diagnostic_only":
        vel = _go2_velocity(row)
        return [-vel[0], vel[1], vel[2]]
    if frame_name == "sign_flip_xy_diagnostic_only":
        vel = _go2_velocity(row)
        return [-vel[0], -vel[1], vel[2]]
    return transform_go2_velocity_for_frame(row, frame_name)


def _source_velocity(row: dict[str, Any] | None) -> list[float]:
    if not row:
        return [math.nan, math.nan, math.nan]
    return [_f(row.get(axis)) for axis in ("vn", "ve", "vd")]


def _go2_position(row: dict[str, Any]) -> list[float]:
    return [_f(row.get(f"go2_position_{axis}")) for axis in range(3)]


def _position_derivative(rows: list[dict[str, Any]]) -> list[tuple[float, list[float]]]:
    out: list[tuple[float, list[float]]] = []
    for prev, cur in zip(rows, rows[1:]):
        t0 = _time_value(prev)
        t1 = _time_value(cur)
        dt = t1 - t0
        p0 = _go2_position(prev)
        p1 = _go2_position(cur)
        if dt <= 0 or not all(math.isfinite(value) for value in [*p0, *p1]):
            continue
        out.append((t1, [(p1[axis] - p0[axis]) / dt for axis in range(3)]))
    return out


def _angle_diff(a: float, b: float) -> float:
    diff = a - b
    while diff > math.pi:
        diff -= 2.0 * math.pi
    while diff <= -math.pi:
        diff += 2.0 * math.pi
    return diff


def _internal_score(go2_rows: list[dict[str, Any]], frame_name: str) -> dict[str, Any]:
    rows = sorted(go2_rows, key=_time_value)
    derivatives = _position_derivative(rows)
    derivative_rows = [
        {"time": item[0], "vn": item[1][0], "ve": item[1][1], "vd": item[1][2]}
        for item in derivatives
    ]
    derivative_index = 0
    derivative_diffs: list[float] = []
    integration_diffs: list[float] = []
    yaw_diffs: list[float] = []
    heading_alignments: list[float] = []
    for index, row in enumerate(rows):
        time_value = _time_value(row)
        candidate = _candidate_velocity(row, frame_name)
        if not all(math.isfinite(value) for value in candidate):
            continue
        if derivative_rows:
            deriv, derivative_index = _nearest_from_index(derivative_rows, time_value, derivative_index, tolerance=0.15)
            if deriv:
                diff = [candidate[axis] - _f(deriv.get(axis_name)) for axis, axis_name in enumerate(("vn", "ve", "vd"))]
                norm = _norm(diff)
                if math.isfinite(norm):
                    derivative_diffs.append(norm)
        if index + 5 < len(rows):
            future = rows[index + 5]
            dt = _time_value(future) - time_value
            p0 = _go2_position(row)
            p1 = _go2_position(future)
            if dt > 0 and all(math.isfinite(value) for value in [*p0, *p1]):
                predicted = [candidate[axis] * dt for axis in range(3)]
                actual = [p1[axis] - p0[axis] for axis in range(3)]
                norm = _norm([predicted[axis] - actual[axis] for axis in range(3)])
                if math.isfinite(norm):
                    integration_diffs.append(norm / max(dt, 1e-6))
        if index > 0:
            prev = rows[index - 1]
            dt = time_value - _time_value(prev)
            yaw = _f(row.get("yaw_rad"))
            prev_yaw = _f(prev.get("yaw_rad"))
            yaw_speed = _f(row.get("yaw_speed_radps"))
            if dt > 0 and all(math.isfinite(value) for value in [yaw, prev_yaw, yaw_speed]):
                yaw_diffs.append(abs(_angle_diff(yaw, prev_yaw) / dt - yaw_speed))
        horizontal = math.hypot(candidate[0], candidate[1])
        yaw = _f(row.get("yaw_rad"))
        if horizontal > 0.2 and math.isfinite(yaw):
            heading = [math.cos(yaw), math.sin(yaw)]
            heading_alignments.append((candidate[0] * heading[0] + candidate[1] * heading[1]) / horizontal)
    derivative_rmse = _rmse(derivative_diffs)
    integration_rmse = _rmse(integration_diffs)
    yaw_rmse = _rmse(yaw_diffs)
    heading_alignment_mean = sum(heading_alignments) / len(heading_alignments) if heading_alignments else None
    score_values = [value for value in [derivative_rmse, integration_rmse] if value is not None]
    score = sum(score_values) / len(score_values) if score_values else None
    if score is not None and heading_alignment_mean is not None:
        score += max(0.0, 1.0 - heading_alignment_mean) * 0.15
    return {
        "position_derivative_rmse": derivative_rmse,
        "velocity_integration_rmse": integration_rmse,
        "yaw_speed_consistency_rmse": yaw_rmse,
        "heading_alignment_mean": heading_alignment_mean,
        "internal_score": score,
    }


def _external_score(
    go2_rows: list[dict[str, Any]],
    receiver_rows: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    frame_name: str,
    *,
    tolerance: float = 0.55,
) -> dict[str, Any]:
    receiver_sorted = sorted(receiver_rows, key=lambda row: _f(row.get("time"), 0.0))
    raw_sorted = sorted(raw_rows, key=lambda row: _f(row.get("time"), 0.0))
    receiver_index = 0
    raw_index = 0
    receiver_diffs: list[float] = []
    raw_diffs: list[float] = []
    receiver_candidate_norms: list[float] = []
    receiver_source_norms: list[float] = []
    raw_candidate_norms: list[float] = []
    raw_source_norms: list[float] = []
    for row in sorted(go2_rows, key=_time_value):
        time_value = _time_value(row)
        candidate = _candidate_velocity(row, frame_name)
        if not all(math.isfinite(value) for value in candidate):
            continue
        receiver, receiver_index = _nearest_from_index(receiver_sorted, time_value, receiver_index, tolerance=tolerance)
        raw, raw_index = _nearest_from_index(raw_sorted, time_value, raw_index, tolerance=tolerance)
        for source, diffs, cnorms, snorms in [
            (_source_velocity(receiver), receiver_diffs, receiver_candidate_norms, receiver_source_norms),
            (_source_velocity(raw), raw_diffs, raw_candidate_norms, raw_source_norms),
        ]:
            diff = _norm([candidate[axis] - source[axis] for axis in range(3)])
            if math.isfinite(diff):
                diffs.append(diff)
                cnorms.append(_norm(candidate))
                snorms.append(_norm(source))
    receiver_rmse = _rmse(receiver_diffs)
    raw_rmse = _rmse(raw_diffs)
    values = [value for value in [receiver_rmse, raw_rmse] if value is not None]
    external = sum(values) / len(values) if values else None
    return {
        "rmse_to_receiver": receiver_rmse,
        "rmse_to_raw": raw_rmse,
        "aligned_count_to_receiver": len(receiver_diffs),
        "aligned_count_to_raw": len(raw_diffs),
        "candidate_norm_vs_receiver_norm_corr": _corr(receiver_candidate_norms, receiver_source_norms),
        "candidate_norm_vs_raw_norm_corr": _corr(raw_candidate_norms, raw_source_norms),
        "external_score": external,
    }


def score_velocity_frames(
    *,
    go2_rows: list[dict[str, Any]],
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Score Go2 velocity frame hypotheses with internal and external evidence."""

    candidates: dict[str, dict[str, Any]] = {}
    for frame_name in FRAME_CANDIDATES:
        internal = _internal_score(go2_rows, frame_name)
        external = _external_score(go2_rows, receiver_velocity_rows, raw_doppler_rows, frame_name)
        ivalue = internal.get("internal_score")
        evalue = external.get("external_score")
        values = [float(value) for value in [ivalue, evalue] if value is not None and math.isfinite(float(value))]
        combined = 0.45 * float(ivalue) + 0.55 * float(evalue) if ivalue is not None and evalue is not None else (sum(values) / len(values) if values else None)
        candidates[frame_name] = {
            "internal": internal,
            "external": external,
            "internal_score": ivalue,
            "external_score": evalue,
            "combined_score": combined,
        }
    ranked = sorted(
        ((name, metrics) for name, metrics in candidates.items() if metrics.get("combined_score") is not None),
        key=lambda item: float(item[1]["combined_score"]),
    )
    best = ranked[0][0] if ranked else ""
    second = ranked[1][0] if len(ranked) > 1 else ""
    best_score = float(ranked[0][1]["combined_score"]) if ranked else math.nan
    second_score = float(ranked[1][1]["combined_score"]) if len(ranked) > 1 else math.nan
    margin = (second_score - best_score) / max(best_score, 1e-6) if math.isfinite(best_score) and math.isfinite(second_score) else None
    if not ranked:
        status = "unresolved"
    elif margin is not None and margin >= 0.08:
        status = "resolved_for_diagnostic"
    elif math.isfinite(best_score) and best_score <= 4.0:
        status = "ambiguous_but_testable"
    else:
        status = "unresolved"
    return {
        "stage": "N7B4_literature_informed_contact_velocity",
        "candidate_count": len(FRAME_CANDIDATES),
        "candidates": candidates,
        "internal_score_definition": "Go2 position derivative/integration/yaw consistency, not truth",
        "external_score_definition": "receiver-native and raw Doppler cross-source consistency, not truth error",
        "best_candidate": best,
        "second_best": second,
        "margin": margin,
        "frame_status": status,
        "selected_frame_for_diagnostic": best if status in {"resolved_for_diagnostic", "ambiguous_but_testable"} else "",
        "top2_frame_for_diagnostic": second if status == "ambiguous_but_testable" else "",
        "no_truth_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "diagnostic_only": True,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_velocity_frame_score(
    *,
    go2_rows: list[dict[str, Any]],
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
    output_dir: str | Path,
) -> tuple[Path, dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = score_velocity_frames(
        go2_rows=go2_rows,
        receiver_velocity_rows=receiver_velocity_rows,
        raw_doppler_rows=raw_doppler_rows,
    )
    path = out / "GO2_VELOCITY_FRAME_SCORE_REPORT.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, report
