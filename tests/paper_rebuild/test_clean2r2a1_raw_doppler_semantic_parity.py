import csv
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.manifest import sha256_file
from legsa_gins.paper_rebuild.paths import load_yaml_mapping
from legsa_gins.paper_rebuild.raw_doppler_parity import (
    AUDIT_ONLY_PROVENANCE_COLUMNS,
    EXPECTED_ACTUAL_FULL_SHA256,
    EXPECTED_SOLVER_SEMANTIC_SHA256,
    RAW_DOPPLER_COLUMNS,
    SOLVER_SEMANTIC_COLUMNS,
    audit_cpp_provenance_consumption,
    compute_raw_doppler_solver_semantic_sha256,
)
from legsa_gins.paper_rebuild.clean2r2a_runner import (
    Clean2R2ARunError,
    EXPECTED_BYTE_PROVIDER_HASHES,
    _require_frozen_file_hashes,
    validate_raw_doppler_parity_contract,
)


ROOT = Path(__file__).resolve().parents[2]
LOCAL_CONFIG = ROOT / "configs/paper_rebuild/DATA_PATHS.CLEAN2R2A.local.yaml"
CONTRACT = ROOT / "configs/paper_rebuild/clean2r2a1_raw_doppler_semantic_parity.yaml"


def _current_provider() -> Path:
    if not LOCAL_CONFIG.is_file():
        pytest.skip("formal local path config is intentionally untracked")
    provider = (
        Path(load_yaml_mapping(LOCAL_CONFIG)["paths"]["provider_root"])
        / "FRESH_AUXILIARIES_CLEAN2R2A/clean_final_v23_time_basis/RAW_DOPPLER_VELOCITY.csv"
    )
    if not provider.is_file():
        pytest.skip("current fresh provider is external formal evidence")
    return provider


def _rows() -> list[list[str]]:
    with _current_provider().open("r", encoding="utf-8", newline="") as handle:
        return list(csv.reader(handle))


def _write(path: Path, rows: list[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerows(rows)


def test_current_fresh_raw_doppler_has_exact_semantic_and_actual_hashes() -> None:
    assert tuple(_rows()[0]) == RAW_DOPPLER_COLUMNS
    provider = _current_provider()
    assert compute_raw_doppler_solver_semantic_sha256(provider) == (
        EXPECTED_SOLVER_SEMANTIC_SHA256
    )
    assert sha256_file(provider) == EXPECTED_ACTUAL_FULL_SHA256


def test_exclusion_set_is_exactly_three_audit_only_columns() -> None:
    assert AUDIT_ONLY_PROVENANCE_COLUMNS == (
        "obs_source_hash",
        "nav_source_hash",
        "conversion_config_hash",
    )
    assert len(SOLVER_SEMANTIC_COLUMNS) == 18
    assert tuple(
        column for column in RAW_DOPPLER_COLUMNS
        if column not in AUDIT_ONLY_PROVENANCE_COLUMNS
    ) == SOLVER_SEMANTIC_COLUMNS


def test_every_solver_semantic_column_change_fails_hash(tmp_path: Path) -> None:
    original = _rows()
    original_hash = compute_raw_doppler_solver_semantic_sha256(_current_provider())
    for column in SOLVER_SEMANTIC_COLUMNS:
        mutated = [row[:] for row in original]
        index = RAW_DOPPLER_COLUMNS.index(column)
        mutated[1][index] = mutated[1][index] + "_CHANGED"
        candidate = tmp_path / f"changed_{index:02d}.csv"
        _write(candidate, mutated)
        assert compute_raw_doppler_solver_semantic_sha256(candidate) != original_hash


def test_only_three_provenance_changes_preserve_semantic_hash(tmp_path: Path) -> None:
    rows = _rows()
    for column in AUDIT_ONLY_PROVENANCE_COLUMNS:
        index = RAW_DOPPLER_COLUMNS.index(column)
        for row in rows[1:]:
            row[index] = "f" * 64
    candidate = tmp_path / "provenance_only.csv"
    _write(candidate, rows)
    assert sha256_file(candidate) != EXPECTED_ACTUAL_FULL_SHA256
    assert compute_raw_doppler_solver_semantic_sha256(candidate) == (
        EXPECTED_SOLVER_SEMANTIC_SHA256
    )


def test_cpp_provenance_fields_are_lineage_only_not_numeric_update() -> None:
    audit = audit_cpp_provenance_consumption(ROOT)
    assert audit["passed"] is True
    assert audit["numeric_update_uses_provenance_fields"] is False
    assert all(row["classification"] == "audit_only_provenance" for row in audit["rows"])


def test_historical_full_byte_hash_is_explicitly_not_a_gate() -> None:
    payload = load_yaml_mapping(CONTRACT)
    historical = payload["raw_doppler"]["historical_noncanonical_full_sha256"]
    assert historical == {
        "value": "a40b9933295f6c2c989884d67cc674313f2fe03113c8acdf1d02ddf28734d722",
        "role": "audit_only",
        "gate": False,
    }
    assert payload["raw_doppler"]["rinex_header_canonicalization_required"] is False
    assert payload["raw_doppler"]["second_fresh_attempt_required"] is False


def test_tracked_contract_is_exactly_bound_to_executing_gate() -> None:
    payload = validate_raw_doppler_parity_contract(ROOT)
    raw = payload["raw_doppler"]
    assert raw["row_count"] == 1248
    assert raw["column_count"] == 21
    assert raw["solver_semantic_column_count"] == 18
    assert tuple(raw["audit_only_provenance_columns"]) == AUDIT_ONLY_PROVENANCE_COLUMNS
    assert raw["solver_semantic_sha256"] == EXPECTED_SOLVER_SEMANTIC_SHA256
    assert raw["current_actual_full_sha256"] == EXPECTED_ACTUAL_FULL_SHA256
    assert payload["other_provider_byte_sha256"] == EXPECTED_BYTE_PROVIDER_HASHES
    assert payload["runtime_gates"] == {
        "raw_hash_lock_verified_count": 22,
        "trace_used_online": False,
        "old_provider_solver_input": False,
        "cpp_provenance_fields_numeric_update": False,
    }


def test_frozen_file_hash_guard_rejects_provider_or_executable_tamper(
    tmp_path: Path,
) -> None:
    frozen = tmp_path / "frozen.bin"
    frozen.write_bytes(b"frozen\n")
    expected = {"solver_or_provider": sha256_file(frozen)}
    _require_frozen_file_hashes(
        {"solver_or_provider": frozen}, expected, label="test freeze",
    )
    frozen.write_bytes(b"tampered\n")
    with pytest.raises(Clean2R2ARunError, match="changed after freeze"):
        _require_frozen_file_hashes(
            {"solver_or_provider": frozen}, expected, label="test freeze",
        )
