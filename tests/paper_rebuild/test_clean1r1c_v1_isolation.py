"""CLEAN1R1C additions must not mutate the preserved V1 provider contract."""

import pytest
from pathlib import Path

from legsa_gins.paper_rebuild.formal_generation import (
    FormalGenerationError,
    _formal_provider_contract_for_identity,
)
from legsa_gins.paper_rebuild.formal_manifest import validate_formal_schema_contract


ROOT = Path(__file__).resolve().parents[2]


def test_v1_and_v2_provider_contracts_are_disjoint() -> None:
    v1 = _formal_provider_contract_for_identity(
        "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
        "CLEAN1_BY2_CLEAN_NORMAL_V1",
    )
    v2 = _formal_provider_contract_for_identity(
        "CLEAN1R1C_FROZEN_PROTOCOL_DIRECT_REIMPLEMENTATION_AND_BY2_FORMAL_EXECUTION",
        "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED",
    )

    assert v1[0] is False
    assert v2[0] is True
    assert len(v1[1]) == 7
    assert "kick_alignment_report" not in v1[1]
    assert "kick_alignment_report" in v2[1]
    assert "src/legsa_gins/paper_rebuild/kick_alignment.py" not in v1[2]
    assert "src/legsa_gins/paper_rebuild/kick_alignment.py" in v2[2]


def test_mixed_provider_identity_is_rejected() -> None:
    with pytest.raises(FormalGenerationError, match="identity mismatch"):
        _formal_provider_contract_for_identity(
            "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
            "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED",
        )


def test_manifest_schema_rejects_mixed_identity_pair() -> None:
    issues = validate_formal_schema_contract(
        str(ROOT / "configs/paper_rebuild/formal_manifest_schema.yaml"),
        {
            "stage_id": "CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION",
            "protocol_id": "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED",
        },
    )
    assert "formal_schema_identity_pair_mismatch" in issues
