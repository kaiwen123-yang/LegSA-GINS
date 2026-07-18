from legsa_gins.paper_rebuild.clean2r2a_runner import method_features
from legsa_gins.paper_rebuild.final_v23_clean_parity import METHOD_FEATURES


def test_ab1111_is_exact_legsa_feature_identity() -> None:
    assert method_features("AB1111") == METHOD_FEATURES["LegSA_Paper_V1"]
