"""Unitree sportmodestate IMU semantic checks.

中文说明：本模块只做 Unitree IMU 语义诊断，不实现 Go2 prior 或 leg odometry factor。
"""

from __future__ import annotations

import math
from typing import Any


def _as_float(value: Any, default: float = 0.0) -> float:
    if value is None or str(value).strip() == "":
        return default
    return float(value)


def quaternion_wxyz_to_rpy(q: tuple[float, float, float, float] | list[float]) -> tuple[float, float, float]:
    w, x, y, z = q
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        pitch = math.copysign(math.pi / 2.0, sinp)
    else:
        pitch = math.asin(sinp)

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)
    return roll, pitch, yaw


def _wrap_rad(value: float) -> float:
    wrapped = (value + math.pi) % (2.0 * math.pi) - math.pi
    if wrapped == math.pi:
        return -math.pi
    return wrapped


def check_quaternion_rpy_consistency(row: dict[str, Any]) -> dict[str, Any]:
    quat = [
        _as_float(row.get("quat_w", row.get("quat_0"))),
        _as_float(row.get("quat_x", row.get("quat_1"))),
        _as_float(row.get("quat_y", row.get("quat_2"))),
        _as_float(row.get("quat_z", row.get("quat_3"))),
    ]
    norm = math.sqrt(sum(value * value for value in quat))
    if norm <= 0.0:
        return {
            "quaternion_rpy_consistency_status": "evidence_missing",
            "max_quat_rpy_delta_rad": None,
        }
    quat = [value / norm for value in quat]
    roll, pitch, yaw = quaternion_wxyz_to_rpy(quat)
    deltas = [
        abs(_wrap_rad(roll - _as_float(row.get("roll_rad")))),
        abs(_wrap_rad(pitch - _as_float(row.get("pitch_rad")))),
        abs(_wrap_rad(yaw - _as_float(row.get("yaw_rad")))),
    ]
    max_delta = max(deltas)
    return {
        "quaternion_rpy_consistency_status": "passed"
        if max_delta < 0.05
        else "suspicious",
        "max_quat_rpy_delta_rad": max_delta,
    }


def accel_norm(row: dict[str, Any]) -> float:
    return math.sqrt(
        _as_float(row.get("acc_x")) ** 2
        + _as_float(row.get("acc_y")) ** 2
        + _as_float(row.get("acc_z")) ** 2
    )


def gyro_norm(row: dict[str, Any]) -> float:
    return math.sqrt(
        _as_float(row.get("gyro_x")) ** 2
        + _as_float(row.get("gyro_y")) ** 2
        + _as_float(row.get("gyro_z")) ** 2
    )


def foot_speed_body_norm(row: dict[str, Any]) -> float:
    return math.sqrt(
        sum(_as_float(row.get(f"foot_speed_body_{index}")) ** 2 for index in range(12))
    )


def foot_force_delta(prev: dict[str, Any] | None, cur: dict[str, Any]) -> float:
    if prev is None:
        return 0.0
    return math.sqrt(
        sum(
            (
                _as_float(cur.get(f"foot_force_{index}"))
                - _as_float(prev.get(f"foot_force_{index}"))
            )
            ** 2
            for index in range(4)
        )
    )


def make_unitree_imu_semantics_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    checks = [check_quaternion_rpy_consistency(row) for row in rows]
    max_delta_values = [
        item["max_quat_rpy_delta_rad"]
        for item in checks
        if item["max_quat_rpy_delta_rad"] is not None
    ]
    suspicious = sum(
        1 for item in checks if item["quaternion_rpy_consistency_status"] == "suspicious"
    )
    status = "passed" if checks and suspicious == 0 else "suspicious"
    accel_values = [accel_norm(row) for row in rows]
    gyro_values = [gyro_norm(row) for row in rows]
    return {
        "quaternion_order": "wxyz",
        "gyro_unit": "rad_per_sec",
        "accel_unit": "m_per_s2",
        "accel_contains_gravity": True,
        "rpy_order": "roll_pitch_yaw",
        "rpy_unit": "rad",
        "go2_body_frame": "FLU",
        "sportmodestate_position_frame": "go2_odom",
        "sportmodestate_velocity_frame": "go2_odom_or_body_evidence_missing",
        "foot_position_body_frame": "body_relative",
        "foot_speed_body_frame": "body_relative",
        "source_role": "go2_body_state_diagnostic",
        "quaternion_rpy_consistency_status": status if rows else "evidence_missing",
        "max_quat_rpy_delta_rad": max(max_delta_values) if max_delta_values else None,
        "rows_checked": len(rows),
        "accel_norm_initial_mps2": accel_values[0] if accel_values else None,
        "accel_norm_max_mps2": max(accel_values) if accel_values else None,
        "gyro_norm_max_radps": max(gyro_values) if gyro_values else None,
        "position_velocity_navigation_measurement": False,
        "foot_position_body_as_leg_odometry_factor": False,
        "go2_prior_claim": False,
        "evidence_status": "unitree_imu_semantics_diagnostic",
    }

