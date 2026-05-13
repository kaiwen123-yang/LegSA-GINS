"""Decision rules for N7C Go2 horizontal velocity weak-prior activation.

中文说明：决策只给出下一阶段工程门禁，不声明优于 final_v23，也不产生
paper performance claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _manifest_int(manifest: dict[str, Any], key: str) -> int:
    try:
        return int(manifest.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _delta_value(report: dict[str, Any], name: str, metric: str) -> float | None:
    value = report.get("comparisons", {}).get(name, {}).get("delta", {}).get(metric)
    return float(value) if isinstance(value, (int, float)) else None


def make_n7c_decision(
    *,
    prior_build_report: dict[str, Any],
    matrix: dict[str, Any],
    variant_summaries: dict[str, Any],
    comparison_report: dict[str, Any],
) -> dict[str, Any]:
    variants = variant_summaries.get("variants", []) if isinstance(variant_summaries, dict) else []
    by_id = {row.get("variant_id"): row for row in variants}
    main = by_id.get("go2_horizontal_velocity_weak_prior_main", {})
    manifest = main.get("manifest", {}) if isinstance(main.get("manifest"), dict) else {}
    update_count = _manifest_int(manifest, "go2_horizontal_velocity_prior_update_count")
    reject_count = _manifest_int(manifest, "go2_velocity_prior_reject_count")
    clean_delta = _delta_value(comparison_report, "go2_horizontal_velocity_main_minus_baseline", "horizontal_rmse_m")
    receiver_stress_delta = _delta_value(comparison_report, "receiver_velocity_stress_plus_go2_minus_no_go2", "horizontal_rmse_m")
    raw_stress_delta = _delta_value(comparison_report, "raw_doppler_stress_plus_go2_minus_no_go2", "horizontal_rmse_m")
    diagnostic_disagree = False
    for row in variants:
        variant_id = str(row.get("variant_id") or "")
        if variant_id.startswith("go2_horizontal_velocity_") and variant_id != "go2_horizontal_velocity_weak_prior_main":
            if row.get("returncode", 0) != 0:
                diagnostic_disagree = True
    clean_degradation = clean_delta is not None and clean_delta > 0.50
    stress_helpful = any(value is not None and value < -0.10 for value in [receiver_stress_delta, raw_stress_delta])
    stress_weak = all(value is None or abs(value) <= 0.10 for value in [receiver_stress_delta, raw_stress_delta])
    if update_count == 0:
        status = "activation_failed"
        next_stage = "N7C2_activation_debug"
    elif clean_degradation:
        status = "not_ready_clean_degradation"
        next_stage = "N7C2_policy_review_or_N8A"
    elif diagnostic_disagree:
        status = "needs_go2_horizontal_policy_review"
        next_stage = "N7C2_policy_review"
    elif stress_helpful:
        status = "ready_for_FGO_or_extended_ablation"
        next_stage = "N8A_no_feedback_FGO_foundation"
    elif stress_weak:
        status = "ready_with_weak_stress_evidence"
        next_stage = "N8A_no_feedback_FGO_foundation"
    else:
        status = "ready_for_FGO_or_extended_ablation"
        next_stage = "N8A_no_feedback_FGO_foundation"
    return {
        "stage": "N7C_go2_horizontal_velocity_weak_prior",
        "status": status,
        "recommended_next_stage": next_stage,
        "update_count": update_count,
        "reject_count": reject_count,
        "clean_horizontal_rmse_delta_m": clean_delta,
        "receiver_stress_horizontal_rmse_delta_m": receiver_stress_delta,
        "raw_doppler_stress_horizontal_rmse_delta_m": raw_stress_delta,
        "diagnostic_variants_disagree_strongly": diagnostic_disagree,
        "prior_epoch_count": int(prior_build_report.get("epoch_count", 0) or 0),
        "required_variants_present": bool(matrix.get("required_variants_present")),
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "fgo": False,
        "output_only_correction": False,
        "trace_tuning": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def write_n7c_decision(decision: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
