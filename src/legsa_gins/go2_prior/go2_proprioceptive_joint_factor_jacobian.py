"""N7C6 Go2 proprioceptive joint factor Jacobian contract.

中文说明：联合观测合同只触碰 roll/pitch attitude error 和 vN/vE velocity error；
明确不触碰 position、yaw、vertical velocity。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


STATE_BLOCKS = ["position", "velocity_north", "velocity_east", "velocity_down", "attitude_roll", "attitude_pitch", "attitude_yaw", "imu_bias"]


def build_joint_factor_jacobian_contract() -> dict[str, Any]:
    toy = toy_finite_difference_check()
    return {
        "stage": "N7C6_go2_proprioceptive_joint_factor",
        "factor_name": "go2_roll_pitch_horizontal_velocity_joint_observation",
        "residual_definition": "r=[roll_filter-roll_go2,pitch_filter-pitch_go2,vN_filter-vN_go2,vE_filter-vE_go2]",
        "residual_dimension": 4,
        "state_dimension": 21,
        "H_shape": [4, 21],
        "R_shape": [4, 4],
        "nonzero_state_blocks": ["attitude_roll", "attitude_pitch", "velocity_north", "velocity_east"],
        "zero_state_blocks": ["position", "velocity_down", "attitude_yaw", "imu_bias"],
        "position_block_touched": False,
        "yaw_block_touched": False,
        "vertical_velocity_block_touched": False,
        "vertical_velocity_disabled": True,
        "R_definition": "diag(std_roll^2,std_pitch^2,std_vn^2,std_ve^2)",
        "sequential_equivalent_allowed": True,
        "finite_difference_check_status": toy["finite_difference_check_status"],
        "toy_finite_difference": toy,
        "go2_roll_pitch_truth_claim": False,
        "go2_velocity_truth_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "paper_performance_claim": False,
        "fgo": False,
    }


def toy_finite_difference_check(eps: float = 1.0e-6) -> dict[str, Any]:
    base = {"roll": 0.1, "pitch": -0.05, "vn": 1.2, "ve": -0.3, "vd": 0.7, "yaw": 0.4, "pos_n": 10.0}
    obs = {"roll": 0.08, "pitch": -0.06, "vn": 1.0, "ve": -0.1}

    def residual(state: dict[str, float]) -> list[float]:
        return [state["roll"] - obs["roll"], state["pitch"] - obs["pitch"], state["vn"] - obs["vn"], state["ve"] - obs["ve"]]

    expected = {
        "roll": [1.0, 0.0, 0.0, 0.0],
        "pitch": [0.0, 1.0, 0.0, 0.0],
        "vn": [0.0, 0.0, 1.0, 0.0],
        "ve": [0.0, 0.0, 0.0, 1.0],
        "vd": [0.0, 0.0, 0.0, 0.0],
        "yaw": [0.0, 0.0, 0.0, 0.0],
        "pos_n": [0.0, 0.0, 0.0, 0.0],
    }
    actual: dict[str, list[float]] = {}
    r0 = residual(base)
    for key in expected:
        shifted = dict(base)
        shifted[key] += eps
        r1 = residual(shifted)
        actual[key] = [(b - a) / eps for a, b in zip(r0, r1)]
    passed = all(all(abs(actual[key][i] - expected[key][i]) < 1.0e-7 for i in range(4)) for key in expected)
    return {"finite_difference_check_status": "toy_passed" if passed else "toy_failed", "expected": expected, "actual": actual}


def write_joint_factor_jacobian_contract(path: str | Path, report: dict[str, Any] | None = None) -> dict[str, Any]:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = report or build_joint_factor_jacobian_contract()
    output.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data
