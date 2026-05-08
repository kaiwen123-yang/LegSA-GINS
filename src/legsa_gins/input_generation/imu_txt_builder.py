"""Build process_data-compatible IMU increments from BY2 sportmodestate text.

中文说明：本模块只复现上传 process_imu 的 parity 输入生成：Go2 body IMU
FLU->FRD、可选安装角修正、初始窗口 gyro bias 和 dtheta/dvel 增量。
这些增量用于 baseline/parity input reconstruction，不是 formal mechanization 结论。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from legsa_gins.datasets.by2.go2_body_state_parser import parse_go2_body_state_text


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(parsed):
        return None
    return parsed


def parse_sportmodestate_text(
    path: str | Path, *, max_messages: int | None = None
) -> list[dict[str, Any]]:
    parsed = parse_go2_body_state_text(path, max_messages=max_messages)
    rows: list[dict[str, Any]] = []
    for row in parsed:
        sec = row.get("stamp_sec")
        nanosec = row.get("stamp_nanosec")
        gyro = [_as_float(row.get("gyro_x")), _as_float(row.get("gyro_y")), _as_float(row.get("gyro_z"))]
        acc = [_as_float(row.get("acc_x")), _as_float(row.get("acc_y")), _as_float(row.get("acc_z"))]
        if sec is None or nanosec is None or any(value is None for value in gyro + acc):
            continue
        rows.append(
            {
                "stamp_sec": int(sec),
                "stamp_nanosec": int(nanosec),
                "timestamp": int(sec) + int(nanosec) * 1.0e-9,
                "gyroscope": [float(value) for value in gyro if value is not None],
                "accelerometer": [float(value) for value in acc if value is not None],
            }
        )
    return rows


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)]
        for i in range(3)
    ]


def _matvec(m: list[list[float]], v: list[float]) -> list[float]:
    return [sum(m[i][j] * v[j] for j in range(3)) for i in range(3)]


def euler_rpy_deg_to_matrix(
    roll_deg: float, pitch_deg: float, yaw_deg: float
) -> list[list[float]]:
    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    rx = [[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]]
    ry = [[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]]
    rz = [[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]]
    return _matmul(_matmul(rz, ry), rx)


def _mean_vec(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return [0.0, 0.0, 0.0]
    return [sum(vector[index] for vector in vectors) / len(vectors) for index in range(3)]


def build_process_data_imu_rows(
    imu_txt_path: str | Path,
    *,
    base_time: float,
    imu_install_roll_deg: float = -1.0,
    imu_install_pitch_deg: float = 0.0,
    imu_install_yaw_deg: float = 0.0,
    imu_gnss_time_offset: float = 0.0,
    max_messages: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    frames = parse_sportmodestate_text(imu_txt_path, max_messages=max_messages)
    correction = euler_rpy_deg_to_matrix(
        imu_install_roll_deg, imu_install_pitch_deg, imu_install_yaw_deg
    )
    processed: list[dict[str, Any]] = []
    for frame in frames:
        gyro = frame["gyroscope"]
        acc = frame["accelerometer"]
        gyro_frd = [gyro[0], -gyro[1], -gyro[2]]
        acc_frd = [acc[0], -acc[1], -acc[2]]
        gyro_corr = _matvec(correction, gyro_frd)
        acc_corr = _matvec(correction, acc_frd)
        processed.append(
            {
                "time": float(frame["timestamp"]) - base_time + imu_gnss_time_offset,
                "gyro": gyro_corr,
                "acc": acc_corr,
            }
        )
    bias_window = min(1000, len(processed))
    gyro_bias = _mean_vec([frame["gyro"] for frame in processed[:bias_window]])
    rows: list[dict[str, Any]] = []
    skipped_dt_count = 0
    for index in range(1, len(processed)):
        prev = processed[index - 1]
        curr = processed[index]
        dt = float(curr["time"]) - float(prev["time"])
        if dt <= 0.0 or dt > 0.1:
            skipped_dt_count += 1
            continue
        gyro_unbiased = [float(curr["gyro"][axis]) - gyro_bias[axis] for axis in range(3)]
        acc = [float(curr["acc"][axis]) for axis in range(3)]
        rows.append(
            {
                "time": float(curr["time"]),
                "dtheta_x": gyro_unbiased[0] * dt,
                "dtheta_y": gyro_unbiased[1] * dt,
                "dtheta_z": gyro_unbiased[2] * dt,
                "dvel_x": acc[0] * dt,
                "dvel_y": acc[1] * dt,
                "dvel_z": acc[2] * dt,
                "dt": dt,
            }
        )
    report = {
        "phase": "N4H1P",
        "source_role": "go2_body_state_to_process_data_imu",
        "receiver_imu_as_body_imu": False,
        "flu_to_frd_applied_once": True,
        "accel_contains_gravity": True,
        "raw_accel_direct_dvel": True,
        "raw_accel_direct_dvel_is_process_data_parity_not_formal_mechanization": True,
        "gyro_bias_window": bias_window,
        "gyro_bias": gyro_bias,
        "input_message_count": len(frames),
        "imu_row_count": len(rows),
        "skipped_dt_count": skipped_dt_count,
        "imu_install_correction_rpy_deg": [
            imu_install_roll_deg,
            imu_install_pitch_deg,
            imu_install_yaw_deg,
        ],
    }
    return rows, report
