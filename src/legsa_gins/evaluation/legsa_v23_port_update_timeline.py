"""Analyze N4H4R3A port runtime update timeline traces.

中文说明：本模块只读取 runtime-only debug CSV，识别 GNSS 覆盖/陈旧/范围外原因，
不修改 solver 输入输出。
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any


def _as_int(value: str | None) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def analyze_runtime_loop_trace(loop_trace_csv: str | Path, skipped_trace_csv: str | Path | None = None) -> dict[str, Any]:
    res_counts: Counter[str] = Counter()
    update_applied = 0
    refresh_total = 0
    rows = 0
    with Path(loop_trace_csv).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows += 1
            res = str(row.get("isToUpdate_res", ""))
            res_counts[res] += 1
            update_applied += _as_int(row.get("update_applied"))
            refresh = _as_int(row.get("gnss_refresh_count_this_loop"))
            refresh_total += refresh

    skipped_counts: Counter[str] = Counter()
    if skipped_trace_csv and Path(skipped_trace_csv).exists():
        with Path(skipped_trace_csv).open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                skipped_counts[row.get("reason", "unknown")] += 1

    return {
        "phase": "N4H4R3A",
        "runtime_loop_rows": rows,
        "res_counts": dict(res_counts),
        "update_applied_count": update_applied,
        "gnss_refresh_total": refresh_total,
        "overwritten_before_update_count": skipped_counts.get("overwritten_before_update", 0),
        "outside_imu_range_count": skipped_counts.get("outside_imu_range", 0),
        "before_start_count": skipped_counts.get("before_start", 0),
        "after_end_count": skipped_counts.get("after_end", 0),
        "stale_count": skipped_counts.get("stale", 0),
        "skipped_reason_counts": dict(skipped_counts),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }


def detect_overwritten_gnss(loop_report: dict[str, Any]) -> bool:
    return int(loop_report.get("overwritten_before_update_count", 0) or 0) > 0
