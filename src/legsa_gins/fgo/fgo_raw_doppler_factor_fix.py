"""N8C3 Raw Doppler FGO factor fix orchestration helpers.

中文说明：集中运行 Raw Doppler factor 合同、dataset link、solver injection 和变体重跑。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow
from legsa_gins.fgo.fgo_raw_doppler_solver_injection import build_solver_injection_report, run_raw_doppler_solver_variant


N8C3_RAW_DOPPLER_VARIANTS = [
    "weak_yaw_smoothness_with_raw_fixed",
    "raw_doppler_off_verified",
    "raw_doppler_weight_x0p5",
    "raw_doppler_weight_x1",
    "raw_doppler_weight_x2",
    "raw_doppler_weight_x4",
    "receiver_velocity_off_raw_on",
    "receiver_velocity_off_raw_off",
    "smoothness_weak_raw_x1",
    "smoothness_weak_raw_x2",
]


def run_n8c3_raw_doppler_variants(
    *,
    ekf_rows: list[dict[str, Any]],
    raw_factors: list[RawDopplerVelocityFactorRow],
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    rows_by_variant: dict[str, list[dict[str, Any]]] = {}
    summaries = []
    for variant in N8C3_RAW_DOPPLER_VARIANTS:
        rows, summary = run_raw_doppler_solver_variant(ekf_rows=ekf_rows, raw_factors=raw_factors, variant=variant)
        rows_by_variant[variant] = rows
        summaries.append(summary)
    baseline = next((row for row in summaries if row.get("variant") == "weak_yaw_smoothness_with_raw_fixed"), {})
    base_cost = float(baseline.get("final_cost", 0.0) or 0.0)
    for row in summaries:
        cost = float(row.get("final_cost", 0.0) or 0.0)
        row["gross_degradation"] = cost > max(1.0, base_cost * 5.0 + 1.0)
    report = {
        "stage": "N8C3_raw_doppler_fgo_factor_fix",
        "variants": summaries,
        "variant_count": len(summaries),
        "required_variants": N8C3_RAW_DOPPLER_VARIANTS,
        "all_required_variants_run": sorted(N8C3_RAW_DOPPLER_VARIANTS) == sorted(row.get("variant") for row in summaries),
        "all_variants_real_solver_rerun": all(row.get("real_solver_rerun") and not row.get("proxy_only") for row in summaries),
        "raw_doppler_direct_equation_available": all(
            row.get("raw_doppler_direct_equation_available") for row in summaries if row.get("raw_doppler_enabled")
        ),
        "weight_scan_diagnostic_only": True,
        "no_final_weight_selected_by_trace": True,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
    return report, rows_by_variant


def build_raw_doppler_fix_comparison_report(*, variant_report: dict[str, Any]) -> dict[str, Any]:
    variants = {row.get("variant"): row for row in variant_report.get("variants", [])}
    with_raw = variants.get("weak_yaw_smoothness_with_raw_fixed", {})
    without_raw = variants.get("raw_doppler_off_verified", {})
    injection = build_solver_injection_report(with_raw_summary=with_raw, without_raw_summary=without_raw)
    return {
        "stage": "N8C3_raw_doppler_fgo_factor_fix",
        "with_raw_variant": with_raw.get("variant"),
        "without_raw_variant": without_raw.get("variant"),
        "raw_factor_row_delta": int(with_raw.get("raw_factor_rows", 0) or 0) - int(without_raw.get("raw_factor_rows", 0) or 0),
        "solver_residual_dim_delta": int(with_raw.get("solver_residual_dim", 0) or 0) - int(without_raw.get("solver_residual_dim", 0) or 0),
        "jacobian_nonzero_delta": int(with_raw.get("jacobian_nonzero_count", 0) or 0) - int(without_raw.get("jacobian_nonzero_count", 0) or 0),
        "with_raw_final_cost": with_raw.get("final_cost"),
        "without_raw_final_cost": without_raw.get("final_cost"),
        "solver_injection_status": injection.get("solver_injection_status"),
        "raw_doppler_on_off_delta_tiny": abs(float(with_raw.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0) - float(without_raw.get("yaw_delta_wrapped_rmse_deg", 0.0) or 0.0)) < 0.05,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
