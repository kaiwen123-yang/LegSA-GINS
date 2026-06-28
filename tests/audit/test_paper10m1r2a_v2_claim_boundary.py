from tests.paper10m1r2a_v2_common import read_csv, read_text


def test_claim_boundary_forbids_performance_and_superiority_claims():
    text = read_text("07_CLAIM_BOUNDARY/PAPER10M1R2A_V2_CLAIM_BOUNDARY_UPDATE.md").lower()
    assert "no performance claim" in text
    assert "no algorithm superiority claim" in text
    assert "no universal superiority claim" in text
    assert "no comprehensive final_v23 superiority claim" in text
    assert "no go2 truth claim" in text


def test_claim_levels_are_only_allowed_values():
    rows = read_csv("04_CASE_MANIFEST/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv")
    allowed = {"main_candidate", "appendix_candidate", "diagnostic_only"}
    assert {row["claim_level"] for row in rows} <= allowed
