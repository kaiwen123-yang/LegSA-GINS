"""中文说明：quaternion/rpy 检查只验证内部一致性，不做 truth 选择。"""

from legsa_gins.go2_state.go2_quaternion_rpy_check import check_quaternion_rpy


def test_go2_quaternion_rpy_wxyz_passes():
    report = check_quaternion_rpy(
        [
            {
                "quat_w": "1.0",
                "quat_x": "0.0",
                "quat_y": "0.0",
                "quat_z": "0.0",
                "roll_rad": "0.0",
                "pitch_rad": "0.0",
                "yaw_rad": "0.0",
            }
        ]
    )
    assert report["quaternion_order_selected"] == "wxyz"
    assert report["rpy_consistency_status"] == "passed"
    assert report["activation_allowed_for_attitude_prior"] is True
