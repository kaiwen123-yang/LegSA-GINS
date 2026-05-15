"""N8H feedback gate visual review.

中文说明：复核 gate 是否过宽或过严，不使用 trace/final_v23 调 gate。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_visual_loader import N8HVisualInputs, PRIMARY_FEEDBACK_VARIANT, safe_float, write_json


def build_gate_review(bundle: N8HVisualInputs) -> dict[str, Any]:
    gate = bundle.reports.get("FGO_FEEDBACK_GATE_REPORT.json", {})
    thresholds = gate.get("gate_thresholds", {})
    stats_report = gate.get("correction_norm_stats", {})
    rows = bundle.update_trace_by_variant.get(PRIMARY_FEEDBACK_VARIANT, [])
    accept_count = int(gate.get("accept_count", 0) or 0)
    reject_count = int(gate.get("reject_count", 0) or 0)
    feedback_count = int(gate.get("feedback_count", accept_count + reject_count) or 0)
    near_cap = {
        "velocity_near_cap_count": _near_cap_count(rows, "velocity_norm_mps", safe_float(thresholds.get("max_velocity_correction_mps")), 0.8),
        "attitude_near_cap_count": _near_cap_count(rows, "attitude_norm_deg", safe_float(thresholds.get("max_attitude_correction_deg")), 0.8),
        "yaw_near_cap_count": _near_cap_count(rows, "yaw_residual_deg", safe_float(thresholds.get("max_yaw_correction_deg")), 0.8, absolute=True),
    }
    classification = _classify_gate(
        accept_count=accept_count,
        reject_count=reject_count,
        feedback_count=feedback_count,
        correction_stats=stats_report,
        thresholds=thresholds,
        near_cap_counts=near_cap,
    )
    return {
        "stage": "N8H",
        "classification": classification,
        "accepted": accept_count,
        "rejected": reject_count,
        "feedback_count": feedback_count,
        "reject_reasons": gate.get("reject_reasons", {}),
        "all_feedback_accepted": feedback_count > 0 and accept_count == feedback_count,
        "correction_norm_stats": stats_report,
        "gate_thresholds": thresholds,
        "near_cap_counts": near_cap,
        "window_size_s": bundle.reports.get("SLIDING_WINDOW_MANAGER_REPORT.json", {}).get("window_duration_s"),
        "window_count": bundle.reports.get("SLIDING_WINDOW_MANAGER_REPORT.json", {}).get("window_count"),
        "epoch_count_range": {
            "min": bundle.reports.get("SLIDING_WINDOW_MANAGER_REPORT.json", {}).get("overlap_stats", {}).get("min_epoch_count", 0),
            "max": bundle.reports.get("SLIDING_WINDOW_MANAGER_REPORT.json", {}).get("overlap_stats", {}).get("max_epoch_count", 0),
        },
        "position_correction_source": "residual_proxy_only_for_primary_position_disabled",
        "solver_residual_proxy": "conservative_residual_proxy",
        "review_notes": _review_notes(classification),
        "no_trace_tuning": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def _near_cap_count(rows: list[dict[str, Any]], key: str, limit: float, ratio: float, *, absolute: bool = False) -> int:
    if limit <= 0.0:
        return 0
    count = 0
    for row in rows:
        value = safe_float(row.get(key))
        if absolute:
            value = abs(value)
        if value >= limit * ratio:
            count += 1
    return count


def _ratio(stats_report: dict[str, Any], block: str, stat: str, thresholds: dict[str, Any], threshold_key: str) -> float:
    threshold = safe_float(thresholds.get(threshold_key))
    if threshold <= 0.0:
        return 0.0
    return safe_float(stats_report.get(block, {}).get(stat)) / threshold


def _classify_gate(
    *,
    accept_count: int,
    reject_count: int,
    feedback_count: int,
    correction_stats: dict[str, Any],
    thresholds: dict[str, Any],
    near_cap_counts: dict[str, int],
) -> str:
    if feedback_count <= 0:
        return "gate_needs_N8H2_policy_review"
    if reject_count > accept_count:
        return "gate_too_strict_suspect"
    attitude_p95_ratio = _ratio(correction_stats, "attitude_deg", "p95", thresholds, "max_attitude_correction_deg")
    attitude_max_ratio = _ratio(correction_stats, "attitude_deg", "max", thresholds, "max_attitude_correction_deg")
    velocity_p95_ratio = _ratio(correction_stats, "velocity_mps", "p95", thresholds, "max_velocity_correction_mps")
    near_cap_total = sum(near_cap_counts.values())
    if accept_count == feedback_count and (attitude_p95_ratio >= 0.75 or velocity_p95_ratio >= 0.75 or near_cap_total > max(3, feedback_count // 20)):
        return "gate_too_loose_suspect"
    if attitude_max_ratio >= 0.9:
        return "gate_needs_N8H2_policy_review"
    return "gate_reasonable"


def _review_notes(classification: str) -> list[str]:
    if classification == "gate_reasonable":
        return ["all accepted, but observed correction norms remain below configured caps"]
    if classification == "gate_too_loose_suspect":
        return ["all accepted and correction norms approach cap often enough to require policy review"]
    if classification == "gate_too_strict_suspect":
        return ["rejections dominate accepted feedback updates"]
    return ["manual N8H2 gate-policy review is required"]


def write_gate_review(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
