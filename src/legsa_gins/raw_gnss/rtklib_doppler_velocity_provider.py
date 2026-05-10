"""Run the N5B RTKLIB Doppler velocity provider.

中文说明：provider 使用 runtime-only RTKLIB helper 输出 Doppler-derived velocity。
它不读取 rnx2rtkp 最终位置解作为 LegSA measurement，也不读取 NAV-PVT velocity 或
.gnss vn/ve/vd 作为 raw Doppler。
"""

from __future__ import annotations

import csv
import math
import subprocess
from pathlib import Path
from typing import Any

from .rtklib_solution_velocity_parser import (
    VELOCITY_FACTOR_FIELDS,
    ecef_velocity_to_ned,
    parse_helper_velocity_csv,
    read_clean_gnss_position_and_times,
)


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:] if text else ""


def _finite(*values: float) -> bool:
    return all(math.isfinite(value) for value in values)


def _approx_position(source: str | Path | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(source, dict):
        if {"lat_deg", "lon_deg"}.issubset(source):
            return {"available": True, "position": source, "source_role": "runtime_dict_position_only"}
        return {"available": False, "position": None, "source_role": "missing"}
    if source:
        report = read_clean_gnss_position_and_times(source)
        if report.get("position"):
            return {"available": True, "position": report["position"], "source_role": "clean_gnss_position_only"}
    return {"available": False, "position": None, "source_role": "missing"}


def _gdop_like(sat_count: int) -> float:
    return 99.0 if sat_count <= 4 else round(math.sqrt(1.0 / max(1, sat_count - 4)), 6)


def run_rtklib_doppler_velocity_provider(
    *,
    obs_path: str | Path,
    nav_path: str | Path | None,
    sp3_path: str | Path | None = None,
    clk_path: str | Path | None = None,
    helper_exe: str | Path | None = None,
    approx_position_source: str | Path | dict[str, Any] | None = None,
    output_dir: str | Path,
    min_sat: int = 5,
) -> dict[str, Any]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    obs = Path(obs_path) if obs_path else Path()
    nav = Path(nav_path) if nav_path else Path()
    helper = Path(helper_exe) if helper_exe else Path()
    helper_csv = out / "RTKLIB_HELPER_DOPPLER_ECEF_VELOCITY.csv"
    provider_csv = out / "RTKLIB_DOPPLER_PROVIDER_VELOCITY.csv"
    blockers: list[str] = []
    command: list[str] = []
    stdout = ""
    stderr = ""
    returncode: int | None = None

    if not helper.exists():
        blockers.append("helper_executable_missing")
    if not obs.exists():
        blockers.append("rinex_obs_missing")
    if not nav.exists():
        blockers.append("broadcast_nav_missing_for_helper")
    approx = _approx_position(approx_position_source)
    if not approx["available"]:
        blockers.append("approx_position_missing")
    if blockers:
        return {
            "factor_csv_generated": False,
            "factor_csv_path": "",
            "factor_epoch_count": 0,
            "factor_valid_epoch_count": 0,
            "sat_count_min": 0,
            "sat_count_median": 0,
            "sat_count_max": 0,
            "velocity_std_policy": "not_available",
            "covariance_available": False,
            "solver_activation_allowed": False,
            "helper_run_status": "not_run",
            "helper_command": command,
            "helper_stdout_tail": stdout,
            "helper_stderr_tail": stderr,
            "helper_returncode": returncode,
            "source_provenance": "rtklib_doppler_helper_velocity",
            "rtklib_position_solution_used_as_solver_input": False,
            "nav_pvt_velocity_used_as_raw_doppler": False,
            "gnss_velocity_used_as_raw_doppler": False,
            "blocker_reasons": sorted(set(blockers)),
        }

    command = [str(helper), str(obs), str(nav), str(helper_csv)]
    proc = subprocess.run(command, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=180)
    stdout, stderr, returncode = proc.stdout, proc.stderr, proc.returncode
    raw_rows = parse_helper_velocity_csv(helper_csv)
    valid_rows: list[dict[str, Any]] = []
    pos = approx["position"]
    for row in raw_rows:
        sat_count = int(row["sat_count"])
        vx, vy, vz = row["vecef_x"], row["vecef_y"], row["vecef_z"]
        if row["provider_status"] != "available" or sat_count < min_sat or not _finite(vx, vy, vz):
            continue
        vn, ve, vd = ecef_velocity_to_ned(vx, vy, vz, pos["lat_deg"], pos["lon_deg"])
        std_vn, std_ve, std_vd = row["std_vx"], row["std_vy"], row["std_vz"]
        if not _finite(vn, ve, vd, std_vn, std_ve, std_vd) or min(std_vn, std_ve, std_vd) <= 0.0:
            continue
        valid_rows.append(
            {
                "time": f"{row['source_epoch_time']:.3f}",
                "vn": f"{vn:.9f}",
                "ve": f"{ve:.9f}",
                "vd": f"{vd:.9f}",
                "std_vn": f"{std_vn:.6f}",
                "std_ve": f"{std_ve:.6f}",
                "std_vd": f"{std_vd:.6f}",
                "sat_count": str(sat_count),
                "doppler_obs_count": str(row["doppler_obs_count"]),
                "gdop_like": f"{_gdop_like(sat_count):.6f}",
                "provider_status": "available",
                "source_epoch_time": f"{row['source_epoch_time']:.3f}",
                "quality_flag": str(row["quality_flag"]),
            }
        )
    if valid_rows:
        with provider_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=VELOCITY_FACTOR_FIELDS)
            writer.writeheader()
            writer.writerows(valid_rows)
    else:
        blockers.append("helper_no_velocity_output" if proc.returncode != 0 else "no_valid_doppler_velocity_rows")

    sat_counts = sorted(int(row["sat_count"]) for row in valid_rows)
    return {
        "factor_csv_generated": bool(valid_rows),
        "factor_csv_path": str(provider_csv) if valid_rows else "",
        "factor_epoch_count": len(raw_rows),
        "factor_valid_epoch_count": len(valid_rows),
        "sat_count_min": sat_counts[0] if sat_counts else 0,
        "sat_count_median": sat_counts[len(sat_counts) // 2] if sat_counts else 0,
        "sat_count_max": sat_counts[-1] if sat_counts else 0,
        "velocity_std_policy": "rtklib_sol_qv_with_floor_0.2_mps",
        "covariance_available": bool(valid_rows),
        "solver_activation_allowed": bool(valid_rows),
        "helper_run_status": "success" if valid_rows else "failed",
        "helper_command": command,
        "helper_stdout_tail": _tail(stdout),
        "helper_stderr_tail": _tail(stderr),
        "helper_returncode": returncode,
        "helper_raw_csv_path": str(helper_csv),
        "approx_position_source_role": approx["source_role"],
        "external_sp3_path": str(sp3_path or ""),
        "external_clk_path": str(clk_path or ""),
        "source_provenance": "rtklib_doppler_helper_velocity",
        "rtklib_position_solution_used_as_solver_input": False,
        "nav_pvt_velocity_used_as_raw_doppler": False,
        "gnss_velocity_used_as_raw_doppler": False,
        "blocker_reasons": sorted(set(blockers)),
    }
