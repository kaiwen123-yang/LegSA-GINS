from legsa_gins.source_aware.source_aware_n6b_ablation_matrix import (
    REQUIRED_N6B_VARIANT_IDS,
    build_n6b_source_aware_ablation_matrix,
)


def test_n6b_ablation_matrix_contains_required_variants(tmp_path):
    # 中文说明：矩阵必须包含 clean、stress 和 spike-response 事后审计组合。
    matrix = build_n6b_source_aware_ablation_matrix(tmp_path / "RAW_DOPPLER_VELOCITY_FACTORS.csv", tmp_path)
    found = {row["variant_id"] for row in matrix["matrix"]}
    assert set(REQUIRED_N6B_VARIANT_IDS).issubset(found)
    assert matrix["paper_performance_claim"] is False
    assert matrix["main_candidate_variant"] == "n6b_lsim_oim"
