"""Tests for N8D whitened balance policy.

中文说明：平衡报告只能基于 solver-visible factor balance。
"""

from legsa_gins.fgo.fgo_whitened_balance_policy import build_whitened_balance_policy_report


def test_whitened_balance_policy_flags_raw_low_share() -> None:
    report = build_whitened_balance_policy_report(
        {
            "variants": [
                {
                    "variant": "balanced_policy_A",
                    "finite_output": True,
                    "factor_balance": [
                        {"factor_type": "SmoothnessFactor", "contribution_share": 0.6, "dimension_normalized_whitened_norm": 1.0, "whitened_residual_p95": 1.0, "factor_count": 4},
                        {"factor_type": "RawDopplerVelocityFactor", "contribution_share": 0.0, "dimension_normalized_whitened_norm": 0.0, "whitened_residual_p95": 0.0, "factor_count": 0},
                    ],
                }
            ]
        }
    )
    assert report["raw_doppler_low_marginal_value_suspect"]
    assert report["selection_uses_solver_visible_diagnostics_only"]
    assert not report["trace_weight_tuning"]
