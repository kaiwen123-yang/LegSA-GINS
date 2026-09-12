from legsa_gins.paper_rebuild.canonical541.provider_generator import apply_degradation
from test_canonical541_helpers import case, make_bundle


def test_same_seed_replays_and_different_seed_changes(tmp_path):
    base = make_bundle(tmp_path); a,_,_=apply_degradation(base, case("D15",0)); b,_,_=apply_degradation(base, case("D15",0)); c,_,_=apply_degradation(base, case("D15",1))
    assert a.hashes() == b.hashes() and a.hashes() != c.hashes()
