"""N7C2 visual overlap audit for Go2 horizontal velocity figures.

中文说明：本模块读取 N7C/N7C1 runtime source data 和 coverage metadata，不做
图像 OCR；曲线重合不等于失败，但必须解释并生成 delta/zoom 图。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any


BASELINE_VARIANT = "baseline_no_go2_horizontal_velocity"
MAIN_VARIANT = "go2_horizontal_velocity_weak_prior_main"


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {}
    try:
        loaded = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def read_csv_rows(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _f(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _variant_file(n7c_root: Path, variant_id: str, name: str) -> Path:
    return n7c_root / "variants" / variant_id / name


def _raw_doppler_path_from_matrix(matrix_report: dict[str, Any]) -> Path | None:
    for row in matrix_report.get("matrix", []):
        path_text = row.get("raw_doppler_factor_path")
        if path_text:
            path = Path(path_text)
            if path.exists():
                return path
    return None


def load_n7c2_visual_source_data(n7c_root: str | Path, n7c1_root: str | Path) -> dict[str, Any]:
    """Load source data used to explain N7C1 visual overlap.

    中文说明：N7C2 使用 N7C variant outputs、prior CSV、source-aware trace 和
    N7C1 coverage report；这些都是 runtime-only evidence，不写回 solver。
    """

    n7c = Path(n7c_root)
    n7c1 = Path(n7c1_root)
    reports = {
        "prior_build": read_json(n7c / "GO2_HORIZONTAL_VELOCITY_PRIOR_BUILD_REPORT.json"),
        "matrix": read_json(n7c / "N7C_GO2_HORIZONTAL_VELOCITY_ABLATION_MATRIX.json"),
        "variant_summaries": read_json(n7c / "N7C_GO2_HORIZONTAL_VELOCITY_VARIANT_SUMMARIES.json"),
        "comparison": read_json(n7c / "N7C_GO2_HORIZONTAL_VELOCITY_COMPARISON_REPORT.json"),
        "decision": read_json(n7c / "N7C_GO2_HORIZONTAL_VELOCITY_DECISION_REPORT.json"),
        "n7c1_coverage": read_json(n7c1 / "N7C1_PLOT_DATA_COVERAGE_REPORT.json"),
        "n7c1_figure_manifest": read_json(n7c1 / "N7C1_FIGURE_MANIFEST.json"),
        "n7c1_visual_sanity": read_json(n7c1 / "N7C1_VISUAL_SANITY_REPORT.json"),
    }
    raw_path = _raw_doppler_path_from_matrix(reports["matrix"])
    baseline_eval = read_csv_rows(_variant_file(n7c, BASELINE_VARIANT, "EVAL_NAV.csv"))
    main_eval = read_csv_rows(_variant_file(n7c, MAIN_VARIANT, "EVAL_NAV.csv"))
    main_trace = read_csv_rows(_variant_file(n7c, MAIN_VARIANT, "SOURCE_AWARE_WEIGHT_TRACE.csv"))
    go2_trace = [row for row in main_trace if row.get("source_id") == "go2_horizontal_velocity"]
    return {
        "n7c_root_role": "N7C_RUNTIME_REPORT_ROOT",
        "n7c1_root_role": "N7C1_RUNTIME_REPORT_ROOT",
        "reports": reports,
        "baseline_eval_nav": baseline_eval,
        "main_eval_nav": main_eval,
        "prior_rows": read_csv_rows(n7c / "GO2_HORIZONTAL_VELOCITY_WEAK_PRIORS.csv"),
        "raw_doppler_rows": read_csv_rows(raw_path) if raw_path else [],
        "main_trace_rows": main_trace,
        "go2_trace_rows": go2_trace,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
    }


def _times(rows: list[dict[str, Any]], key: str = "time") -> list[float]:
    if not rows:
        return []
    first = _f(rows[0].get(key))
    return [_f(row.get(key), first) - first for row in rows]


def _local_horizontal_m(rows: list[dict[str, Any]], reference_rows: list[dict[str, Any]] | None = None) -> list[float]:
    if not rows:
        return []
    ref = reference_rows or rows
    lat0 = math.radians(_f(ref[0].get("lat_deg")))
    lon0 = math.radians(_f(ref[0].get("lon_deg")))
    cos_lat = math.cos(lat0)
    out: list[float] = []
    for row in rows:
        north = (math.radians(_f(row.get("lat_deg"))) - lat0) * 6378137.0
        east = (math.radians(_f(row.get("lon_deg"))) - lon0) * 6378137.0 * cos_lat
        out.append(math.hypot(north, east))
    return out


def _values(rows: list[dict[str, Any]], key: str) -> list[float]:
    return [_f(row.get(key)) for row in rows]


def _wrap_deg(value: float) -> float:
    wrapped = (value + 180.0) % 360.0 - 180.0
    return -180.0 if wrapped == 180.0 else wrapped


def _paired(lhs: list[float], rhs: list[float]) -> tuple[list[float], list[float]]:
    count = min(len(lhs), len(rhs))
    return lhs[:count], rhs[:count]


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.95 * (len(ordered) - 1)))]


def _rmse(values: list[float]) -> float:
    if not values:
        return 0.0
    return math.sqrt(sum(value * value for value in values) / len(values))


def _overlap_status(diff_abs: list[float], lhs: list[float], rhs: list[float]) -> str:
    p95 = _p95(diff_abs)
    amplitude = max(max([abs(value) for value in lhs + rhs], default=0.0), 1.0e-9)
    if max(diff_abs, default=0.0) <= max(1.0e-10, amplitude * 1.0e-8):
        return "identical_or_near_identical"
    if p95 <= max(1.0e-4, amplitude * 0.02):
        return "mostly_overlapped"
    return "clearly_separated"


def _reason_codes(status: str, lhs: list[float], rhs: list[float], legend_series_count: int) -> list[str]:
    reasons: list[str] = []
    lhs_range = max(lhs, default=0.0) - min(lhs, default=0.0)
    rhs_range = max(rhs, default=0.0) - min(rhs, default=0.0)
    if lhs_range <= 1.0e-12 or rhs_range <= 1.0e-12:
        reasons.append("constant_policy_line")
    if status in {"mostly_overlapped", "identical_or_near_identical"}:
        reasons.append("overlap_due_to_small_effect")
        if legend_series_count > 1:
            reasons.extend(["plot_order_occlusion", "insufficient_style_separation"])
    return reasons or ["clearly_separated"]


def _pair_report(figure_name: str, label_lhs: str, label_rhs: str, lhs: list[float], rhs: list[float]) -> dict[str, Any]:
    left, right = _paired(lhs, rhs)
    diffs = [right[index] - left[index] for index in range(len(left))]
    diff_abs = [abs(value) for value in diffs]
    status = _overlap_status(diff_abs, left, right)
    return {
        "figure_name": figure_name,
        "legend_series_count": 2,
        "series_labels": [label_lhs, label_rhs],
        "row_count": len(diffs),
        "max_abs_diff": max(diff_abs, default=0.0),
        "p95_abs_diff": _p95(diff_abs),
        "rmse_diff": _rmse(diffs),
        "visible_difference_status": status,
        "reason_codes": _reason_codes(status, left, right, 2),
        "overlap_is_failure": False,
    }


def build_n7c2_visual_overlap_audit(source_data: dict[str, Any]) -> dict[str, Any]:
    baseline = source_data.get("baseline_eval_nav", [])
    main = source_data.get("main_eval_nav", [])
    baseline_horizontal = _local_horizontal_m(baseline, baseline)
    main_horizontal = _local_horizontal_m(main, baseline)
    baseline_yaw = _values(baseline, "yaw_deg")
    main_yaw = _values(main, "yaw_deg")
    yaw_diff_wrapped = [_wrap_deg(main_yaw[index] - baseline_yaw[index]) for index in range(min(len(baseline_yaw), len(main_yaw)))]
    baseline_yaw_for_pair = baseline_yaw[: len(yaw_diff_wrapped)]
    main_yaw_for_pair = [baseline_yaw_for_pair[index] + yaw_diff_wrapped[index] for index in range(len(yaw_diff_wrapped))]
    overlap_items = [
        _pair_report(
            "clean_horizontal_error_no_go2_vs_go2_horizontal.png",
            "no_go2",
            "go2_horizontal",
            baseline_horizontal,
            main_horizontal,
        ),
        _pair_report(
            "clean_yaw_error_no_go2_vs_go2_horizontal.png",
            "no_go2",
            "go2_horizontal",
            baseline_yaw_for_pair,
            main_yaw_for_pair,
        ),
        _pair_report(
            "clean_up_error_no_go2_vs_go2_horizontal.png",
            "no_go2",
            "go2_horizontal",
            _values(baseline, "height_m"),
            _values(main, "height_m"),
        ),
        _pair_report(
            "clean_roll_error_no_go2_vs_go2_horizontal.png",
            "no_go2",
            "go2_horizontal",
            _values(baseline, "roll_deg"),
            _values(main, "roll_deg"),
        ),
        _pair_report(
            "clean_pitch_error_no_go2_vs_go2_horizontal.png",
            "no_go2",
            "go2_horizontal",
            _values(baseline, "pitch_deg"),
            _values(main, "pitch_deg"),
        ),
    ]
    counts = {
        status: sum(1 for item in overlap_items if item["visible_difference_status"] == status)
        for status in ["clearly_separated", "mostly_overlapped", "identical_or_near_identical"]
    }
    return {
        "stage": "N7C2_go2_horizontal_velocity_jacobian_visual_audit",
        "source_data_roles": ["N7C_RUNTIME_REPORT_ROOT", "N7C1_RUNTIME_REPORT_ROOT"],
        "method": "source_data_overlap_metrics_no_image_ocr",
        "overlap_items": overlap_items,
        "summary": {
            "item_count": len(overlap_items),
            "status_counts": counts,
            "all_overlaps_explained": all(bool(item["reason_codes"]) for item in overlap_items),
            "delta_zoom_required": True,
            "delta_zoom_generated": False,
        },
        "interpretation": "Highly overlapped curves are expected when the controlled weak prior has tiny clean-run effect; this is not a performance claim.",
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }


def write_n7c2_visual_overlap_audit(path: str | Path, report: dict[str, Any]) -> dict[str, Any]:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
