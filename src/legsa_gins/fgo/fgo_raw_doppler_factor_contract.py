"""N8C3 RawDopplerVelocityFactor contract.

中文说明：定义 Raw Doppler 速度因子的 residual/Jacobian/R 合同，不使用 trace/final_v23。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.fgo.fgo_factor_types import RawDopplerVelocityFactorRow


VELOCITY_COLUMNS = (6, 7, 8)
VELOCITY_BLOCKS = ("velocity_north", "velocity_east", "velocity_down")
RAW_DOPPLER_DIMENSION = 3


def write_json_report(path: str | Path, report: dict[str, Any]) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output


def raw_doppler_residual(state_vector: list[float], factor: RawDopplerVelocityFactorRow) -> list[float]:
    measurement = factor.measurement()
    return [float(state_vector[column]) - measurement[index] for index, column in enumerate(VELOCITY_COLUMNS)]


def raw_doppler_whitened_residual(
    state_vector: list[float],
    factor: RawDopplerVelocityFactorRow,
    *,
    weight_scale: float = 1.0,
) -> list[float]:
    scale = math.sqrt(max(0.0, weight_scale))
    return [
        value * scale / max(std, 1e-9)
        for value, std in zip(raw_doppler_residual(state_vector, factor), factor.std())
    ]


def raw_doppler_jacobian_entries(*, row_offset: int = 0) -> list[dict[str, float]]:
    entries = []
    for dim, column in enumerate(VELOCITY_COLUMNS):
        entries.append({"row": float(row_offset + dim), "column": float(column), "value": 1.0})
    return entries


def finite_difference_contract_check(eps: float = 1e-6) -> dict[str, Any]:
    factor = RawDopplerVelocityFactorRow(state_index=0, time=0.0, vn_mps=1.0, ve_mps=-0.5, vd_mps=0.25)
    base = [0.0, 0.0, 0.0, 0.1, -0.2, 45.0, 1.2, -0.3, 0.4]
    base_residual = raw_doppler_residual(base, factor)
    derivatives: dict[str, list[float]] = {}
    names = ["lat", "lon", "height", "roll", "pitch", "yaw", "vn", "ve", "vd"]
    for column, name in enumerate(names):
        perturbed = list(base)
        perturbed[column] += eps
        residual = raw_doppler_residual(perturbed, factor)
        derivatives[name] = [(right - left) / eps for left, right in zip(base_residual, residual)]
    velocity_ok = all(abs(derivatives[name][index] - 1.0) < 1e-6 for index, name in enumerate(["vn", "ve", "vd"]))
    non_velocity_ok = all(
        max(abs(value) for value in derivatives[name]) < 1e-6
        for name in ["lat", "lon", "height", "roll", "pitch", "yaw"]
    )
    return {
        "toy_passed": bool(velocity_ok and non_velocity_ok),
        "velocity_derivatives": {name: derivatives[name] for name in ["vn", "ve", "vd"]},
        "non_velocity_derivatives": {name: derivatives[name] for name in ["lat", "lon", "height", "roll", "pitch", "yaw"]},
    }


def build_raw_doppler_factor_contract_report() -> dict[str, Any]:
    fd = finite_difference_contract_check()
    return {
        "stage": "N8C3_raw_doppler_fgo_factor_fix",
        "factor_type": "RawDopplerVelocityFactor",
        "observation": "z = [vN_rawdoppler, vE_rawdoppler, vD_rawdoppler]",
        "prediction": "h(x) = [vN_state, vE_state, vD_state]",
        "residual": "r = h(x) - z",
        "residual_dimension": RAW_DOPPLER_DIMENSION,
        "state_blocks_touched": list(VELOCITY_BLOCKS),
        "jacobian_policy": "identity_wrt_velocity_block_only",
        "jacobian_entries": raw_doppler_jacobian_entries(row_offset=0),
        "touches_position": False,
        "touches_attitude": False,
        "touches_yaw": False,
        "touches_bias": False,
        "r_policy": "raw_doppler_std_or_covariance_no_zero_weight",
        "no_zero_weight": True,
        "no_r_shrink_without_explicit_config": True,
        "source_aware_scaling_allowed_if_existing_policy_allows": True,
        "finite_difference": fd,
        "toy_passed": bool(fd.get("toy_passed")),
        "no_feedback": True,
        "output_substitution": False,
        "trace_solver_input": False,
        "trace_weight_tuning": False,
        "final_v23_output_solver_input": False,
        "final_v23_weight_tuning": False,
        "paper_performance_claim": False,
    }
