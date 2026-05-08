"""Receiver-native measurement-floor evaluation for BY2.

中文说明：本模块直接评估 receiver-native GNSS status 与 trace reference 的一致性。
trace 只作为 evaluation-only reference；这里不生成 proposed solver 输出，不回写滤波器，
不做 output-only correction，也不删除 bad epoch。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from legsa_gins.datasets.by2.dual_antenna_heading_convention import (
    apply_transverse_heading_offset,
    heading_offset_deg_for_mode,
)
from legsa_gins.evaluation.target_gates import evaluate_target_gates
from legsa_gins.evaluation.trajectory_metrics import (
    align_by_timestamp,
    compute_errors,
    load_trace_reference as _load_trace_reference,
    summary_metrics,
)


DIRECT_EVAL_NAV_HEADER = [
    "timestamp",
    "algo_time_sec",
    "raw_time",
    "lat_deg",
    "lon_deg",
    "height_m",
    "yaw_deg",
    "pitch_deg",
    "roll_deg",
    "status",
    "source_role",
    "source_name",
    "heading_offset_mode",
    "heading_offset_deg",
    "baseline_heading_deg",
    "body_heading_candidate_deg",
    "heading_mounting_diagnostic_only",
    "trace_solver_input",
]


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = str(value).strip()
    if text == "":
        return default
    return float(text)


def _as_bool(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_receiver_status_standard(path: str | Path) -> list[dict[str, Any]]:
    """Load standardized receiver status rows.

    The loader preserves original columns and adds no solver-facing semantics.
    """

    rows = _read_csv(path)
    rows.sort(
        key=lambda row: _as_float(
            row.get("algo_time_sec"),
            _as_float(row.get("time_unix"), _as_float(row.get("tow"), 0.0)),
        )
        or 0.0
    )
    return rows


def load_trace_eval_reference(path: str | Path) -> list[dict[str, float]]:
    """Load trace reference for evaluation only."""

    return _load_trace_reference(path)


def _heading_from_row(row: dict[str, Any]) -> float | None:
    return _as_float(row.get("baseline_heading_deg"), _as_float(row.get("heading_deg")))


def make_direct_receiver_eval_nav(
    receiver_rows: list[dict[str, Any]],
    *,
    source_name: str,
    heading_offset_mode: str,
) -> list[dict[str, Any]]:
    """Build EVAL_NAV-like rows directly from receiver-native status."""

    offset_deg = heading_offset_deg_for_mode(heading_offset_mode)
    eval_rows: list[dict[str, Any]] = []
    for row in receiver_rows:
        lat = _as_float(row.get("lat_deg"))
        lon = _as_float(row.get("lon_deg"))
        height = _as_float(row.get("height_m"))
        has_position = _as_bool(row.get("has_position")) and None not in {lat, lon, height}
        if not has_position:
            continue
        timestamp = _as_float(
            row.get("algo_time_sec"),
            _as_float(row.get("time_unix"), _as_float(row.get("tow"))),
        )
        if timestamp is None:
            continue
        baseline_heading = _heading_from_row(row)
        has_heading = _as_bool(row.get("heading_valid")) and baseline_heading is not None
        body_heading = (
            apply_transverse_heading_offset(float(baseline_heading), offset_deg)
            if has_heading and baseline_heading is not None
            else 0.0
        )
        raw_time = _as_float(row.get("raw_time"), _as_float(row.get("time_unix")))
        eval_rows.append(
            {
                "timestamp": float(timestamp),
                "algo_time_sec": float(timestamp),
                "raw_time": raw_time,
                "lat_deg": float(lat),
                "lon_deg": float(lon),
                "height_m": float(height),
                "yaw_deg": float(body_heading),
                "pitch_deg": 0.0,
                "roll_deg": 0.0,
                "status": "direct_receiver_measurement_floor",
                "source_role": "measurement_floor",
                "source_name": source_name,
                "heading_offset_mode": heading_offset_mode,
                "heading_offset_deg": offset_deg,
                "baseline_heading_deg": baseline_heading,
                "body_heading_candidate_deg": float(body_heading),
                "heading_mounting_diagnostic_only": True,
                "trace_solver_input": False,
            }
        )
    eval_rows.sort(key=lambda item: float(item["timestamp"]))
    return eval_rows


def _eval_rows_for_metrics(rows: list[dict[str, Any]]) -> list[dict[str, float]]:
    return [
        {
            "timestamp": float(row["timestamp"]),
            "lat_deg": float(row["lat_deg"]),
            "lon_deg": float(row["lon_deg"]),
            "height_m": float(row["height_m"]),
            "roll_deg": float(row["roll_deg"]),
            "pitch_deg": float(row["pitch_deg"]),
            "yaw_deg": float(row["yaw_deg"]),
        }
        for row in rows
    ]


def evaluate_measurement_floor(
    receiver_eval_nav: list[dict[str, Any]],
    trace_eval_reference: list[dict[str, float]],
    *,
    max_dt: float = 0.05,
) -> dict[str, Any]:
    """Evaluate direct receiver rows against trace reference."""

    aligned = align_by_timestamp(
        _eval_rows_for_metrics(receiver_eval_nav),
        trace_eval_reference,
        max_dt=max_dt,
    )
    summary = summary_metrics(compute_errors(aligned))
    summary.update(
        {
            "evaluation_role": "receiver_native_measurement_floor",
            "trace_solver_input": False,
            "trace_evaluation_only": True,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
            "proposed_solver_output": False,
            "numerical_performance_claim": False,
        }
    )
    return summary


def compare_filter_trial_to_measurement_floor(
    filter_summary: dict[str, Any],
    floor_summary: dict[str, Any],
) -> dict[str, Any]:
    """Classify whether the observed gap is likely input/evaluator or filter-side."""

    filter_h = _as_float(filter_summary.get("horizontal_rmse_m"))
    floor_h = _as_float(floor_summary.get("horizontal_rmse_m"))
    floor_yaw = _as_float(floor_summary.get("yaw_rmse_deg"))

    floor_h_good = floor_h is not None and floor_h <= 2.0
    filter_worse = bool(
        floor_h_good
        and filter_h is not None
        and filter_h > max(5.0, 2.0 * max(floor_h or 0.0, 1.0))
    )
    input_or_eval = bool(floor_h is not None and floor_h > 5.0)
    heading_issue = bool(floor_yaw is not None and floor_yaw > 10.0)
    gate_report = evaluate_target_gates(
        {
            "horizontal_rmse_m": floor_h,
            "up_rmse_m": floor_summary.get("up_rmse_m"),
            "yaw_rmse_deg": floor_yaw,
            "roll_rmse_deg": floor_summary.get("roll_rmse_deg", 0.0),
            "pitch_rmse_deg": floor_summary.get("pitch_rmse_deg", 0.0),
        }
    )
    floor_exceeds_gate = not bool(gate_report["target_gate_pass"])

    if input_or_eval:
        recommended = "input_source_or_final_v23_input_parity_audit"
        conclusion = "input_or_evaluator_issue"
    elif filter_worse:
        recommended = "N4H_full_kf_gins_style_ekf_reconstruction"
        conclusion = "filter_update_or_mechanization_issue"
    elif heading_issue:
        recommended = "heading_convention_or_antenna_order_audit"
        conclusion = "heading_convention_issue"
    else:
        recommended = "N4H_full_kf_gins_style_ekf_reconstruction"
        conclusion = "measurement_floor_sane_filter_reconstruction_allowed"

    return {
        "filter_worse_than_measurement_floor": filter_worse,
        "measurement_floor_exceeds_target_gate": floor_exceeds_gate,
        "likely_filter_issue": bool(filter_worse and not input_or_eval),
        "likely_input_or_evaluator_issue": input_or_eval,
        "likely_heading_convention_issue": heading_issue,
        "target_gate_pass": bool(gate_report["target_gate_pass"]),
        "ready_for_factor_stacking": bool(gate_report["ready_for_factor_stacking"]),
        "recommended_next_stage": recommended,
        "conclusion": conclusion,
        "trace_solver_input": False,
        "proposed_solver_output": False,
        "numerical_performance_claim": False,
    }


def write_direct_receiver_eval_nav(rows: list[dict[str, Any]], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DIRECT_EVAL_NAV_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in DIRECT_EVAL_NAV_HEADER})


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
