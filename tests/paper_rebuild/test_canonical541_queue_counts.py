from legsa_gins.paper_rebuild.canonical541.case_manifest import build_case_manifest
from legsa_gins.paper_rebuild.canonical541.seed_anchor import seed_manifest
from legsa_gins.paper_rebuild.canonical541.run_registry import build_logical_queues


def test_queue_counts_2164_4869():
    cases=build_case_manifest([{**r,"anchor_time_s":200,"selection_status":"test"} for r in seed_manifest()]); full,abl=build_logical_queues(cases)
    assert len(full)==2164 and len(abl)==4869 and len(full)+len(abl)==7033
