"""N7B3 Go2 velocity frame cross-source review.

中文说明：本模块只比较 Go2 velocity 与 receiver-native / raw Doppler velocity
的一致性，不把 Go2 velocity、receiver velocity 或 raw Doppler velocity 当 truth，
也不读取 trace/final_v23 output 选 frame。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Callable

from .go2_contact_state import _f, _time_value
from .go2_velocity_quality import _corr, _nearest_from_index, _norm, _rmse


FrameTransform = Callable[[dict[str, Any]], list[float]]


def _go2_velocity(row: dict[str, Any]) -> list[float]:
    return [_f(row.get(f"go2_velocity_{axis}")) for axis in range(3)]


def _source_velocity(row: dict[str, Any] | None) -> list[float]:
    if not row:
        return [math.nan, math.nan, math.nan]
    return [_f(row.get(axis)) for axis in ("vn", "ve", "vd")]


def _rpy(row: dict[str, Any]) -> tuple[float, float, float]:
    return (_f(row.get("roll_rad"), 0.0), _f(row.get("pitch_rad"), 0.0), _f(row.get("yaw_rad"), 0.0))


def _rotate_rpy(vector: list[float], row: dict[str, Any], *, yaw_only: bool = False) -> list[float]:
    roll, pitch, yaw = _rpy(row)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    if yaw_only:
        return [cy * vector[0] - sy * vector[1], sy * vector[0] + cy * vector[1], vector[2]]
    # Rz(yaw) * Ry(pitch) * Rx(roll), used only as a diagnostic frame hypothesis.
    return [
        cy * cp * vector[0] + (cy * sp * sr - sy * cr) * vector[1] + (cy * sp * cr + sy * sr) * vector[2],
        sy * cp * vector[0] + (sy * sp * sr + cy * cr) * vector[1] + (sy * sp * cr - cy * sr) * vector[2],
        -sp * vector[0] + cp * sr * vector[1] + cp * cr * vector[2],
    ]


def _frame_hypotheses() -> dict[str, FrameTransform]:
    return {
        "go2_velocity_as_world_enu_or_ned_direct": lambda row: _go2_velocity(row),
        "go2_velocity_as_body_flu_then_rotate_by_go2_attitude": lambda row: _rotate_rpy(_go2_velocity(row), row),
        "go2_velocity_flu_to_frd_then_rotate": lambda row: _rotate_rpy(
            [_go2_velocity(row)[0], -_go2_velocity(row)[1], -_go2_velocity(row)[2]],
            row,
        ),
        "sign_flip_y": lambda row: [_go2_velocity(row)[0], -_go2_velocity(row)[1], _go2_velocity(row)[2]],
        "sign_flip_z": lambda row: [_go2_velocity(row)[0], _go2_velocity(row)[1], -_go2_velocity(row)[2]],
        "xy_swap_diagnostic_only": lambda row: [_go2_velocity(row)[1], _go2_velocity(row)[0], _go2_velocity(row)[2]],
        "yaw_only_rotation_diagnostic_only": lambda row: _rotate_rpy(_go2_velocity(row), row, yaw_only=True),
    }


def _candidate_metrics(
    go2_rows: list[dict[str, Any]],
    receiver_rows: list[dict[str, Any]],
    raw_rows: list[dict[str, Any]],
    transform: FrameTransform,
    *,
    tolerance: float,
) -> dict[str, Any]:
    receiver_sorted = sorted(receiver_rows, key=lambda row: _f(row.get("time"), 0.0))
    raw_sorted = sorted(raw_rows, key=lambda row: _f(row.get("time"), 0.0))
    receiver_index = 0
    raw_index = 0
    receiver_diff_norms: list[float] = []
    raw_diff_norms: list[float] = []
    receiver_candidate_norms: list[float] = []
    receiver_source_norms: list[float] = []
    raw_candidate_norms: list[float] = []
    raw_source_norms: list[float] = []
    receiver_axis_diff = [[], [], []]
    raw_axis_diff = [[], [], []]
    samples: list[dict[str, Any]] = []
    for row in sorted(go2_rows, key=_time_value):
        time_value = _time_value(row)
        candidate = transform(row)
        if not all(math.isfinite(value) for value in candidate):
            continue
        receiver, receiver_index = _nearest_from_index(receiver_sorted, time_value, receiver_index, tolerance=tolerance)
        raw, raw_index = _nearest_from_index(raw_sorted, time_value, raw_index, tolerance=tolerance)
        for source_name, source, diff_norms, candidate_norms, source_norms, axis_diff in [
            ("receiver", _source_velocity(receiver), receiver_diff_norms, receiver_candidate_norms, receiver_source_norms, receiver_axis_diff),
            ("raw", _source_velocity(raw), raw_diff_norms, raw_candidate_norms, raw_source_norms, raw_axis_diff),
        ]:
            diff = [candidate[axis] - source[axis] for axis in range(3)]
            diff_norm = _norm(diff)
            if math.isfinite(diff_norm):
                diff_norms.append(diff_norm)
                candidate_norms.append(_norm(candidate))
                source_norms.append(_norm(source))
                for axis in range(3):
                    axis_diff[axis].append(diff[axis])
                if len(samples) < 200:
                    samples.append(
                        {
                            "time": time_value,
                            "source": source_name,
                            "candidate_vn": candidate[0],
                            "candidate_ve": candidate[1],
                            "candidate_vd": candidate[2],
                            "source_vn": source[0],
                            "source_ve": source[1],
                            "source_vd": source[2],
                            "diff_norm": diff_norm,
                        }
                    )
    receiver_rmse = _rmse(receiver_diff_norms)
    raw_rmse = _rmse(raw_diff_norms)
    combined_values = [value for value in [receiver_rmse, raw_rmse] if value is not None]
    combined = sum(combined_values) / len(combined_values) if combined_values else None
    return {
        "aligned_count_to_receiver": len(receiver_diff_norms),
        "aligned_count_to_raw": len(raw_diff_norms),
        "rmse_to_receiver": receiver_rmse,
        "rmse_to_raw": raw_rmse,
        "combined_cross_source_rmse": combined,
        "bias": {
            "to_receiver": {
                "vn": _mean_or_none(receiver_axis_diff[0]),
                "ve": _mean_or_none(receiver_axis_diff[1]),
                "vd": _mean_or_none(receiver_axis_diff[2]),
            },
            "to_raw": {
                "vn": _mean_or_none(raw_axis_diff[0]),
                "ve": _mean_or_none(raw_axis_diff[1]),
                "vd": _mean_or_none(raw_axis_diff[2]),
            },
        },
        "correlation": {
            "candidate_norm_vs_receiver_norm": _corr(receiver_candidate_norms, receiver_source_norms),
            "candidate_norm_vs_raw_norm": _corr(raw_candidate_norms, raw_source_norms),
        },
        "samples": samples,
    }


def _mean_or_none(values: list[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    return sum(finite) / len(finite) if finite else None


def review_go2_velocity_frame(
    *,
    go2_rows: list[dict[str, Any]],
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
    tolerance: float = 0.55,
) -> dict[str, Any]:
    candidates: dict[str, dict[str, Any]] = {}
    for name, transform in _frame_hypotheses().items():
        candidates[name] = _candidate_metrics(
            go2_rows,
            receiver_velocity_rows,
            raw_doppler_rows,
            transform,
            tolerance=tolerance,
        )
    ranked = sorted(
        ((name, metrics) for name, metrics in candidates.items() if metrics.get("combined_cross_source_rmse") is not None),
        key=lambda item: float(item[1]["combined_cross_source_rmse"]),
    )
    best_name = ranked[0][0] if ranked else ""
    second = ranked[1][1]["combined_cross_source_rmse"] if len(ranked) > 1 else None
    best_value = ranked[0][1]["combined_cross_source_rmse"] if ranked else None
    if not ranked:
        ambiguity = "insufficient_cross_source_data"
        recommended = ""
    elif second is not None and best_value is not None and float(second) <= float(best_value) * 1.08:
        ambiguity = "ambiguous_close_candidates"
        recommended = ""
    elif best_value is not None and float(best_value) > 3.0:
        ambiguity = "high_residual_review_required"
        recommended = best_name
    else:
        ambiguity = "resolved_for_diagnostic_prior"
        recommended = best_name
    best = candidates.get(best_name, {})
    return {
        "stage": "N7B3_go2_contact_velocity_diagnostic_activation",
        "candidate_count": len(candidates),
        "candidates": candidates,
        "best_candidate_by_cross_source_consistency": best_name,
        "rmse_to_receiver": best.get("rmse_to_receiver"),
        "rmse_to_raw": best.get("rmse_to_raw"),
        "bias": best.get("bias", {}),
        "correlation": best.get("correlation", {}),
        "frame_ambiguity_status": ambiguity,
        "recommended_frame_for_diagnostic_prior": recommended,
        "metric_namespace": "cross_source_consistency_not_truth_error",
        "no_truth_claim": True,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "activation_performed": False,
        "diagnostic_only": True,
        "paper_performance_claim": False,
        "fgo": False,
    }


def transform_go2_velocity_for_frame(row: dict[str, Any], frame_name: str) -> list[float]:
    """Return a diagnostic NED-like velocity candidate for a named frame hypothesis."""

    transform = _frame_hypotheses().get(frame_name)
    if transform is None:
        return [math.nan, math.nan, math.nan]
    return transform(row)


def write_go2_velocity_frame_review(
    *,
    go2_rows: list[dict[str, Any]],
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
    output_dir: str | Path,
) -> tuple[Path, dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = review_go2_velocity_frame(
        go2_rows=go2_rows,
        receiver_velocity_rows=receiver_velocity_rows,
        raw_doppler_rows=raw_doppler_rows,
    )
    path = out / "GO2_VELOCITY_FRAME_REVIEW_REPORT.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, report
