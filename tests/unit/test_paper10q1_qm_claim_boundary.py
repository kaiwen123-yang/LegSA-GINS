from scripts.paper10q1_qm_claim_boundary import claim_rows, forbidden_claim_markdown


def test_qm_forbidden_claims_include_universal_improvement_and_legacy_counter():
    text = forbidden_claim_markdown().lower()
    assert "universally improves all metrics" in text
    assert "legacy bad-a1 consumed" in text
    assert "full-qm dominates no-qm" in text


def test_allowed_claims_are_bounded_not_universal():
    allowed = " ".join(row["claim_en"] for row in claim_rows()["allowed"]).lower()
    assert "bounded protection" in allowed
    assert "universally improves" not in allowed
    assert "dominates no-qm" not in allowed
