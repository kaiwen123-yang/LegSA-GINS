from __future__ import annotations

import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.clean2_case_provider import (
    EXPECTED_BASE_PROVIDER_HASHES,
    Clean2CaseProviderError,
    _read_dual_provider,
    _validate_terminal_base_provider_evidence,
    _write_export_safe_base_provider_snapshot,
    materialize_case_bundle,
    validate_case_provider_index,
)
from legsa_gins.paper_rebuild.clean2_classic_cases import apply_classic_case
from legsa_gins.paper_rebuild.evidence import assert_export_text_is_redacted
from legsa_gins.paper_rebuild.manifest import sha256_file, write_json_atomic


def _base_evidence() -> dict:
    return {
        "provider_hashes": dict(EXPECTED_BASE_PROVIDER_HASHES),
        "shared_provider_paths": {
            "imu": "/fresh/imu",
            "raw_doppler": "/fresh/rd",
            "go2_roll_pitch": "/fresh/rp",
            "go2_horizontal_velocity": "/fresh/hv",
        },
        "raw_source_hashes": {f"raw/{index}": "6" * 64 for index in range(22)},
        "raw_pre_checkpoint_sha256": "7" * 64,
        "raw_post_checkpoint_sha256": "8" * 64,
        "raw_hash_lock_sha256": "9" * 64,
        "code_freeze_commit": "a" * 40,
        "clean_input_manifest_sha256": "b" * 64,
        "auxiliary_bundle_manifest_sha256": "c" * 64,
        "base_dual_yaw_provider_sha256": "d" * 64,
    }


def _terminal_base_evidence(tmp_path: Path, clean2_base_files, monkeypatch) -> dict:
    providers = tmp_path / "fresh-providers"
    providers.mkdir()
    shared_paths = {}
    for role in ("imu", "raw_doppler", "go2_roll_pitch", "go2_horizontal_velocity"):
        path = providers / f"{role}.txt"
        path.write_text(f"fresh {role}\n", encoding="utf-8")
        shared_paths[role] = str(path)
        monkeypatch.setitem(EXPECTED_BASE_PROVIDER_HASHES, role, sha256_file(path))
    monkeypatch.setitem(
        EXPECTED_BASE_PROVIDER_HASHES, "gnss", sha256_file(clean2_base_files["gnss"])
    )
    evidence = _base_evidence()
    evidence.update(
        {
            "provider_hashes": dict(EXPECTED_BASE_PROVIDER_HASHES),
            "shared_provider_paths": shared_paths,
            "base_gnss_path": str(clean2_base_files["gnss"]),
            "base_dual_yaw_provider_path": str(clean2_base_files["dual"]),
            "base_dual_yaw_provider_sha256": sha256_file(clean2_base_files["dual"]),
        }
    )
    return evidence


def test_export_safe_base_snapshot_contains_aliases_and_hashes_only(tmp_path: Path):
    manifest, hashes = _write_export_safe_base_provider_snapshot(
        base_provider_evidence=_base_evidence(), destination=tmp_path / "04_BASE_PROVIDER"
    )
    assert_export_text_is_redacted(manifest.read_text(encoding="utf-8"))
    assert_export_text_is_redacted(hashes.read_text(encoding="utf-8"))
    assert '"/fresh/' not in manifest.read_text(encoding="utf-8")


