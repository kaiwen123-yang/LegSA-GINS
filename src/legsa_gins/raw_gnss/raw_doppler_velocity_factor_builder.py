"""Build the final EKF raw Doppler velocity factor CSV for N5B.

中文说明：最终 factor CSV 只含 Doppler-derived velocity，不含 RTKLIB position
solution，也不使用 NAV-PVT velocity 或 .gnss vn/ve/vd。
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

from .rtklib_solution_velocity_parser import VELOCITY_FACTOR_FIELDS, read_clean_gnss_position_and_times


def _float(value: Any, fallback: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return fallback
    return out if math.isfinite(out) else fallback


def _read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _time_range(rows: list[dict[str, str]], key: str = "time") -> tuple[float, float] | None:
    values = [_float(row.get(key), math.nan) for row in rows]
    finite = [value for value in values if math.isfinite(value)]
    return (min(finite), max(finite)) if finite else None


def _overlaps(a: tuple[float, float], b: tuple[float, float], tolerance: float = 1.0) -> bool:
    return a[0] <= b[1] + tolerance and b[0] <= a[1] + tolerance


def build_factor_file_from_provider(
    provider_csv: str | Path,
    output_dir: str | Path,
    *,
    clean_gnss_path: str | Path | None = None,
    source_type: str = "rtklib_doppler_helper_velocity",
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    provider_path = Path(provider_csv)
    final_csv = out / "RAW_DOPPLER_VELOCITY_FACTORS.csv"
    blockers: list[str] = []
    if source_type in {"nav_pvt_velocity", "gnss_15col_velocity", "receiver_native_velocity"}:
        blockers.append(f"forbidden_source_{source_type}")
    rows = _read_rows(provider_path)
    if not rows:
        blockers.append("provider_csv_missing_or_empty")
    valid_rows: list[dict[str, str]] = []
    for row in rows:
        stds = [_float(row.get("std_vn")), _float(row.get("std_ve")), _float(row.get("std_vd"))]
        values = [_float(row.get("vn")), _float(row.get("ve")), _float(row.get("vd"))]
        if row.get("provider_status") != "available":
            continue
        if min(stds) <= 0.0 or not all(math.isfinite(value) for value in stds + values):
            continue
        valid_rows.append({field: row.get(field, "") for field in VELOCITY_FACTOR_FIELDS})
    if not valid_rows:
        blockers.append("no_valid_provider_rows")

    time_alignment_policy = "provider_time_used_directly"
    time_offset_sec = 0.0
    clean_range: tuple[float, float] | None = None
    provider_range = _time_range(valid_rows, "time") if valid_rows else None
    if clean_gnss_path:
        clean = read_clean_gnss_position_and_times(clean_gnss_path)
        clean_times = clean.get("times", [])
        if clean_times:
            clean_range = (min(clean_times), max(clean_times))
            if provider_range and not _overlaps(provider_range, clean_range):
                time_offset_sec = provider_range[0] - clean_range[0]
                time_alignment_policy = "first_epoch_offset_to_clean_gnss_time_only"
                for row in valid_rows:
                    source_time = _float(row.get("source_epoch_time", row.get("time")))
                    row["time"] = f"{source_time - time_offset_sec:.9f}"
                provider_range = _time_range(valid_rows, "time")
        else:
            blockers.append("clean_gnss_time_reference_missing")
    if clean_range and provider_range and not _overlaps(provider_range, clean_range):
        blockers.append("factor_time_does_not_overlap_clean_replay")

    activation_allowed = bool(valid_rows) and not blockers
    if activation_allowed:
        with final_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=VELOCITY_FACTOR_FIELDS)
            writer.writeheader()
            writer.writerows(valid_rows)
    sat_counts = sorted(int(float(row.get("sat_count", "0"))) for row in valid_rows)
    return {
        "factor_csv_generated": activation_allowed,
        "factor_csv_path": str(final_csv) if activation_allowed else "",
        "factor_epoch_count": len(rows),
        "factor_valid_epoch_count": len(valid_rows),
        "sat_count_min": sat_counts[0] if sat_counts else 0,
        "sat_count_median": sat_counts[len(sat_counts) // 2] if sat_counts else 0,
        "sat_count_max": sat_counts[-1] if sat_counts else 0,
        "time_alignment_policy": time_alignment_policy,
        "time_offset_sec": time_offset_sec,
        "clean_replay_time_range": clean_range,
        "factor_time_range": provider_range,
        "raw_doppler_solver_activation_allowed": activation_allowed,
        "not_sourced_from_nav_pvt": source_type != "nav_pvt_velocity",
        "not_sourced_from_gnss_15col_velocity": source_type != "gnss_15col_velocity",
        "rtklib_position_solution_used_as_solver_input": False,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "blocker_reasons": sorted(set(blockers)),
    }
