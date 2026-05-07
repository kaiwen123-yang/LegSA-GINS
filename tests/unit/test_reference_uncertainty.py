"""中文说明：unit 测试验证小模块约定和边界，不做 numerical performance claim。
"""

from legsa_gins.evaluation.reference_uncertainty import classify_reference_uncertainty


def test_strong_reference_allows_strict_claim():
    status = classify_reference_uncertainty(
        has_independent_reference=True,
        has_covariance=True,
        has_mount_log=True,
    )

    assert status.status == "strong_reference"
    assert status.strict_claim_allowed is True


def test_moderate_reference_uncertainty_blocks_strict_claim():
    status = classify_reference_uncertainty(
        has_independent_reference=False,
        has_covariance=True,
        has_mount_log=False,
    )

    assert status.status == "moderate_reference_uncertainty"
    assert status.strict_claim_allowed is False


def test_missing_reference_evidence_blocks_strict_claim():
    status = classify_reference_uncertainty(
        has_independent_reference=False,
        has_covariance=False,
        has_mount_log=False,
    )

    assert status.status == "evidence_missing"
    assert status.strict_claim_allowed is False