def test_case_index_rehash_rejects_ledger_mutation(
    tmp_path: Path, classic_catalog, clean2_base_files, monkeypatch
):
    evidence = _terminal_base_evidence(tmp_path, clean2_base_files, monkeypatch)
    base_manifest, base_hashes = _write_export_safe_base_provider_snapshot(
        base_provider_evidence=evidence, destination=tmp_path / "04_BASE_PROVIDER"
    )
    evidence.update(
        {
            "export_safe_base_manifest_path": str(base_manifest),
            "export_safe_base_manifest_sha256": sha256_file(base_manifest),
            "export_safe_base_hashes_path": str(base_hashes),
            "export_safe_base_hashes_sha256": sha256_file(base_hashes),
        }
    )
    root = tmp_path / "05_CASE_PROVIDERS"
    root.mkdir()
    results = []
    for case in classic_catalog.cases:
        results.append(
            materialize_case_bundle(
                apply_classic_case(clean2_base_files["epochs"], case),
                base_gnss_path=clean2_base_files["gnss"],
                base_dual_yaw_provider_path=clean2_base_files["dual"],
                base_rows=clean2_base_files["rows"],
                base_payload=clean2_base_files["payload"],
                base_extension_audit={
                    "first15_token_parity": True,
                    "first15_numerical_parity": True,
                },
                destination=root / case.case_id,
                mapping_catalog=classic_catalog,
                base_provider_evidence=evidence,
            )
        )
    index = write_json_atomic(
        root / "CLASSIC18_PROVIDER_INDEX.json",
        {
            "schema_version": "paper_rebuild.clean2_case_provider_index.v1",
            "stage_id": "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18",
            "case_count": 18,
            "cases": results,
            "trace_read_count": 0,
            "raw_mutation_count": 0,
            "code_freeze_commit": "a" * 40,
            "code_worktree_dirty": False,
            "base_provider_evidence": evidence,
            "all_terminal_pass": True,
        },
    )
    assert len(validate_case_provider_index(index, expected_code_commit="a" * 40)[1]) == 18
    ledger = root / "C04_baseline_vector_noise_seed0/CASE_PERTURBATION_LEDGER.csv"
    ledger.write_text(ledger.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    with pytest.raises(Clean2CaseProviderError, match="output/ledger/policy hash changed"):
        validate_case_provider_index(index, expected_code_commit="a" * 40)


def test_case_index_rehash_rejects_frozen_provider_hash_drift(
    tmp_path: Path, classic_catalog, clean2_base_files, monkeypatch
):
    evidence = _terminal_base_evidence(tmp_path, clean2_base_files, monkeypatch)
    base_manifest, base_hashes = _write_export_safe_base_provider_snapshot(
        base_provider_evidence=evidence, destination=tmp_path / "04_BASE_PROVIDER"
    )
    evidence.update(
        {
            "export_safe_base_manifest_path": str(base_manifest),
            "export_safe_base_manifest_sha256": sha256_file(base_manifest),
            "export_safe_base_hashes_path": str(base_hashes),
            "export_safe_base_hashes_sha256": sha256_file(base_hashes),
        }
    )
    root = tmp_path / "05_CASE_PROVIDERS"
    root.mkdir()
    results = [
        materialize_case_bundle(
            apply_classic_case(clean2_base_files["epochs"], case),
            base_gnss_path=clean2_base_files["gnss"],
            base_dual_yaw_provider_path=clean2_base_files["dual"],
            base_rows=clean2_base_files["rows"],
            base_payload=clean2_base_files["payload"],
            base_extension_audit={
                "first15_token_parity": True,
                "first15_numerical_parity": True,
            },
            destination=root / case.case_id,
            mapping_catalog=classic_catalog,
            base_provider_evidence=evidence,
        )
        for case in classic_catalog.cases
    ]
    index = write_json_atomic(
        root / "CLASSIC18_PROVIDER_INDEX.json",
        {
            "schema_version": "paper_rebuild.clean2_case_provider_index.v1",
            "stage_id": "CLEAN2_BY2_MODULE_ABLATION_AND_CLASSIC18",
            "case_count": 18,
            "cases": results,
            "trace_read_count": 0,
            "raw_mutation_count": 0,
            "code_freeze_commit": "a" * 40,
            "code_worktree_dirty": False,
            "base_provider_evidence": evidence,
            "all_terminal_pass": True,
        },
    )
    validate_case_provider_index(index, expected_code_commit="a" * 40)
    Path(evidence["shared_provider_paths"]["imu"]).write_text("drift\n", encoding="utf-8")
    with pytest.raises(Clean2CaseProviderError, match="BASE_PROVIDER_PARITY_FAILED"):
        validate_case_provider_index(index, expected_code_commit="a" * 40)


def test_sanitized_base_hash_csv_requires_exact_map(
    tmp_path: Path, clean2_base_files, monkeypatch
):
    evidence = _terminal_base_evidence(tmp_path, clean2_base_files, monkeypatch)
    manifest, hashes = _write_export_safe_base_provider_snapshot(
        base_provider_evidence=evidence, destination=tmp_path / "04_BASE_PROVIDER"
    )
    evidence.update(
        {
            "export_safe_base_manifest_path": str(manifest),
            "export_safe_base_manifest_sha256": sha256_file(manifest),
            "export_safe_base_hashes_path": str(hashes),
            "export_safe_base_hashes_sha256": sha256_file(hashes),
        }
    )
    _validate_terminal_base_provider_evidence(
        evidence, expected_code_commit="a" * 40
    )
    hashes.write_text(
        hashes.read_text(encoding="utf-8") + f"unexpected,{'f' * 64}\n",
        encoding="utf-8",
    )
    evidence["export_safe_base_hashes_sha256"] = sha256_file(hashes)
    with pytest.raises(Clean2CaseProviderError, match="hash map is inconsistent"):
        _validate_terminal_base_provider_evidence(
            evidence, expected_code_commit="a" * 40
        )


def test_terminal_base_provider_rejects_missing_actual_file(
    tmp_path: Path, clean2_base_files, monkeypatch
):
    evidence = _terminal_base_evidence(tmp_path, clean2_base_files, monkeypatch)
    manifest, hashes = _write_export_safe_base_provider_snapshot(
        base_provider_evidence=evidence, destination=tmp_path / "04_BASE_PROVIDER"
    )
    evidence.update(
        {
            "export_safe_base_manifest_path": str(manifest),
            "export_safe_base_manifest_sha256": sha256_file(manifest),
            "export_safe_base_hashes_path": str(hashes),
            "export_safe_base_hashes_sha256": sha256_file(hashes),
        }
    )
    Path(evidence["shared_provider_paths"]["go2_roll_pitch"]).unlink()
    with pytest.raises(Clean2CaseProviderError, match="path is missing"):
        _validate_terminal_base_provider_evidence(
            evidence, expected_code_commit="a" * 40
        )


def test_dual_provider_rejects_yaw_vector_inconsistency(tmp_path: Path):
    provider = tmp_path / "dual.csv"
    provider.write_text(
        "time,baseline_n_m,baseline_e_m,baseline_d_m,baseline_length_m,body_yaw_ned_deg,yaw_std_deg,physical_in_band,gnss_order,lateral_to_body_offset_deg,wrap_safe_residual,trace_sign_or_offset_selection\n"
        "1,0.35,0,0,0.35,0,1.5,True,GNSS2-GNSS1,90,True,False\n",
        encoding="utf-8",
    )
    with pytest.raises(Clean2CaseProviderError, match="physical vector/yaw gate"):
        _read_dual_provider(provider)
