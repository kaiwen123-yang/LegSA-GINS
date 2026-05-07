"""BY2 time-domain audit helpers.

中文说明：本模块只判断时间字段外观和可比较性，不估计物理 clock offset。
"""

from __future__ import annotations

import csv
import statistics
from pathlib import Path
from typing import Any


class TimeDomainType:
    UNIX_EPOCH_LIKE = "UNIX_EPOCH_LIKE"
    GPS_TOW_LIKE = "GPS_TOW_LIKE"
    RELATIVE_BOOT_OR_LOCAL = "RELATIVE_BOOT_OR_LOCAL"
    UNKNOWN = "UNKNOWN"


def _as_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _read_values(path: str | Path, field: str) -> list[float]:
    values: list[float] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            value = _as_float(row.get(field))
            if value is not None:
                values.append(value)
    return values


def _monotonic(values: list[float]) -> bool:
    return all(cur >= prev for prev, cur in zip(values, values[1:]))


def infer_time_domain(values: list[float]) -> dict[str, Any]:
    clean = [value for value in values if value is not None]
    if not clean:
        return {
            "time_domain": TimeDomainType.UNKNOWN,
            "count": 0,
            "median": None,
            "min": None,
            "max": None,
            "monotonic": False,
        }
    median = statistics.median(clean)
    monotonic = _monotonic(clean)
    if median > 1.0e9:
        domain = TimeDomainType.UNIX_EPOCH_LIKE
    elif 0.0 <= median <= 604800.0:
        domain = TimeDomainType.GPS_TOW_LIKE
    elif median < 1.0e7 and monotonic:
        domain = TimeDomainType.RELATIVE_BOOT_OR_LOCAL
    else:
        domain = TimeDomainType.UNKNOWN
    return {
        "time_domain": domain,
        "count": len(clean),
        "median": median,
        "min": min(clean),
        "max": max(clean),
        "monotonic": monotonic,
    }


def _reasonable_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("min") is None or right.get("min") is None:
        return False
    overlap_start = max(float(left["min"]), float(right["min"]))
    overlap_end = min(float(left["max"]), float(right["max"]))
    return overlap_end > overlap_start


def audit_by2_time_domains(
    go2_body_state_csv: str | Path,
    gnss_status_csv: str | Path,
    trace_csv: str | Path | None = None,
) -> dict[str, Any]:
    go2_field = "timestamp"
    gnss_field = "time_unix"
    trace_field = "timestamp"
    go2 = infer_time_domain(_read_values(go2_body_state_csv, go2_field))
    gnss = infer_time_domain(_read_values(gnss_status_csv, gnss_field))
    trace = infer_time_domain(_read_values(trace_csv, trace_field)) if trace_csv else {
        "time_domain": TimeDomainType.UNKNOWN,
        "count": 0,
        "median": None,
        "min": None,
        "max": None,
        "monotonic": False,
    }
    direct_allowed = (
        go2["time_domain"] == TimeDomainType.UNIX_EPOCH_LIKE
        and gnss["time_domain"] == TimeDomainType.UNIX_EPOCH_LIKE
        and _reasonable_overlap(go2, gnss)
    )
    return {
        "go2_raw_time_domain": go2["time_domain"],
        "gnss_time_domain": gnss["time_domain"],
        "trace_time_domain": trace["time_domain"],
        "go2_time_field": go2_field,
        "gnss_time_field": gnss_field,
        "trace_time_field": trace_field if trace_csv else None,
        "go2_time_summary": go2,
        "gnss_time_summary": gnss,
        "trace_time_summary": trace,
        "direct_time_comparison_allowed": bool(direct_allowed),
        "clock_sync_claim": False,
        "physical_time_offset_claim": False,
        "event_normalized_time_axis": True,
        "trace_used_for_alignment": False,
        "trace_solver_input": False,
        "evidence_status": "time_domain_audited_no_clock_sync_claim"
        if go2["count"] and gnss["count"]
        else "evidence_missing",
    }

