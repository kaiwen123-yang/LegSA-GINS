"""Tests for N8C2 decision rules.

中文说明：验证 Raw Doppler activation_missing 优先阻断进入 N8D。
"""

from legsa_gins.fgo.fgo_n8c2_decision import make_n8c2_decision


def test_decision_prioritizes_raw_doppler_activation_missing() -> None:
    decision = make_n8c2_decision(
        activation_report={"classification_counts": {"suspicious_no_effect": 1}},
        whitening_report={"smoothness_dominance_classification": "true_residual_dominance"},
        smoothness_report={"component_causing_spikes": "yaw_smoothness"},
        raw_doppler_report={"classification": "activation_missing"},
        toggle_report={"status": "toggle_integrity_passed"},
        figure_manifest={"figure_count_total": 14, "required_figures_nonempty": True},
    )
    assert decision["status"] == "raw_doppler_activation_missing"
    assert decision["recommended_next_stage"] == "N8C3_raw_doppler_factor_fix"
    assert not decision["paper_performance_claim"]
