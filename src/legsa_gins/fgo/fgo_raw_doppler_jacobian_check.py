"""N8C3 Raw Doppler Jacobian checks.

中文说明：验证 Raw Doppler Jacobian 只触碰速度状态块。
"""

from __future__ import annotations

from typing import Any

from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow
from legsa_gins.fgo.fgo_raw_doppler_factor_contract import finite_difference_contract_check
from legsa_gins.fgo.fgo_raw_doppler_solver_injection import assemble_raw_doppler_residual_vector


def build_raw_doppler_jacobian_check_report(
    *,
    solution_vectors: list[list[float]],
    raw_factors: list[RawDopplerVelocityFactorRow],
) -> dict[str, Any]:
    assembly = assemble_raw_doppler_residual_vector(
        solution_vectors=solution_vectors,
        factors=raw_factors,
        raw_enabled=True,
        raw_weight_scale=1.0,
    )
    fd = finite_difference_contract_check()
    passed = bool(fd.get("toy_passed")) and int(assembly.get("jacobian_nonzero_count", 0) or 0) > 0
    return {
        "stage": "N8C3_raw_doppler_fgo_factor_fix",
        "toy_finite_difference_passed": bool(fd.get("toy_passed")),
        "real_jacobian_nonzero_count": assembly.get("jacobian_nonzero_count", 0),
        "real_jacobian_row_count": assembly.get("jacobian_row_count", 0),
        "state_blocks_touched": assembly.get("state_blocks_touched", []),
        "touches_velocity_only": assembly.get("state_blocks_touched") == ["velocity_north", "velocity_east", "velocity_down"],
        "jacobian_contract_passed": passed,
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
    }
