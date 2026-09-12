from legsa_gins.paper_rebuild.canonical541.provider_generator import apply_degradation
from test_canonical541_helpers import case, make_bundle


def test_raw_conflict_does_not_modify_receiver(tmp_path):
    base=make_bundle(tmp_path); out,_,_=apply_degradation(base,case("D50"))
    assert out.tables["receiver_velocity"].sha256()==base.tables["receiver_velocity"].sha256()
    assert out.tables["raw_doppler"].sha256()!=base.tables["raw_doppler"].sha256()
