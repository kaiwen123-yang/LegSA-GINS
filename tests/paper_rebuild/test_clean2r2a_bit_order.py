from pathlib import Path

from legsa_gins.paper_rebuild.clean2r2a_ablation import BIT_ORDER, load_ablation_contract


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "configs/paper_rebuild/clean2r2a_ablation_2pow4.yaml"


def test_clean2r2a_bit_order_is_rd_sa_rp_hv() -> None:
    assert BIT_ORDER == ("RD", "SA", "RP", "HV")
    for profile in load_ablation_contract(CONTRACT):
        observed = "".join("1" if profile.module_flags[factor] else "0" for factor in BIT_ORDER)
        assert observed == profile.bit_string
        assert profile.configuration_id == f"AB{observed}"
