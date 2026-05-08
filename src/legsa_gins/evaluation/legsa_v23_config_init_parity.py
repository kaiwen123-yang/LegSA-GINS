"""Config/init parity diagnostics for N4H4D1.

中文说明：检查 LegSA-v23-core config parser 后的内部单位和初始化量，
重点筛查 deg/rad、height、initatt、IMU noise、antlever 和 start/end。
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def load_legsa_config_snapshot(path: str | Path) -> dict[str, Any]:
    """中文说明：读取 CONFIG_INIT_SNAPSHOT；缺失则显式 evidence_missing。"""

    file_path = Path(path)
    if not file_path.exists():
        return {"evidence_status": "evidence_missing", "missing": file_path.name}
    return json.loads(file_path.read_text(encoding="utf-8"))


def load_external_clean_config_if_available(
    n4h2g_root: str | Path | None = None,
    dual_root: str | Path | None = None,
    external_root: str | Path | None = None,
) -> dict[str, Any]:
    """中文说明：只读加载外部 clean config/policy；找不到时保留 evidence_missing。"""

    candidates: list[Path] = []
    for root in [n4h2g_root, dual_root, external_root]:
        if not root:
            continue
        base = Path(root)
        candidates.extend(
            [
                base / "kf-gins-n4h2g-clean-replay.yaml",
                base / "config.yaml",
                base / "config.conf",
            ]
        )
    found = next((path for path in candidates if path.exists()), None)
    if found is None:
        return {"external_config_status": "evidence_missing"}
    text = found.read_text(encoding="utf-8", errors="ignore")
    return {
        "external_config_status": "loaded",
        "source_role": "external_clean_config_read_only",
        "has_initpos": "initpos" in text.lower(),
        "has_initatt": "initatt" in text.lower(),
        "has_antlever": "antlever" in text.lower(),
        "has_imunoise": "imunoise" in text.lower() or "noise" in text.lower(),
    }


def _vector(snapshot: dict[str, Any], key: str) -> list[float]:
    values = snapshot.get(key)
    if not isinstance(values, list) or len(values) < 3:
        return [math.nan, math.nan, math.nan]
    return [float(values[0]), float(values[1]), float(values[2])]


def _finite(values: list[float]) -> bool:
    return all(math.isfinite(value) for value in values)


def compare_config_init(snapshot: dict[str, Any], external_config_or_policy: dict[str, Any] | None = None) -> dict[str, Any]:
    """中文说明：输出 config/init parity 判别；只诊断，不修配置、不调参。"""

    policy = external_config_or_policy or {}
    initpos_deg = _vector(snapshot, "initpos_deg_m_input")
    initpos_rad = _vector(snapshot, "initpos_rad_m_internal")
    initatt_deg = _vector(snapshot, "initatt_deg_input")
    initatt_rad = _vector(snapshot, "initatt_rad_internal")
    initatt_back = _vector(snapshot, "initatt_deg_internal_backconverted")
    initpos_std = _vector(snapshot, "initposstd_m")
    initatt_std_deg = _vector(snapshot, "initattstd_deg")
    antlever = _vector(snapshot, "antlever_m")
    imu_noise = _vector(snapshot, "imunoise_internal_units")
    start = float(snapshot.get("starttime", math.nan))
    end = float(snapshot.get("endtime", math.nan))

    lat_rad_expected = math.radians(initpos_deg[0]) if math.isfinite(initpos_deg[0]) else math.nan
    lon_rad_expected = math.radians(initpos_deg[1]) if math.isfinite(initpos_deg[1]) else math.nan
    config_units_issue = bool(
        not _finite(initpos_deg + initpos_rad + initatt_deg + initatt_rad)
        or abs(initpos_rad[0] - lat_rad_expected) > 1e-8
        or abs(initpos_rad[1] - lon_rad_expected) > 1e-8
        or abs(initpos_rad[2] - initpos_deg[2]) > 1e-9
        or max(abs(initatt_back[i] - initatt_deg[i]) for i in range(3)) > 1e-6
    )
    height_rad_conversion_issue = bool(math.isfinite(initpos_rad[2]) and abs(initpos_rad[2]) < 1.0 and abs(initpos_deg[2]) > 5.0)
    initatt_yaw_mismatch = bool(abs(initatt_deg[2] - initatt_back[2]) > 1e-6)
    initroll_pitch_mismatch = bool(max(abs(initatt_deg[i] - initatt_back[i]) for i in [0, 1]) > 1e-6)
    antlever_mismatch = bool(_finite(antlever) and max(abs(value) for value in antlever) > 5.0)
    imunoise_unit_issue = bool(_finite(imu_noise) and any(abs(value) > 10.0 for value in imu_noise))
    init_covariance_suspicious = bool(
        _finite(initpos_std + initatt_std_deg)
        and (any(value <= 0.0 for value in initpos_std + initatt_std_deg) or any(value > 1.0e4 for value in initpos_std))
    )
    start_end_mismatch = bool(not math.isfinite(start) or not math.isfinite(end) or end <= start)
    evidence_missing = [
        key
        for key in ["has_initpos", "has_initatt", "has_antlever", "has_imunoise"]
        if policy.get("external_config_status") == "loaded" and policy.get(key) is False
    ]
    if policy.get("external_config_status") != "loaded":
        evidence_missing.append("external_clean_config")

    return {
        "phase": "N4H4D1",
        "config_units_issue": config_units_issue or height_rad_conversion_issue,
        "height_rad_conversion_issue": height_rad_conversion_issue,
        "initatt_yaw_mismatch": initatt_yaw_mismatch,
        "initroll_pitch_mismatch": initroll_pitch_mismatch,
        "antlever_mismatch": antlever_mismatch,
        "imunoise_unit_issue": imunoise_unit_issue,
        "init_covariance_suspicious": init_covariance_suspicious,
        "start_end_mismatch": start_end_mismatch,
        "evidence_missing": evidence_missing,
        "trace_solver_input": False,
        "final_v23_output_substitution": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "numerical_performance_claim": False,
    }

