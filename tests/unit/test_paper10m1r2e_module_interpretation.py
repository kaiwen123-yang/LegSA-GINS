from scripts.paper10m1r2e_result_review import classify_module


def classify(removed_module, median="0", help_count="0", hurt_count="0", same="541", tradeoff="0"):
    return classify_module(
        {
            "removed_module": removed_module,
            "median_delta_horizontal_rmse_m": median,
            "module_help_count": help_count,
            "module_hurt_count": hurt_count,
            "same_order_count": same,
            "metric_tradeoff_count": tradeoff,
        }
    )


def test_zero_delta_modules_are_not_claimable_as_effective():
    joint = classify("go2_joint_factor")
    feedback = classify("fgo_feedback_or_ekf_only_alias")
    assert joint["interpretation_label"] == "neutral_no_effect"
    assert "no_measured_delta" in joint["claim_strength"]
    assert feedback["interpretation_label"] == "alias_or_duplicate"
    assert "alias" in feedback["claim_strength"]


def test_qm_is_tradeoff_not_universal_improvement():
    qm = classify("multi_state_qm", median="-0.007258874", help_count="44", hurt_count="497", same="0", tradeoff="47")
    assert qm["interpretation_label"] == "tradeoff"
    assert qm["claim_strength"] == "mechanism_evidence_metric_tradeoff"


def test_raw_doppler_is_weak_positive():
    raw = classify("raw_doppler", median="0.000639087", help_count="497", hurt_count="42", same="2", tradeoff="431")
    assert raw["interpretation_label"] == "weak_positive_evidence"
    assert raw["claim_strength"] == "weak_bounded_auxiliary"
