"""中文说明：单元测试覆盖 N7C3 有界自适应策略的消融矩阵契约。"""

from pathlib import Path

from legsa_gins.go2_prior.go2_horizontal_velocity_adaptive_ablation import (
    REQUIRED_N7C3_VARIANT_IDS,
    build_n7c3_bounded_adaptive_ablation_matrix,
)


def test_n7c3_ablation_matrix_has_required_variants_and_boundaries(tmp_path: Path):
    paths = {
        "fixed_std_2mps": tmp_path / "fixed.csv",
        "bounded_adaptive": tmp_path / "adaptive.csv",
        "high_confidence_only": tmp_path / "high.csv",
        "probability_weighted_original": tmp_path / "original.csv",
    }
    matrix = build_n7c3_bounded_adaptive_ablation_matrix(
        output_dir=tmp_path,
        raw_doppler_factor_path=tmp_path / "raw.csv",
        prior_paths=paths,
    )
    ids = [row["variant_id"] for row in matrix["matrix"]]
    assert ids == REQUIRED_N7C3_VARIANT_IDS
    assert matrix["required_variants_present"] is True
    assert all(row["go2_position_prior_enabled"] is False for row in matrix["matrix"])
    assert all(row["go2_yaw_prior_enabled"] is False for row in matrix["matrix"])
    assert all(row["go2_horizontal_velocity_bounded_std_policy"] == "n7c3_bounded_adaptive_std_soft_gating" for row in matrix["matrix"])
