"""Evaluate N5D receiver-native velocity stress pairs.

中文说明：本模块只比较 no_raw 与 plus_raw 诊断组合；delta 不能写成论文
性能，也不能作为 R-scale/STD-scale 调参结论。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


METRIC_KEYS = ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg", "roll_rmse_deg", "pitch_rmse_deg"]

PAIR_IDS = [
    ("velocity_isolation", "position_yaw_only", "position_yaw_plus_raw_doppler_r1"),
    ("receiver_velocity_disabled", "receiver_velocity_disabled_no_raw", "receiver_velocity_disabled_plus_raw"),
    ("receiver_velocity_std_scale_5", "receiver_velocity_std_scale_5_no_raw", "receiver_velocity_std_scale_5_plus_raw"),
    ("receiver_velocity_outage_30s", "receiver_velocity_outage_30s_no_raw", "receiver_velocity_outage_30s_plus_raw"),
    ("receiver_velocity_noise_0p5", "receiver_velocity_noise_0p5_no_raw", "receiver_velocity_noise_0p5_plus_raw"),
]


def _summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {}
    return report.get("summary") or report.get("parity_metrics") or {}


def _metric_delta(plus: dict[str, Any] | None, no_raw: dict[str, Any] | None) -> dict[str, float | None]:
    plus_summary = _summary(plus)
    no_raw_summary = _summary(no_raw)
    out: dict[str, float | None] = {}
    for key in METRIC_KEYS:
        pv = plus_summary.get(key)
        nv = no_raw_summary.get(key)
        out[key] = float(pv) - float(nv) if isinstance(pv, (int, float)) and isinstance(nv, (int, float)) else None
    return out


def classify_raw_doppler_effect(delta: dict[str, float | None]) -> str:
    """Classify one plus_raw minus no_raw delta.

    中文说明：阈值只用于诊断归类，不是调参门限或 paper gate。
    """

    h = delta.get("horizontal_rmse_m")
    up = delta.get("up_rmse_m")
    yaw = delta.get("yaw_rmse_deg")
    numeric = [value for value in [h, up, yaw] if value is not None]
    if not numeric:
        return "evidence_missing"
    if any(value is not None and value > limit for value, limit in [(h, 0.20), (up, 0.20), (yaw, 0.50)]):
        return "degrades"
    if any(value is not None and value < -limit for value, limit in [(h, 0.02), (up, 0.02), (yaw, 0.05)]):
        return "helps"
    return "neutral"


def evaluate_n5d_stress_pairs(variant_reports: list[dict[str, Any]]) -> dict[str, Any]:
    by_id = {str(report.get("variant_id")): report for report in variant_reports}
    pairs: list[dict[str, Any]] = []
    for pair_id, no_raw_id, plus_raw_id in PAIR_IDS:
        no_raw = by_id.get(no_raw_id)
        plus_raw = by_id.get(plus_raw_id)
        delta = _metric_delta(plus_raw, no_raw)
        effect = classify_raw_doppler_effect(delta)
        pairs.append(
            {
                "pair_id": pair_id,
                "no_raw_variant_id": no_raw_id,
                "plus_raw_variant_id": plus_raw_id,
                "no_raw_summary": _summary(no_raw),
                "plus_raw_summary": _summary(plus_raw),
                "delta_plus_raw_minus_no_raw": delta,
                "raw_doppler_effect": effect,
                "diagnostic_only": True,
                "paper_performance_claim": False,
                "proposed_factor_claim": False,
            }
        )

    clean_delta = _metric_delta(by_id.get("baseline_plus_raw_doppler_r1"), by_id.get("baseline_full"))
    clean_effect = classify_raw_doppler_effect(clean_delta)
    stress_pairs = [pair for pair in pairs if pair["pair_id"].startswith("receiver_velocity")]
    help_count = sum(pair["raw_doppler_effect"] == "helps" for pair in stress_pairs)
    degrade_count = sum(pair["raw_doppler_effect"] == "degrades" for pair in stress_pairs)
    return {
        "stage": "N5D_raw_doppler_visual_validation_and_velocity_stress_protocol",
        "clean_delta_baseline_plus_raw_minus_baseline": clean_delta,
        "clean_raw_doppler_effect": clean_effect,
        "pairwise_stress_deltas": pairs,
        "stress_help_pair_count": help_count,
        "stress_degrade_pair_count": degrade_count,
        "stress_variants_completed": all(pair["raw_doppler_effect"] != "evidence_missing" for pair in pairs),
        "velocity_isolation_contribution": next((pair for pair in pairs if pair["pair_id"] == "velocity_isolation"), {}),
        "evidence_raw_doppler_independent_velocity_constraint": help_count > 0
        or (next((pair for pair in pairs if pair["pair_id"] == "velocity_isolation"), {}).get("raw_doppler_effect") == "helps"),
        "stress_results_are_diagnostic_only": True,
        "R_scale_screen_tuning_claim": False,
        "std_scale_screen_tuning_claim": False,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
