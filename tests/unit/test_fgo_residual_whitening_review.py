"""Tests for N8C2 residual whitening review.

中文说明：验证白化审查能保留 Raw Doppler activation_missing 边界。
"""

from legsa_gins.fgo.fgo_residual_whitening_review import build_residual_whitening_review


def test_whitening_classifies_missing_raw_doppler_activation() -> None:
    report = build_residual_whitening_review(
        activation_report={
            "factor_activation_rows": [
                {"factor_type": "RawDopplerVelocityFactor", "total_whitened_sq": 1.0, "contribution_norm": 1.0, "residual_row_count": 4, "residual_dimension": 3, "dimension_normalized_residual_p95": 0.1, "included_in_solver_residual": False},
                {"factor_type": "SmoothnessFactor", "total_whitened_sq": 10.0, "contribution_norm": 3.0, "residual_row_count": 4, "residual_dimension": 9, "dimension_normalized_residual_p95": 0.2, "included_in_solver_residual": True},
            ]
        }
    )
    assert report["raw_doppler_whitening_classification"] == "activation_missing"
    assert report["dimension_normalized_review_complete"]
