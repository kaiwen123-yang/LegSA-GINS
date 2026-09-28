import numpy as np
from legsa_gins.paper_rebuild.canonical541.provider_generator import apply_degradation
from test_canonical541_helpers import case, make_bundle


def test_d41_uses_gnss2_minus_gnss1_plus_90(tmp_path):
    base=make_bundle(tmp_path); out,_,_=apply_degradation(base,case("D41"))
    for row in out.tables["dual_yaw"].rows[:20]:
        expected=(np.degrees(np.arctan2(float(row["baseline_e_m"]),float(row["baseline_n_m"])))+90+180)%360-180
        assert abs(((float(row["yaw_deg"])-expected+180)%360)-180)<1e-6
    assert out.tables["gnss_position"].sha256()==base.tables["gnss_position"].sha256()
