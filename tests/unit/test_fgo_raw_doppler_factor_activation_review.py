"""Tests for N8C2 RawDopplerVelocityFactor activation review.

中文说明：验证 Raw Doppler 未进入 solver residual 时必须报缺失。
"""

from legsa_gins.fgo.fgo_raw_doppler_factor_activation_review import build_raw_doppler_factor_activation_review


def test_raw_doppler_activation_missing_when_not_in_solver_residual() -> None:
    report = build_raw_doppler_factor_activation_review(
        activation_report={
            "factor_activation_rows": [
                {"factor_type": "RawDopplerVelocityFactor", "included_in_solver_residual": False, "proxy_residual_evidence": True, "factor_count": 4, "residual_dimension": 3},
                {"factor_type": "ReceiverVelocityFactor", "contribution_share": 0.3},
                {"factor_type": "SmoothnessFactor", "contribution_share": 0.6},
            ]
        },
        whitening_report={"raw_doppler_whitening_classification": "activation_missing"},
    )
    assert report["classification"] == "activation_missing"
    assert report["proxy_residual_evidence"]
    assert not report["trace_weight_tuning"]
