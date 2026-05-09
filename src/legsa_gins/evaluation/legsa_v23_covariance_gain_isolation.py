"""N4H4D5 covariance/gain isolation diagnostics."""

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


def _read(path: str | Path) -> list[dict[str, str]]:
    p = Path(path)
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
        return list(csv.DictReader(handle))


def _stats(values: list[float]) -> dict[str, float | None]:
    clean = [v for v in values if math.isfinite(v)]
    if not clean:
        return {"count": 0, "p95": None, "max": None, "min": None, "mean": None}
    ordered = sorted(clean)
    return {
        "count": len(clean),
        "p95": ordered[min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95)))],
        "max": max(clean),
        "min": min(clean),
        "mean": sum(clean) / len(clean),
    }


def analyze_covariance_gain_trace(cov_trace_csv: str | Path, update_block_trace_csv: str | Path) -> dict[str, Any]:
    """中文说明：检查 P_phi/R/K/dx_phi 的尺度是否驱动反馈过修正。"""

    cov_rows = _read(cov_trace_csv)
    block_rows = _read(update_block_trace_csv)
    update_rows = [row for row in cov_rows if row.get("event_type", "").startswith("update_")]
    p_phi_first = [_float(row, "P_phi_trace") for row in update_rows[:10]]
    k_by_block: dict[str, list[float]] = {}
    dx_by_block: dict[str, list[float]] = {}
    r_by_block: dict[str, list[float]] = {}
    cond_by_block: dict[str, list[float]] = {}
    for row in block_rows:
        block = row.get("block_type", "unknown")
        k_by_block.setdefault(block, []).append(_float(row, "K_norm"))
        dx_by_block.setdefault(block, []).append(_float(row, "dx_delta_phi_norm_deg"))
        r_by_block.setdefault(block, []).append(_float(row, "R_trace"))
        cond_by_block.setdefault(block, []).append(_float(row, "S_condition_estimate"))
    k_stats = {block: _stats(values) for block, values in k_by_block.items()}
    dx_stats = {block: _stats(values) for block, values in dx_by_block.items()}
    r_stats = {block: _stats(values) for block, values in r_by_block.items()}
    min_diag = [_float(row, "cov_min_diag") for row in cov_rows]
    k_values = [_float(row, "K_norm") for row in block_rows]
    dx_values = [_float(row, "dx_delta_phi_norm_deg") for row in block_rows]
    gain_spike = any(value > 50.0 for value in k_values)
    dx_spike = any(value > 5.0 for value in dx_values)
    return {
        "initial_P_traces": cov_rows[0] if cov_rows else {},
        "P_phi_trace_first_10_updates": p_phi_first,
        "P_phi_trace_first_10_updates_stats": _stats(p_phi_first),
        "R_trace_stats_by_block": r_stats,
        "S_condition_estimate_stats_by_block": {block: _stats(values) for block, values in cond_by_block.items()},
        "K_norm_stats_by_block": k_stats,
        "dx_phi_stats_by_block": dx_stats,
        "covariance_min_diag_stats": _stats(min_diag),
        "gain_spike_times": [_float(row, "gnss_time") for row in block_rows if _float(row, "K_norm") > 50.0][:10],
        "dx_phi_spike_times": [_float(row, "gnss_time") for row in block_rows if _float(row, "dx_delta_phi_norm_deg") > 5.0][:10],
        "correlation_K_norm_vs_dx_phi": "positive_if_spikes_overlap" if gain_spike and dx_spike else "weak_or_evidence_missing",
        "attitude_covariance_too_large": bool((_stats(p_phi_first)["max"] or 0.0) > 0.1),
        "measurement_R_too_small": bool(any((stats["min"] or 1.0) < 1.0e-8 for stats in r_stats.values())),
        "gain_spike_drives_feedback": bool(gain_spike and dx_spike),
        "covariance_not_invalid_but_overconfident": bool((_stats(min_diag)["min"] or 0.0) > 0.0 and dx_spike),
        "covariance_model_needs_unit_parity_audit": bool(dx_spike),
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }
