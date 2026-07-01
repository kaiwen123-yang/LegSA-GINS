from scripts.paper10m1r2e_claim_boundary import FORBIDDEN_CLAIM_KEYS, claim_rows, forbidden_claim_markdown


def test_claim_tables_include_bounded_allowed_and_diagnostic_zero_delta():
    rows = claim_rows()
    allowed = {row["claim_id"] for row in rows["allowed"]}
    diagnostic_text = " ".join(row["claim_en"] for row in rows["diagnostic"])
    assert {"A01", "A02", "A03", "A04"}.issubset(allowed)
    assert "Go2 joint" in diagnostic_text
    assert "FGO feedback" in diagnostic_text


def test_forbidden_claim_markdown_freezes_required_boundaries():
    text = forbidden_claim_markdown()
    for key in [
        "universal_superiority",
        "final_paper_claim_ready",
        "by3_yaw_generalization",
        "complete_9f_fgo_validated",
        "go2_joint_effective_when_zero_delta",
        "fgo_feedback_effective_when_zero_delta",
    ]:
        assert key in FORBIDDEN_CLAIM_KEYS
        assert key in text
