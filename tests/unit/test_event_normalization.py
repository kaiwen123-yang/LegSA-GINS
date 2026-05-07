"""中文说明：event normalization 测试 kick 与 formal start 分离。"""

import csv

from legsa_gins.experiments.by2_filter_trial import convert_go2_body_state_to_imu_increments
from legsa_gins.time_alignment.event_normalization import (
    detect_go2_formal_motion_start,
    detect_go2_kick_event,
    normalize_time_axis,
)


def test_kick_is_not_formal_start_and_algo_time_is_own_zero(tmp_path):
    path = tmp_path / "go2.csv"
    fields = [
        "timestamp",
        "gyro_x",
        "gyro_y",
        "gyro_z",
        "acc_x",
        "acc_y",
        "acc_z",
        "go2_velocity_0",
        "go2_velocity_1",
        "go2_velocity_2",
        "yaw_speed_radps",
        *[f"foot_force_{i}" for i in range(4)],
        *[f"foot_speed_body_{i}" for i in range(12)],
        "mode",
        "gait_type",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(20):
            moving = index >= 8
            row = {field: 0.0 for field in fields}
            row["timestamp"] = 1.7e9 + index * 0.1
            row["acc_z"] = 9.80665
            row["gyro_z"] = 2.0 if index == 3 else (0.1 if moving else 0.0)
            row["acc_x"] = 8.0 if index == 3 else 0.0
            row["go2_velocity_0"] = 0.05 if moving else 0.0
            row["yaw_speed_radps"] = 0.08 if moving else 0.0
            row["mode"] = 2 if moving else 1
            row["gait_type"] = 1 if moving else 0
            for foot in range(12):
                row[f"foot_speed_body_{foot}"] = 0.1 if moving else 0.0
            writer.writerow(row)

    kick = detect_go2_kick_event(path)
    formal = detect_go2_formal_motion_start(path, kick)

    assert formal["go2_formal_start_raw_time"] > kick["go2_kick_raw_time"]
    assert normalize_time_axis(formal["go2_formal_start_raw_time"], formal["go2_formal_start_raw_time"]) == 0.0
    assert "go2_to_gnss_offset_sec" not in formal


def test_imu_increment_modes_zero_and_gravity_compensated(tmp_path):
    path = tmp_path / "go2_algo.csv"
    fields = [
        "timestamp",
        "raw_time",
        "algo_time_sec",
        "quat_w",
        "quat_x",
        "quat_y",
        "quat_z",
        "gyro_x",
        "gyro_y",
        "gyro_z",
        "acc_x",
        "acc_y",
        "acc_z",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for index in range(3):
            writer.writerow(
                {
                    "timestamp": index * 0.1,
                    "raw_time": 1.7e9 + index * 0.1,
                    "algo_time_sec": index * 0.1,
                    "quat_w": 1.0,
                    "quat_x": 0.0,
                    "quat_y": 0.0,
                    "quat_z": 0.0,
                    "gyro_x": 0.0,
                    "gyro_y": 0.0,
                    "gyro_z": 0.1,
                    "acc_x": 1.0,
                    "acc_y": 0.0,
                    "acc_z": 9.80665,
                }
            )

    zero_csv = tmp_path / "zero.csv"
    quat_csv = tmp_path / "quat.csv"
    convert_go2_body_state_to_imu_increments(path, zero_csv, imu_propagation_mode="gyro_only_zero_dvel")
    convert_go2_body_state_to_imu_increments(path, quat_csv, imu_propagation_mode="quaternion_gravity_compensated")

    zero_rows = list(csv.DictReader(zero_csv.open(encoding="utf-8")))
    quat_rows = list(csv.DictReader(quat_csv.open(encoding="utf-8")))
    assert all(float(row["dvel_x"]) == 0.0 and float(row["dvel_y"]) == 0.0 and float(row["dvel_z"]) == 0.0 for row in zero_rows)
    assert any(float(row["dvel_z"]) != -9.80665 * 0.1 for row in quat_rows)
