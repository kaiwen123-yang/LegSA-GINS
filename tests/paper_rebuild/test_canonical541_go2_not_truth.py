from legsa_gins.paper_rebuild.canonical541.case_manifest import build_case_manifest
from legsa_gins.paper_rebuild.canonical541.seed_anchor import seed_manifest


def test_go2_truth_claim_is_never_allowed():
    rows=build_case_manifest([{**r,"anchor_time_s":200,"selection_status":"test"} for r in seed_manifest()])
    assert all(row["go2_truth_claim_allowed"] is False for row in rows)
