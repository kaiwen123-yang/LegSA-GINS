from legsa_gins.paper_rebuild.canonical541.case_manifest import build_case_manifest
from legsa_gins.paper_rebuild.canonical541.seed_anchor import seed_manifest


def test_no_placeholder():
    rows = build_case_manifest([{**r, "anchor_time_s": 200, "selection_status": "test"} for r in seed_manifest()])
    assert all("placeholder" not in str(row).lower() for row in rows)
