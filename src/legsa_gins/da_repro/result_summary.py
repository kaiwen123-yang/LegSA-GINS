"""Summaries for DA01 row-level outputs."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .common import percentile, rmse


def method_level_summary(row_results: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = Counter(str(row.get("terminal_status", "")) for row in row_results)
    yaw_values = [
        float(row["yaw_rmse_deg"])
        for row in row_results
        if row.get("yaw_rmse_deg") not in (None, "", "None") and row.get("terminal_status", "").startswith("COMPLETED")
    ]
    return {
        "method_id": "DA01_TEUNISSEN_CLAMBDA",
        "row_count": len(row_results),
        "status_counts": dict(sorted(statuses.items())),
        "completed_rows": sum(count for status, count in statuses.items() if status.startswith("COMPLETED")),
        "full_backend_completed_rows": statuses.get("COMPLETED_EVALUABLE_FULL_BACKEND", 0),
        "diagnostic_fallback_completed_rows": statuses.get("COMPLETED_EVALUABLE_DIAGNOSTIC_FALLBACK", 0),
        "yaw_rmse_mean_deg": sum(yaw_values) / len(yaw_values) if yaw_values else None,
        "yaw_rmse_rmse_deg": rmse(yaw_values),
        "yaw_rmse_p95_deg": percentile(yaw_values, 0.95),
        "trace_used_online": False,
        "status_fallback_is_full_backend": False,
    }


def case_family_summary(row_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in row_results:
        grouped[str(row.get("case_family", ""))].append(row)
    out: list[dict[str, Any]] = []
    for family, rows in sorted(grouped.items()):
        yaw = [
            float(row["yaw_rmse_deg"])
            for row in rows
            if row.get("yaw_rmse_deg") not in (None, "", "None") and row.get("terminal_status", "").startswith("COMPLETED")
        ]
        out.append(
            {
                "case_family": family,
                "row_count": len(rows),
                "completed_rows": sum(1 for row in rows if str(row.get("terminal_status", "")).startswith("COMPLETED")),
                "yaw_rmse_mean_deg": sum(yaw) / len(yaw) if yaw else None,
                "yaw_rmse_p95_deg": percentile(yaw, 0.95),
            }
        )
    return out
