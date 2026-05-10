from legsa_gins.raw_gnss.raw_doppler_ablation_matrix import build_n5c_ablation_matrix


def test_required_variants_and_flags(tmp_path):
    # 中文说明：只有 r1 baseline+raw Doppler 是 proposed-candidate diagnostic row。
    report = build_n5c_ablation_matrix(tmp_path / "factor.csv", tmp_path)
    rows = {row["variant_id"]: row for row in report["matrix"]}
    assert set(rows) == {
        "baseline_full",
        "baseline_plus_raw_doppler_r1",
        "position_yaw_plus_raw_doppler_r1",
        "position_yaw_only",
        "baseline_plus_raw_doppler_r0p5",
        "baseline_plus_raw_doppler_r2",
        "baseline_plus_raw_doppler_r5",
    }
    assert rows["baseline_plus_raw_doppler_r1"]["proposed_candidate"] is True
    assert all(row["proposed_candidate"] == (name == "baseline_plus_raw_doppler_r1") for name, row in rows.items())
    assert rows["position_yaw_plus_raw_doppler_r1"]["diagnostic_only"] is True
    assert rows["baseline_plus_raw_doppler_r0p5"]["diagnostic_only"] is True
    assert report["paper_performance_claim"] is False
