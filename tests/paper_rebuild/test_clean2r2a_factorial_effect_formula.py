import pytest
from pathlib import Path

from legsa_gins.paper_rebuild.clean2r2a_ablation import canonical_ablation_profiles
from legsa_gins.paper_rebuild.clean2r2a_analysis import (
    factorial_main_effects,
    factorial_pairwise_interactions,
    full_vs_strong_delta,
    validate_statistical_contract,
)


ROOT = Path(__file__).resolve().parents[2]
STATISTICS = ROOT / "configs/paper_rebuild/clean2r2a_statistical_contract.yaml"


def test_clean2r2a_main_effect_uses_frozen_effect_coding() -> None:
    validate_statistical_contract(STATISTICS)
    values = {
        profile.configuration_id: 5.0 + 3.0 * profile.effect_code("RD")
        for profile in canonical_ablation_profiles()
    }
    effects = factorial_main_effects(values)
    assert effects["RD"] == pytest.approx(6.0)
    assert effects["SA"] == pytest.approx(0.0)
    assert effects["RP"] == pytest.approx(0.0)
    assert effects["HV"] == pytest.approx(0.0)
    assert full_vs_strong_delta(values) == pytest.approx(6.0)


def test_clean2r2a_pairwise_effect_uses_same_frozen_formula() -> None:
    validate_statistical_contract(STATISTICS)
    values = {
        profile.configuration_id: 2.0 * profile.effect_code("RD") * profile.effect_code("SA")
        for profile in canonical_ablation_profiles()
    }
    interactions = factorial_pairwise_interactions(values)
    assert interactions["RD:SA"] == pytest.approx(4.0)
    assert all(
        value == pytest.approx(0.0)
        for name, value in interactions.items()
        if name != "RD:SA"
    )
