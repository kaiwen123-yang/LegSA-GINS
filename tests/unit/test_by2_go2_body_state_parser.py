"""中文说明：Go2 body-state parser 测试只验证 diagnostic 解析，不构造导航量或 Go2 prior。
"""

from legsa_gins.datasets.by2.go2_body_state_parser import parse_go2_body_state_text


TOY_BODY_TEXT = """
stamp:
  sec: 1700000000
  nanosec: 250000000
error_code: 0
imu_state:
  quaternion:
  - 1.0
  - 0.0
  - 0.0
  - 0.0
  gyroscope:
  - 0.1
  - 0.2
  - 0.3
  accelerometer:
  - 1.0
  - 2.0
  - 3.0
  rpy:
  - 0.01
  - 0.02
  - 0.03
  temperature: 38.0
mode: 1
gait_type: 2
foot_raise_height: 0.05
position:
- 1.0
- 2.0
- 3.0
velocity:
- 0.1
- 0.2
- 0.3
yaw_speed: 0.4
foot_force:
- 10
- 20
- 30
- 40
foot_position_body:
- 0
- 1
- 2
- 3
- 4
- 5
- 6
- 7
- 8
- 9
- 10
- 11
foot_speed_body:
- 0.0
- 0.1
- 0.2
- 0.3
- 0.4
- 0.5
- 0.6
- 0.7
- 0.8
- 0.9
- 1.0
- 1.1
---
"""


def test_parse_go2_body_state_diagnostic_fields(tmp_path):
    path = tmp_path / "by2.txt"
    path.write_text(TOY_BODY_TEXT, encoding="utf-8")

    rows = parse_go2_body_state_text(path)
    row = rows[0]

    assert row["timestamp"] == 1700000000.25
    assert row["yaw_speed_radps"] == 0.4
    assert row["foot_force_0"] == 10
    assert row["foot_position_body_11"] == 11
    assert row["foot_speed_body_11"] == 1.1
    assert row["source_role"] == "go2_body_state_diagnostic"
    assert row["position_velocity_navigation_measurement"] is False
    assert row["frame_adapter_required"] is True
