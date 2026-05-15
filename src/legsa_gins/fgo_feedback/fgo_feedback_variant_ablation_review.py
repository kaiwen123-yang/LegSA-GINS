"""N8H feedback variant ablation review.

中文说明：审计多 variant 差异和 reject-all sanity，不做性能宣称。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .fgo_feedback_visual_loader import (
    BASELINE_VARIANT,
    N8G_VARIANT_ORDER,
    N8HVisualInputs,
    REJECT_ALL_VARIANT,
    safe_float,
    safe_int,
    stats,
    write_json,
)


def build_variant_ablation_review(bundle: N8HVisualInputs) -> dict[str, Any]:
    variants = [_build_variant_entry(bundle, variant_id) for variant_id in N8G_VARIANT_ORDER if variant_id in bundle.variant_summaries]
    reject_all = next((item for item in variants if item["variant_id"] == REJECT_ALL_VARIANT), {})
    reject_all_sanity_passed = bool(
        reject_all
        and reject_all.get("feedback_accept_count") == 0
        and reject_all.get("baseline_delta", {}).get("horizontal_m", {}).get("max", 1.0) <= 1.0e-9
        and reject_all.get("baseline_delta", {}).get("yaw_deg", {}).get("max", 1.0) <= 1.0e-9
    )
    no_substitution = all(item.get("no_output_substitution") and item.get("no_direct_nav_override") for item in variants)
    return {
        "stage": "N8H",
        "variant_count": len(variants),
        "variants": variants,
        "baseline_variant": BASELINE_VARIANT,
        "reject_all_sanity_passed": reject_all_sanity_passed,
        "reject_all_nearly_matches_baseline": reject_all_sanity_passed,
        "gross_degradation_present": any(item.get("gross_degradation") for item in variants),
        "no_output_substitution": no_substitution,
        "no_direct_nav_override": no_substitution,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }


def _build_variant_entry(bundle: N8HVisualInputs, variant_id: str) -> dict[str, Any]:
    summary = bundle.variant_summaries.get(variant_id, {})
    manifest = bundle.run_manifests.get(variant_id, {})
    observations = bundle.observations_by_variant.get(variant_id, [])
    trace_rows = bundle.update_trace_by_variant.get(variant_id, [])
    evaluation = bundle.evaluation_by_variant.get(variant_id, {})
    enabled = {
        "position": bool(summary.get("position_enabled")),
        "velocity": bool(summary.get("velocity_enabled")),
        "attitude": bool(summary.get("attitude_enabled")),
    }
    raw_position = [safe_float(row.get("position_norm_m")) for row in trace_rows]
    raw_velocity = [safe_float(row.get("velocity_norm_mps")) for row in trace_rows]
    raw_attitude = [safe_float(row.get("attitude_norm_deg")) for row in trace_rows]
    top = sorted(
        (
            {
                "time": safe_float(row.get("update_time", row.get("observation_time"))),
                "position_norm_m": safe_float(row.get("position_norm_m")),
                "velocity_norm_mps": safe_float(row.get("velocity_norm_mps")),
                "attitude_norm_deg": safe_float(row.get("attitude_norm_deg")),
            }
            for row in trace_rows
        ),
        key=lambda row: max(row["position_norm_m"], row["velocity_norm_mps"] * 10.0, row["attitude_norm_deg"]),
        reverse=True,
    )[:5]
    baseline_delta = evaluation.get(
        "feedback_vs_baseline_delta",
        {
            "horizontal_m": {"p50": 0.0, "p95": 0.0, "max": 0.0},
            "yaw_deg": {"p50": 0.0, "p95": 0.0, "max": 0.0},
            "roll_pitch_deg": {"p50": 0.0, "p95": 0.0, "max": 0.0},
        },
    )
    return {
        "variant_id": variant_id,
        "feedback_mode": summary.get("feedback_mode", manifest.get("fgo_feedback_mode", "")),
        "diagnostic_only": bool(summary.get("diagnostic_only")),
        "reject_all": bool(summary.get("reject_all")),
        "state_blocks": enabled,
        "feedback_observation_rows": len(observations),
        "feedback_valid_rows": sum(1 for row in observations if safe_int(row.get("feedback_valid")) == 1),
        "feedback_update_count": safe_int(summary.get("feedback_update_count", manifest.get("feedback_update_count"))),
        "feedback_accept_count": safe_int(summary.get("feedback_accept_count", manifest.get("feedback_accept_count"))),
        "feedback_reject_count": safe_int(summary.get("feedback_reject_count", manifest.get("feedback_reject_count"))),
        "gate_status": "reject_all_sanity" if summary.get("reject_all") else "runtime_gate_applied",
        "correction_norm_stats": {
            "position_m": stats(raw_position if enabled["position"] else [0.0 for _ in trace_rows]),
            "velocity_mps": stats(raw_velocity if enabled["velocity"] else [0.0 for _ in trace_rows]),
            "attitude_deg": stats(raw_attitude if enabled["attitude"] else [0.0 for _ in trace_rows]),
            "raw_position_residual_proxy_m": stats(raw_position),
        },
        "nav_eval_metrics": {
            "row_count_compared": safe_int(evaluation.get("row_count_compared")),
            "metric_namespace": "feedback_vs_baseline_delta",
        },
        "baseline_delta": baseline_delta,
        "gross_degradation": bool(evaluation.get("clean_gross_degradation", False)),
        "time_segments_with_largest_correction": top,
        "no_output_substitution": summary.get("no_output_substitution") is not False
        and manifest.get("fgo_feedback_output_substitution") is not True,
        "no_direct_nav_override": summary.get("no_direct_nav_override") is not False
        and manifest.get("fgo_feedback_direct_nav_override") is not True,
    }


def write_variant_ablation_review(path: str | Path, report: dict[str, Any]) -> None:
    write_json(path, report)
