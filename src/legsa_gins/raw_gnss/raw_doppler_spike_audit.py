"""N5D1 raw Doppler velocity spike audit.

中文说明：本审计逐历元解释 raw Doppler velocity spike，只报告证据；N5D1 不删除
spike epoch、不调 gate、不把 spike 当作 output-only correction。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.raw_gnss.raw_doppler_visual_loader import (
    load_raw_doppler_factor_rows,
    load_receiver_velocity_rows,
)


def _finite(values: list[float]) -> list[float]:
    return [value for value in values if math.isfinite(value)]


def _percentile(values: list[float], pct: float) -> float | None:
    ordered = sorted(_finite(values))
    if not ordered:
        return None
    index = max(0, min(len(ordered) - 1, math.ceil(pct * len(ordered)) - 1))
    return ordered[index]


def _norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _safe_float(value: Any) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return math.nan
    return out if math.isfinite(out) else math.nan


def _nearest_receiver(raw_time: float, receiver_rows: list[dict[str, float]]) -> tuple[dict[str, float] | None, float | None]:
    if not receiver_rows:
        return None, None
    best = min(receiver_rows, key=lambda row: abs(float(row["time"]) - raw_time))
    return best, raw_time - float(best["time"])


def _component_jump(prev: dict[str, Any] | None, cur: dict[str, Any]) -> dict[str, float]:
    if prev is None:
        return {"vn": 0.0, "ve": 0.0, "vd": 0.0, "norm": 0.0}
    dn = float(cur["vn"]) - float(prev["vn"])
    de = float(cur["ve"]) - float(prev["ve"])
    dd = float(cur["vd"]) - float(prev["vd"])
    return {"vn": dn, "ve": de, "vd": dd, "norm": _norm([dn, de, dd])}


def audit_raw_doppler_spikes(
    *,
    factor_csv: str | Path,
    receiver_velocity_path: str | Path | None = None,
    update_manifest: dict[str, Any] | None = None,
    residual_rows: list[dict[str, Any]] | None = None,
    velocity_jump_threshold_mps: float = 5.0,
    diff_norm_threshold_mps: float = 5.0,
) -> dict[str, Any]:
    """Audit suspicious raw Doppler velocity epochs.

    中文说明：spike_count 对应 N5C 的 suspicious velocity jump 规则；raw-vs-receiver
    diff 仅作为交叉源一致性辅助证据，不把 receiver velocity 当 truth。
    """

    raw_rows = load_raw_doppler_factor_rows(factor_csv)
    receiver_rows = load_receiver_velocity_rows(receiver_velocity_path) if receiver_velocity_path else []
    residual_by_time = {}
    for row in residual_rows or []:
        time_value = _safe_float(row.get("time", row.get("timestamp")))
        if math.isfinite(time_value):
            residual_by_time[round(time_value, 6)] = row
    diff_norms: list[float] = []
    jump_norms: list[float] = []
    enriched: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for raw in raw_rows:
        raw_time = float(raw["time"])
        receiver, dt = _nearest_receiver(raw_time, receiver_rows)
        jump = _component_jump(previous, raw)
        jump_norms.append(float(jump["norm"]))
        if receiver:
            diff_n = float(raw["vn"]) - float(receiver["vn"])
            diff_e = float(raw["ve"]) - float(receiver["ve"])
            diff_d = float(raw["vd"]) - float(receiver["vd"])
            diff_norm = _norm([diff_n, diff_e, diff_d])
        else:
            diff_n = diff_e = diff_d = math.nan
            diff_norm = math.nan
        if math.isfinite(diff_norm):
            diff_norms.append(diff_norm)
        residual = residual_by_time.get(round(raw_time, 6), {})
        enriched.append(
            {
                "time": raw_time,
                "vn": float(raw["vn"]),
                "ve": float(raw["ve"]),
                "vd": float(raw["vd"]),
                "receiver_vn": float(receiver["vn"]) if receiver else None,
                "receiver_ve": float(receiver["ve"]) if receiver else None,
                "receiver_vd": float(receiver["vd"]) if receiver else None,
                "diff_n": diff_n,
                "diff_e": diff_e,
                "diff_d": diff_d,
                "diff_norm": diff_norm,
                "component_jumps": jump,
                "std_vn": float(raw["std_vn"]),
                "std_ve": float(raw["std_ve"]),
                "std_vd": float(raw["std_vd"]),
                "sat_count": int(float(raw.get("sat_count", 0.0) or 0.0)),
                "provider_status": str(raw.get("provider_status", "")),
                "time_diff_to_receiver": dt,
                "residual_norm": residual.get("residual_norm", residual.get("norm")),
            }
        )
        previous = raw

    diff_p99 = _percentile(diff_norms, 0.99)
    jump_p99 = _percentile(jump_norms, 0.99)
    spike_epochs: list[dict[str, Any]] = []
    consistency_outliers: list[dict[str, Any]] = []
    for row in enriched:
        jump_norm = float(row["component_jumps"]["norm"])
        diff_norm = float(row["diff_norm"]) if math.isfinite(float(row["diff_norm"])) else math.nan
        reasons = []
        if jump_norm > velocity_jump_threshold_mps:
            reasons.append("component_jump_gt_threshold")
        if diff_p99 is not None and math.isfinite(diff_norm) and diff_norm > max(diff_norm_threshold_mps, diff_p99):
            reasons.append("raw_minus_receiver_diff_gt_p99_or_threshold")
        primary_spike = jump_norm > velocity_jump_threshold_mps
        if not reasons:
            continue
        # 中文说明：update/reject 状态来自运行 manifest 的全局证据；没有逐历元 trace 时保留 evidence_missing。
        applied: bool | str = "evidence_missing"
        rejected: bool | str = "evidence_missing"
        if update_manifest:
            if int(update_manifest.get("raw_doppler_update_count", 0) or 0) > 0:
                applied = True
            if int(update_manifest.get("raw_doppler_reject_count", 0) or 0) == 0:
                rejected = False
        suggested = "velocity_component_jump"
        if row["time_diff_to_receiver"] is not None and abs(float(row["time_diff_to_receiver"])) > 0.08:
            suggested = "time_alignment_check_needed"
        item = {
            "time": row["time"],
            "vn": row["vn"],
            "ve": row["ve"],
            "vd": row["vd"],
            "receiver_vn": row["receiver_vn"],
            "receiver_ve": row["receiver_ve"],
            "receiver_vd": row["receiver_vd"],
            "diff_norm": row["diff_norm"],
            "component_jumps": row["component_jumps"],
            "std_vn": row["std_vn"],
            "std_ve": row["std_ve"],
            "std_vd": row["std_vd"],
            "sat_count": row["sat_count"],
            "provider_status": row["provider_status"],
            "time_diff_to_receiver": row["time_diff_to_receiver"],
            "raw_doppler_update_applied": applied,
            "residual_norm": row["residual_norm"],
            "rejected": rejected,
            "suggested_reason": suggested,
            "reason_codes": reasons,
        }
        if primary_spike:
            spike_epochs.append(item)
        else:
            consistency_outliers.append(item)

    max_jump = max(jump_norms) if jump_norms else 0.0
    max_diff = max(diff_norms) if diff_norms else None
    high_impact = max_jump > 15.0 or (max_diff is not None and max_diff > 10.0)
    impact = "medium" if spike_epochs else "low"
    if not receiver_rows:
        impact = "evidence_missing"
    elif high_impact:
        impact = "high"
    action = "source_aware_candidate" if spike_epochs else "monitor_only"
    if high_impact:
        action = "gating_needed"
    return {
        "stage": "N5D1_visual_data_coverage_spike_audit",
        "spike_count": len(spike_epochs),
        "spike_epochs": spike_epochs,
        "consistency_outlier_count": len(consistency_outliers),
        "consistency_outlier_epochs": consistency_outliers,
        "max_velocity_jump": max_jump,
        "max_diff_norm": max_diff,
        "diff_norm_p99": diff_p99,
        "velocity_jump_p99": jump_p99,
        "spike_impact_on_EKF": impact,
        "recommended_action": action,
        "receiver_velocity_not_truth": True,
        "raw_doppler_velocity_not_nav_pvt": True,
        "raw_doppler_velocity_not_gnss_15col": True,
        "spike_epochs_removed": False,
        "gate_tuned": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def write_spike_audit_report(path: str | Path, report: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
