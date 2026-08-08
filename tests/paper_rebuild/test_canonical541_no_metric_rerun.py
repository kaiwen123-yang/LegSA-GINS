from legsa_gins.paper_rebuild.canonical541.full_method_registry import build_full_queue
from legsa_gins.paper_rebuild.canonical541.case_manifest import build_case_manifest
from legsa_gins.paper_rebuild.canonical541.seed_anchor import seed_manifest


def test_no_metric_rerun_flag():
    cases=build_case_manifest([{**r,"anchor_time_s":200,"selection_status":"test"} for r in seed_manifest()])
    assert all(row["metric_driven_rerun"] is False for row in build_full_queue(cases))
