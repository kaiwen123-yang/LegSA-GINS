"""Evaluator for N4H4R3 source-backed port clean replay.

中文说明：本模块只做 fresh evaluation；dual_final_v23 official reference 是评价参考，
不是 solver input，不做 output-only correction，不删除 epoch。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.official_case_review_reproduction import parse_kfgins_nav
from legsa_gins.evaluation.trajectory_metrics import EARTH_RADIUS_M, write_error_series
from legsa_gins.evaluation.legsa_v23_port_parity_decision import EXTERNAL_CLEAN_REFERENCE


def _wrap_deg(value: float) -> float:
    wrapped = (value + 180.0) % 360.0 - 180.0
    return -180.0 if wrapped == 180.0 else wrapped


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _p95(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1))
    return ordered[index]


def _max(values: list[float]) -> float | None:
    return max(values) if values else None


def load_port_eval_nav(path: str | Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            timestamp = float(raw.get("time") or raw.get("timestamp") or raw.get("algo_time_sec"))
            rows.append(
                {
                    "timestamp": timestamp,
                    "time": timestamp,
                    "lat_deg": float(raw["lat_deg"]),
                    "lon_deg": float(raw["lon_deg"]),
                    "height_m": float(raw["height_m"]),
                    "roll_deg": float(raw["roll_deg"]),
                    "pitch_deg": float(raw["pitch_deg"]),
                    "yaw_deg": float(raw["yaw_deg"]),
                }
            )
    rows.sort(key=lambda row: row["timestamp"])
    return rows


def align_by_time(
    estimate_rows: list[dict[str, float]],
    reference_rows: list[dict[str, float]],
    tolerance: float = 0.005,
) -> list[tuple[dict[str, float], dict[str, float], float]]:
    aligned: list[tuple[dict[str, float], dict[str, float], float]] = []
    if not estimate_rows or not reference_rows:
        return aligned
    ref_index = 0
    for est in estimate_rows:
        timestamp = est["timestamp"]
        while (
            ref_index + 1 < len(reference_rows)
            and abs(reference_rows[ref_index + 1]["timestamp"] - timestamp)
            <= abs(reference_rows[ref_index]["timestamp"] - timestamp)
        ):
            ref_index += 1
        ref = reference_rows[ref_index]
        dt = timestamp - ref["timestamp"]
        if abs(dt) <= tolerance:
            aligned.append((est, ref, dt))
    return aligned


def compute_error_rows(
    aligned_rows: list[tuple[dict[str, float], dict[str, float], float]]
) -> list[dict[str, float]]:
    errors: list[dict[str, float]] = []
    for est, ref, dt in aligned_rows:
        ref_lat_rad = math.radians(ref["lat_deg"])
        north = math.radians(est["lat_deg"] - ref["lat_deg"]) * EARTH_RADIUS_M
        east = math.radians(est["lon_deg"] - ref["lon_deg"]) * EARTH_RADIUS_M * math.cos(ref_lat_rad)
        up = est["height_m"] - ref["height_m"]
        errors.append(
            {
                "timestamp": est["timestamp"],
                "reference_timestamp": ref["timestamp"],
                "dt": dt,
                "north_error_m": north,
                "east_error_m": east,
                "up_error_m": up,
                "horizontal_error_m": math.hypot(north, east),
                "roll_error_deg": _wrap_deg(est["roll_deg"] - ref["roll_deg"]),
                "pitch_error_deg": _wrap_deg(est["pitch_deg"] - ref["pitch_deg"]),
                "yaw_error_deg": _wrap_deg(est["yaw_deg"] - ref["yaw_deg"]),
            }
        )
    return errors


def summarize_port_errors(errors: list[dict[str, float]]) -> dict[str, Any]:
    horizontal = [abs(row["horizontal_error_m"]) for row in errors]
    up = [row["up_error_m"] for row in errors]
    roll = [row["roll_error_deg"] for row in errors]
    pitch = [row["pitch_error_deg"] for row in errors]
    yaw = [row["yaw_error_deg"] for row in errors]
    yaw_abs = [abs(value) for value in yaw]
    summary = {
        "phase": "N4H4R3",
        "count": len(errors),
        "aligned_count": len(errors),
        "evidence_status": "diagnostic_aligned" if len(errors) > 100 else "insufficient_alignment",
        "horizontal_rmse_m": _rmse(horizontal),
        "horizontal_p95_m": _p95(horizontal),
        "horizontal_max_m": _max(horizontal),
        "up_rmse_m": _rmse(up),
        "up_p95_m": _p95([abs(value) for value in up]),
        "up_max_m": _max([abs(value) for value in up]),
        "yaw_rmse_deg": _rmse(yaw),
        "yaw_p95_deg": _p95(yaw_abs),
        "yaw_max_deg": _max(yaw_abs),
        "roll_rmse_deg": _rmse(roll),
        "roll_p95_deg": _p95([abs(value) for value in roll]),
        "roll_max_deg": _max([abs(value) for value in roll]),
        "pitch_rmse_deg": _rmse(pitch),
        "pitch_p95_deg": _p95([abs(value) for value in pitch]),
        "pitch_max_deg": _max([abs(value) for value in pitch]),
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
    summary.update(
        {
            "horizontal_gate_pass": summary["horizontal_rmse_m"] is not None
            and summary["horizontal_rmse_m"] <= 2.0,
            "up_gate_pass": summary["up_rmse_m"] is not None and summary["up_rmse_m"] <= 3.0,
            "yaw_gate_pass": summary["yaw_rmse_deg"] is not None and summary["yaw_rmse_deg"] <= 2.0,
            "roll_strict_pass": summary["roll_rmse_deg"] is not None and summary["roll_rmse_deg"] <= 1.0,
            "pitch_strict_pass": summary["pitch_rmse_deg"] is not None and summary["pitch_rmse_deg"] <= 1.0,
            "roll_relaxed_pass": summary["roll_rmse_deg"] is not None and summary["roll_rmse_deg"] <= 1.6,
            "pitch_relaxed_pass": summary["pitch_rmse_deg"] is not None and summary["pitch_rmse_deg"] <= 1.6,
        }
    )
    return summary


def evaluate_port_clean_replay(
    port_eval_nav: str | Path,
    dual_root: str | Path,
    error_series_path: str | Path | None = None,
    *,
    tolerance: float = 0.005,
) -> dict[str, Any]:
    estimate_rows = load_port_eval_nav(port_eval_nav)
    reference_rows = parse_kfgins_nav(Path(dual_root) / "KF_GINS_Navresult.nav")
    aligned = align_by_time(estimate_rows, reference_rows, tolerance=tolerance)
    errors = compute_error_rows(aligned)
    if error_series_path:
        write_error_series(errors, error_series_path)
    summary = summarize_port_errors(errors)
    return {
        "phase": "N4H4R3",
        "estimate_count": len(estimate_rows),
        "reference_count": len(reference_rows),
        "aligned_count": len(aligned),
        "summary": summary,
        "external_clean_reference": EXTERNAL_CLEAN_REFERENCE,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
    }


def write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
