"""Compute clean replay IMU/GNSS overlap expectation for N4H4R3A.

中文说明：expected update count 必须来自有效 overlap 里的 GNSS 行，不能直接用
total GNSS row count。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def parse_imu_times(path: str | Path) -> list[float]:
    return _parse_first_column_times(path)


def parse_gnss_times(path: str | Path) -> list[float]:
    return _parse_first_column_times(path)


def _parse_first_column_times(path: str | Path) -> list[float]:
    times: list[float] = []
    with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            try:
                times.append(float(stripped.replace(",", " ").split()[0]))
            except (IndexError, ValueError):
                continue
    return times


def compute_overlap_expectation(
    imu_times: list[float],
    gnss_times: list[float],
    config_start: float,
    config_end: float,
    tolerance_policy: float = 0.001,
) -> dict[str, Any]:
    first_imu = imu_times[0] if imu_times else None
    last_imu = imu_times[-1] if imu_times else None
    first_gnss = gnss_times[0] if gnss_times else None
    last_gnss = gnss_times[-1] if gnss_times else None
    if first_imu is None or last_imu is None or first_gnss is None or last_gnss is None:
        return {
            "evidence_status": "evidence_missing",
            "imu_count": len(imu_times),
            "gnss_count": len(gnss_times),
            "update_count_low": True,
            "paper_performance_claim": False,
            "proposed_factor_claim": False,
            "trace_solver_input": False,
            "final_v23_output_solver_input": False,
            "output_only_correction": False,
            "bad_epoch_deletion_for_metric": False,
        }
    effective_start = max(config_start, first_imu)
    configured_end = config_end if config_end > 0 else min(last_imu, last_gnss)
    effective_end = min(configured_end, last_imu, last_gnss)
    in_overlap = [t for t in gnss_times if effective_start < t <= effective_end + tolerance_policy]
    before_first_imu = [t for t in gnss_times if t <= first_imu]
    after_last_imu = [t for t in gnss_times if t > last_imu]
    outside_config = [t for t in gnss_times if t <= config_start or (config_end > 0 and t > config_end)]
    expected = len(in_overlap)
    return {
        "evidence_status": "diagnostic_overlap_computed",
        "imu_count": len(imu_times),
        "gnss_count": len(gnss_times),
        "first_imu_time": first_imu,
        "last_imu_time": last_imu,
        "first_gnss_time": first_gnss,
        "last_gnss_time": last_gnss,
        "config_start": config_start,
        "config_end": config_end,
        "effective_start": effective_start,
        "effective_end": effective_end,
        "overlap_start": effective_start,
        "overlap_end": effective_end,
        "overlap_duration": effective_end - effective_start,
        "gnss_rows_in_effective_overlap": expected,
        "gnss_rows_in_overlap": expected,
        "gnss_rows_before_first_imu": len(before_first_imu),
        "gnss_rows_after_last_imu": len(after_last_imu),
        "gnss_rows_outside_config": len(outside_config),
        "expected_update_count_min": expected,
        "expected_update_count_max": expected,
        "expected_update_count_policy": "gnss rows inside effective IMU/config overlap",
        "tolerance_policy_sec": tolerance_policy,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }


def classify_update_count(overlap_report: dict[str, Any], actual_update_count: int) -> dict[str, Any]:
    expected_min = int(overlap_report.get("expected_update_count_min", 0) or 0)
    expected_max = int(overlap_report.get("expected_update_count_max", 0) or 0)
    count_low = expected_min > 0 and actual_update_count < 0.8 * expected_min
    matches = expected_min <= actual_update_count <= expected_max if expected_max else False
    return {
        "actual_update_count": actual_update_count,
        "expected_update_count_min": expected_min,
        "expected_update_count_max": expected_max,
        "update_count_matches_overlap_expected": matches,
        "update_count_low": count_low,
        "gnss_rows_skipped_unexpectedly": count_low,
    }
