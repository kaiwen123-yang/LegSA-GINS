from scripts.paper10q1_qm_claim_boundary import forbidden_claim_markdown


def test_forbidden_qm_claims_are_marked_do_not_claim():
    text = forbidden_claim_markdown().lower()
    for phrase in [
        "qm universally improves all metrics",
        "qm significantly improves normal-condition accuracy",
        "full-qm dominates no-qm",
        "final paper readiness",
        "by3 yaw generalization",
    ]:
        assert phrase in text
    assert text.count("do not") >= 8


def test_forbidden_markdown_does_not_assert_final_paper_ready():
    text = forbidden_claim_markdown().lower()
    assert "do not claim final paper readiness" in text
    assert "claim final paper readiness." not in text.replace("do not claim final paper readiness.", "")
