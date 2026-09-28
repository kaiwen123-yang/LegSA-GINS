from legsa_gins.paper_rebuild.canonical541.provider_generator import apply_degradation
from legsa_gins.paper_rebuild.canonical541.full_method_registry import FULL_METHODS
from legsa_gins.paper_rebuild.canonical541.runner import method_bound_bundle
from test_canonical541_helpers import case, make_bundle


def test_single_invariant_to_dual_yaw(tmp_path):
    base=make_bundle(tmp_path); degraded,_,_=apply_degradation(base,case("D33")); bound=method_bound_bundle(base,degraded,FULL_METHODS[0])
    assert bound.hashes()==base.hashes()
