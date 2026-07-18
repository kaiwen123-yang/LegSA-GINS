from pathlib import Path

from legsa_gins.paper_rebuild.clean2r2a_ablation import (
    VARIANT_IDS,
    load_ablation_contract,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "configs/paper_rebuild/clean2r2a_ablation_2pow4.yaml"


def test_clean2r2a_has_exactly_16_ordered_variants() -> None:
    profiles = load_ablation_contract(CONTRACT)
    assert len(profiles) == 16
    assert tuple(profile.configuration_id for profile in profiles) == VARIANT_IDS
    assert len({profile.bit_string for profile in profiles}) == 16
