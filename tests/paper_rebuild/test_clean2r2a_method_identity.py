from pathlib import Path

from legsa_gins.paper_rebuild.clean2r2a_ablation import (
    assert_canonical_method_identities,
    load_ablation_contract,
)
from legsa_gins.paper_rebuild.clean2r2a_run_registry import build_clean_run_registry
from legsa_gins.paper_rebuild.methods import EXPECTED_FEATURES


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "configs/paper_rebuild/clean2r2a_ablation_2pow4.yaml"


def test_clean2r2a_canonical_method_identities_are_exact() -> None:
    profiles = load_ablation_contract(CONTRACT)
    assert_canonical_method_identities(profiles)
    by_id = {row["configuration_id"]: row for row in build_clean_run_registry(CONTRACT)}
    for method_id in ("single_antenna_EKF", "basic_dual_yaw_EKF"):
        assert {field: by_id[method_id][field] for field in EXPECTED_FEATURES[method_id]} == EXPECTED_FEATURES[method_id]
    assert by_id["AB0000"]["canonical_equivalent_method_id"] == "strong_dual_yaw_EKF"
    assert by_id["AB1111"]["canonical_equivalent_method_id"] == "LegSA_Paper_V1"
    assert {field: by_id["AB0000"][field] for field in EXPECTED_FEATURES["strong_dual_yaw_EKF"]} == EXPECTED_FEATURES["strong_dual_yaw_EKF"]
    assert {field: by_id["AB1111"][field] for field in EXPECTED_FEATURES["LegSA_Paper_V1"]} == EXPECTED_FEATURES["LegSA_Paper_V1"]
