from legsa_gins.da_repro.ambiguity_provider import ambiguity_summary
from legsa_gins.da_repro.dd_los_provider import BaselineEpoch


def test_da3r2_ambiguity_provider():
    epoch = BaselineEpoch(1, 1, 0, 0, 1, 8, 0.01, 0.01, 0.02, 4.0, 90.0, 0.0, "fixed")
    assert ambiguity_summary([epoch])["ambiguity_ready"] is True
