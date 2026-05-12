"""中文说明：N7A parser 测试只用 toy sportmodestate，不读取真实 by2.txt。"""

from pathlib import Path

from legsa_gins.go2_state.go2_body_state_parser import standardize_go2_body_state


SAMPLE = """stamp:
  sec: 100
  nanosec: 500000000
imu_state:
  quaternion: [1.0, 0.0, 0.0, 0.0]
  gyroscope: [0.1, 0.2, 0.3]
  accelerometer: [0.0, 0.0, 9.8]
  rpy: [0.0, 0.0, 0.0]
  temperature: 32.0
mode: 1
gait_type: 2
foot_raise_height: 0.05
position: [1.0, 2.0, 0.3]
body_height: 0.28
velocity: [0.1, 0.0, 0.0]
yaw_speed: 0.4
foot_force: [10, 20, 30, 40]
foot_position_body: [0,0,0,0,0,0,0,0,0,0,0,0]
foot_speed_body: [0,0,0,0,0,0,0,0,0,0,0,0]
"""


def test_go2_body_state_parser_reports_not_truth(tmp_path: Path):
    path = tmp_path / "by2.txt"
    path.write_text(SAMPLE, encoding="utf-8")
    rows, report = standardize_go2_body_state(path, base_time=100.0)
    assert len(rows) == 1
    assert rows[0]["aligned_time"] == 0.5
    assert report["row_count"] == 1
    assert report["quaternion_found"] is True
    assert report["position_found"] is True
    assert report["not_truth"] is True
    assert report["source_role"] == "go2_body_state_internal_odometry_and_imu_state"
