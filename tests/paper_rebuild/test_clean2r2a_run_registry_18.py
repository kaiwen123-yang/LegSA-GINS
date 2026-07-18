from pathlib import Path

from legsa_gins.paper_rebuild.clean2r2a_run_registry import (
    FORMAL_CONFIGURATION_ORDER,
    build_clean_run_registry,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "configs/paper_rebuild/clean2r2a_ablation_2pow4.yaml"


def test_clean2r2a_registry_has_18_unique_identities() -> None:
    rows = build_clean_run_registry(CONTRACT)
    assert len(rows) == 18
    assert tuple(row["configuration_id"] for row in rows) == FORMAL_CONFIGURATION_ORDER
    assert [row["run_order"] for row in rows] == list(range(1, 19))
    assert len({row["run_id"] for row in rows}) == 18
    assert len({row["profile_identity_hash"] for row in rows}) == 18
