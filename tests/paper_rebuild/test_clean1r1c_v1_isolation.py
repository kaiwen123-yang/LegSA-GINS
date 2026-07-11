"""CLEAN1R1C additions must not mutate the preserved V1 provider contract."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.formal_generation import (
    FormalGenerationError,
    _formal_provider_contract_for_identity,
)
from legsa_gins.paper_rebuild.formal_manifest import validate_formal_schema_contract
from legsa_gins.paper_rebuild.formal_provider import (
    FormalProviderError,
    _provider_protocol_suffix,
)
from scripts.paper_rebuild.generate_clean1_by2_inputs import (
    _assert_protocol_path_identity,
)


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


def test_provider_identity_accepts_only_canonical_or_guarded_attempt() -> None:
    v1 = "CLEAN1_BY2_CLEAN_NORMAL_V1"
    v2 = "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED"
    assert _provider_protocol_suffix(Path(v1)) == v1
    assert _provider_protocol_suffix(Path(v2)) == v2
    assert _provider_protocol_suffix(Path(f".{v2}.attempt-{'a' * 32}")) == v2
    malformed = (
        f".{v2}.attempt-{'a' * 31}",
        f".{v2}.attempt-{'g' * 32}",
        f"{v2}.attempt-{'a' * 32}",
        ".CLEAN1_BY2_CLEAN_NORMAL_V3.attempt-" + "a" * 32,
    )
    for name in malformed:
        with pytest.raises(FormalProviderError):
            _provider_protocol_suffix(Path(name))


def test_v2_protocol_with_v1_local_suffix_fails_before_any_write(
    tmp_path: Path,
) -> None:
    paths = SimpleNamespace(
        provider_root=tmp_path / "CLEAN1_BY2_CLEAN_NORMAL_V1",
        runtime_root=tmp_path / "CLEAN1_BY2_CLEAN_NORMAL_V1",
    )
    protocol = SimpleNamespace(
        payload={"protocol_id": "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED"}
    )
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        _assert_protocol_path_identity(paths, protocol)
    assert list(tmp_path.iterdir()) == []
