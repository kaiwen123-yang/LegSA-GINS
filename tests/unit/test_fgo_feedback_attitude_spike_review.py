"""Unit tests for N8I attitude spike review.

中文说明：4 deg 以上 attitude correction spike 应被记录，并检查保守 gate 是否可拦截。
"""

from types import SimpleNamespace

from legsa_gins.fgo_feedback.fgo_feedback_attitude_spike_review import build_attitude_spike_review


def test_attitude_spike_review_detects_repeated_spikes():
    bundle = SimpleNamespace(
        trace_rows={
            "primary_horizontal_velocity_attitude_default": [
                {"update_time": 1.0, "attitude_norm_deg": 4.2, "yaw_residual_deg": 1.0, "velocity_norm_mps": 0.1, "position_norm_m": 0.0, "accepted": 1},
                {"update_time": 2.0, "attitude_norm_deg": 4.8, "yaw_residual_deg": 1.2, "velocity_norm_mps": 0.1, "position_norm_m": 0.0, "accepted": 1},
                {"update_time": 3.0, "attitude_norm_deg": 4.1, "yaw_residual_deg": 1.1, "velocity_norm_mps": 0.1, "position_norm_m": 0.0, "accepted": 1},
            ],
            "primary_hv_att_conservative_gate": [{"update_time": 1.0, "attitude_norm_deg": 3.0, "accepted": 1}],
        },
        gate_reports={"primary_hv_att_conservative_gate": {"reject_reasons": {"attitude_correction_gate": 3}}},
        policy_summaries={"primary_hv_att_conservative_gate": {"feedback_accept_count": 3}},
        evaluation_by_policy={"primary_hv_att_conservative_gate": {"clean_gross_degradation": False}},
        n8h_reports={"FGO_FEEDBACK_CORRECTION_REVIEW_REPORT.json": {"attitude_correction_spike_count_primary": 3}},
    )
    report = build_attitude_spike_review(bundle)
    assert report["default_attitude_spike_count"] == 3
    assert report["spike_pattern"] == "repeated"
    assert report["would_conservative_gate_reject_spikes"] is True
