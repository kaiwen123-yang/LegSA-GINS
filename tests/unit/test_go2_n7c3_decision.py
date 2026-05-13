"""中文说明：单元测试覆盖 N7C3 决策状态与边界声明。"""

from legsa_gins.go2_prior.go2_n7c3_decision import make_n7c3_decision


def _std(**override):
    data = {"max_std_le_5": True, "std_vn_max": 4.0, "std_ve_max": 4.0, "std_vn_p50": 2.5, "std_vn_p95": 4.0, "std_ve_p50": 2.5, "std_ve_p95": 4.0}
    data.update(override)
    return data


def _soft(**override):
    data = {"update_count_expected": 10, "skip_count": 2, "soft_gated_count": 5}
    data.update(override)
    return data


def _comparison(clean_delta=0.0, stress_delta=0.0):
    return {
        "bounded_adaptive_manifest": {"go2_horizontal_velocity_prior_update_count": 10},
        "comparisons": {
            "bounded_adaptive_minus_fixed_clean": {"delta": {"horizontal_rmse_m": clean_delta}},
            "receiver_velocity_stress_bounded_adaptive_minus_fixed": {"delta": {"horizontal_rmse_m": stress_delta}},
            "raw_doppler_stress_bounded_adaptive_minus_fixed": {"delta": {"horizontal_rmse_m": stress_delta}},
        },
    }


def test_decision_blocks_std_above_physical_bound():
    decision = make_n7c3_decision(std_report=_std(max_std_le_5=False, std_vn_max=8.0), soft_gating_report=_soft(), comparison_report=_comparison(), figure_manifest={})
    assert decision["status"] == "policy_failed_physical_bound"


def test_decision_ready_when_clean_neutral_and_stress_improves():
    decision = make_n7c3_decision(std_report=_std(), soft_gating_report=_soft(), comparison_report=_comparison(clean_delta=0.01, stress_delta=-0.2), figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True})
    assert decision["status"] == "bounded_adaptive_policy_ready_for_N8A"
    assert decision["go2_velocity_truth_claim"] is False
    assert decision["fgo"] is False


def test_decision_marks_fixed_sufficient_when_no_benefit_no_degradation():
    decision = make_n7c3_decision(std_report=_std(), soft_gating_report=_soft(), comparison_report=_comparison(clean_delta=0.0, stress_delta=0.0), figure_manifest={})
    assert decision["status"] == "fixed_std_policy_sufficient_bounded_adaptive_optional"
