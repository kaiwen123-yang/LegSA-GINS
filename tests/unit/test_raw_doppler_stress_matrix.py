from legsa_gins.raw_gnss.raw_doppler_stress_matrix import REQUIRED_VARIANT_IDS, build_n5d_stress_matrix


def test_n5d_required_stress_variants_and_flags(tmp_path):
    # 中文说明：stress matrix 只定义诊断组合，不产生 paper/proposed claim。
    report = build_n5d_stress_matrix(tmp_path / "factor.csv", tmp_path)
    rows = {row["variant_id"]: row for row in report["matrix"]}
    assert set(REQUIRED_VARIANT_IDS).issubset(rows)
    assert rows["baseline_full"]["receiver_velocity_stress_mode"] == "none"
    assert rows["receiver_velocity_disabled_plus_raw"]["receiver_velocity_stress_mode"] == "disabled"
    assert rows["receiver_velocity_std_scale_5_plus_raw"]["receiver_velocity_std_scale"] == 5.0
    assert rows["receiver_velocity_noise_0p5_plus_raw"]["receiver_velocity_additive_noise_seed"] == 20260510
    assert rows["baseline_plus_raw_doppler_r1"]["proposed_factor_diagnostic_evidence"] is True
    assert all(row["paper_performance_claim"] is False for row in rows.values())
    assert all(row["proposed_factor_claim"] is False for row in rows.values())
