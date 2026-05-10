"""N5C raw Doppler ablation decision logic.

中文说明：N5C 只给诊断工程证据和下一阶段建议，不输出 paper performance claim。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _score(delta: dict[str, Any]) -> float | None:
    values = []
    for key in ["horizontal_rmse_m", "up_rmse_m", "yaw_rmse_deg"]:
        value = delta.get(key)
        if isinstance(value, (int, float)):
            values.append(float(value))
    return sum(values) if values else None


def make_n5c_decision(
    factor_diag: dict[str, Any],
    velocity_comp: dict[str, Any],
    time_align: dict[str, Any],
    ablation_comparison: dict[str, Any],
) -> dict[str, Any]:
    update_count = int(ablation_comparison.get("raw_doppler_update_count", 0) or time_align.get("actual_update_count", 0) or 0)
    blockers: list[str] = []
    if update_count == 0:
        status = "activation_failed"
        next_stage = "N5B2_raw_doppler_activation_fix"
        blockers.append("raw_doppler_update_count_zero")
    elif not time_align.get("update_alignment_ok", False):
        status = "alignment_issue"
        next_stage = "N5D_raw_doppler_time_alignment_fix"
        blockers.append("raw_doppler_time_alignment_not_ok")
    elif velocity_comp.get("possible_pvt_velocity_copy_suspect", False):
        status = "source_integrity_issue"
        next_stage = "N5D_raw_doppler_source_integrity_fix"
        blockers.append("possible_pvt_velocity_copy_suspect")
    elif ablation_comparison.get("raw_doppler_degrades_diagnostic", False):
        status = "noise_model_needed"
        next_stage = "N5D_raw_doppler_noise_model_or_gating_fix"
    else:
        status = "ablation_ready"
        next_stage = "N5D_raw_doppler_visual_validation_and_stress_protocol"

    iso_score = _score(ablation_comparison.get("velocity_isolation_delta", {}))
    independent = bool(iso_score is not None and iso_score <= 0.0 and update_count > 0)
    return {
        "stage": "N5C_raw_doppler_ablation_protocol",
        "status": status,
        "recommended_next_stage": next_stage,
        "blocker_reasons": blockers,
        "raw_doppler_update_count": update_count,
        "factor_epoch_count": factor_diag.get("epoch_count", 0),
        "factor_valid_epoch_count": factor_diag.get("valid_epoch_count", 0),
        "evidence_raw_doppler_independent_velocity_constraint": independent,
        "raw_doppler_beneficial_diagnostic": bool(ablation_comparison.get("raw_doppler_beneficial_diagnostic", False)),
        "raw_doppler_neutral_diagnostic": bool(ablation_comparison.get("raw_doppler_neutral_diagnostic", False)),
        "raw_doppler_degrades_diagnostic": bool(ablation_comparison.get("raw_doppler_degrades_diagnostic", False)),
        "proposed_factor_diagnostic_evidence": update_count > 0 and not blockers,
        "proposed_factor_claim": False,
        "paper_performance_claim": False,
        "no_outperform_final_v23_claim": True,
        "final_v23_output_solver_input": False,
        "trace_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "rtklib_position_solution_used_as_solver_input": False,
        "nav_pvt_velocity_used_as_raw_doppler": False,
        "gnss_velocity_used_as_raw_doppler": False,
    }


def write_decision(report: dict[str, Any], path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
