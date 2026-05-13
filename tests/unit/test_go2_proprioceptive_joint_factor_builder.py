"""Unit tests for N7C6 joint factor builder.

中文说明：测试 roll/pitch + 水平速度联合观测 CSV 构造。
"""

from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_builder import build_joint_factor_rows


def test_joint_factor_builder_outputs_4d_observation_rows():
    joint, attitude, velocity = build_joint_factor_rows(
        go2_rows=[{"time": 0.0, "aligned_time": 0.0, "roll_rad": 0.01, "pitch_rad": -0.01}],
        horizontal_rows=[{"time": 0.0, "vn": 1.0, "ve": 0.2}],
        std_roll_pitch_deg=1.6,
        std_vn_ve=1.0,
        policy_name="joint_rp1p6deg_hv1p0",
    )
    assert joint and attitude and velocity
    assert set(["roll_rad", "pitch_rad", "vn", "ve"]).issubset(joint[0])
    assert joint[0]["std_vd"] == 999.0
    assert joint[0]["go2_truth_claim"] == "false"
