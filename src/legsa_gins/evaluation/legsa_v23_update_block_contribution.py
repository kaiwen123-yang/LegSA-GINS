"""N4H4D5 update-block contribution diagnostics.

中文说明：分析 position/velocity/yaw MeasurementBlock 对 dx 的诊断贡献；
这些 CSV 只来自 debug output，不作为性能结果。
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


def _stats(values: list[float]) -> dict[str, float | None]:
    clean = [value for value in values if math.isfinite(value)]
    if not clean:
        return {"count": 0, "p95": None, "max": None, "mean": None}
    ordered = sorted(clean)
    p95 = ordered[min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95)))]
    return {"count": len(clean), "p95": p95, "max": max(clean), "mean": sum(clean) / len(clean)}


def _read_csv(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        return list(csv.DictReader(handle))


def analyze_update_block_trace(update_block_trace_csv: str | Path, feedback_delta_trace_csv: str | Path) -> dict[str, Any]:
    """中文说明：定位哪个量测块最容易贡献大 dx_phi 或 feedback 姿态跳变。"""

    rows = _read_csv(update_block_trace_csv)
    by_block: dict[str, list[float]] = {"position": [], "velocity": [], "yaw": []}
    k_by_block: dict[str, list[float]] = {"position": [], "velocity": [], "yaw": []}
    first_block_over_5: dict[str, Any] | None = None
    for row in rows:
        block = row.get("block_type", "unknown")
        phi = _float(row, "dx_delta_phi_norm_deg")
        k_norm = _float(row, "K_norm")
        by_block.setdefault(block, []).append(phi)
        k_by_block.setdefault(block, []).append(k_norm)
        if first_block_over_5 is None and phi > 5.0:
            first_block_over_5 = {
                "update_index": int(_float(row, "update_index")),
                "block_type": block,
                "gnss_time": _float(row, "gnss_time"),
                "dx_delta_phi_norm_deg": phi,
            }
    block_stats = {block: _stats(values) for block, values in by_block.items()}
    k_stats = {block: _stats(values) for block, values in k_by_block.items()}
    worst_block = max(block_stats, key=lambda block: block_stats[block]["p95"] or -1.0) if block_stats else "evidence_missing"
    feedback_rows = _read_csv(feedback_delta_trace_csv)
    feedback_phi = [_float(row, "phi_delta_deg_norm") for row in feedback_rows]
    feedback_roll = [abs(_float(row, "roll_delta")) for row in feedback_rows]
    feedback_pitch = [abs(_float(row, "pitch_delta")) for row in feedback_rows]
    feedback_yaw = [abs(_float(row, "yaw_delta")) for row in feedback_rows]
    reset_ok = all(row.get("dx_reset_after_feedback", "").lower() == "true" for row in feedback_rows) if feedback_rows else False
    return {
        "row_count": len(rows),
        "worst_block_by_dx_phi": worst_block,
        "position_block_dx_phi": block_stats.get("position", _stats([])),
        "velocity_block_dx_phi": block_stats.get("velocity", _stats([])),
        "yaw_block_dx_phi": block_stats.get("yaw", _stats([])),
        "K_norm_by_block": k_stats,
        "blocks_causing_K_norm_gt_threshold": [
            block for block, stats in k_stats.items() if stats["max"] is not None and stats["max"] > 50.0
        ],
        "first_block_causing_dx_phi_gt_5deg": first_block_over_5,
        "feedback_delta_stats": {
            "phi_delta_deg": _stats(feedback_phi),
            "roll_delta_deg": _stats(feedback_roll),
            "pitch_delta_deg": _stats(feedback_pitch),
            "yaw_delta_deg": _stats(feedback_yaw),
        },
        "position_block_overdrives_attitude": bool((block_stats.get("position", {}).get("p95") or 0.0) > 5.0),
        "velocity_block_overdrives_attitude": bool((block_stats.get("velocity", {}).get("p95") or 0.0) > 5.0),
        "yaw_block_overdrives_attitude": bool((block_stats.get("yaw", {}).get("p95") or 0.0) > 5.0),
        "feedback_applies_large_phi": bool((_stats(feedback_phi)["p95"] or 0.0) > 5.0),
        "feedback_reset_ok": reset_ok,
        "no_single_block_dominates": bool(
            len([block for block, stats in block_stats.items() if (stats["p95"] or 0.0) > 5.0]) != 1
        ),
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
