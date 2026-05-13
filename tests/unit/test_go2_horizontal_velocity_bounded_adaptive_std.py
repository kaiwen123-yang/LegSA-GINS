"""中文说明：单元测试覆盖 Go2 水平速度有界自适应标准差策略。"""

from legsa_gins.go2_prior.go2_horizontal_velocity_bounded_adaptive_std import (
    STD_VD_DISABLED,
    bounded_std_for_confidence,
    build_bounded_adaptive_go2_horizontal_velocity_priors,
)


def test_bounded_std_policy_never_uses_8_or_10_mps():
    assert bounded_std_for_confidence(0.9)[:2] == (1.0, True)
    assert bounded_std_for_confidence(0.7)[:2] == (1.5, True)
    assert bounded_std_for_confidence(0.4)[:2] == (2.5, True)
    assert bounded_std_for_confidence(0.2)[:2] == (4.0, True)
    assert bounded_std_for_confidence(0.1)[:2] == (5.0, False)


def test_bounded_adaptive_rows_cap_horizontal_and_disable_vertical():
    source = [{"time": index, "vn": 0.1, "ve": 0.2, "vd": 99.0} for index in range(5)]
    confidence = [
        {"time": index, "confidence": value, "confidence_level": level, "reason_codes": "toy"}
        for index, (value, level) in enumerate([(0.9, "high"), (0.7, "medium"), (0.4, "low"), (0.2, "low"), (0.1, "invalid")])
    ]
    rows, report = build_bounded_adaptive_go2_horizontal_velocity_priors(source_prior_rows=source, confidence_rows=confidence)
    assert max(float(row["std_vn"]) for row in rows) <= 5.0
    assert max(float(row["std_ve"]) for row in rows) <= 5.0
    assert not any(float(row["std_vn"]) in {8.0, 10.0} for row in rows)
    assert all(row["vd"] == 0.0 for row in rows)
    assert all(row["std_vd"] == STD_VD_DISABLED for row in rows)
    assert rows[-1]["update_flag"] == "false"
    assert report["max_std_le_5"] is True
    assert report["contains_8_or_10_mps_std"] is False
