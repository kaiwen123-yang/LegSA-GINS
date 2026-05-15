"""Unit tests for N8J final runner specs.

中文说明：final runner 只包含 selected policy 和固定 reference variants。
"""

from legsa_gins.fgo_feedback.fgo_feedback_final_runner import final_variant_specs


def test_final_runner_variants_are_fixed():
    ids = [spec.policy_id for spec in final_variant_specs()]
    assert ids == [
        "baseline_no_feedback",
        "n8j_selected_conservative_feedback",
        "default_gate_feedback_for_reference",
        "reject_all_sanity",
        "velocity_only_reference",
        "attitude_only_reference",
        "diagnostic_PVA_reference",
    ]
    selected = final_variant_specs()[1]
    assert selected.gate_policy == "combined_conservative_gate"
    assert selected.window_duration_s == 5.0
    assert selected.feedback_stride_s == 1.0
