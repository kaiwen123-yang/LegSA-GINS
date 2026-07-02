from scripts.paper10q2r1_claim_boundary import (
    paper2a_allowed_claims,
    paper2a_forbidden_claims_md,
)


def test_allowed_paper2a_claims_do_not_promote_exact_reproduction():
    text = "\n".join(row["claim_text"] for row in paper2a_allowed_claims()).lower()
    assert "exact official external reproduction is not claimed" in "\n".join(row["required_caveat"].lower() for row in paper2a_allowed_claims())
    assert "proves universal" not in text
    assert "beats all" not in text


def test_forbidden_paper2a_claims_block_superiority_and_stress_claims():
    text = paper2a_forbidden_claims_md()
    assert "exact external reproduction" in text
    assert "universal performance superiority" in text
    assert "BY3 yaw generalization" in text
    assert "XB high-precision severe-GNSS" in text
