"""Covariance/config parity audit for N4H4R3B.

中文说明：这里检查 P/R/Qc/config 是否明显偏离 clean replay policy；不通过调参
改善结果，也不把过优指标写成性能 claim。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any


def _read_config(config: str | Path | dict[str, Any]) -> dict[str, str]:
    if isinstance(config, dict):
        return {str(k): str(v) for k, v in config.items()}
    path = Path(config)
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _array(config: dict[str, str], key: str) -> list[float]:
    text = config.get(key, "").strip().strip("[]")
    values: list[float] = []
    for part in text.replace(",", " ").split():
        try:
            values.append(float(part))
        except ValueError:
            continue
    return values


def _scalar(config: dict[str, str], key: str, default: float | None = None) -> float | None:
    try:
        return float(config[key])
    except (KeyError, ValueError):
        return default


def _all_present(config: dict[str, str], keys: list[str]) -> bool:
    return all(key in config and str(config[key]).strip() for key in keys)


def _any_small(values: list[float], threshold: float) -> bool:
    return bool(values) and any(abs(value) < threshold for value in values)


def compare_port_config_to_external_policy(
    port_config: str | Path | dict[str, Any],
    clean_manifest: dict[str, Any] | None = None,
    source_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = _read_config(port_config)
    clean_manifest = clean_manifest or {}
    source_policy = source_policy or {}
    required = [
        "initpos",
        "initvel",
        "initatt",
        "initposstd",
        "initvelstd",
        "initattstd",
        "arw",
        "vrw",
        "gbstd",
        "abstd",
        "gsstd",
        "asstd",
        "corrtime",
        "antlever",
    ]
    evidence_missing = not config
    missing_required = [key for key in required if key not in config]
    corrtime = _scalar(config, "corrtime")
    initposstd = _array(config, "initposstd")
    initvelstd = _array(config, "initvelstd")
    initattstd = _array(config, "initattstd")
    yaw_std_min = _scalar(config, "yaw_std_min_deg", source_policy.get("yaw_std_min_deg", 0.5))
    yaw_soft = _scalar(config, "yaw_res_soft_deg", source_policy.get("yaw_res_soft_deg", 6.0))
    yaw_hard = _scalar(config, "yaw_res_hard_deg", source_policy.get("yaw_res_hard_deg", 15.0))

    clean_provenance_missing = config.get("clean_input_provenance_label") != "clean_status_yaw_no_synthetic_noise"
    measurement_R_too_small = bool(
        _any_small(initposstd, 1.0e-3)
        or _any_small(initvelstd, 1.0e-4)
        or _any_small(initattstd, 1.0e-4)
        or bool(clean_manifest.get("gnss_measurement_std_too_small", False))
    )
    covariance_p_large = bool(
        any(abs(value) > 1.0e3 for value in initposstd)
        or any(abs(value) > 100.0 for value in initvelstd)
        or any(abs(value) > 30.0 for value in initattstd)
    )
    covariance_p_small = bool(
        _any_small(initposstd, 1.0e-6) or _any_small(initvelstd, 1.0e-6) or _any_small(initattstd, 1.0e-6)
    )
    yaw_std_mismatch = bool(yaw_std_min is not None and yaw_std_min <= 0.0)
    velocity_std_mismatch = bool(_any_small(_array(config, "vrw"), 1.0e-12))
    position_std_mismatch = bool(len(initposstd) not in [0, 3])
    scheme_c_mismatch = bool(
        yaw_soft is None
        or yaw_hard is None
        or not math.isclose(float(yaw_soft), 6.0, rel_tol=0.0, abs_tol=1.0e-9)
        or not math.isclose(float(yaw_hard), 15.0, rel_tol=0.0, abs_tol=1.0e-9)
    )
    process_noise_missing = not _all_present(config, ["arw", "vrw", "gbstd", "abstd", "corrtime"])
    qc_suspect = bool(corrtime is None or corrtime <= 0.0 or process_noise_missing)
    mismatch = any(
        [
            evidence_missing,
            bool(missing_required),
            clean_provenance_missing,
            measurement_R_too_small,
            covariance_p_large,
            covariance_p_small,
            yaw_std_mismatch,
            velocity_std_mismatch,
            position_std_mismatch,
            scheme_c_mismatch,
            qc_suspect,
        ]
    )
    return {
        "phase": "N4H4R3B",
        "config_matches_external_clean_policy": not mismatch,
        "missing_required_config_keys": missing_required,
        "measurement_R_too_small_suspect": measurement_R_too_small,
        "covariance_P_too_large_suspect": covariance_p_large,
        "covariance_P_too_small_suspect": covariance_p_small,
        "yaw_std_mismatch": yaw_std_mismatch,
        "velocity_std_mismatch": velocity_std_mismatch,
        "position_std_mismatch": position_std_mismatch,
        "scheme_C_mismatch": scheme_c_mismatch,
        "process_noise_Qc_suspect": qc_suspect,
        "clean_provenance_missing": clean_provenance_missing,
        "config_policy_evidence_missing": evidence_missing,
        "covariance_config_mismatch": mismatch,
        "corrtime_value": corrtime,
        "engineering_backbone_parity_only": True,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
