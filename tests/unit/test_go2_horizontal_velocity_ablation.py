"""N7C ablation matrix unit tests.

中文说明：单测只验证矩阵边界和 variant 覆盖，不运行真实 replay。
"""

from pathlib import Path

from legsa_gins.go2_prior.go2_horizontal_velocity_ablation import (
    REQUIRED_N7C_VARIANT_IDS,
    build_n7c_go2_horizontal_velocity_ablation_matrix,
)


def test_n7c_ablation_matrix_contains_required_variants(tmp_path):
    prior_paths = {
        "main": tmp_path / "main.csv",
        "probability_weighted": tmp_path / "prob.csv",
        "contact_weighted": tmp_path / "contact.csv",
        "high_confidence_only": tmp_path / "high.csv",
    }
    matrix = build_n7c_go2_horizontal_velocity_ablation_matrix(
        output_dir=tmp_path,
        raw_doppler_factor_path=Path("RAW_DOPPLER_VELOCITY_FACTORS.csv"),
        prior_paths=prior_paths,
        run_stress=True,
    )
    ids = {row["variant_id"] for row in matrix["matrix"]}
    assert all(item in ids for item in REQUIRED_N7C_VARIANT_IDS)
    main = next(row for row in matrix["matrix"] if row["variant_id"] == "go2_horizontal_velocity_weak_prior_main")
    assert main["enable_go2_horizontal_velocity_prior"] is True
    assert main["go2_horizontal_velocity_prior_vertical_disabled"] is True
    assert main["go2_yaw_prior_enabled"] is False
    assert main["go2_position_prior_enabled"] is False
    assert matrix["paper_performance_claim"] is False
