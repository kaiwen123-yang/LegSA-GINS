from pathlib import Path


def test_q2r2_receiver_imu_forbidden_as_go2_body_imu():
    text = Path("src/legsa_gins/external_dual_methods/by2_dual_provider_factory.py").read_text(encoding="utf-8")
    assert "forbidden as Go2 body IMU" in text
    assert '"receiver_imu_as_body_imu": "false"' in text
