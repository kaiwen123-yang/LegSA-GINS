"""Tests for N8E claim-boundary review.

中文说明：验证越界 claim 会阻断，否定语境不会误报。
"""

from legsa_gins.fgo.fgo_claim_boundary_review import review_claim_texts


def test_claim_boundary_flags_positive_claims() -> None:
    report = review_claim_texts({"bad.md": "This stage will outperform final_v23 with an FGO feedback loop."})
    assert report["decision"] == "block"
    assert report["forbidden_claim_count"] >= 2


def test_claim_boundary_ignores_negated_boundary_language() -> None:
    report = review_claim_texts(
        {
            "ok.md": (
                "No paper performance claim. No outperform final_v23 claim. "
                "FGO output is not fed back into EKF. Go2 velocity is not truth."
            )
        }
    )
    assert report["decision"] == "pass"
    assert report["forbidden_claim_count"] == 0
