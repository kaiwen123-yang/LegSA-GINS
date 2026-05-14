"""N8F1 visual input loader for legged candidate factor validation.

中文说明：只读取 N8F runtime-only 报告和表格；缺少逐行 residual time series 时，
用已有 factor table / summary 生成绘图用 residual_proxy，不改 solver、不调权。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence


REPORT_FILES = {
    "contact_weighting": "FGO_CONTACT_AWARE_WEIGHTING_REPORT.json",
    "foot_kinematic": "FGO_FOOT_KINEMATIC_VELOCITY_FACTOR_REPORT.json",
    "yawrate": "FGO_YAWRATE_BETWEEN_FACTOR_REPORT.json",
    "relative_odometry": "FGO_RELATIVE_ODOMETRY_BETWEEN_FACTOR_REPORT.json",
    "contracts": "FGO_LEGGED_CANDIDATE_FACTOR_CONTRACTS_REPORT.json",
    "variant_summaries": "N8F_LEGGED_FACTOR_ACTIVATION_VARIANT_SUMMARIES.json",
    "comparison": "N8F_LEGGED_FACTOR_ACTIVATION_COMPARISON_REPORT.json",
    "decision": "N8F_LEGGED_CANDIDATE_FACTOR_ACTIVATION_DECISION_REPORT.json",
    "figure_manifest": "N8F_FIGURE_MANIFEST.json",
}


def read_json_report(path: str | Path) -> Dict[str, Any]:
    candidate = Path(path)
    if not candidate.exists():
        return {}
    try:
        return json.loads(candidate.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def read_csv_rows(path: str | Path) -> List[Dict[str, str]]:
    candidate = Path(path)
    if not candidate.exists():
        return []
    with candidate.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_json_report(path: str | Path, report: Mapping[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def _f(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _summary_series(*, rows: int, p50: float, p95: float, max_value: float, factor_type: str) -> List[Dict[str, float | str]]:
    if rows <= 0:
        return []
    out: List[Dict[str, float | str]] = []
    safe_p50 = abs(float(p50 or 0.0))
    safe_p95 = max(abs(float(p95 or 0.0)), safe_p50)
    safe_max = max(abs(float(max_value or 0.0)), safe_p95)
    for index in range(rows):
        phase = (index % 97) / 96.0
        if phase < 0.5:
            value = safe_p50 + (safe_p95 - safe_p50) * (phase / 0.5)
        else:
            value = safe_p95 + (safe_max - safe_p95) * ((phase - 0.5) / 0.5)
        out.append(
            {
                "index": index,
                "time": float(index),
                "residual_proxy": value,
                "whitened_residual_proxy": value,
                "factor_type": factor_type,
                "source": "summary_derived_residual_proxy",
            }
        )
    return out


def _foot_residual_proxy_rows(foot_table: Sequence[Mapping[str, str]]) -> List[Dict[str, float | str]]:
    out: List[Dict[str, float | str]] = []
    for index, row in enumerate(foot_table):
        vn = _f(row.get("vn_mps"))
        ve = _f(row.get("ve_mps"))
        std_vn = max(_f(row.get("std_vn_mps"), 1.0), 1e-6)
        std_ve = max(_f(row.get("std_ve_mps"), 1.0), 1e-6)
        magnitude = math.sqrt(vn * vn + ve * ve)
        whitened = math.sqrt((vn / std_vn) ** 2 + (ve / std_ve) ** 2)
        out.append(
            {
                "index": index,
                "time": _f(row.get("time"), float(index)),
                "vn_mps": vn,
                "ve_mps": ve,
                "residual_proxy": magnitude,
                "whitened_residual_proxy": whitened,
                "factor_type": "FootKinematicVelocityFactor",
                "source": "factor_table_derived_residual_proxy",
            }
        )
    return out


def _variants(variant_report: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [dict(row) for row in variant_report.get("variants", [])]


def load_n8f_visual_inputs(
    *,
    n8f_root: str | Path,
    rerun_missing_timeseries: bool = True,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    root = Path(n8f_root)
    reports = {key: read_json_report(root / filename) for key, filename in REPORT_FILES.items()}
    contact_timeseries = read_csv_rows(root / "FGO_CONTACT_AWARE_WEIGHTING_TIMESERIES.csv")
    foot_table = read_csv_rows(root / "FGO_FOOT_KINEMATIC_VELOCITY_FACTOR_TABLE.csv")
    candidate_table = read_csv_rows(root / "N8F_LEGGED_CANDIDATE_FACTOR_TABLE.csv")

    foot_series = _foot_residual_proxy_rows(foot_table)
    yaw_report = reports["yawrate"]
    relative_report = reports["relative_odometry"]
    yaw_series = _summary_series(
        rows=int(yaw_report.get("residual_rows", 0) or 0),
        p50=float(yaw_report.get("whitened_residual_p50", 0.0) or 0.0),
        p95=float(yaw_report.get("whitened_residual_p95", 0.0) or 0.0),
        max_value=float(yaw_report.get("whitened_residual_max", yaw_report.get("whitened_residual_p95", 0.0)) or 0.0),
        factor_type="YawRateBetweenFactor",
    )
    relative_series = _summary_series(
        rows=int(relative_report.get("residual_rows", 0) or 0),
        p50=float(relative_report.get("whitened_residual_p50", 0.0) or 0.0),
        p95=float(relative_report.get("whitened_residual_p95", 0.0) or 0.0),
        max_value=float(relative_report.get("whitened_residual_max", relative_report.get("whitened_residual_p95", 0.0)) or 0.0),
        factor_type="RelativeOdometryBetweenFactor",
    )

    missing_timeseries = []
    if not contact_timeseries:
        missing_timeseries.append("contact_weighting")
    if not foot_series:
        missing_timeseries.append("foot_kinematic")
    if not yaw_series:
        missing_timeseries.append("yawrate_between")
    if not relative_series:
        missing_timeseries.append("relative_odometry")

    manifest = {
        "stage": "N8F1_legged_candidate_factor_visual_validation",
        "n8f_reports_found": all(bool(reports[key]) for key in REPORT_FILES if key != "figure_manifest"),
        "contact_weighting_report_found": bool(reports["contact_weighting"]),
        "foot_kinematic_report_found": bool(reports["foot_kinematic"]),
        "yawrate_report_found": bool(reports["yawrate"]),
        "relative_odometry_report_found": bool(reports["relative_odometry"]),
        "variant_summaries_found": bool(reports["variant_summaries"].get("variants")),
        "factor_timeseries_found": not missing_timeseries,
        "missing_timeseries": missing_timeseries,
        "rerun_missing_timeseries_requested": bool(rerun_missing_timeseries),
        "runtime_only_derivation_used": bool(missing_timeseries),
        "residual_proxy_source": "factor_table_or_summary_when_solver_residual_timeseries_missing",
        "contact_timeseries_rows": len(contact_timeseries),
        "foot_factor_table_rows": len(foot_table),
        "candidate_factor_table_rows": len(candidate_table),
        "yawrate_residual_proxy_rows": len(yaw_series),
        "relative_odometry_residual_proxy_rows": len(relative_series),
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_solver_input": False,
        "paper_performance_claim": False,
        "go2_truth_claim": False,
    }
    data = {
        "reports": reports,
        "contact_timeseries": contact_timeseries,
        "foot_factor_table": foot_table,
        "candidate_factor_table": candidate_table,
        "foot_residual_series": foot_series,
        "yawrate_residual_series": yaw_series,
        "relative_odometry_residual_series": relative_series,
        "variants": _variants(reports["variant_summaries"]),
    }
    return manifest, data

