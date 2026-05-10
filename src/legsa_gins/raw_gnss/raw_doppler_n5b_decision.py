"""N5B raw Doppler activation decision helper.

中文说明：只有 factor file 生成且 EKF raw_doppler_update_count > 0 时，才允许标记
real activation completed。
"""

from __future__ import annotations

from typing import Any


def decide_n5b_activation(
    helper_report: dict[str, Any],
    provider_report: dict[str, Any],
    factor_report: dict[str, Any],
    trial_report: dict[str, Any],
) -> dict[str, Any]:
    blockers = set(helper_report.get("blocker_reasons", []))
    blockers.update(provider_report.get("blocker_reasons", []))
    blockers.update(factor_report.get("blocker_reasons", []))
    blockers.update(trial_report.get("blocker_reasons", []))
    update_count = int(trial_report.get("raw_doppler_update_count", 0) or 0)
    if trial_report.get("real_activation_status") == "completed_enabled" and update_count > 0:
        status = "completed_enabled"
        next_stage = "N5C_raw_doppler_ablation_protocol"
    elif helper_report.get("helper_compile_status") != "success":
        status = "helper_compile_failed"
        next_stage = "N5B2_rtklib_helper_compile_fix"
    elif provider_report.get("factor_valid_epoch_count", 0) == 0:
        status = "helper_compiled_but_no_velocity_output"
        next_stage = "N5B2_rtklib_velocity_output_fix"
    elif not provider_report.get("covariance_available", False):
        status = "covariance_missing"
        next_stage = "N5B2_doppler_velocity_covariance_model"
    elif factor_report.get("factor_csv_generated") and update_count == 0:
        status = "activation_failed_update_alignment_or_loader"
        next_stage = "N5B2_raw_doppler_time_alignment_fix"
    else:
        status = trial_report.get("real_activation_status", "blocked")
        next_stage = trial_report.get("recommended_next_stage", "N5B2_data_availability_recheck")
    return {
        "real_activation_status": status,
        "raw_doppler_update_count": update_count,
        "recommended_next_stage": next_stage,
        "blocking_issue": sorted(blockers)[0] if blockers and status != "completed_enabled" else "",
        "blocker_reasons": sorted(blockers),
        "paper_performance_claim": False,
        "outperform_final_v23_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }
