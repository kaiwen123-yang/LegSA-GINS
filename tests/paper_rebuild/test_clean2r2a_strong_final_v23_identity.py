from legsa_gins.paper_rebuild.clean2r2a_runner import method_features
from legsa_gins.paper_rebuild.final_v23_clean_parity import METHOD_FEATURES


def test_ab0000_is_exact_strong_feature_identity() -> None:
    assert method_features("AB0000") == METHOD_FEATURES["strong_dual_yaw_EKF"]
