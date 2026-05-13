"""中文说明：单元测试覆盖 N7C4 强度扫描消融矩阵。"""

from pathlib import Path

from legsa_gins.go2_prior.go2_horizontal_velocity_strength_ablation import (
    REQUIRED_N7C4_VARIANT_IDS,
    build_n7c4_strength_ablation_matrix,
)


def test_strength_ablation_matrix_has_required_variants(tmp_path: Path):
    prior_paths = {
        "fixed_std_2p0": tmp_path / "2.csv",
        "fixed_std_1p5": tmp_path / "15.csv",
        "fixed_std_1p0": tmp_path / "1.csv",
        "fixed_std_0p75_aggressive": tmp_path / "075.csv",
        "recalibrated_adaptive": tmp_path / "a.csv",
        "recalibrated_adaptive_aggressive": tmp_path / "aa.csv",
    }
    matrix = build_n7c4_strength_ablation_matrix(output_dir=tmp_path, raw_doppler_factor_path=tmp_path / "raw.csv", prior_paths=prior_paths)
    found = {row["variant_id"] for row in matrix["matrix"]}
    assert all(variant_id in found for variant_id in REQUIRED_N7C4_VARIANT_IDS)
    assert matrix["go2_vertical_velocity_prior_enabled"] is False
