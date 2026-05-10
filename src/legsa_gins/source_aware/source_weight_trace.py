"""Read and summarize SOURCE_AWARE_WEIGHT_TRACE.csv.

中文说明：trace 是运行后审计产物，只能用于报告，不允许反向进入权重策略。
"""

from __future__ import annotations

import csv
from pathlib import Path
from statistics import median
from typing import Any

from .measurement_source_types import OBSERVATION_SOURCE_IDS


def read_source_weight_trace(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _float(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[int((len(values) - 1) * q)]


def summarize_source_weight_trace(rows: list[dict[str, Any]]) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    policy_versions = sorted({row.get("policy_version", "") for row in rows if row.get("policy_version")})
    for source_id in OBSERVATION_SOURCE_IDS:
        source_rows = [row for row in rows if row.get("source_id") == source_id]
        scales = [_float(row, "combined_R_scale", 1.0) for row in source_rows]
        rejects = [row for row in source_rows if str(row.get("rejected", "0")).lower() in {"1", "true"}]
        stats[source_id] = {
            "update_count": len(source_rows),
            "reject_count": len(rejects),
            "R_scale_p50": median(scales) if scales else 0.0,
            "R_scale_p95": _percentile(scales, 0.95),
            "R_scale_max": max(scales) if scales else 0.0,
            "R_scale_changed_count": sum(value > 1.0 for value in scales),
        }
    return {
        "trace_row_count": len(rows),
        "sources_covered": sorted({row.get("source_id", "") for row in rows if row.get("source_id")}),
        "policy_versions": policy_versions,
        "used_innovation_covariance_count": sum(
            1 for row in rows if str(row.get("used_innovation_covariance", "0")).lower() in {"1", "true"}
        ),
        "stats_by_source": stats,
        "source_aware_trace_generated": bool(rows),
        "paper_performance_claim": False,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
    }


def write_trace_summary(rows: list[dict[str, Any]], path: str | Path) -> dict[str, Any]:
    report = summarize_source_weight_trace(rows)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    import json

    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
