"""N8C3 Raw Doppler dataset linking.

中文说明：把 N5B runtime-only Raw Doppler 因子 CSV 对齐到 FGO epoch，不复制原始数据。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow
from legsa_gins.fgo.fgo_yaw_convention_fix import _f


RAW_DOPPLER_CSV_CANDIDATES = [
    "RAW_DOPPLER_VELOCITY_FACTORS.csv",
    "RTKLIB_DOPPLER_PROVIDER_VELOCITY.csv",
]


def _read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def find_raw_doppler_factor_csv(n5b_root: str | Path) -> Path | None:
    root = Path(n5b_root)
    for name in RAW_DOPPLER_CSV_CANDIDATES:
        candidate = root / name
        if candidate.exists():
            return candidate
    matches = sorted(root.rglob("*DOPPLER*VELOCITY*.csv"))
    return matches[0] if matches else None


def read_raw_doppler_source_rows(n5b_root: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = find_raw_doppler_factor_csv(n5b_root)
    rows = _read_csv(path) if path else []
    valid = [
        row
        for row in rows
        if math.isfinite(_f(row.get("time"), float("nan")))
        and math.isfinite(_f(row.get("vn", row.get("vn_mps")), float("nan")))
        and math.isfinite(_f(row.get("ve", row.get("ve_mps")), float("nan")))
        and math.isfinite(_f(row.get("vd", row.get("vd_mps")), float("nan")))
    ]
    times = [_f(row.get("time")) for row in valid]
    meta = {
        "source_found": path is not None and bool(rows),
        "source_file_role": "N5B_REPORT_OUTPUT_DIR/RAW_DOPPLER_VELOCITY_FACTORS.csv" if path and path.name == "RAW_DOPPLER_VELOCITY_FACTORS.csv" else "N5B_REPORT_OUTPUT_DIR/raw_doppler_velocity_csv",
        "source_epoch_count": len(rows),
        "source_valid_epoch_count": len(valid),
        "source_time_start": min(times) if times else None,
        "source_time_end": max(times) if times else None,
    }
    return valid, meta


def _nearest_by_time(sorted_rows: list[dict[str, Any]], target_time: float, start_index: int) -> tuple[int, dict[str, Any] | None, float]:
    if not sorted_rows:
        return start_index, None, float("inf")
    index = min(max(start_index, 0), len(sorted_rows) - 1)
    while index + 1 < len(sorted_rows) and _f(sorted_rows[index + 1].get("time")) <= target_time:
        index += 1
    candidates = [index]
    if index + 1 < len(sorted_rows):
        candidates.append(index + 1)
    best_index = min(candidates, key=lambda item: abs(_f(sorted_rows[item].get("time")) - target_time))
    best = sorted_rows[best_index]
    return best_index, best, abs(_f(best.get("time")) - target_time)


def link_raw_doppler_to_fgo_epochs(
    *,
    fgo_rows: list[dict[str, Any]],
    n5b_root: str | Path,
    tolerance_sec: float = 0.25,
) -> tuple[list[RawDopplerVelocityFactorRow], dict[str, Any]]:
    source_rows, meta = read_raw_doppler_source_rows(n5b_root)
    sorted_rows = sorted(source_rows, key=lambda row: _f(row.get("time")))
    factors: list[RawDopplerVelocityFactorRow] = []
    nearest_index = 0
    residual_alignment_errors: list[float] = []
    for state_index, state in enumerate(fgo_rows):
        state_time = _f(state.get("time", state.get("timestamp")), float(state_index))
        nearest_index, source, dt = _nearest_by_time(sorted_rows, state_time, nearest_index)
        if source is None or dt > tolerance_sec:
            continue
        factors.append(
            RawDopplerVelocityFactorRow(
                state_index=state_index,
                time=state_time,
                vn_mps=_f(source.get("vn", source.get("vn_mps"))),
                ve_mps=_f(source.get("ve", source.get("ve_mps"))),
                vd_mps=_f(source.get("vd", source.get("vd_mps"))),
                std_vn_mps=max(_f(source.get("std_vn", source.get("std_vn_mps")), 0.2), 1e-6),
                std_ve_mps=max(_f(source.get("std_ve", source.get("std_ve_mps")), 0.2), 1e-6),
                std_vd_mps=max(_f(source.get("std_vd", source.get("std_vd_mps")), 0.2), 1e-6),
                active=True,
            )
        )
        residual_alignment_errors.append(dt)
    missing_reason = ""
    if not meta.get("source_found"):
        missing_reason = "raw_doppler_source_missing"
    elif not factors:
        missing_reason = "time_alignment_blocker"
    report = {
        "stage": "N8C3_raw_doppler_fgo_factor_fix",
        **meta,
        "fgo_epoch_count": len(fgo_rows),
        "aligned_factor_count": len(factors),
        "alignment_policy": f"nearest_time_within_{tolerance_sec:.3f}s",
        "alignment_tolerance_sec": tolerance_sec,
        "alignment_abs_dt_max": max(residual_alignment_errors) if residual_alignment_errors else None,
        "alignment_abs_dt_p50": sorted(residual_alignment_errors)[len(residual_alignment_errors) // 2] if residual_alignment_errors else None,
        "factor_table_rows": len(factors),
        "factor_table_sample": [factor.to_dict() for factor in factors[:5]],
        "factor_rows_have_time_measurement_std_state_index_type_active": all(
            factor.active and factor.factor_type == "RawDopplerVelocityFactor" for factor in factors
        ),
        "missing_reason": missing_reason,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "no_feedback": True,
    }
    return factors, report


def write_factor_table_runtime_json(path: str | Path, factors: list[RawDopplerVelocityFactorRow]) -> Path:
    """中文说明：仅写 runtime JSON，禁止写 tracked FGO_FACTOR_TABLE.csv。"""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"factor_type": "RawDopplerVelocityFactor", "factor_table_rows": [factor.to_dict() for factor in factors]}
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
