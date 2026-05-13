"""中文说明：单元测试覆盖 N7C5 contact probability 作为权重/候选审查。"""

from legsa_gins.go2_prior.go2_contact_probability_factor_review import build_go2_contact_probability_factor_review


def test_contact_probability_review_prefers_probability_weighting():
    rows = [
        {
            "time": index * 0.1,
            "support_probability": 0.8,
            "swing_probability": 0.2,
            "uncertainty_probability": 0.1,
            "alternating_contact_hint": 0.8,
            "hard_contact_count": 4,
            **{f"foot_{foot}_contact_probability": 0.8 for foot in range(4)},
        }
        for index in range(5)
    ]
    report = build_go2_contact_probability_factor_review(rows)
    assert report["usable_as_weight"] is True
    assert report["usable_as_factor"] is True
    assert report["contact_truth_claim"] is False
    assert report["no_hard_threshold_default"] is True
