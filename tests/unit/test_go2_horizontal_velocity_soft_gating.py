"""中文说明：单元测试覆盖有界自适应 Go2 水平速度先验的软门控报告。"""

from legsa_gins.go2_prior.go2_horizontal_velocity_soft_gating import build_go2_horizontal_velocity_soft_gating_report


def test_soft_gating_updates_low_confidence_and_skips_invalid():
    rows = [
        {"confidence_level": "high", "update_flag": "true", "source_status": "active", "std_vn": 1.0, "std_ve": 1.0},
        {"confidence_level": "medium", "update_flag": "true", "source_status": "active", "std_vn": 1.5, "std_ve": 1.5},
        {"confidence_level": "low", "update_flag": "true", "source_status": "active", "std_vn": 4.0, "std_ve": 4.0},
        {"confidence_level": "invalid", "update_flag": "false", "source_status": "inactive", "std_vn": 5.0, "std_ve": 5.0},
    ]
    report = build_go2_horizontal_velocity_soft_gating_report(rows)
    assert report["update_count_expected"] == 3
    assert report["skip_count"] == 1
    assert report["soft_gated_count"] == 1
    assert report["max_std_le_5"] is True
    assert report["vertical_disabled"] is True
