from legsa_gins.paper_rebuild.canonical541.case_manifest import build_case_manifest
from legsa_gins.paper_rebuild.canonical541.seed_anchor import seed_manifest


def test_case_manifest_exact_count_and_ids():
    anchors = [{**row, "anchor_time_s": 206.2, "selection_status": "test"} for row in seed_manifest()]
    cases = build_case_manifest(anchors)
    assert len(cases) == 541 and cases[0]["case_id"] == "C00_clean_normal" and cases[-1]["case_id"] == "D60_seed_08"
