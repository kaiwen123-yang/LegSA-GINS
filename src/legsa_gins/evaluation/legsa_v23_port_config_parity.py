"""Audit runtime clean config parity for N4H4R3A.

中文说明：runtime config 可以包含本机路径，但 tracked docs/config 不可包含；本模块
只输出诊断报告。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _read_key_values(path: str | Path) -> dict[str, str]:
    kv: dict[str, str] = {}
    with Path(path).open("r", encoding="utf-8", errors="ignore") as handle:
        for raw in handle:
            line = raw.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            kv[key.strip()] = value.strip().strip('"').strip("'")
    return kv


def _float(kv: dict[str, str], key: str, default: float = 0.0) -> float:
    try:
        return float(kv.get(key, default))
    except ValueError:
        return default


def audit_port_clean_config(
    config_path: str | Path,
    clean_manifest: dict[str, Any] | None = None,
    port_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = _read_key_values(config_path)
    clean_manifest = clean_manifest or {}
    port_manifest = port_manifest or {}
    imupath = config.get("imupath") or config.get("imu_path", "")
    gnsspath = config.get("gnsspath") or config.get("gnss_path", "")
    start = _float(config, "starttime")
    end = _float(config, "endtime")
    overlap_start = float(clean_manifest.get("overlap_start") or clean_manifest.get("effective_start") or start)
    overlap_end = float(clean_manifest.get("overlap_end") or clean_manifest.get("effective_end") or end)

    config_start_end_too_short = bool(end > 0 and (end - start) < 0.8 * max(0.0, overlap_end - overlap_start))
    config_end_before_gnss_overlap = bool(end > 0 and end < overlap_start)
    wrong_input = not (Path(imupath).name == "CLEAN_STATUS_YAW.imu" and Path(gnsspath).name == "CLEAN_STATUS_YAW.gnss")
    missing_antlever = "antlever" not in config
    missing_imunoise = any(key not in config for key in ["arw", "vrw", "gbstd", "abstd", "corrtime"])
    clean_provenance_missing = config.get("clean_input_provenance_label") != "clean_status_yaw_no_synthetic_noise"
    trace_path = "trace" in imupath.lower() or "trace" in gnsspath.lower()
    final_output_path = "KF_GINS_Navresult" in imupath or "KF_GINS_Navresult" in gnsspath
    config_ok = not any(
        [
            config_start_end_too_short,
            config_end_before_gnss_overlap,
            wrong_input,
            missing_antlever,
            missing_imunoise,
            clean_provenance_missing,
            trace_path,
            final_output_path,
        ]
    )
    return {
        "phase": "N4H4R3A",
        "config_ok": config_ok,
        "imupath_exists": Path(imupath).exists(),
        "gnsspath_exists": Path(gnsspath).exists(),
        "config_starttime": start,
        "config_endtime": end,
        "config_start_end_too_short": config_start_end_too_short,
        "config_end_before_gnss_overlap": config_end_before_gnss_overlap,
        "config_uses_wrong_input": wrong_input,
        "config_missing_antlever": missing_antlever,
        "config_missing_imunoise": missing_imunoise,
        "clean_provenance_missing": clean_provenance_missing,
        "trace_path_detected": trace_path,
        "final_v23_output_path_detected": final_output_path,
        "port_manifest_phase": port_manifest.get("phase"),
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
    }
