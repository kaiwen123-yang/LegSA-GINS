"""中文说明：IMU txt builder 测试 process_imu parity，不声明 formal mechanization。"""

import math

from legsa_gins.input_generation.imu_txt_builder import build_process_data_imu_rows


def _write_body(path, base_time):
    messages = []
    for index in range(3):
        stamp = base_time + index * 0.01
        secs = int(stamp)
        nsecs = int(round((stamp - secs) * 1.0e9))
        messages.append(
            "\n".join(
                [
                    "stamp:",
                    f"  sec: {secs}",
                    f"  nanosec: {nsecs}",
                    "imu_state:",
                    "  gyroscope: [0.0, 0.0, 0.0]",
                    "  accelerometer: [1.0, 2.0, -3.0]",
                ]
            )
        )
    path.write_text("\n---\n".join(messages) + "\n", encoding="utf-8")


def test_process_data_imu_rows_flu_to_frd_and_report(tmp_path):
    base_time = 1772784000.0
    body = tmp_path / "by2.txt"
    _write_body(body, base_time)

    rows, report = build_process_data_imu_rows(
        body,
        base_time=base_time,
        imu_install_roll_deg=0.0,
        imu_install_pitch_deg=0.0,
        imu_install_yaw_deg=0.0,
    )

    assert len(rows) == 2
    assert set(["time", "dtheta_x", "dtheta_y", "dtheta_z", "dvel_x", "dvel_y", "dvel_z"]).issubset(rows[0])
    assert math.isclose(rows[0]["dvel_x"], 0.01, abs_tol=1e-7)
    assert math.isclose(rows[0]["dvel_y"], -0.02, abs_tol=1e-7)
    assert math.isclose(rows[0]["dvel_z"], 0.03, abs_tol=1e-7)
    assert report["receiver_imu_as_body_imu"] is False
    assert report["flu_to_frd_applied_once"] is True
    assert report["gyro_bias_window"] == 3
