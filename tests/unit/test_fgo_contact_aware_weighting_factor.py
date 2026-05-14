"""Unit tests for N8F contact-aware weighting.

中文说明：contact 只影响 R scale，不生成状态残差或 hard truth。
"""

from legsa_gins.fgo.fgo_contact_aware_weighting_factor import build_contact_aware_weights, compute_contact_scale, summarize_contact_aware_weights


def test_contact_scale_respects_support_and_slip() -> None:
    good = compute_contact_scale(0.9, 0.05, 0.1)
    risky = compute_contact_scale(0.2, 0.9, 0.8)
    assert good < risky


def test_contact_report_has_no_direct_residual() -> None:
    rows = build_contact_aware_weights(
        epoch_times=[0.0, 0.2],
        mode_rows=[{"time": "0.0", "support_probability": "0.8"}, {"time": "0.2", "support_probability": "0.4"}],
        foot_rows=[{"time": "0.0", "slip_risk": "0.2"}, {"time": "0.2", "slip_risk": "0.7"}],
    )
    report = summarize_contact_aware_weights(rows)
    assert report["rows"] == 2
    assert report["direct_state_residual"] is False
    assert report["hard_contact_truth"] is False

