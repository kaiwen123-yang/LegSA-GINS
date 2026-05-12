"""N7B2 contact-conditioned velocity segment review.

中文说明：本模块比较 contact state 下的 Go2/receiver/raw-Doppler velocity
consistency；这是 source consistency，不是 truth error，也不激活 solver。
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from .go2_velocity_quality import _f, _nearest_from_index, _norm


def _go2_velocity(row: dict[str, Any]) -> list[float]:
    return [_f(row.get(f"go2_velocity_{axis}")) for axis in range(3)]


def _source_velocity(row: dict[str, Any] | None) -> list[float]:
    if row is None:
        return [math.nan, math.nan, math.nan]
    return [_f(row.get(axis)) for axis in ["vn", "ve", "vd"]]


def _time_value(row: dict[str, Any]) -> float:
    aligned = _f(row.get("aligned_time"))
    return aligned if math.isfinite(aligned) else _f(row.get("time"), 0.0)


def _mean(values: list[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    return sum(finite) / len(finite) if finite else None


def _rmse(values: list[float]) -> float | None:
    finite = [value for value in values if math.isfinite(value)]
    return math.sqrt(sum(value * value for value in finite) / len(finite)) if finite else None


def _label_by_time(contact_rows: list[dict[str, Any]], time_value: float, start: int) -> tuple[str, int]:
    row, index = _nearest_from_index(contact_rows, time_value, start, tolerance=0.10)
    return (str(row.get("contact_label_v2", "unknown")) if row else "unknown"), index


def review_contact_velocity_segments(
    go2_rows: list[dict[str, Any]],
    *,
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
    contact_v2_rows: list[dict[str, Any]],
    contact_v1_rows: list[dict[str, Any]] | None = None,
    tolerance: float = 0.55,
) -> dict[str, Any]:
    receiver_rows = sorted(receiver_velocity_rows, key=lambda row: _f(row.get("time"), 0.0))
    raw_rows = sorted(raw_doppler_rows, key=lambda row: _f(row.get("time"), 0.0))
    contact_rows = sorted(contact_v2_rows, key=lambda row: _f(row.get("time"), 0.0))
    receiver_index = 0
    raw_index = 0
    contact_index = 0
    buckets: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in sorted(go2_rows, key=_time_value):
        time_value = _time_value(row)
        go2 = _go2_velocity(row)
        if not all(math.isfinite(value) for value in go2):
            continue
        receiver, receiver_index = _nearest_from_index(receiver_rows, time_value, receiver_index, tolerance=tolerance)
        raw, raw_index = _nearest_from_index(raw_rows, time_value, raw_index, tolerance=tolerance)
        label, contact_index = _label_by_time(contact_rows, time_value, contact_index)
        receiver_velocity = _source_velocity(receiver)
        raw_velocity = _source_velocity(raw)
        receiver_diff = _norm([go2[axis] - receiver_velocity[axis] for axis in range(3)])
        raw_diff = _norm([go2[axis] - raw_velocity[axis] for axis in range(3)])
        if math.isfinite(receiver_diff):
            buckets[label]["receiver_diff_norm"].append(receiver_diff)
            for axis, name in enumerate(["bias_n", "bias_e", "bias_d"]):
                buckets[label][name].append(go2[axis] - receiver_velocity[axis])
        if math.isfinite(raw_diff):
            buckets[label]["raw_doppler_diff_norm"].append(raw_diff)
        buckets[label]["go2_velocity_norm"].append(_norm(go2))
    by_state: dict[str, dict[str, Any]] = {}
    for label, values in sorted(buckets.items()):
        by_state[label] = {
            "count": len(values.get("go2_velocity_norm", [])),
            "go2_velocity_norm_mean": _mean(values.get("go2_velocity_norm", [])),
            "velocity_diff_rmse_to_receiver": _rmse(values.get("receiver_diff_norm", [])),
            "velocity_diff_rmse_to_raw_doppler": _rmse(values.get("raw_doppler_diff_norm", [])),
            "bias_n": _mean(values.get("bias_n", [])),
            "bias_e": _mean(values.get("bias_e", [])),
            "bias_d": _mean(values.get("bias_d", [])),
        }
    walking = by_state.get("walking_contact", {})
    uncertain = by_state.get("uncertain", {})
    walking_count = int(walking.get("count", 0) or 0)
    walking_receiver_rmse = walking.get("velocity_diff_rmse_to_receiver")
    uncertain_count = int(uncertain.get("count", 0) or 0)
    improves = walking_count > 0 and uncertain_count > 0
    readiness = "insufficient_contact_segments"
    if walking_count >= 10 and isinstance(walking_receiver_rmse, (int, float)):
        readiness = "acceptable" if float(walking_receiver_rmse) <= 2.5 else "review"
    return {
        "stage": "N7B2_go2_contact_threshold_review",
        "velocity_consistency_by_contact_state": by_state,
        "bias_by_contact_state": {
            label: {key: value for key, value in state.items() if key in {"bias_n", "bias_e", "bias_d"}}
            for label, state in by_state.items()
        },
        "velocity_norm_distribution_by_contact_state": {
            label: {
                "count": state.get("count"),
                "go2_velocity_norm_mean": state.get("go2_velocity_norm_mean"),
            }
            for label, state in by_state.items()
        },
        "contact_improves_velocity_quality_interpretation": improves,
        "readiness_status": readiness,
        "contact_v1_rows_available": bool(contact_v1_rows),
        "cross_source_velocity_truth_error_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "go2_velocity_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "paper_performance_claim": False,
        "fgo": False,
    }


def write_contact_velocity_segment_review(
    go2_rows: list[dict[str, Any]],
    output_dir: str | Path,
    *,
    receiver_velocity_rows: list[dict[str, Any]],
    raw_doppler_rows: list[dict[str, Any]],
    contact_v2_rows: list[dict[str, Any]],
    contact_v1_rows: list[dict[str, Any]] | None = None,
) -> tuple[Path, dict[str, Any]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    report = review_contact_velocity_segments(
        go2_rows,
        receiver_velocity_rows=receiver_velocity_rows,
        raw_doppler_rows=raw_doppler_rows,
        contact_v2_rows=contact_v2_rows,
        contact_v1_rows=contact_v1_rows,
    )
    path = out / "GO2_CONTACT_VELOCITY_SEGMENT_REVIEW.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path, report
