"""N4H4D6 IMU error-state feedback diagnostics.

中文说明：本模块只分析 runtime-only 的 IMU_ERROR_FEEDBACK_TRACE.csv，
用于判断 bias/scale 反馈是否和姿态发散耦合；不改 solver，不产生性能结论。
"""

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


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        return list(csv.DictReader(handle))


def _stats(values: list[float]) -> dict[str, float | None]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return {"count": 0, "p50": None, "p95": None, "max": None, "mean": None}
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "p50": ordered[len(ordered) // 2],
        "p95": ordered[min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95)))],
        "max": max(clean),
        "mean": sum(clean) / len(clean),
    }


def analyze_imu_error_feedback(trace_csv: str | Path) -> dict[str, Any]:
    """中文说明：统计 BG/BA/SG/SA 误差反馈大小和是否单调增长。"""

    rows = _read_csv(trace_csv)
    dx_stats = {
        "dx_bg": _stats([_float(row, "dx_bg_norm") for row in rows]),
        "dx_ba": _stats([_float(row, "dx_ba_norm") for row in rows]),
        "dx_sg": _stats([_float(row, "dx_sg_norm") for row in rows]),
        "dx_sa": _stats([_float(row, "dx_sa_norm") for row in rows]),
    }
    norms_after = {
        "gyrbias": [_float(row, "gyrbias_norm_after") for row in rows],
        "accbias": [_float(row, "accbias_norm_after") for row in rows],
        "gyrscale": [_float(row, "gyrscale_norm_after") for row in rows],
        "accscale": [_float(row, "accscale_norm_after") for row in rows],
    }
    norm_stats = {name: _stats(values) for name, values in norms_after.items()}
    first_large: dict[str, Any] | None = None
    for row in rows:
        large_bias = max(_float(row, "dx_bg_norm"), _float(row, "dx_ba_norm"))
        large_scale = max(_float(row, "dx_sg_norm"), _float(row, "dx_sa_norm"))
        if first_large is None and (large_bias > 0.01 or large_scale > 0.01):
            first_large = {
                "update_index": int(_float(row, "update_index")),
                "gnss_time": _float(row, "gnss_time"),
                "dx_bg_norm": _float(row, "dx_bg_norm"),
                "dx_ba_norm": _float(row, "dx_ba_norm"),
                "dx_sg_norm": _float(row, "dx_sg_norm"),
                "dx_sa_norm": _float(row, "dx_sa_norm"),
            }
    monotonic_growth = {
        name: bool(len(values) >= 3 and values[-1] > values[0] and values[-1] >= max(values[: max(1, len(values) // 2)]))
        for name, values in norms_after.items()
    }
    bias_feedback_overcorrection = bool(
        (dx_stats["dx_bg"]["p95"] or 0.0) > 0.01 or (dx_stats["dx_ba"]["p95"] or 0.0) > 0.05
    )
    scale_feedback_overcorrection = bool(
        (dx_stats["dx_sg"]["p95"] or 0.0) > 0.01 or (dx_stats["dx_sa"]["p95"] or 0.0) > 0.01
    )
    primary = bool(bias_feedback_overcorrection or scale_feedback_overcorrection or any(monotonic_growth.values()))
    return {
        "phase": "N4H4D6",
        "row_count": len(rows),
        "dx_stats": dx_stats,
        "bias_scale_norm_after_stats": norm_stats,
        "bias_scale_norm_growth": monotonic_growth,
        "first_large_bias_scale_feedback": first_large,
        "bias_feedback_overcorrection": bias_feedback_overcorrection,
        "scale_feedback_overcorrection": scale_feedback_overcorrection,
        "imu_error_feedback_coupled_with_attitude_divergence": primary,
        "bias_scale_feedback_primary_suspect": primary,
        "diagnostic_only": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }

