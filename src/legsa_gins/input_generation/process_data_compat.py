"""Generate process_data-compatible final_v23 runtime input files.

中文说明：本模块从 BY2 gnss1-status / gnss1-raw / gnss1+gnss2 status /
Go2 sportmodestate text 重建 15-column `.gnss` 和 7-column `.imu` 输入。
它是 input reconstruction，不是 solver、raw GNSS 解算、FGO 或性能评价。
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

from legsa_gins.input_generation.imu_txt_builder import build_process_data_imu_rows
from legsa_gins.input_generation.status_yaw_builder import (
    apply_yaw_install_and_ned,
    build_a1_dual_diff_yaw_rows,
    compute_yaw_std,
    status_time_header,
)
from legsa_gins.input_generation.ubx_nav_pvt import extract_pvt_velocity_rows


GNSS_COLUMNS = [
    "time",
    "lat",
    "lon",
    "height",
    "std_n",
    "std_e",
    "std_d",
    "vn",
    "ve",
    "vd",
    "std_vn",
    "std_ve",
    "std_vd",
    "yaw",
    "yaw_std",
]

IMU_COLUMNS = [
    "time",
    "dtheta_x",
    "dtheta_y",
    "dtheta_z",
    "dvel_x",
    "dvel_y",
    "dvel_z",
]


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = str(value).strip()
    if text == "":
        return default
    try:
        parsed = float(text)
    except ValueError:
        return default
    if math.isnan(parsed):
        return default
    return parsed


def _read_csv(path: str | Path, *, max_rows: int | None = None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            if max_rows is not None and index >= max_rows:
                break
            rows.append(row)
    return rows


def _nearest(
    rows: list[dict[str, Any]], time_value: float, *, key: str, tolerance: float
) -> dict[str, Any] | None:
    if not rows:
        return None
    lo = 0
    hi = len(rows) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        mt = float(rows[mid][key])
        if mt < time_value:
            lo = mid + 1
        elif mt > time_value:
            hi = mid - 1
        else:
            return rows[mid]
    candidates = []
    if 0 <= hi < len(rows):
        candidates.append(rows[hi])
    if 0 <= lo < len(rows):
        candidates.append(rows[lo])
    if not candidates:
        return None
    best = min(candidates, key=lambda item: abs(float(item[key]) - time_value))
    return best if abs(float(best[key]) - time_value) <= tolerance else None


def _status_base_rows(
    gnss1_status_path: str | Path, *, base_time: float, max_rows: int | None
) -> tuple[list[dict[str, Any]], int]:
    rows = _read_csv(gnss1_status_path, max_rows=max_rows)
    output: list[dict[str, Any]] = []
    missing = 0
    for row in rows:
        lat = _as_float(row.get("pos_lat"), _as_float(row.get("lat_deg")))
        lon = _as_float(row.get("pos_lon"), _as_float(row.get("lon_deg")))
        height = _as_float(row.get("pos_height"), _as_float(row.get("height_m")))
        acc_h = _as_float(row.get("pos_acc_h"), _as_float(row.get("pos_acc_h_m")))
        acc_v = _as_float(row.get("pos_acc_v"), _as_float(row.get("pos_acc_v_m")))
        try:
            timestamp = status_time_header(row)
        except ValueError:
            timestamp = _as_float(row.get("Time"), _as_float(row.get("time_unix")))
        if None in {lat, lon, height, acc_h, acc_v, timestamp}:
            missing += 1
            continue
        output.append(
            {
                "time": float(timestamp) - base_time,
                "stamp": float(timestamp),
                "lat": float(lat),
                "lon": float(lon),
                "height": float(height),
                "std_n": float(acc_h),
                "std_e": float(acc_h),
                "std_d": float(acc_v),
            }
        )
    output.sort(key=lambda item: float(item["time"]))
    return output, missing


def _write_table(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            values = [float(row[column]) for column in columns]
            handle.write(" ".join(f"{value:.12g}" for value in values) + "\n")


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _ensure_nominal_generation(
    *, enable_outage: bool, outlier_mode: str, yaw_noise_std_deg: float
) -> None:
    if enable_outage:
        raise ValueError("N4H1P does not implement outage injection.")
    if outlier_mode != "none":
        raise ValueError("N4H1P does not implement outlier injection.")
    if yaw_noise_std_deg != 0.0:
        raise ValueError("N4H1P does not implement yaw-noise injection.")


def generate_process_data_compat_inputs(
    fix_root: str | Path,
    body_imu: str | Path,
    output_dir: str | Path,
    *,
    base_time: float = 1772784000.0,
    yaw_source_mode: str = "status",
    yaw_sign: float = 1.0,
    yaw_install_offset_deg: float = 0.0,
    yaw_std_mode: str = "fixed_1p5",
    status_fixed_yaw_std_deg: float = 1.5,
    enable_outage: bool = False,
    outlier_mode: str = "none",
    yaw_noise_std_deg: float = 0.0,
    imu_install_roll_deg: float = -1.0,
    imu_install_pitch_deg: float = 0.0,
    imu_install_yaw_deg: float = 0.0,
    imu_gnss_time_offset: float = 0.0,
    max_status_rows: int | None = None,
    max_raw_rows: int | None = None,
    max_imu_messages: int | None = None,
) -> dict[str, Any]:
    _ensure_nominal_generation(
        enable_outage=enable_outage,
        outlier_mode=outlier_mode,
        yaw_noise_std_deg=yaw_noise_std_deg,
    )
    if yaw_source_mode not in {"status", "trace"}:
        raise ValueError(f"Unsupported yaw source mode: {yaw_source_mode}")
    if yaw_source_mode == "trace":
        raise ValueError("trace yaw is diagnostic-only and is not a formal N4H1P input source.")

    root = Path(fix_root)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    gnss1_status = root / "gnss1-status.csv"
    gnss2_status = root / "gnss2-status.csv"
    gnss1_raw = root / "gnss1-raw.csv"

    base_rows, missing_status_count = _status_base_rows(
        gnss1_status, base_time=base_time, max_rows=max_status_rows
    )
    pvt_rows = extract_pvt_velocity_rows(gnss1_raw, base_time=base_time, max_rows=max_raw_rows)
    yaw_rows, yaw_audit = build_a1_dual_diff_yaw_rows(
        gnss1_status,
        gnss2_status,
        base_time=base_time,
        max_rows=max_status_rows,
    )
    yaw_rows = compute_yaw_std(yaw_rows, yaw_std_mode)
    if yaw_std_mode == "fixed_1p5" and status_fixed_yaw_std_deg != 1.5:
        for row in yaw_rows:
            row["yaw_std"] = float(status_fixed_yaw_std_deg)
            row["yaw_std_mode"] = "fixed_status_override"
    yaw_rows = apply_yaw_install_and_ned(
        yaw_rows, sign=yaw_sign, offset_deg=yaw_install_offset_deg
    )
    yaw_rows.sort(key=lambda item: float(item["aligned_time"]))

    gnss_rows: list[dict[str, Any]] = []
    missing_velocity_count = 0
    missing_yaw_count = 0
    for base in base_rows:
        t = float(base["time"])
        vel = _nearest(pvt_rows, t, key="time", tolerance=0.1)
        if vel is None:
            missing_velocity_count += 1
            continue
        yaw = _nearest(yaw_rows, t, key="aligned_time", tolerance=0.6)
        if yaw is None:
            missing_yaw_count += 1
            continue
        row = dict(base)
        row.update(
            {
                "vn": float(vel["vn"]),
                "ve": float(vel["ve"]),
                "vd": float(vel["vd"]),
                "std_vn": 0.05,
                "std_ve": 0.05,
                "std_vd": 0.05,
                "yaw": float(yaw["yaw_ned_deg"]),
                "yaw_std": float(yaw["yaw_std"]),
            }
        )
        gnss_rows.append(row)

    imu_rows, imu_report = build_process_data_imu_rows(
        body_imu,
        base_time=base_time,
        imu_install_roll_deg=imu_install_roll_deg,
        imu_install_pitch_deg=imu_install_pitch_deg,
        imu_install_yaw_deg=imu_install_yaw_deg,
        imu_gnss_time_offset=imu_gnss_time_offset,
        max_messages=max_imu_messages,
    )

    gnss_path = out / "BY2_PROCESS_DATA_COMPAT.gnss"
    imu_path = out / "BY2_PROCESS_DATA_COMPAT.imu"
    report_path = out / "PROCESS_DATA_COMPAT_REPORT.json"
    yaw_audit_path = out / "STATUS_YAW_A1_AUDIT.json"
    imu_report_path = out / "IMU_PROCESS_DATA_COMPAT_REPORT.json"
    _write_table(gnss_path, gnss_rows, GNSS_COLUMNS)
    _write_table(imu_path, imu_rows, IMU_COLUMNS)

    yaw_audit.update(
        {
            "yaw_sign": float(yaw_sign),
            "yaw_install_offset_deg": float(yaw_install_offset_deg),
            "yaw_std_mode": yaw_std_mode,
            "yaw_std_policy": "fixed_1p5" if yaw_std_mode == "fixed_1p5" else yaw_std_mode,
            "yaw_ned_row_count": len(yaw_rows),
            "trace_solver_input": False,
            "trace_yaw_for_solver": False,
        }
    )
    report = {
        "phase": "N4H1P",
        "runtime_input_reconstructed": True,
        "base_time": float(base_time),
        "time_mode": "legacy_base_time_process_data_compat",
        "gnss_columns": 15,
        "imu_columns": 7,
        "gnss_row_count": len(gnss_rows),
        "imu_row_count": len(imu_rows),
        "position_source": "gnss1_status_pos_lat_lon_height",
        "position_std_source": "gnss1_status_pos_acc_h_v",
        "velocity_source": "gnss1_raw_UBX_NAV_PVT",
        "velocity_std_policy": "fixed_0p05_observed_in_uploaded_code",
        "pvt_sacc_parsed": True,
        "pvt_sacc_used_for_velocity_std": False,
        "yaw_source": "A1_dual_diff_status",
        "yaw_formula": "-atan2(rel_e,rel_n)",
        "yaw_ned_formula": "90_minus_yaw_body",
        "yaw_source_mode": yaw_source_mode,
        "yaw_std_mode": yaw_std_mode,
        "trace_solver_input": False,
        "trace_yaw_for_solver": False,
        "output_only_correction": False,
        "bad_epoch_deletion_for_metric": False,
        "raw_doppler_claim": False,
        "go2_prior_claim": False,
        "source_aware_weighting_claim": False,
        "fgo_smoother_claim": False,
        "numerical_performance_claim": False,
        "enable_outage": bool(enable_outage),
        "outlier_mode": outlier_mode,
        "yaw_noise_injection": yaw_noise_std_deg != 0.0,
        "yaw_noise_std_deg": float(yaw_noise_std_deg),
        "status_input_rows": len(base_rows),
        "status_missing_position_or_time_count": missing_status_count,
        "pvt_velocity_rows": len(pvt_rows),
        "status_yaw_rows": len(yaw_rows),
        "rows_without_pvt_velocity_match": missing_velocity_count,
        "rows_without_status_yaw_match": missing_yaw_count,
        "generated_files": {
            "gnss": gnss_path.name,
            "imu": imu_path.name,
            "process_data_compat_report": report_path.name,
            "status_yaw_a1_audit": yaw_audit_path.name,
            "imu_report": imu_report_path.name,
        },
        "formal_allowed": True,
        "generated_inputs_are_baseline_parity_only": True,
    }
    _write_json(report_path, report)
    _write_json(yaw_audit_path, yaw_audit)
    _write_json(imu_report_path, imu_report)
    return {
        "output_dir": str(out),
        "gnss_path": str(gnss_path),
        "imu_path": str(imu_path),
        "report_path": str(report_path),
        "status_yaw_a1_audit_path": str(yaw_audit_path),
        "imu_report_path": str(imu_report_path),
        "report": report,
        "status_yaw_a1_audit": yaw_audit,
        "imu_report": imu_report,
    }
