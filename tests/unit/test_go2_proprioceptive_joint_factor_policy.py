"""Unit tests for N7C6 joint factor policy matrix.

中文说明：测试 N7C6 joint factor 变体矩阵完整性。
"""

from pathlib import Path

from legsa_gins.go2_prior.go2_proprioceptive_joint_factor_policy import build_n7c6_joint_factor_matrix


def test_joint_factor_policy_matrix_has_required_variants(tmp_path: Path):
    prior_paths = {
        name: {"joint": tmp_path / name / "joint.csv", "attitude": tmp_path / name / "att.csv", "horizontal": tmp_path / name / "hv.csv"}
        for name in [
            "joint_rp5deg_hv1p0",
            "joint_rp3deg_hv1p0",
            "joint_rp1p6deg_hv1p0",
            "joint_rp1deg_hv1p0",
            "joint_rp0p75_hv1p0_diagnostic",
            "joint_rp1p6deg_hv0p75_diagnostic",
        ]
    }
    matrix = build_n7c6_joint_factor_matrix(output_dir=tmp_path, raw_doppler_factor_path=tmp_path / "raw.csv", prior_paths=prior_paths)
    assert matrix["required_variants_present"] is True
    assert matrix["go2_position_prior_enabled"] is False
    assert matrix["sequential_equivalent"] is True
