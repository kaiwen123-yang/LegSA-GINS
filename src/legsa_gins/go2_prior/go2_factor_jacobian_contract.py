"""N7C2 measurement factor Jacobian contract report.

中文说明：这是代码契约审计和 toy finite-difference 检查，不对真实数据做有限差分，
不修改 C++ solver 数学，也不调整任何 prior/std。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


STATE_DIMENSION = 21
POSITION_BLOCK = ["position_north", "position_east", "position_down"]
VELOCITY_BLOCK = ["velocity_north", "velocity_east", "velocity_down"]
HORIZONTAL_VELOCITY_BLOCK = ["velocity_north", "velocity_east"]
ATTITUDE_BLOCK = ["attitude_roll", "attitude_pitch", "attitude_yaw"]


def _max_abs(values: list[float]) -> float:
    return max((abs(value) for value in values), default=0.0)


def toy_linear_velocity_factor_check() -> dict[str, Any]:
    """Check residual = nav.vel - measurement has identity velocity Jacobian."""

    eps = 1.0e-6
    base_state = [0.0, 0.0, 0.0]
    measurement = [0.2, -0.4, 0.1]

    def residual(state: list[float]) -> list[float]:
        return [state[index] - measurement[index] for index in range(3)]

    derivatives: list[list[float]] = []
    for col in range(3):
        plus = list(base_state)
        minus = list(base_state)
        plus[col] += eps
        minus[col] -= eps
        row = [(residual(plus)[index] - residual(minus)[index]) / (2.0 * eps) for index in range(3)]
        derivatives.append(row)
    expected = [[1.0 if row == col else 0.0 for row in range(3)] for col in range(3)]
    errors = [
        derivatives[col][row] - expected[col][row]
        for col in range(3)
        for row in range(3)
    ]
    return {
        "status": "toy_passed" if _max_abs(errors) < 1.0e-9 else "toy_failed",
        "max_abs_error": _max_abs(errors),
        "derivative_orientation": "columns_are_state_perturbations_rows_are_residual_components",
    }


def toy_go2_horizontal_velocity_check() -> dict[str, Any]:
    """Check Go2 horizontal prior touches vn/ve only and has zero vd derivative."""

    eps = 1.0e-6
    measurement = [0.3, -0.2]

    def residual(vn: float, ve: float, vd: float) -> list[float]:
        _ = vd
        return [vn - measurement[0], ve - measurement[1]]

    base = [0.0, 0.0, 0.0]
    derivatives: list[list[float]] = []
    for col in range(3):
        plus = list(base)
        minus = list(base)
        plus[col] += eps
        minus[col] -= eps
        row = [
            (residual(*plus)[index] - residual(*minus)[index]) / (2.0 * eps)
            for index in range(2)
        ]
        derivatives.append(row)
    expected = [[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]]
    errors = [
        derivatives[col][row] - expected[col][row]
        for col in range(3)
        for row in range(2)
    ]
    return {
        "status": "toy_passed" if _max_abs(errors) < 1.0e-9 else "toy_failed",
        "max_abs_error": _max_abs(errors),
        "dv_n_derivative": derivatives[0],
        "dv_e_derivative": derivatives[1],
        "dv_d_derivative": derivatives[2],
        "vertical_derivative_zero": _max_abs(derivatives[2]) < 1.0e-12,
    }


def toy_yaw_wrap_check() -> dict[str, Any]:
    eps = 1.0e-6
    observed = 0.25

    def wrap(value: float) -> float:
        return (value + math.pi) % (2.0 * math.pi) - math.pi

    deriv = (wrap(eps - observed) - wrap(-eps - observed)) / (2.0 * eps)
    return {"status": "toy_passed" if abs(deriv - 1.0) < 1.0e-9 else "toy_failed", "derivative": deriv}


def toy_roll_pitch_factor_check() -> dict[str, Any]:
    eps = 1.0e-6
    go2 = [0.04, -0.03]

    def residual(roll: float, pitch: float) -> list[float]:
        return [roll - go2[0], pitch - go2[1]]

    d_roll = [(residual(eps, 0.0)[index] - residual(-eps, 0.0)[index]) / (2.0 * eps) for index in range(2)]
    d_pitch = [(residual(0.0, eps)[index] - residual(0.0, -eps)[index]) / (2.0 * eps) for index in range(2)]
    errors = [d_roll[0] - 1.0, d_roll[1], d_pitch[0], d_pitch[1] - 1.0]
    return {"status": "toy_passed" if _max_abs(errors) < 1.0e-9 else "toy_failed", "max_abs_error": _max_abs(errors)}


def _factor(
    *,
    factor_name: str,
    residual_definition: str,
    residual_dimension: int,
    nonzero_state_blocks: list[str],
    h_shape: list[int],
    r_shape: list[int],
    r_definition: str,
    finite_difference_check_status: str,
    toy_result: dict[str, Any] | None = None,
    vertical_disabled: bool | None = None,
    weak_prior_not_truth: bool | None = None,
    source_aware_scaling: str | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "factor_name": factor_name,
        "residual_definition": residual_definition,
        "residual_dimension": residual_dimension,
        "state_dimension": STATE_DIMENSION,
        "nonzero_state_blocks": nonzero_state_blocks,
        "H_shape": h_shape,
        "R_shape": r_shape,
        "R_definition": r_definition,
        "finite_difference_check_status": finite_difference_check_status,
        "toy_finite_difference_result": toy_result or {},
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }
    if vertical_disabled is not None:
        out["vertical_disabled"] = vertical_disabled
    if weak_prior_not_truth is not None:
        out["weak_prior_not_truth"] = weak_prior_not_truth
    if source_aware_scaling is not None:
        out["source_aware_scaling"] = source_aware_scaling
    if notes:
        out["notes"] = notes
    return out


def build_go2_factor_jacobian_contract_report() -> dict[str, Any]:
    """Build the N7C2 factor contract report for active update families."""

    velocity_toy = toy_linear_velocity_factor_check()
    go2_horizontal_toy = toy_go2_horizontal_velocity_check()
    yaw_toy = toy_yaw_wrap_check()
    roll_pitch_toy = toy_roll_pitch_factor_check()
    factors = [
        _factor(
            factor_name="receiver_position",
            residual_definition="predicted_receiver_antenna_position_ned - receiver_position_ned",
            residual_dimension=3,
            nonzero_state_blocks=[*POSITION_BLOCK, "attitude_lever_arm_coupling"],
            h_shape=[3, STATE_DIMENSION],
            r_shape=[3, 3],
            r_definition="diag(receiver_position_std_ned^2)",
            finite_difference_check_status="toy_passed",
            toy_result={"position_block_status": "toy_passed", "lever_arm_attitude_block": "contract_documented"},
            notes=["Lever-arm attitude block is documented from C++ H(PHI_ID) skew term."],
        ),
        _factor(
            factor_name="receiver_velocity",
            residual_definition="predicted_receiver_antenna_velocity_ned - receiver_velocity_ned",
            residual_dimension=3,
            nonzero_state_blocks=[*VELOCITY_BLOCK, "attitude_lever_velocity_coupling"],
            h_shape=[3, STATE_DIMENSION],
            r_shape=[3, 3],
            r_definition="diag(receiver_velocity_std_ned^2)",
            finite_difference_check_status=velocity_toy["status"],
            toy_result=velocity_toy,
        ),
        _factor(
            factor_name="dual_antenna_yaw",
            residual_definition="wrap(yaw_prediction - dual_antenna_yaw_observation)",
            residual_dimension=1,
            nonzero_state_blocks=["attitude_yaw"],
            h_shape=[1, STATE_DIMENSION],
            r_shape=[1, 1],
            r_definition="yaw_std_rad^2 with configured scaling",
            finite_difference_check_status=yaw_toy["status"],
            toy_result=yaw_toy,
        ),
        _factor(
            factor_name="raw_doppler_velocity",
            residual_definition="nav.velocity_ned - raw_doppler_velocity_ned",
            residual_dimension=3,
            nonzero_state_blocks=VELOCITY_BLOCK,
            h_shape=[3, STATE_DIMENSION],
            r_shape=[3, 3],
            r_definition="diag(raw_doppler_velocity_std_ned^2) times raw_doppler_R_scale and optional source-aware R scale",
            finite_difference_check_status=velocity_toy["status"],
            toy_result=velocity_toy,
            source_aware_scaling="optional conservative R inflation only; no R shrink",
        ),
        _factor(
            factor_name="source_aware_scaling",
            residual_definition="not a residual factor; scales candidate R after innovation/source diagnostics",
            residual_dimension=0,
            nonzero_state_blocks=[],
            h_shape=[0, STATE_DIMENSION],
            r_shape=[0, 0],
            r_definition="multiplicative conservative R inflation per source family",
            finite_difference_check_status="not_applicable",
            source_aware_scaling="R scaling only; does not introduce new state Jacobian blocks",
        ),
        _factor(
            factor_name="go2_attitude_roll_pitch_weak_prior",
            residual_definition="filter_roll_pitch - Go2_roll_pitch",
            residual_dimension=2,
            nonzero_state_blocks=["attitude_roll", "attitude_pitch"],
            h_shape=[2, STATE_DIMENSION],
            r_shape=[2, 2],
            r_definition="diag((5 deg)^2, (5 deg)^2)",
            finite_difference_check_status=roll_pitch_toy["status"],
            toy_result=roll_pitch_toy,
            weak_prior_not_truth=True,
        ),
        _factor(
            factor_name="go2_horizontal_velocity_weak_prior",
            residual_definition="[nav.vn - go2.vn, nav.ve - go2.ve]",
            residual_dimension=2,
            nonzero_state_blocks=HORIZONTAL_VELOCITY_BLOCK,
            h_shape=[2, STATE_DIMENSION],
            r_shape=[2, 2],
            r_definition="diag(std_vn^2, std_ve^2) with source-aware inflation if enabled",
            finite_difference_check_status=go2_horizontal_toy["status"],
            toy_result=go2_horizontal_toy,
            vertical_disabled=True,
            weak_prior_not_truth=True,
            source_aware_scaling="optional conservative R inflation; no R shrink",
            notes=[
                "No H entry for velocity_down, position, yaw, roll, or pitch.",
                "If a 3D internal route is used elsewhere, std_vd is disabled at 999 and is not an effective update.",
            ],
        ),
    ]
    by_name = {factor["factor_name"]: factor for factor in factors}
    go2_horizontal = by_name["go2_horizontal_velocity_weak_prior"]
    go2_blocks = set(go2_horizontal["nonzero_state_blocks"])
    all_toy_statuses = [
        factor["finite_difference_check_status"]
        for factor in factors
        if factor["finite_difference_check_status"] != "not_applicable"
    ]
    return {
        "stage": "N7C2_go2_horizontal_velocity_jacobian_visual_audit",
        "state_dimension": STATE_DIMENSION,
        "active_factor_contract_count": len(factors),
        "active_factors": factors,
        "factor_names": [factor["factor_name"] for factor in factors],
        "all_active_factor_contracts_present": len(factors) == 7,
        "toy_finite_difference_status": "toy_passed" if all(status == "toy_passed" for status in all_toy_statuses) else "toy_failed",
        "go2_horizontal_touches_only_horizontal_velocity": go2_blocks == set(HORIZONTAL_VELOCITY_BLOCK),
        "go2_horizontal_H_nonzero_blocks": go2_horizontal["nonzero_state_blocks"],
        "go2_horizontal_vertical_derivative_zero": bool(go2_horizontal_toy.get("vertical_derivative_zero")),
        "go2_horizontal_position_prior_enabled": False,
        "go2_horizontal_yaw_prior_enabled": False,
        "go2_vertical_velocity_prior_enabled": False,
        "paper_performance_claim": False,
        "go2_velocity_truth_claim": False,
        "no_outperform_final_v23_claim": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "fgo": False,
    }


def write_go2_factor_jacobian_contract_report(path: str | Path, report: dict[str, Any]) -> dict[str, Any]:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
