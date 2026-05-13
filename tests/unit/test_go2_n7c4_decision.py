"""中文说明：单元测试覆盖 N7C4 强度校准决策规则。"""

from legsa_gins.go2_prior.go2_n7c4_decision import make_n7c4_strength_decision


def _comparison(delta_1p0=0.0, delta_1p5=0.0, adaptive_delta=0.0):
    zero = {"horizontal_rmse_m": 0.0, "up_rmse_m": 0.0, "yaw_rmse_deg": 0.0, "roll_rmse_deg": 0.0, "pitch_rmse_deg": 0.0}
    one = dict(zero, horizontal_rmse_m=delta_1p0)
    one5 = dict(zero, horizontal_rmse_m=delta_1p5)
    adaptive = dict(zero, horizontal_rmse_m=adaptive_delta)
    return {
        "comparisons": {
            "fixed_1p0_minus_fixed_2p0_clean": {"delta": one},
            "fixed_1p5_minus_fixed_2p0_clean": {"delta": one5},
            "recalibrated_adaptive_minus_fixed_2p0_clean": {"delta": adaptive},
            "receiver_velocity_stress_adaptive_minus_fixed_2p0": {"delta": dict(zero, horizontal_rmse_m=0.0)},
            "raw_doppler_stress_adaptive_minus_fixed_2p0": {"delta": dict(zero, horizontal_rmse_m=0.0)},
        },
        "candidate_manifests": {"fixed_2p0": {"go2_horizontal_velocity_prior_update_count": 10}, "fixed_1p0": {"go2_horizontal_velocity_prior_update_count": 10}},
    }


def test_n7c4_decision_prefers_fixed_1p0_when_clean_and_not_overconfident():
    nis = {"variants": {"fixed_1p0": {"overconfidence_status": "not_overconfident"}, "fixed_1p5": {"overconfidence_status": "not_overconfident"}, "recalibrated_adaptive": {"overconfidence_status": "not_overconfident"}}}
    decision = make_n7c4_strength_decision(
        confidence_report={"confidence_counts": {"high": 1}},
        prior_report={"variant_std_policies": {}},
        nis_report=nis,
        comparison_report=_comparison(),
        figure_manifest={"required_figures_generated": True, "required_figures_nonempty": True, "figure_count_total": 10},
    )
    assert decision["recommended_default_policy"] == "fixed_1p0"
    assert decision["status"] == "stronger_policy_ready"
