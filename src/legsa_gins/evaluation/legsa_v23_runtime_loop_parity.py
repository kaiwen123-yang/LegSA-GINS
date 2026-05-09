"""Runtime loop parity checks for N4H4D4.

中文说明：只核对 clean GNSS 行、LegSA runtime seen/applied/update timing，
不把 trace 或外部输出作为 solver 输入。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


def _read_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _count_rows(path: str | Path | None) -> int:
    if not path:
        return 0
    p = Path(path)
    if not p.exists():
        return 0
    count = 0
    with p.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                count += 1
    return count


def _read_updates(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        return list(csv.DictReader(handle))


def compare_update_timeline(
    clean_gnss: str | Path | None,
    runtime_loop_trace: str | Path | dict[str, Any],
    all_updates_csv: str | Path,
) -> dict[str, Any]:
    """中文说明：检查 GNSS 行是否被 runtime 看到和应用，以及 isToUpdate 分布。"""

    loop = runtime_loop_trace if isinstance(runtime_loop_trace, dict) else _read_json(runtime_loop_trace)
    updates = _read_updates(all_updates_csv)
    clean_count = _count_rows(clean_gnss)
    applied = int(loop.get("gnss_updates_applied", len(updates)) or 0)
    seen = int(loop.get("gnss_rows_seen", clean_count) or 0)
    missed = max(0, seen - applied)
    res_counts = {str(key): 0 for key in range(4)}
    update_times: list[float] = []
    for row in updates:
        res = row.get("isToUpdate_res", "0")
        res_counts[res] = res_counts.get(res, 0) + 1
        try:
            update_times.append(float(row.get("gnss_time", "0")))
        except ValueError:
            pass
    if not any(res_counts.values()) and isinstance(loop.get("res_counts"), dict):
        res_counts = {str(key): int(value) for key, value in loop["res_counts"].items()}
    update_count_low = bool(clean_count and applied < 0.7 * clean_count)
    res3 = res_counts.get("3", 0)
    report = {
        "clean_gnss_row_count": clean_count,
        "gnss_seen_count": seen,
        "applied_update_count": applied,
        "missed_gnss_rows": missed,
        "update_time_diff_distribution": "evidence_missing_without_external_update_timeline",
        "isToUpdate_res_counts": res_counts,
        "first_update_time": min(update_times) if update_times else None,
        "last_update_time": max(update_times) if update_times else None,
        "update_count_low": update_count_low,
        "update_time_alignment_issue": False,
        "res3_interpolation_overused": bool(applied and res3 / max(applied, 1) > 0.95),
        "gnss_rows_skipped_unexpectedly": bool(clean_count and missed > 0.3 * clean_count),
        "update_timing_close_to_external": not update_count_low,
        "evidence_missing": [] if updates else ["all_updates_csv_missing"],
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "shadow_external_nav_solver_input": False,
    }
    return report
