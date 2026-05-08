"""Automatic pre-review checks for dual replay visual bundles.

中文说明：这些检查只是绘图前/图像包 sanity，不是 formal pass，也不修改
solver output。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


REQUIRED_FIGURES = [
    "01_trajectory/dual_replay_traj_truth_est.png",
    "02_position_errors/dual_replay_pos_horizontal.png",
    "04_attitude/dual_replay_yaw_error_deg.png",
    "08_summary_panels/dual_replay_summary_panel.png",
    "09_case_review/visual_case_review.md",
]


def _numeric_values(data: Any) -> list[float]:
    values: list[float] = []
    if isinstance(data, dict):
        for value in data.values():
            values.extend(_numeric_values(value))
    elif isinstance(data, list):
        for value in data:
            values.extend(_numeric_values(value))
    elif isinstance(data, (int, float)):
        values.append(float(data))
    return values


def check_time_monotonic(rows: list[dict[str, Any]], time_key: str = "timestamp") -> dict[str, Any]:
    previous: float | None = None
    monotonic = True
    for row in rows:
        if time_key not in row:
            continue
        current = float(row[time_key])
        if previous is not None and current < previous:
            monotonic = False
            break
        previous = current
    return {"time_monotonic": monotonic, "count": len(rows)}


def check_no_nan_inf(data: Any) -> dict[str, Any]:
    values = _numeric_values(data)
    return {
        "no_nan_inf": all(math.isfinite(value) for value in values),
        "numeric_value_count": len(values),
    }


def check_error_spike(
    error_series: list[dict[str, Any]],
    *,
    horizontal_threshold_m: float = 2.0,
    yaw_abs_threshold_deg: float = 10.0,
) -> dict[str, Any]:
    horizontal = [abs(float(row.get("horizontal_error_m", 0.0))) for row in error_series]
    yaw_abs = [abs(float(row.get("yaw_error_deg", 0.0))) for row in error_series]
    max_horizontal = max(horizontal) if horizontal else None
    max_yaw = max(yaw_abs) if yaw_abs else None
    return {
        "horizontal_error_max_m": max_horizontal,
        "yaw_error_abs_max_deg": max_yaw,
        "horizontal_error_max_reasonable": isinstance(max_horizontal, (int, float))
        and max_horizontal <= horizontal_threshold_m,
        "yaw_error_abs_max_reasonable": isinstance(max_yaw, (int, float)) and max_yaw <= yaw_abs_threshold_deg,
    }


def check_terminal_error(error_series: list[dict[str, Any]]) -> dict[str, Any]:
    if not error_series:
        return {"terminal_error_status": "evidence_missing"}
    last = error_series[-1]
    return {
        "terminal_horizontal_error_m": last.get("horizontal_error_m"),
        "terminal_up_error_m": last.get("up_error_m"),
        "terminal_yaw_error_deg": last.get("yaw_error_deg"),
        "terminal_error_status": "available",
    }


def check_yaw_wrap_discontinuity(
    error_series: list[dict[str, Any]],
    *,
    jump_threshold_deg: float = 90.0,
) -> dict[str, Any]:
    yaws = [float(row.get("yaw_error_deg", 0.0)) for row in error_series]
    jumps = [abs(yaws[index] - yaws[index - 1]) for index in range(1, len(yaws))]
    max_jump = max(jumps) if jumps else 0.0
    return {
        "yaw_error_max_consecutive_jump_deg": max_jump,
        "yaw_wrap_spike_detected": max_jump > jump_threshold_deg,
    }


def check_reference_estimate_overlap(
    reference_rows: list[dict[str, Any]],
    estimate_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not reference_rows or not estimate_rows:
        return {
            "reference_estimate_overlap_reasonable": False,
            "evidence_status": "evidence_missing",
        }
    ref_start = float(reference_rows[0].get("timestamp", reference_rows[0].get("time")))
    ref_end = float(reference_rows[-1].get("timestamp", reference_rows[-1].get("time")))
    est_start = float(estimate_rows[0].get("timestamp", estimate_rows[0].get("time")))
    est_end = float(estimate_rows[-1].get("timestamp", estimate_rows[-1].get("time")))
    overlap = max(0.0, min(ref_end, est_end) - max(ref_start, est_start))
    ref_span = max(0.0, ref_end - ref_start)
    est_span = max(0.0, est_end - est_start)
    ratio = overlap / max(1.0e-9, min(ref_span, est_span))
    return {
        "reference_start": ref_start,
        "reference_end": ref_end,
        "estimate_start": est_start,
        "estimate_end": est_end,
        "overlap_seconds": overlap,
        "overlap_ratio": ratio,
        "reference_estimate_overlap_reasonable": ratio >= 0.99,
        "evidence_status": "available",
    }


def check_plot_file_count(output_dir: str | Path, expected_min_count: int = 30) -> dict[str, Any]:
    root = Path(output_dir)
    figures = sorted(root.rglob("*.png")) if root.exists() else []
    return {
        "figure_count": len(figures),
        "expected_min_count": expected_min_count,
        "required_figures_generated": len(figures) >= expected_min_count,
    }


def check_required_figures(output_dir: str | Path, required_figures: list[str] | None = None) -> dict[str, Any]:
    root = Path(output_dir)
    required = required_figures or REQUIRED_FIGURES
    missing = [name for name in required if not (root / name).exists()]
    return {
        "required_figures": required,
        "missing_figures": missing,
        "required_figure_set_complete": not missing,
    }


def strict_yaw_gate_status(yaw_rmse_deg: float | None) -> dict[str, Any]:
    yaw = float(yaw_rmse_deg) if isinstance(yaw_rmse_deg, (int, float)) else None
    return {
        "yaw_rmse_deg": yaw,
        "yaw_gate_pass": yaw is not None and yaw <= 2.0,
        "yaw_near_boundary": yaw is not None and 1.8 <= yaw <= 2.2,
        "near_boundary_not_relaxed": yaw is not None and yaw > 2.0,
    }


def build_visual_sanity_report(
    *,
    output_dir: str | Path,
    reference_rows: list[dict[str, Any]],
    estimate_rows: list[dict[str, Any]],
    error_series: list[dict[str, Any]],
    metrics_snapshot: dict[str, Any],
    expected_count: int | None = None,
    expected_min_figures: int = 30,
) -> dict[str, Any]:
    time_ref = check_time_monotonic(reference_rows)
    time_est = check_time_monotonic(estimate_rows)
    finite = check_no_nan_inf([reference_rows, estimate_rows, error_series, metrics_snapshot])
    spikes = check_error_spike(error_series)
    terminal = check_terminal_error(error_series)
    yaw_wrap = check_yaw_wrap_discontinuity(error_series)
    overlap = check_reference_estimate_overlap(reference_rows, estimate_rows)
    figure_count = check_plot_file_count(output_dir, expected_min_figures)
    required = check_required_figures(output_dir)
    count_matches = expected_count is None or len(error_series) == int(expected_count)
    report = {
        "phase": "N4H2E",
        "time_monotonic": bool(time_ref["time_monotonic"] and time_est["time_monotonic"]),
        "no_nan_inf": bool(finite["no_nan_inf"]),
        "count_matches_expected": count_matches,
        "expected_count": expected_count,
        "error_series_count": len(error_series),
        **spikes,
        **terminal,
        **yaw_wrap,
        "reference_estimate_overlap_reasonable": overlap["reference_estimate_overlap_reasonable"],
        "overlap": overlap,
        "figure_count": figure_count["figure_count"],
        "required_figures_generated": bool(
            figure_count["required_figures_generated"] and required["required_figure_set_complete"]
        ),
        "required_figure_report": required,
        "yaw_gate_status": strict_yaw_gate_status(metrics_snapshot.get("yaw_rmse_deg")),
        "visual_manual_review_required": True,
        "manual_visual_review_required": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
    return report


def write_visual_sanity_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output

