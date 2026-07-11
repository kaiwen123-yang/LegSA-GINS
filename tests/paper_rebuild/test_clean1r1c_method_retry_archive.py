"""Guarded CLEAN1R1C method-retry archival is dry-runnable and idempotent."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.manifest import sha256_file
from scripts.paper_rebuild import audit_clean1r1c_by2 as final_audit
from scripts.paper_rebuild import generate_clean1_by2_inputs as generator


OLD = "644d2a022e9927d4fd09917003e88ad6c83aa1dc"
NEW = "b" * 40
INHERITED = "7d1cb382f69e2c055f7e535198218246533822c3"
PROTOCOL = "CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _fixture(tmp_path: Path, monkeypatch: object) -> tuple[object, Path, Path, dict[str, object]]:
    clean = tmp_path / "clean"
    provider = clean / "04_PROVIDER_FREEZE" / PROTOCOL
    runtime_parent = clean / "05_BY2_CLEAN"
    runtime = runtime_parent / f".{PROTOCOL}.attempt-{'c' * 32}"
    stage = clean / "stage"
    archive = clean / "stage_FAILED_ATTEMPTS" / OLD
    for directory in (
        provider / "providers",
        runtime / "01_single_antenna_EKF/logs",
        stage / "00_AUTHORIZATION",
        stage / "03_DATA_HASH_AND_ROLES",
        stage / "04_PROVIDER_AUDIT",
        stage / "06_RUN_MANIFESTS",
        stage / "07_EVALUATION",
        stage / "08_EVIDENCE_AUDIT",
        clean / "stage_FAILED_ATTEMPTS" / INHERITED,
        provider.parent / f".{PROTOCOL}.attempt-5eab359802b14798b3f7822bab617fdd",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    artifact = provider / "providers/a.csv"
    artifact.write_text("fresh\n", encoding="utf-8")
    hashes = {"artifact": sha256_file(artifact)}
    bundle = hashlib.sha256(
        json.dumps(hashes, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    provider_manifest = {
        "generator_code_commit": OLD,
        "generator_worktree_dirty": False,
        "provider_bundle_hash": bundle,
        "trace_used_online": False,
        "raw_doppler_backend": {"raw_doppler_backend_lineage_proven": True},
        "artifacts": {"artifact": {"relative_path": "providers/a.csv"}},
        "provider_hashes": hashes,
    }
    _write_json(provider / "CLEAN_INPUT_MANIFEST.json", provider_manifest)
    _write_json(stage / "04_PROVIDER_AUDIT/PROVIDER_MANIFEST.json", provider_manifest)
    _write_json(
        stage / "08_EVIDENCE_AUDIT/PRE_RUN_GATE_DECISION.json",
        {
            "code_freeze_commit": OLD,
            "provider_bundle_hash": bundle,
            "fresh_provider_generated": True,
            "formal_runs_authorized_by_all_gates": True,
            "raw_pre_verified": 22,
            "raw_post_verified": 22,
            "raw_mutation_count": 0,
        },
    )
    _write_json(
        stage / "06_RUN_MANIFESTS/FOUR_METHOD_RUN_BLOCKED.json",
        {
            "schema_version": "paper-rebuild-clean1-four-run-gate-v1",
            "formal_run_count": 0,
            "method_count_required": 4,
            "metric_driven_rerun": False,
            "terminal_status": "FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH",
            "paper_performance_claim": False,
        },
    )
    _write_json(
        stage / "03_DATA_HASH_AND_ROLES/BY2_RAW_22_SUMMARY.json",
        {"passed": True, "pre_verified": 22, "post_verified": 22, "raw_mutation": 0},
    )
    _write_json(
        stage / "08_EVIDENCE_AUDIT/PROMOTION_COMPLETE.json",
        {
            "provider_final_promoted": True,
            "stage_final_promoted": True,
            "provider_bundle_hash": bundle,
        },
    )
    _write_json(
        stage / "00_AUTHORIZATION/PRIOR_TECHNICAL_ATTEMPT.json",
        {
            "code_freeze_commit": INHERITED,
            "replacement_code_commit": OLD,
            "formal_run_count": 0,
            "preserved_without_delete": True,
            "evidence_manifest_sha256": "e" * 64,
        },
    )
    _write_json(
        provider.parent
        / f".{PROTOCOL}.attempt-5eab359802b14798b3f7822bab617fdd"
        / "CLEAN_INPUT_MANIFEST.json",
        {"generator_code_commit": INHERITED},
    )
    counts = {
        "position_update_count": 2,
        "receiver_velocity_update_count": 2,
        "dual_yaw_update_count": 0,
        "raw_doppler_update_count": 0,
        "source_aware_evaluation_count": 0,
        "go2_roll_pitch_update_count": 0,
        "go2_horizontal_velocity_update_count": 0,
        "selected_fgo_feedback_update_count": 0,
        "nine_factor_fgo_update_count": 0,
        "qa_fallback_count": 0,
        "multi_state_qm_update_count": 0,
        "contact_fk_update_count": 0,
    }
    solver = {
        "stage_id": "CLEAN1R1C_FROZEN_PROTOCOL_DIRECT_REIMPLEMENTATION_AND_BY2_FORMAL_EXECUTION",
        "protocol_id": PROTOCOL,
        "algorithm_id": "single_antenna_EKF",
        "run_id": "01_single_antenna_EKF",
        "module_update_counts": counts,
    }
    run_root = runtime / "01_single_antenna_EKF"
    _write_json(run_root / "RUN_MANIFEST.json", solver)
    _write_json(
        run_root / "logs/SOLVER_FILE_OPEN_CROSSCHECK.json",
        {
            "passed": True,
            "legacy_path_read_count": 0,
            "raw_root_read_relative_paths": [],
            "unexpected_provider_relative_paths": [],
            "unexpected_clean_root_relative_paths": [],
        },
    )

    paths = SimpleNamespace(
        clean_root=clean,
        code_root=tmp_path,
        provider_root=provider,
        runtime_root=runtime_parent / PROTOCOL,
    )
    stage_count, stage_hash = generator._tree_digest_without_retry_archive(stage)
    runtime_count, runtime_hash = generator._tree_digest_exact(runtime)
    specification = {
        "terminal_status": "FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH",
        "superseded_reason": "fixture",
        "expected_stage_file_count": stage_count,
        "expected_stage_tree_sha256": stage_hash,
        "expected_provider_manifest_sha256": sha256_file(
            provider / "CLEAN_INPUT_MANIFEST.json"
        ),
        "expected_provider_bundle_hash": bundle,
        "expected_runtime_file_count": runtime_count,
        "expected_runtime_tree_sha256": runtime_hash,
        "expected_solver_manifest_sha256": sha256_file(
            run_root / "RUN_MANIFEST.json"
        ),
    }
    monkeypatch.setattr(generator, "FAILED_ATTEMPT_DIR_NAME", "stage_FAILED_ATTEMPTS")
    monkeypatch.setattr(generator, "_git_first_parent", lambda *_args: OLD)
    return paths, stage, archive, specification


def test_method_retry_archive_dry_run_then_idempotent_completion(
    tmp_path: Path, monkeypatch: object
) -> None:
    paths, stage, archive, specification = _fixture(tmp_path, monkeypatch)
    dry = generator._preserve_method_contract_attempt_for_retry(
        paths,
        new_code_commit=NEW,
        old_code_commit=OLD,
        specification=specification,
        stage_source=stage,
        stage_archive=archive,
        perform_archive=False,
    )
    assert dry["archive_dry_run"] is True
    assert stage.is_dir() and paths.provider_root.is_dir()

    complete = generator._preserve_method_contract_attempt_for_retry(
        paths,
        new_code_commit=NEW,
        old_code_commit=OLD,
        specification=specification,
        stage_source=stage,
        stage_archive=archive,
        perform_archive=True,
    )
    assert complete["archive_state"] == "COMPLETE"
    assert not stage.exists() and not paths.provider_root.exists()
    assert (archive / "11_TECHNICAL_RETRY_ARCHIVE/preserved_provider").is_dir()
    assert (archive / "11_TECHNICAL_RETRY_ARCHIVE/preserved_runtime").is_dir()

    repeated = generator._preserve_method_contract_attempt_for_retry(
        paths,
        new_code_commit=NEW,
        old_code_commit=OLD,
        specification=specification,
        stage_source=stage,
        stage_archive=archive,
        perform_archive=True,
    )
    assert repeated["archive_state"] == "COMPLETE"


def test_method_retry_archive_rejects_malformed_runtime_attempt(
    tmp_path: Path, monkeypatch: object
) -> None:
    paths, stage, archive, specification = _fixture(tmp_path, monkeypatch)
    runtime_parent = paths.runtime_root.parent
    runtime = next(runtime_parent.glob(f".{PROTOCOL}.attempt-*"))
    runtime.rename(runtime_parent / f".{PROTOCOL}.attempt-not-a-uuid")
    with pytest.raises(RuntimeError, match="FAIL_CLEAN1_EVIDENCE_CONTAMINATION"):
        generator._preserve_method_contract_attempt_for_retry(
            paths,
            new_code_commit=NEW,
            old_code_commit=OLD,
            specification=specification,
            stage_source=stage,
            stage_archive=archive,
            perform_archive=False,
        )


def _prepare_final_chain(
    tmp_path: Path, monkeypatch: object
) -> tuple[Path, object, Path, Path]:
    paths, stage, archive, specification = _fixture(tmp_path, monkeypatch)
    complete = generator._preserve_method_contract_attempt_for_retry(
        paths,
        new_code_commit=NEW,
        old_code_commit=OLD,
        specification=specification,
        stage_source=stage,
        stage_archive=archive,
        perform_archive=True,
    )
    active_stage = paths.clean_root / "stage"
    _write_json(
        active_stage / "00_AUTHORIZATION/PRIOR_TECHNICAL_ATTEMPT.json",
        complete,
    )
    paths.raw_root = tmp_path / "raw"
    paths.raw_root.mkdir()
    inherited_provider = (
        paths.provider_root.parent
        / f".{PROTOCOL}.attempt-5eab359802b14798b3f7822bab617fdd"
    )
    inherited_files = {
        path.relative_to(inherited_provider).as_posix()
        for path in inherited_provider.rglob("*")
        if path.is_file()
    }
    inherited_spec = {
        "expected_provider_file_count": len(inherited_files),
        "expected_provider_tree_sha256": generator.canonical_file_tree_digest(
            inherited_provider, inherited_files
        ),
        "expected_provider_manifest_sha256": sha256_file(
            inherited_provider / "CLEAN_INPUT_MANIFEST.json"
        ),
    }
    monkeypatch.setitem(final_audit.FAILED_CLEAN1_ATTEMPT_SPECS, OLD, specification)
    monkeypatch.setitem(
        final_audit.FAILED_CLEAN1_ATTEMPT_SPECS, INHERITED, inherited_spec
    )
    monkeypatch.setattr(
        final_audit,
        "validate_failed_clean1_attempt_evidence",
        lambda *_args, **_kwargs: {"evidence_manifest_sha256": "e" * 64},
    )
    preserved_artifact = (
        archive / "11_TECHNICAL_RETRY_ARCHIVE/preserved_provider/providers/a.csv"
    )
    return active_stage, paths, preserved_artifact, inherited_provider


def test_final_chain_gate_rejects_mutated_preserved_provider_artifact(
    tmp_path: Path, monkeypatch: object
) -> None:
    stage, paths, artifact, _inherited = _prepare_final_chain(
        tmp_path, monkeypatch
    )
    assert final_audit._validate_technical_retry_chain(stage, paths, NEW) is True
    artifact.write_text("mutated\n", encoding="utf-8")
    assert final_audit._validate_technical_retry_chain(stage, paths, NEW) is False


def test_final_chain_gate_rejects_deleted_inherited_provider_file(
    tmp_path: Path, monkeypatch: object
) -> None:
    stage, paths, _artifact, inherited = _prepare_final_chain(
        tmp_path, monkeypatch
    )
    assert final_audit._validate_technical_retry_chain(stage, paths, NEW) is True
    (inherited / "CLEAN_INPUT_MANIFEST.json").unlink()
    assert final_audit._validate_technical_retry_chain(stage, paths, NEW) is False
