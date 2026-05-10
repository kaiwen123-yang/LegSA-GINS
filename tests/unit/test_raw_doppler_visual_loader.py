import csv

from legsa_gins.raw_gnss.raw_doppler_visual_loader import load_n5d_visual_inputs


def test_loader_preserves_source_flags_and_n5c_reports(tmp_path):
    # 中文说明：clean .gnss velocity 只能作为对照，source flags 必须保持禁止替代。
    factor = tmp_path / "factor.csv"
    with factor.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd", "sat_count", "provider_status"])
        writer.writeheader()
        writer.writerow({"time": 1, "vn": 1, "ve": 0, "vd": 0, "std_vn": 0.2, "std_ve": 0.2, "std_vd": 0.2, "sat_count": 8, "provider_status": "available"})
    clean = tmp_path / "clean"
    clean.mkdir()
    (clean / "clean.gnss").write_text("1 0 0 0 0 0 0 1.1 0 0 0 0 0 0 0\n", encoding="utf-8")
    n5c = tmp_path / "n5c"
    n5c.mkdir()
    (n5c / "RAW_DOPPLER_VELOCITY_COMPARISON_REPORT.json").write_text('{"possible_pvt_velocity_copy_suspect": false}\n', encoding="utf-8")
    data = load_n5d_visual_inputs(factor_csv=factor, clean_root=clean, n5c_root=n5c, variant_reports=[])
    assert data["source_flags"]["raw_doppler_not_nav_pvt"] is True
    assert data["source_flags"]["raw_doppler_not_gnss_15col"] is True
    assert data["velocity_comparison"]["possible_pvt_velocity_copy_suspect"] is False
    assert len(data["raw_receiver_velocity_pairs"]) == 1
