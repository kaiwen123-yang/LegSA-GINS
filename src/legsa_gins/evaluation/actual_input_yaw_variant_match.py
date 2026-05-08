"""Compare actual dual input.gnss yaw against process_data variants.

中文说明：variant 对比只用于判定 yaw/noise provenance；trace-yaw variant
只能 diagnostic，不可作为 solver input 或 formal clean evidence。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.evaluation.actual_vs_replay_yaw_path import (
    nearest_align,
    parse_15col_gnss,
    wrap_deg180,
)


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return math.sqrt(sum(value * value for value in values) / len(values))


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _p95_abs(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(abs(value) for value in values)
    index = int(math.ceil(0.95 * len(ordered))) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def _max_abs(values: list[float]) -> float | None:
    return max((abs(value) for value in values), default=None)


def _horizontal_diff_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    radius = 6378137.0
    lat = math.radians((float(a["lat"]) + float(b["lat"])) * 0.5)
    dn = math.radians(float(a["lat"]) - float(b["lat"])) * radius
    de = math.radians(float(a["lon"]) - float(b["lon"])) * radius * math.cos(lat)
    return math.hypot(dn, de)


def _velocity_diff_mps(a: dict[str, Any], b: dict[str, Any]) -> float:
    return math.sqrt(
        (float(a["vn"]) - float(b["vn"])) ** 2
        + (float(a["ve"]) - float(b["ve"])) ** 2
        + (float(a["vd"]) - float(b["vd"])) ** 2
    )


def _outage_pattern_match(actual_rows: list[dict[str, Any]], variant_rows: list[dict[str, Any]]) -> bool:
    if not actual_rows or not variant_rows:
        return False
    actual_times = {round(float(row["time"]), 3) for row in actual_rows}
    variant_times = {round(float(row["time"]), 3) for row in variant_rows}
    intersection = len(actual_times & variant_times)
    union = len(actual_times | variant_times)
    return union > 0 and intersection / union >= 0.995


def compare_actual_input_to_variants(
    actual_input_gnss: str | Path,
    variant_inputs: dict[str, str | Path | dict[str, Any]],
    *,
    tolerance: float = 0.05,
) -> dict[str, Any]:
    """Compare actual input.gnss with generated process_data variants."""

    actual_rows = parse_15col_gnss(actual_input_gnss)
    variant_reports: dict[str, Any] = {}
    for name, value in variant_inputs.items():
        formal_allowed = True
        path_value: str | Path | None
        if isinstance(value, dict):
            path_value = value.get("path")
            formal_allowed = bool(value.get("formal_allowed", True))
        else:
            path_value = value
        path = Path(path_value) if path_value else None
        if path is None or not path.exists():
            variant_reports[name] = {
                "variant": name,
                "evidence_status": "evidence_missing",
                "formal_allowed": formal_allowed,
            }
            continue
        variant_rows = parse_15col_gnss(path)
        pairs = nearest_align(actual_rows, variant_rows, "time", tolerance)
        yaw_diffs = [wrap_deg180(float(a["yaw"]) - float(b["yaw"])) for a, b, _ in pairs]
        yaw_std_diffs = [float(a["yaw_std"]) - float(b["yaw_std"]) for a, b, _ in pairs]
        position_diffs = [_horizontal_diff_m(a, b) for a, b, _ in pairs]
        velocity_diffs = [_velocity_diff_mps(a, b) for a, b, _ in pairs]
        yaw_rmse = _rmse(yaw_diffs)
        if not pairs:
            status = "evidence_missing"
        elif yaw_rmse is not None and yaw_rmse <= 0.2 and len(actual_rows) == len(variant_rows):
            status = "exact_or_near_match"
        elif yaw_rmse is not None and yaw_rmse <= 3.0:
            status = "close_but_not_exact"
        else:
            status = "mismatch"
        variant_reports[name] = {
            "variant": name,
            "path": str(path),
            "formal_allowed": formal_allowed,
            "actual_count": len(actual_rows),
            "variant_count": len(variant_rows),
            "aligned_count": len(pairs),
            "row_count_match": len(actual_rows) == len(variant_rows),
            "time_match_count": len(pairs),
            "yaw_diff_rmse_deg": yaw_rmse,
            "yaw_diff_mean_deg": _mean(yaw_diffs),
            "yaw_diff_p95_deg": _p95_abs(yaw_diffs),
            "yaw_diff_max_deg": _max_abs(yaw_diffs),
            "yaw_std_diff_mean_deg": _mean(yaw_std_diffs),
            "position_diff_rmse_m": _rmse(position_diffs),
            "velocity_diff_rmse_mps": _rmse(velocity_diffs),
            "outage_pattern_match": _outage_pattern_match(actual_rows, variant_rows),
            "exact_or_near_match_status": status,
            "evidence_status": "compared",
        }
    comparable = [
        (name, report)
        for name, report in variant_reports.items()
        if isinstance(report.get("yaw_diff_rmse_deg"), (int, float))
    ]
    best_name = None
    best_report: dict[str, Any] = {}
    if comparable:
        best_name, best_report = min(comparable, key=lambda item: float(item[1]["yaw_diff_rmse_deg"]))

    safe_rmse = (variant_reports.get("status_safe_no_noise") or {}).get("yaw_diff_rmse_deg")
    gaussian_rmse = (variant_reports.get("status_gaussian_1p5_no_outlier") or {}).get("yaw_diff_rmse_deg")
    legacy_rmse = (variant_reports.get("status_gaussian_1p5_legacy15") or {}).get("yaw_diff_rmse_deg")
    status = "evidence_missing_or_unmodeled_generation"
    if isinstance(safe_rmse, (int, float)) and safe_rmse <= 0.2:
        status = "no_evidence_of_injected_yaw_noise"
    elif isinstance(gaussian_rmse, (int, float)) and gaussian_rmse <= 0.2:
        status = "likely_gaussian_1p5_injected"
    elif isinstance(legacy_rmse, (int, float)) and legacy_rmse <= 0.2:
        status = "likely_gaussian_plus_legacy_outlier"
    elif best_name and best_name.startswith("status_gaussian_1p5_legacy15") and best_report.get("outage_pattern_match"):
        status = "likely_gaussian_plus_legacy_outlier"

    nominal_clean_allowed = status == "no_evidence_of_injected_yaw_noise"
    return {
        "phase": "N4H2F",
        "actual_input_role": "DUAL_FINAL_V23_ARTIFACT_ROOT/input.gnss",
        "variant_reports": variant_reports,
        "best_matching_variant": best_name,
        "best_yaw_diff_rmse_deg": best_report.get("yaw_diff_rmse_deg") if best_report else None,
        "safe_no_noise_yaw_diff_rmse_deg": safe_rmse,
        "gaussian_1p5_yaw_diff_rmse_deg": gaussian_rmse,
        "legacy15_yaw_diff_rmse_deg": legacy_rmse,
        "actual_yaw_noise_injection_status": status,
        "fixed_yaw_std_1p5_detected": None,
        "yaw_std_is_not_yaw_noise": True,
        "nominal_clean_claim_allowed": nominal_clean_allowed,
        "trace_yaw_diagnostic_only": True,
        "trace_solver_input": False,
        "output_only_correction": False,
        "solver_output_changed": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
        "evidence_missing": [] if comparable else ["variant_inputs"],
    }


def write_actual_input_yaw_variant_match_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
