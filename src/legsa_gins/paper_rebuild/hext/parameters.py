"""Frozen literature parameters and the unexecuted shared-parameter proposal."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import yaml


@dataclass(frozen=True)
class Ext05Parameters:
    """Only these four injection fields may differ in the registered S variant."""

    phase5_parameter_blocks: dict[str, Any]
    gyro_psd_rad2_s: tuple[float, float, float]
    accel_psd_m2_s3: tuple[float, float, float]
    accel_scale: float = 1.0
    imu_gap_policy: str = "frozen_filter_raise"


def _mapping(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("parameter contract must be a mapping")
    return payload


def _positive_three(values: Any, name: str) -> tuple[float, float, float]:
    result = tuple(float(value) for value in values)
    if len(result) != 3 or any(not math.isfinite(v) or v <= 0.0 for v in result):
        raise ValueError(f"{name} must contain three positive finite entries")
    return result


def literature_parameters(contract: Mapping[str, Any]) -> Ext05Parameters:
    """Keep the complete PHASE5 parameter mapping, with no reinterpreted values."""
    noise = contract["process_noise_psd_paper_experiment"]
    return Ext05Parameters(
        phase5_parameter_blocks=deepcopy(dict(contract)),
        gyro_psd_rad2_s=_positive_three(noise["gyro_rad2_per_s"], "literature gyro PSD"),
        accel_psd_m2_s3=_positive_three(noise["accelerometer_m2ps3"], "literature accel PSD"),
    )


def load_parameters(
    phase5_contract_path: Path,
    *,
    variant_enabled: bool = False,
    sensor_model_path: Path | None = None,
) -> Ext05Parameters:
    parameters = literature_parameters(_mapping(phase5_contract_path))
    if not variant_enabled:
        # The disabled branch does not even open the alternative sensor model.
        return parameters
    if sensor_model_path is None:
        raise ValueError("shared parameters require the frozen calibrated sensor model")
    model = _mapping(sensor_model_path)
    arw = _positive_three(model["frozen_arw"], "frozen ARW")
    gyro = tuple((value * math.pi / 180.0 / 60.0) ** 2 for value in arw)
    vrw = _positive_three(model["vrw"], "frozen VRW")
    q = _positive_three(model["q"], "calibrated q")
    calculated_q = tuple((value / 60.0) ** 2 for value in vrw)
    if not np.allclose(q, calculated_q, rtol=1.0e-13, atol=0.0):
        raise ValueError("calibrated q disagrees with (vrw/60)^2")
    scale = float(model["s"])
    if not math.isfinite(scale) or scale <= 0.0:
        raise ValueError("calibrated acceleration scale is not positive finite")
    return Ext05Parameters(
        phase5_parameter_blocks=parameters.phase5_parameter_blocks,
        gyro_psd_rad2_s=gyro,
        accel_psd_m2_s3=q,
        accel_scale=scale,
        imu_gap_policy="mirror_legsa_drop",
    )


def scaled_frd_specific_force(force: np.ndarray, scale: float) -> np.ndarray:
    """Scale all unrounded FRD axes after FLU/install, before time integration.

    The placement matches clean5_imu_parity/providers.py:50-54,101.  The
    literature recursive previous-sample hold and static calibration remain
    untouched; this helper changes only the common scalar on the force.
    """
    if scale == 1.0:
        return force
    return force * scale


def require_implemented_gap_policy(parameters: Ext05Parameters) -> None:
    if parameters.imu_gap_policy == "mirror_legsa_drop":
        raise NotImplementedError("mirror_legsa_drop mechanism awaits H-EXT-02 human decision")
    if parameters.imu_gap_policy != "frozen_filter_raise":
        raise ValueError("unregistered IMU gap policy")
