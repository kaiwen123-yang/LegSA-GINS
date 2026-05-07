"""中文说明：Unitree IMU 语义测试只验证 wxyz/rpy/重力字段。"""

from legsa_gins.datasets.by2.unitree_imu_semantics import (
    check_quaternion_rpy_consistency,
    make_unitree_imu_semantics_report,
    quaternion_wxyz_to_rpy,
)


def test_quaternion_wxyz_matches_rpy_and_accel_gravity_semantics():
    roll, pitch, yaw = quaternion_wxyz_to_rpy([1.0, 0.0, 0.0, 0.0])
    assert roll == 0.0
    assert pitch == 0.0
    assert yaw == 0.0

    row = {
        "quat_w": 1.0,
        "quat_x": 0.0,
        "quat_y": 0.0,
        "quat_z": 0.0,
        "roll_rad": 0.0,
        "pitch_rad": 0.0,
        "yaw_rad": 0.0,
        "acc_x": 0.0,
        "acc_y": 0.0,
        "acc_z": 9.80665,
    }
    assert check_quaternion_rpy_consistency(row)["quaternion_rpy_consistency_status"] == "passed"
    report = make_unitree_imu_semantics_report([row])
    assert report["quaternion_order"] == "wxyz"
    assert report["accel_contains_gravity"] is True
    assert report["go2_body_frame"] == "FLU"

