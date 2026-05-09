"""Port-vs-final_v23 NAV parity evaluator for N4H4R3C.

中文说明：该指标只比较 port NAV 与 dual_final_v23 NAV 的工程骨架一致性，
不是 absolute performance，也不是论文性能结论。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.legsa_v23_port_clean_replay_evaluator import align_by_time, compute_error_rows
from legsa_gins.evaluation.legsa_v23_port_measurement_copy_guard import parse_nav_or_eval_nav
from legsa_gins.evaluation.legsa_v23_port_metric_namespace import MetricNamespace
from legsa_gins.evaluation.official_case_review_reproduction import parse_kfgins_nav


def _write_json(path: str | Path, data: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _first_data_line(path: Path) -> str:
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            return stripped
    return ""


def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, float]]:
    normalized: list[dict[str, float]] = []
    for row in rows:
        timestamp = float(row.get("timestamp", row.get("time", row.get("tow", row.get("algo_time_sec")))))
        normalized.append(
            {
                "timestamp": timestamp,
                "time": timestamp,
                "lat_deg": float(row.get("lat_deg", row.get("lat"))),
                "lon_deg": float(row.get("lon_deg", row.get("lon"))),
                "height_m": float(row.get("height_m", row.get("height"))),
                "roll_deg": float(row.get("roll_deg", row.get("roll"))),
                "pitch_deg": float(row.get("pitch_deg", row.get("pitch"))),
                "yaw_deg": float(row.get("yaw_deg", row.get("yaw"))),
            }
        )
    normalized.sort(key=lambda item: item["timestamp"])
    return normalized


def load_nav_rows(path_or_rows: str | Path | list[dict[str, Any]]) -> list[dict[str, float]]:
    """Load LegSA CSV/NAV or KF_GINS 11-column NAV rows."""

    if isinstance(path_or_rows, list):
        return _normalize_rows(path_or_rows)
    path = Path(path_or_rows)
    first = _first_data_line(path)
    if "," in first and any(name in first for name in ["time", "timestamp", "lat_deg"]):
        return _normalize_rows(parse_nav_or_eval_nav(path))
    fields = first.replace(",", " ").split()
    if len(fields) == 11:
        return _normalize_rows(parse_kfgins_nav(path))
    return _normalize_rows(parse_nav_or_eval_nav(path))


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


def _ok(value: float | None, threshold: float) -> bool:
    return value is not None and value <= threshold


def _summarize(errors: list[dict[str, float]]) -> dict[str, Any]:
    horizontal = [abs(row["horizontal_error_m"]) for row in errors]
    up = [row["up_error_m"] for row in errors]
    roll = [row["roll_error_deg"] for row in errors]
    pitch = [row["pitch_error_deg"] for row in errors]
    yaw = [row["yaw_error_deg"] for row in errors]
    yaw_abs = [abs(value) for value in yaw]
    roll_abs = [abs(value) for value in roll]
    pitch_abs = [abs(value) for value in pitch]
    up_abs = [abs(value) for value in up]
    summary = {
        "aligned_count": len(errors),
        "horizontal_rmse_m": _rmse(horizontal),
        "up_rmse_m": _rmse(up),
        "yaw_rmse_deg": _rmse(yaw),
        "roll_rmse_deg": _rmse(roll),
        "pitch_rmse_deg": _rmse(pitch),
        "horizontal_p95_m": _p95(horizontal),
        "up_p95_m": _p95(up_abs),
        "yaw_p95_deg": _p95(yaw_abs),
        "roll_p95_deg": _p95(roll_abs),
        "pitch_p95_deg": _p95(pitch_abs),
    }
    gate = {
        "horizontal_rmse_m_le_0_5": _ok(summary["horizontal_rmse_m"], 0.5),
        "up_rmse_m_le_0_8": _ok(summary["up_rmse_m"], 0.8),
        "yaw_rmse_deg_le_0_5": _ok(summary["yaw_rmse_deg"], 0.5),
        "roll_rmse_deg_le_0_5": _ok(summary["roll_rmse_deg"], 0.5),
        "pitch_rmse_deg_le_0_5": _ok(summary["pitch_rmse_deg"], 0.5),
    }
    summary["parity_gate"] = gate
    summary["parity_small"] = bool(errors and all(gate.values()))
    return summary


def evaluate_port_vs_final_v23_nav(
    port_nav: str | Path | list[dict[str, Any]],
    final_v23_nav: str | Path | list[dict[str, Any]],
    output_dir: str | Path,
    *,
    tolerance: float = 0.005,
) -> dict[str, Any]:
    """Compare port NAV/EVAL_NAV against dual_final_v23 NAV."""

    port_rows = load_nav_rows(port_nav)
    final_rows = load_nav_rows(final_v23_nav)
    aligned = align_by_time(port_rows, final_rows, tolerance=tolerance)
    errors = compute_error_rows(aligned)
    summary = _summarize(errors)
    times = [row["timestamp"] for row in port_rows]
    aligned_times = [est["timestamp"] for est, _, _ in aligned]
    report = {
        "phase": "N4H4R3C",
        "namespace": MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value,
        "solver_output_role": "port_nav",
        "reference_role": "dual_final_v23_nav_eval_only",
        "port_nav_count": len(port_rows),
        "final_v23_nav_count": len(final_rows),
        "aligned_count": summary["aligned_count"],
        "horizontal_rmse_m": summary["horizontal_rmse_m"],
        "up_rmse_m": summary["up_rmse_m"],
        "yaw_rmse_deg": summary["yaw_rmse_deg"],
        "roll_rmse_deg": summary["roll_rmse_deg"],
        "pitch_rmse_deg": summary["pitch_rmse_deg"],
        "horizontal_p95_m": summary["horizontal_p95_m"],
        "up_p95_m": summary["up_p95_m"],
        "yaw_p95_deg": summary["yaw_p95_deg"],
        "roll_p95_deg": summary["roll_p95_deg"],
        "pitch_p95_deg": summary["pitch_p95_deg"],
        "first_time": min(times) if times else None,
        "last_time": max(times) if times else None,
        "first_aligned_time": min(aligned_times) if aligned_times else None,
        "last_aligned_time": max(aligned_times) if aligned_times else None,
        "alignment_tolerance_sec": tolerance,
        "parity_small": summary["parity_small"],
        "parity_gate": summary["parity_gate"],
        "absolute_performance_metric": False,
        "engineering_parity_to_baseline_output": True,
        "reference_eval_only": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "no_outperform_final_v23_claim": True,
    }
    _write_json(Path(output_dir) / "PORT_VS_FINALV23_NAV_PARITY_REPORT.json", report)
    return report


def write_nav_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    """Small test helper kept stdlib-only for toy audit generation."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row[field] for field in fields})
