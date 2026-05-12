"""中文说明：N7B orchestration 保持 velocity/yaw prior disabled。"""

from legsa_gins.go2_prior.go2_contact_velocity_readiness import run_go2_contact_velocity_readiness


def test_go2_contact_velocity_readiness_bundle(tmp_path):
    rows = []
    for i in range(12):
        rows.append(
            {
                "aligned_time": float(i),
                "mode": "walk",
                "gait_type": 1,
                "go2_velocity_0": 0.4,
                "go2_velocity_1": 0.0,
                "go2_velocity_2": 0.0,
                "yaw_rad": i * 0.1,
                "yaw_speed_radps": 0.1,
                **{f"foot_force_{foot}": 25.0 for foot in range(4)},
                **{f"foot_speed_body_{axis}": 0.04 for axis in range(12)},
            }
        )
    receiver = [{"time": float(i), "vn": 0.4, "ve": 0.0, "vd": 0.0} for i in range(12)]
    raw = [{"time": float(i), "vn": 0.4, "ve": 0.0, "vd": 0.0} for i in range(12)]
    bundle = run_go2_contact_velocity_readiness(
        go2_rows=rows,
        receiver_velocity_rows=receiver,
        raw_doppler_rows=raw,
        output_dir=tmp_path,
        n7a_weak_prior_report={"activation_allowed": True},
    )
    assert bundle["decision"]["go2_velocity_prior_enabled"] is False
    assert bundle["decision"]["go2_yaw_prior_enabled"] is False
    assert (tmp_path / "GO2_CONTACT_STATE_REPORT.json").exists()
