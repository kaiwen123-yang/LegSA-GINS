from legsa_gins.source_aware.source_aware_ablation_matrix import (
    REQUIRED_VARIANT_IDS,
    build_n6a_source_aware_ablation_matrix,
)


def test_source_aware_ablation_matrix_contains_required_variants(tmp_path):
    # 中文说明：矩阵必须包含 clean、stress 和 spike sentinel 诊断组合。
    report = build_n6a_source_aware_ablation_matrix(tmp_path / "RAW_DOPPLER_VELOCITY_FACTORS.csv", tmp_path)
    found = {row["variant_id"] for row in report["matrix"]}
    assert set(REQUIRED_VARIANT_IDS).issubset(found)
    assert report["no_R_shrink"] is True
    assert report["paper_performance_claim"] is False
