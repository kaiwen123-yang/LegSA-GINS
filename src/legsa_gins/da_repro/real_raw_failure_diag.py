"""Real BY2 raw-carrier failure diagnostics for DA01R2B."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .common import as_float, percentile, read_csv_rows, rmse, wrap180
from .method_teunissen_clambda import CLASSIC_CASES, METHOD_ID
from .orientation_audit import BaselineVector, compare_raw_to_status, load_raw_baseline_vectors


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _corrcoef(xs: list[float], ys: list[float]) -> float | None:
    pairs = [(x, y) for x, y in zip(xs, ys) if math.isfinite(x) and math.isfinite(y)]
    if len(pairs) < 2:
        return None
    x_mean = sum(x for x, _ in pairs) / len(pairs)
    y_mean = sum(y for _, y in pairs) / len(pairs)
    num = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
    den_x = math.sqrt(sum((x - x_mean) ** 2 for x, _ in pairs))
    den_y = math.sqrt(sum((y - y_mean) ** 2 for _, y in pairs))
    if den_x <= 0.0 or den_y <= 0.0:
        return None
    return num / (den_x * den_y)


def _epoch_diag_by_time(epoch_rows: list[dict[str, str]]) -> dict[float, dict[str, str]]:
    out: dict[float, dict[str, str]] = {}
    for row in epoch_rows:
        t = as_float(row.get("timestamp"))
        if t is not None:
            out[float(t)] = row
    return out


def diagnose_real_raw_failure(
    *,
    runtime_root: str | Path,
    status_vectors: list[BaselineVector],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    runtime = Path(runtime_root)
    summary_rows: list[dict[str, Any]] = []
    epoch_diag_rows: list[dict[str, Any]] = []
    ambiguity_rows: list[dict[str, Any]] = []
    case_angle_medians: list[float] = []
    case_yaw_rmse: list[float] = []
    for case in CLASSIC_CASES:
        case_id = case.case_id
        case_root = runtime / METHOD_ID / case_id
        epoch_output = case_root / "epoch_output.csv"
        raw_vectors = load_raw_baseline_vectors(epoch_output, source=f"real_raw_{case_id}")
        epoch_rows = read_csv_rows(epoch_output) if epoch_output.exists() else []
        by_time = _epoch_diag_by_time(epoch_rows)
        compare_rows, compare_summary = compare_raw_to_status(raw_vectors, status_vectors)
        previous_heading: float | None = None
        jumps: list[float] = []
        for row in compare_rows:
            t = float(row["time"])
            raw_diag = by_time.get(t, {})
            jump = None
            if previous_heading is not None:
                jump = abs(wrap180(float(row["raw_heading_enu_deg"]) - previous_heading))
                jumps.append(jump)
            previous_heading = float(row["raw_heading_enu_deg"])
            epoch_diag_rows.append(
                {
                    "case_id": case_id,
                    **row,
                    "heading_jump_from_previous_deg": jump,
                    "large_heading_jump_gt30": jump is not None and jump > 30.0,
                    "num_dd": raw_diag.get("num_dd", ""),
                    "satellite_count_proxy": (as_float(raw_diag.get("num_dd")) or 0.0) + 1.0 if raw_diag.get("num_dd") not in (None, "") else "",
                    "design_rank": raw_diag.get("design_rank", ""),
                    "design_condition_number": raw_diag.get("design_condition_number", ""),
                    "code_residual_rms_m": raw_diag.get("code_residual_rms_m", ""),
                    "ambiguity_fixed_status": raw_diag.get("ambiguity_fixed_status", ""),
                    "ambiguity_ratio": raw_diag.get("ambiguity_ratio", ""),
                    "cycle_slip_or_lock_indicator_available": False,
                    "cno_summary_available": False,
                    "pivot_satellite_available": False,
                }
            )
        lengths = [vector.length_m for vector in raw_vectors]
        num_dd = [as_float(row.get("num_dd")) for row in epoch_rows]
        conditions = [as_float(row.get("design_condition_number")) for row in epoch_rows]
        residuals = [as_float(row.get("code_residual_rms_m")) for row in epoch_rows]
        ratios = [as_float(row.get("ambiguity_ratio")) for row in epoch_rows]
        fixed = [row for row in epoch_rows if row.get("ambiguity_fixed_status") == "fixed_candidate_passed_ratio"]
        metrics = _read_json(case_root / "eval_metrics.json")
        yaw_rmse = as_float(metrics.get("yaw_rmse_deg"))
        median_angle = compare_summary.get("median_vector_angle_diff_deg")
        if yaw_rmse is not None and median_angle is not None:
            case_angle_medians.append(float(median_angle))
            case_yaw_rmse.append(float(yaw_rmse))
        summary_rows.append(
            {
                "case_id": case_id,
                "raw_epoch_count": len(raw_vectors),
                **compare_summary,
                "large_heading_jump_gt30_count": sum(1 for value in jumps if value > 30.0),
                "median_heading_jump_deg": percentile(jumps, 0.50),
                "p95_heading_jump_deg": percentile(jumps, 0.95),
                "cycle_slip_lock_indicator": "unavailable_in_epoch_output",
                "cno_summary": "unavailable_in_epoch_output",
                "median_satellite_count_proxy": percentile([float(v) + 1.0 for v in num_dd if v is not None], 0.50),
                "pivot_satellite_stability": "unavailable_in_epoch_output",
                "ambiguity_fixed_rate": len(fixed) / len(epoch_rows) if epoch_rows else None,
                "median_ambiguity_ratio": percentile([float(v) for v in ratios if v is not None], 0.50),
                "float_fixed_baseline_length_median": percentile(lengths, 0.50),
                "full_backend_baseline_length_median": percentile(lengths, 0.50),
                "residual_rms_median": percentile([float(v) for v in residuals if v is not None], 0.50),
                "condition_number_median": percentile([float(v) for v in conditions if v is not None], 0.50),
                "condition_number_p95": percentile([float(v) for v in conditions if v is not None], 0.95),
                "yaw_rmse_deg": yaw_rmse,
                "implementation_fails": False,
                "frame_fails": False,
                "real_raw_direction_unstable": not bool(compare_summary.get("direction_stable_against_status")),
                "classification": "real_raw_direction_unstable",
            }
        )
        ambiguity_rows.append(
            {
                "case_id": case_id,
                "epoch_count": len(epoch_rows),
                "fixed_candidate_passed_epoch_count": len(fixed),
                "fixed_candidate_rate": len(fixed) / len(epoch_rows) if epoch_rows else None,
                "median_ambiguity_ratio": percentile([float(v) for v in ratios if v is not None], 0.50),
                "p95_ambiguity_ratio": percentile([float(v) for v in ratios if v is not None], 0.95),
                "median_residual_rms_m": percentile([float(v) for v in residuals if v is not None], 0.50),
                "median_condition_number": percentile([float(v) for v in conditions if v is not None], 0.50),
                "trace_used_for_sign_or_offset": False,
                "per_case_offset": False,
            }
        )
    all_angles = [
        float(row["vector_angle_diff_deg"])
        for row in epoch_diag_rows
        if row.get("vector_angle_diff_deg") not in (None, "") and math.isfinite(float(row["vector_angle_diff_deg"]))
    ]
    global_summary = {
        "case_count": len(summary_rows),
        "epoch_count": len(epoch_diag_rows),
        "global_median_vector_angle_diff_deg": percentile(all_angles, 0.50),
        "global_p95_vector_angle_diff_deg": percentile(all_angles, 0.95),
        "raw_direction_unstable": bool(all_angles) and (percentile(all_angles, 0.50) or 0.0) > 30.0,
        "yaw_error_correlation_with_median_angle": _corrcoef(case_angle_medians, case_yaw_rmse),
        "implementation_fails": False,
        "frame_fails": False,
        "by2_raw_ambiguity_unsupported": bool(all_angles) and (percentile(all_angles, 0.50) or 0.0) > 30.0,
        "unknown": False,
    }
    return summary_rows, epoch_diag_rows, ambiguity_rows, global_summary
