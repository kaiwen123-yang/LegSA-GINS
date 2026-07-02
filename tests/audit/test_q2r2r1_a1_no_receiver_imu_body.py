from pathlib import Path


def test_a1_receiver_imu_is_not_body_imu():
    text = Path("scripts/experiments/run_paper10q2r2r1_a1_dual_matrix.py").read_text(encoding="utf-8")
    assert "receiver_imu_as_body_imu" in text
    assert '"receiver_imu_as_body_imu": "false"' in text
    assert '"receiver_imu_as_body_imu": "true"' not in text
