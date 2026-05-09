"""N4H4D6 IMU compensation timing diagnostics."""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any


def _float(row: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def _bool(row: dict[str, str], key: str) -> bool:
    return str(row.get(key, "")).lower() == "true"


def _read(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        return list(csv.DictReader(handle))


def _stats(values: list[float]) -> dict[str, float | None]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return {"count": 0, "p95": None, "max": None, "mean": None}
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "p95": ordered[min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95)))],
        "max": max(clean),
        "mean": sum(clean) / len(clean),
    }


def analyze_imu_compensation_timing(trace_csv: str | Path) -> dict[str, Any]:
    """中文说明：检测 IMU 是否重复补偿、未持久补偿或 res=3 插值后补偿状态异常。"""

    rows = _read(trace_csv)
    applied_rows = [row for row in rows if _bool(row, "compensation_applied")]
    propagation_rows = [row for row in rows if not _bool(row, "compensation_applied")]
    repeated = any(_bool(row, "repeated_compensation_detected") or _float(row, "compensation_count_for_current_imu") > 1 for row in rows)
    not_persistent = any(row.get("imucur_compensated", "").lower() == "false" for row in propagation_rows)
    res3_issue = any(
        row.get("imupre_compensated", "").lower() == "false" and _float(row, "imu_dt") > 0.0 for row in propagation_rows
    )
    norm_change = [
        abs(_float(row, "dtheta_norm_after") - _float(row, "dtheta_norm_before"))
        + abs(_float(row, "dvel_norm_after") - _float(row, "dvel_norm_before"))
        for row in applied_rows
    ]
    after_dvel = [_float(row, "dvel_norm_after") for row in applied_rows]
    before_dvel = [_float(row, "dvel_norm_before") for row in applied_rows]
    ratios = [
        after / max(before, 1.0e-12)
        for before, after in zip(before_dvel, after_dvel)
        if math.isfinite(before) and math.isfinite(after)
    ]
    compensation_explosion = bool((_stats(ratios)["max"] or 0.0) > 10.0)
    return {
        "phase": "N4H4D6",
        "row_count": len(rows),
        "applied_row_count": len(applied_rows),
        "propagation_row_count": len(propagation_rows),
        "norm_change_stats": _stats(norm_change),
        "dvel_compensation_ratio_stats": _stats(ratios),
        "repeated_compensation_detected": repeated,
        "compensation_not_persistent_issue": not_persistent,
        "res3_interpolation_compensation_issue": res3_issue,
        "bias_scale_compensation_explosion": compensation_explosion,
        "compensation_timing_ok": bool(rows and not repeated and not not_persistent and not res3_issue and not compensation_explosion),
        "diagnostic_only": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
