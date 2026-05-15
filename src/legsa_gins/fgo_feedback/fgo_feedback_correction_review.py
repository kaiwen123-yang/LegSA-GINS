"""N8H feedback correction review.

中文说明：只审计 feedback correction 分布，不调参，不替换 EKF NAV。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_visual_loader import (
    N8HVisualInputs,
    PRIMARY_FEEDBACK_VARIANT,
    safe_float,
    safe_int,
    stats,
    write_json,
)


def build_correction_review(bundle: N8HVisualInputs) -> dict[str, Any]:
    variants: list[dict[str, Any]] = []
    top_epochs: list[dict[str, Any]] = []
    for variant_id, rows in bundle.update_trace_by_variant.items():
        summary = bundle.variant_summaries.get(variant_id, {})
        enabled = _enabled_blocks(summary)
        raw_position = [safe_float(row.get("position_norm_m")) for row in rows]
        raw_velocity = [safe_float(row.get("velocity_norm_mps")) for row in rows]
        raw_attitude = [safe_float(row.get("attitude_norm_deg")) for row in rows]
        yaw = [abs(safe_float(row.get("yaw_residual_deg"))) for row in rows]
        applied_position = raw_position if enabled["position"] else [0.0 for _ in rows]
        applied_velocity = raw_velocity if enabled["velocity"] else [0.0 for _ in rows]
        applied_attitude = raw_attitude if enabled["attitude"] else [0.0 for _ in rows]
        variant_report = {
            "variant_id": variant_id,
            "row_count": len(rows),
            "accepted_count_from_trace": sum(1 for row in rows if safe_int(row.get("accepted")) == 1),
            "position_enabled": enabled["position"],
            "velocity_enabled": enabled["velocity"],
            "attitude_enabled": enabled["attitude"],
            "raw_residual_proxy_stats": {
                "position_m": stats(raw_position),
                "velocity_mps": stats(raw_velocity),
                "attitude_deg": stats(raw_attitude),
                "yaw_abs_deg": stats(yaw),
            },
            "applied_correction_stats": {
                "position_m": stats(applied_position),
                "velocity_mps": stats(applied_velocity),
                "attitude_deg": stats(applied_attitude),
                "yaw_abs_deg": stats(yaw if enabled["attitude"] else [0.0 for _ in rows]),
            },
            "spike_counts": {
                "position_raw_over_3m": sum(1 for value in raw_position if value > 3.0),
                "velocity_raw_over_0_75mps": sum(1 for value in raw_velocity if value > 0.75),
                "attitude_raw_over_4deg": sum(1 for value in raw_attitude if value > 4.0),
            },
        }
        variants.append(variant_report)
        for row in rows:
            score = max(
                safe_float(row.get("position_norm_m")),
                safe_float(row.get("velocity_norm_mps")) * 10.0,
                safe_float(row.get("attitude_norm_deg")),
            )
            top_epochs.append(
                {
                    "variant_id": variant_id,
                    "time": safe_float(row.get("update_time", row.get("observation_time"))),
                    "position_norm_m": safe_float(row.get("position_norm_m")),
                    "velocity_norm_mps": safe_float(row.get("velocity_norm_mps")),
                    "attitude_norm_deg": safe_float(row.get("attitude_norm_deg")),
                    "yaw_residual_deg": safe_float(row.get("yaw_residual_deg")),
                    "accepted": safe_int(row.get("accepted")) == 1,
                    "score": score,
                }
            )
    top_epochs = sorted(top_epochs, key=lambda item: item["score"], reverse=True)[:10]
    primary = next((item for item in variants if item["variant_id"] == PRIMARY_FEEDBACK_VARIANT), {})
    return {
        "stage": "N8H",
        "variant_count": len(variants),
        "variants": variants,
        "primary_feedback_variant": PRIMARY_FEEDBACK_VARIANT,
        "primary_correction_stats": primary.get("applied_correction_stats", {}),
        "top_correction_epochs": top_epochs,
        "attitude_correction_spike_count_primary": primary.get("spike_counts", {}).get("attitude_raw_over_4deg", 0),
        "correlation_with_fgo_window_residual": {"available": False, "reason": "residual_norm_series_not_available"},
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def _enabled_blocks(summary: dict[str, Any]) -> dict[str, bool]:
    return {
        "position": bool(summary.get("position_enabled")),
        "velocity": bool(summary.get("velocity_enabled")),
        "attitude": bool(summary.get("attitude_enabled")),
    }


def write_correction_review(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
