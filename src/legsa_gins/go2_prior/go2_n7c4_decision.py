"""Decision rules for N7C4 Go2 horizontal velocity prior strength calibration.

中文说明：决策只基于 clean neutral gate、stress diagnostic delta 和
solver-visible residual/NIS proxy，不做论文性能声明。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _delta(report: dict[str, Any], name: str, metric: str = "horizontal_rmse_m") -> float | None:
    value = report.get("comparisons", {}).get(name, {}).get("delta", {}).get(metric)
    return float(value) if isinstance(value, (int, float)) else None


def _clean_neutral(report: dict[str, Any], comparison_name: str) -> bool:
    delta = report.get("comparisons", {}).get(comparison_name, {}).get("delta", {})
    gates = {
        "horizontal_rmse_m": 0.10,
        "up_rmse_m": 0.20,
        "yaw_rmse_deg": 0.30,
        "roll_rmse_deg": 0.15,
        "pitch_rmse_deg": 0.15,
    }
    return all(isinstance(delta.get(key), (int, float)) and float(delta[key]) <= limit for key, limit in gates.items())


def _not_overconfident(nis_report: dict[str, Any], variant_id: str) -> bool:
    row = nis_report.get("variants", {}).get(variant_id, {})
    return row.get("overconfidence_status") == "not_overconfident"


def _manifest_count(report: dict[str, Any], variant_id: str, key: str) -> int:
    value = report.get("candidate_manifests", {}).get(variant_id, {}).get(key, 0)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def make_n7c4_strength_decision(
    *,
    confidence_report: dict[str, Any],
    prior_report: dict[str, Any],
    nis_report: dict[str, Any],
    comparison_report: dict[str, Any],
    figure_manifest: dict[str, Any],
) -> dict[str, Any]:
    fixed_1p0_neutral = _clean_neutral(comparison_report, "fixed_1p0_minus_fixed_2p0_clean")
    fixed_1p5_neutral = _clean_neutral(comparison_report, "fixed_1p5_minus_fixed_2p0_clean")
    adaptive_neutral = _clean_neutral(comparison_report, "recalibrated_adaptive_minus_fixed_2p0_clean")
    fixed_1p0_ok = fixed_1p0_neutral and _not_overconfident(nis_report, "fixed_1p0")
    fixed_1p5_ok = fixed_1p5_neutral and _not_overconfident(nis_report, "fixed_1p5")
    adaptive_ok = adaptive_neutral and _not_overconfident(nis_report, "recalibrated_adaptive")
    stress_adaptive = [
        _delta(comparison_report, "receiver_velocity_stress_adaptive_minus_fixed_2p0"),
        _delta(comparison_report, "raw_doppler_stress_adaptive_minus_fixed_2p0"),
    ]
    adaptive_stress_improves = any(value is not None and value < -0.01 for value in stress_adaptive)
    stronger_degrade = not fixed_1p0_neutral and not fixed_1p5_neutral and not adaptive_neutral
    if adaptive_ok and adaptive_stress_improves:
        recommended = "recalibrated_adaptive"
        status = "adaptive_policy_ready"
    elif fixed_1p0_ok:
        recommended = "fixed_1p0"
        status = "stronger_policy_ready"
    elif fixed_1p5_ok:
        recommended = "fixed_1p5"
        status = "moderate_policy_ready"
    elif stronger_degrade:
        recommended = "fixed_2p0"
        status = "keep_fixed_2p0_and_proceed_N8A"
    else:
        recommended = "fixed_2p0"
        status = "weak_policy_required"
    return {
        "stage": "N7C4_go2_horizontal_velocity_strength_calibration",
        "status": status,
        "recommended_default_policy": recommended,
        "confidence_counts": confidence_report.get("confidence_counts", {}),
        "variant_std_policies": prior_report.get("variant_std_policies", {}),
        "fixed_1p0_clean_neutral": fixed_1p0_neutral,
        "fixed_1p0_nis_status": nis_report.get("variants", {}).get("fixed_1p0", {}).get("overconfidence_status"),
        "fixed_1p5_clean_neutral": fixed_1p5_neutral,
        "fixed_1p5_nis_status": nis_report.get("variants", {}).get("fixed_1p5", {}).get("overconfidence_status"),
        "adaptive_clean_neutral": adaptive_neutral,
        "adaptive_nis_status": nis_report.get("variants", {}).get("recalibrated_adaptive", {}).get("overconfidence_status"),
        "clean_fixed_1p0_minus_2p0_horizontal_rmse_delta_m": _delta(comparison_report, "fixed_1p0_minus_fixed_2p0_clean"),
        "clean_fixed_1p5_minus_2p0_horizontal_rmse_delta_m": _delta(comparison_report, "fixed_1p5_minus_fixed_2p0_clean"),
        "clean_adaptive_minus_2p0_horizontal_rmse_delta_m": _delta(comparison_report, "recalibrated_adaptive_minus_fixed_2p0_clean"),
        "receiver_stress_fixed_1p0_minus_2p0_horizontal_rmse_delta_m": _delta(comparison_report, "receiver_velocity_stress_fixed_1p0_minus_fixed_2p0"),
        "receiver_stress_adaptive_minus_2p0_horizontal_rmse_delta_m": _delta(comparison_report, "receiver_velocity_stress_adaptive_minus_fixed_2p0"),
        "raw_doppler_stress_fixed_1p0_minus_2p0_horizontal_rmse_delta_m": _delta(comparison_report, "raw_doppler_stress_fixed_1p0_minus_fixed_2p0"),
        "raw_doppler_stress_adaptive_minus_2p0_horizontal_rmse_delta_m": _delta(comparison_report, "raw_doppler_stress_adaptive_minus_fixed_2p0"),
        "fixed_2p0_update_count": _manifest_count(comparison_report, "fixed_2p0", "go2_horizontal_velocity_prior_update_count"),
        "fixed_1p0_update_count": _manifest_count(comparison_report, "fixed_1p0", "go2_horizontal_velocity_prior_update_count"),
        "adaptive_update_count": _manifest_count(comparison_report, "recalibrated_adaptive", "go2_horizontal_velocity_prior_update_count"),
        "figures_generated": bool(figure_manifest.get("required_figures_generated", False)),
        "figures_nonempty": bool(figure_manifest.get("required_figures_nonempty", False)),
        "figure_count": figure_manifest.get("figure_count_total", 0),
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "go2_vertical_velocity_prior_enabled": False,
        "go2_position_prior_enabled": False,
        "go2_yaw_prior_enabled": False,
        "vertical_disabled": True,
        "no_trace_tuning": True,
        "no_final_v23_tuning": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }


def write_n7c4_strength_decision(path: str | Path, decision: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output
