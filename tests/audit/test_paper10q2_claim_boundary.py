from scripts.paper10q2_horizontal_claim_boundary import (
    allowed_claim_rows,
    conditional_claim_rows,
    forbidden_claim_markdown,
)


def test_allowed_claims_are_bounded():
    text = "\n".join(row["claim_text"] for row in allowed_claim_rows())
    assert "exactly reproduced" not in text.lower()
    assert "universally outperform" not in text.lower()
    assert "final paper claim ready" not in text.lower()


def test_conditional_claims_require_reexport_or_targeted_rerun():
    text = "\n".join(row["condition"] for row in conditional_claim_rows())
    assert "re-exported" in text or "re-export" in text
    assert "targeted" in text


def test_forbidden_claims_explicitly_block_false_reproduction():
    forbidden = forbidden_claim_markdown()
    assert "five external dual-antenna algorithms" in forbidden
    assert "twenty literature algorithms" in forbidden
    assert "method-inspired policy baselines" in forbidden
