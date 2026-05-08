"""Coverage report for process_data-compatible GNSS row retention.

中文说明：本模块只检查 input reconstruction 的行覆盖闭合度，不通过删除
status rows 或放宽阈值来制造通过结论。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return float(numerator) / float(denominator)


def make_process_data_coverage_report(
    *,
    status_base_row_count: int,
    pvt_velocity_row_count: int,
    yaw_row_count: int,
    gnss_output_row_count: int,
    pvt_merge_match_count_before_fill: int,
    yaw_merge_match_count_before_fill: int,
    dropna_count: int,
    pvt_missing_after_fill_count: int = 0,
    yaw_missing_after_fill_count: int = 0,
) -> dict[str, Any]:
    output_to_status_ratio = _ratio(gnss_output_row_count, status_base_row_count)
    output_to_yaw_ratio = _ratio(gnss_output_row_count, yaw_row_count)
    if output_to_status_ratio is None:
        coverage_status = "failed"
    elif output_to_status_ratio >= 0.8:
        coverage_status = "passed"
    elif output_to_status_ratio >= 0.2:
        coverage_status = "suspicious"
    else:
        coverage_status = "failed"
    coverage_warning = None
    if coverage_status != "passed":
        coverage_warning = (
            "coverage_suspicious: GNSS output rows are materially below the "
            "gnss1-status base table; do not claim row-retention parity."
        )
    return {
        "phase": "N4H1P2",
        "status_base_row_count": int(status_base_row_count),
        "pvt_velocity_row_count": int(pvt_velocity_row_count),
        "yaw_row_count": int(yaw_row_count),
        "gnss_output_row_count": int(gnss_output_row_count),
        "output_to_status_ratio": output_to_status_ratio,
        "output_to_yaw_ratio": output_to_yaw_ratio,
        "pvt_merge_match_count_before_fill": int(pvt_merge_match_count_before_fill),
        "yaw_merge_match_count_before_fill": int(yaw_merge_match_count_before_fill),
        "pvt_missing_after_fill_count": int(pvt_missing_after_fill_count),
        "yaw_missing_after_fill_count": int(yaw_missing_after_fill_count),
        "dropna_count": int(dropna_count),
        "coverage_status": coverage_status,
        "coverage_warning": coverage_warning,
        "evidence_status": "process_data_row_retention_audited",
    }


def validate_process_data_coverage_report(report: dict[str, Any]) -> bool:
    required = [
        "status_base_row_count",
        "pvt_velocity_row_count",
        "yaw_row_count",
        "gnss_output_row_count",
        "output_to_status_ratio",
        "output_to_yaw_ratio",
        "pvt_merge_match_count_before_fill",
        "yaw_merge_match_count_before_fill",
        "dropna_count",
        "coverage_status",
        "coverage_warning",
        "evidence_status",
    ]
    missing = [field for field in required if field not in report]
    if missing:
        raise ValueError(f"Coverage report missing fields: {missing}")
    if report["coverage_status"] not in {"passed", "suspicious", "failed"}:
        raise ValueError(f"Unsupported coverage_status: {report['coverage_status']}")
    ratio = report.get("output_to_status_ratio")
    if ratio is not None and ratio < 0.0:
        raise ValueError("output_to_status_ratio must be non-negative.")
    return True


def write_process_data_coverage_report(report: dict[str, Any], output_path: str | Path) -> None:
    validate_process_data_coverage_report(report)
    path = Path(output_path)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
