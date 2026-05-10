"""N5D raw Doppler visual sanity checks.

中文说明：sanity checks 只判断图像/来源/时间/诊断矩阵是否可用于下一阶段评审，
不做论文性能结论，不删除 bad epoch。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def _finite_recursive(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, int) or value is None or isinstance(value, str) or isinstance(value, bool):
        return True
    if isinstance(value, dict):
        return all(_finite_recursive(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_finite_recursive(item) for item in value)
    return True


def _monotonic(rows: list[dict[str, Any]], key: str = "time") -> bool:
    values = [float(row[key]) for row in rows if isinstance(row.get(key), (int, float)) and math.isfinite(float(row[key]))]
    return all(a <= b for a, b in zip(values, values[1:])) if values else False


def _variant_update_counts_ok(variant_reports: list[dict[str, Any]]) -> tuple[bool, int]:
    enabled = [row for row in variant_reports if row.get("enable_raw_doppler") or row.get("raw_doppler_solver_enabled")]
    counts = [int(row.get("raw_doppler_update_count", 0) or 0) for row in enabled]
    expected = int(next((row.get("raw_doppler_update_count", 0) for row in enabled if row.get("variant_id") == "baseline_plus_raw_doppler_r1"), 0) or 0)
    if expected <= 0 and counts:
        expected = max(counts)
    ok = bool(counts) and expected > 0 and all(count == expected for count in counts if count > 0)
    return ok, expected


def _clean_no_gross_divergence(stress_eval: dict[str, Any]) -> bool:
    delta = stress_eval.get("clean_delta_baseline_plus_raw_minus_baseline", {})
    limits = {"horizontal_rmse_m": 0.5, "up_rmse_m": 0.5, "yaw_rmse_deg": 2.0}
    for key, limit in limits.items():
        value = delta.get(key)
        if isinstance(value, (int, float)) and value > limit:
            return False
    return True


def build_visual_sanity_report(
    *,
    inputs: dict[str, Any],
    figure_manifest: dict[str, Any],
    stress_eval: dict[str, Any],
) -> dict[str, Any]:
    variant_reports = list(inputs.get("variant_reports", []))
    updates_ok, expected = _variant_update_counts_ok(variant_reports)
    velocity = inputs.get("velocity_comparison", {})
    time_alignment = inputs.get("time_alignment", {})
    no_nan_inf = _finite_recursive(inputs) and _finite_recursive(stress_eval)
    time_monotonic = _monotonic(inputs.get("raw_factor_rows", []), "time")
    reject_counts = [int(row.get("raw_doppler_reject_count", 0) or 0) for row in variant_reports]
    update_counts = [int(row.get("raw_doppler_update_count", 0) or 0) for row in variant_reports]
    reject_reasonable = max(reject_counts, default=0) <= max(5, int(0.2 * max(update_counts, default=0)))
    stress_completed = bool(stress_eval.get("stress_variants_completed", False))
    figure_count = int(figure_manifest.get("figure_count_total", 0) or 0)
    raw_velocity_not_pvt_copy = not bool(velocity.get("possible_pvt_velocity_copy_suspect", False))
    raw_velocity_not_gnss_15col_copy = bool(velocity.get("raw_doppler_not_gnss_15col", True)) and raw_velocity_not_pvt_copy
    checks = {
        "raw_doppler_update_count_expected": expected,
        "raw_doppler_update_count_consistent": updates_ok,
        "raw_doppler_reject_count_reasonable": reject_reasonable,
        "time_alignment_ok": bool(time_alignment.get("update_alignment_ok", True)),
        "no_nan_inf": no_nan_inf,
        "time_monotonic": time_monotonic,
        "raw_velocity_not_pvt_copy": raw_velocity_not_pvt_copy,
        "raw_velocity_not_gnss_15col_copy": raw_velocity_not_gnss_15col_copy,
        "clean_variant_no_gross_divergence": _clean_no_gross_divergence(stress_eval),
        "stress_variants_completed": stress_completed,
        "figures_generated": figure_count,
        "figures_generated_minimum_ok": figure_count >= 25,
        "pure_single_absent": bool(figure_manifest.get("pure_single_absent", True)),
        "no_outperform_final_v23_claim": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
    required = [
        "raw_doppler_update_count_consistent",
        "raw_doppler_reject_count_reasonable",
        "time_alignment_ok",
        "no_nan_inf",
        "time_monotonic",
        "raw_velocity_not_pvt_copy",
        "raw_velocity_not_gnss_15col_copy",
        "clean_variant_no_gross_divergence",
        "stress_variants_completed",
        "figures_generated_minimum_ok",
        "pure_single_absent",
    ]
    return {
        "stage": "N5D_raw_doppler_visual_validation_and_velocity_stress_protocol",
        **checks,
        "visual_stress_candidate_passed": all(bool(checks[key]) for key in required),
    }


def write_visual_sanity_report(path: str | Path, report: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
