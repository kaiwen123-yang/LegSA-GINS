"""N4H4D6 covariance-unit parity audit.

中文说明：这里审计 KF-GINS-style IMU 噪声单位换算线索；缺失字段保留
evidence_missing，不脑补配置，也不修改 solver。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

D2R = math.pi / 180.0


def gyro_bias_deg_h_to_rad_s(value: float) -> float:
    return value * D2R / 3600.0


def acc_bias_mgal_to_mps2(value: float) -> float:
    return value * 1.0e-5


def scale_ppm_to_unit(value: float) -> float:
    return value * 1.0e-6


def arw_deg_sqrt_hr_to_rad_sqrt_s(value: float) -> float:
    return value * D2R / 60.0


def vrw_mps_sqrt_hr_to_mps_sqrt_s(value: float) -> float:
    return value / 60.0


def corr_time_hr_to_sec(value: float) -> float:
    return value * 3600.0


def qc_bias_variance(std_internal: float, corr_time_sec: float) -> float:
    if corr_time_sec <= 0.0:
        return float("nan")
    return 2.0 / corr_time_sec * std_internal * std_internal


def _load(path_or_dict: str | Path | dict[str, Any] | None) -> dict[str, Any]:
    if path_or_dict is None:
        return {}
    if isinstance(path_or_dict, dict):
        return path_or_dict
    p = Path(path_or_dict)
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _num(data: dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else None


def audit_covariance_unit_parity(
    unit_snapshot: str | Path | dict[str, Any] | None,
    config_snapshot: str | Path | dict[str, Any] | None = None,
    reference_docs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """中文说明：检查 bias/scale 初值、过程噪声和 corr time 单位证据。"""

    units = _load(unit_snapshot)
    config = _load(config_snapshot)
    reference_docs = reference_docs or {}
    initbg = _num(units, "initbgstd_internal")
    initba = _num(units, "initbastd_internal")
    initsg = _num(units, "initsgstd_internal")
    initsa = _num(units, "initsastd_internal")
    corr_time = _num(units, "corr_time_internal")
    bias_scale_available = all(value is not None for value in [initbg, initba, initsg, initsa])
    init_units_ok = bool(
        bias_scale_available
        and 1.0e-12 < float(initbg) < 1.0
        and 1.0e-8 < float(initba) < 10.0
        and 1.0e-12 < float(initsg) < 1.0
        and 1.0e-12 < float(initsa) < 1.0
    )
    process_keys = [
        "gyr_arw_internal",
        "acc_vrw_internal",
        "gyrbias_std_internal",
        "accbias_std_internal",
        "gyrscale_std_internal",
        "accscale_std_internal",
    ]
    process_values = [_num(units, key) for key in process_keys]
    process_noise_units_ok = all(value is not None and value >= 0.0 for value in process_values)
    corr_time_units_ok = corr_time is not None and corr_time > 1.0
    qc_model_ok = corr_time_units_ok and initbg is not None and math.isfinite(qc_bias_variance(float(initbg), float(corr_time)))
    p_bias_too_large = bool(bias_scale_available and (float(initbg) > 0.1 or float(initba) > 1.0))
    p_bias_too_small = bool(bias_scale_available and (float(initbg) < 1.0e-10 or float(initba) < 1.0e-8))
    evidence_missing = [
        key
        for key in ["corr_time_internal"]
        if not isinstance(units.get(key), (int, float))
    ]
    mismatch = bool(evidence_missing or p_bias_too_large or p_bias_too_small or not process_noise_units_ok)
    return {
        "phase": "N4H4D6",
        "init_bias_scale_std_units_ok": init_units_ok,
        "process_noise_units_ok": bool(process_noise_units_ok),
        "corr_time_units_ok": bool(corr_time_units_ok),
        "Qc_bias_model_ok": bool(qc_model_ok),
        "P_bias_scale_initial_too_large": p_bias_too_large,
        "P_bias_scale_initial_too_small": p_bias_too_small,
        "P_phi_bias_cross_cov_large": bool(reference_docs.get("P_phi_bias_cross_cov_large", False)),
        "covariance_unit_mismatch_suspect": mismatch,
        "evidence_missing": evidence_missing,
        "config_snapshot_loaded": bool(config),
        "unit_conversion_examples": {
            "gyro_bias_1_deg_h_rad_s": gyro_bias_deg_h_to_rad_s(1.0),
            "acc_bias_1_mgal_mps2": acc_bias_mgal_to_mps2(1.0),
            "scale_1_ppm_unit": scale_ppm_to_unit(1.0),
            "arw_1_deg_sqrt_hr_rad_sqrt_s": arw_deg_sqrt_hr_to_rad_sqrt_s(1.0),
            "vrw_1_mps_sqrt_hr_mps_sqrt_s": vrw_mps_sqrt_hr_to_mps_sqrt_s(1.0),
            "corr_time_1_hr_sec": corr_time_hr_to_sec(1.0),
        },
        "diagnostic_only": True,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }

