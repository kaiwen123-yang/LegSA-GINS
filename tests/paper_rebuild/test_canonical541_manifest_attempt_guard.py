from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml

from legsa_gins.paper_rebuild.canonical541.authorization import (
    PROTOCOL_ID, RUNTIME_ROLE, STAGE_ID,
)


SCRIPT = Path(__file__).resolve().parents[2] / "scripts/paper_rebuild/build_canonical541_manifest.py"
SPEC = importlib.util.spec_from_file_location("canonical_manifest_builder", SCRIPT)
builder = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(builder)


def _local_config(path: Path, runtime_root: Path) -> Path:
    path.write_text(yaml.safe_dump({"paths": {"runtime_root": str(runtime_root)}}), encoding="utf-8")
    return path


def test_manifest_builder_rejects_bare_stage_before_any_write(monkeypatch, tmp_path):
    bare = tmp_path / STAGE_ID; bare.mkdir()
    local = _local_config(tmp_path / "local.yaml", bare)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--local-config", str(local),
                        "--code-freeze-commit", "a" * 40, "--executable", str(local)])
    with pytest.raises(Exception, match="runtime_root must be exactly"):
        builder.main()
    assert list(bare.iterdir()) == []


def test_manifest_builder_rejects_nonmatching_output_override_before_write(monkeypatch, tmp_path):
    stage = tmp_path / STAGE_ID; configured = stage / ".attempt_configured"
    override = stage / ".attempt_override"; configured.mkdir(parents=True); override.mkdir()
    local = _local_config(tmp_path / "local.yaml", configured)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--local-config", str(local),
                        "--output-root", str(override), "--code-freeze-commit", "a" * 40,
                        "--executable", str(local)])
    with pytest.raises(SystemExit, match="exactly equal"):
        builder.main()
    assert list(configured.iterdir()) == [] and list(override.iterdir()) == []


def _freeze_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    stage = tmp_path / STAGE_ID
    attempt = stage / ".attempt_test"
    attempt.mkdir(parents=True)
    origin_stage = tmp_path / "CLEAN2R2B_BY2_CANONICAL_541_CASE_MATRIX"
    external = origin_stage / "05_PROVIDER_GENERATION"
    finalized = external / "FINALIZED"
    finalized.mkdir(parents=True)
    gate = origin_stage / "06_PROVIDER_READY/PROVIDER_GATE.json"
    gate.parent.mkdir()
    gate.write_text(
        json.dumps({
            "finalized_provider_root": str(finalized.resolve()),
            "passed": True, "provider_generation": 541, "provider_ready": 541,
            "effect_validation": 541, "provider_sha_rows": 4328,
            "provider_sha_closure": True, "raw_mutation": 0, "trace_open_count": 0,
        }) + "\n",
        encoding="utf-8",
    )
    executable = tmp_path / "solver"
    executable.write_bytes(b"solver")
    return attempt, external, executable


def test_external_finalized_provider_origin_does_not_count_as_attempt_generation(tmp_path):
    attempt, external, executable = _freeze_fixture(tmp_path)
    gate = builder._initialize_code_freeze(
        output=attempt, external_provider_root=external,
        executable=executable.resolve(), code_freeze_commit="a" * 40,
    )
    origin_gate = external.parent / "06_PROVIDER_READY/PROVIDER_GATE.json"
    assert gate["provider_generation_count_at_freeze"] == 0
    assert gate["formal_solver_run_count_at_freeze"] == 0
    assert gate["trace_open_count_at_freeze"] == 0
    assert gate["attempt_owned_provider_artifact_count"] == 0
    assert gate["attempt_owned_readiness_artifact_count"] == 0
    assert gate["attempt_owned_prepared_input_artifact_count"] == 0
    assert gate["attempt_owned_formal_artifact_count"] == 0
    assert gate["attempt_owned_output_seal_artifact_count"] == 0
    assert gate["attempt_owned_misplaced_execution_artifact_count"] == 0
    assert gate["attempt_owned_trace_ledger_count"] == 0
    assert gate["external_provider_origin"] == {
        "role": "READ_ONLY_PROVIDER_REUSE_ORIGIN_NOT_ATTEMPT_OWNED",
        "path": str(external.resolve()),
        "finalized_provider_root": str((external / "FINALIZED").resolve()),
        "provider_gate_path": str(origin_gate.resolve()),
        "provider_gate_sha256": hashlib.sha256(origin_gate.read_bytes()).hexdigest(),
        "passed": True, "provider_generation": 541, "provider_ready": 541,
        "effect_validation": 541, "provider_sha_rows": 4328,
        "provider_sha_closure": True, "raw_mutation": 0, "trace_open_count": 0,
    }
    assert gate["protocol_id"] == PROTOCOL_ID and gate["runtime_role"] == RUNTIME_ROLE
    written = json.loads(
        (attempt / "01_GIT_FREEZE/CANONICAL541_CODE_FREEZE.json").read_text()
    )
    assert written == gate


def test_attempt_owned_provider_marker_blocks_before_freeze_write(tmp_path):
    attempt, external, executable = _freeze_fixture(tmp_path)
    (attempt / "05_PROVIDER_GENERATION/FINALIZED").mkdir(parents=True)
    with pytest.raises(SystemExit, match="attempt-owned readiness/providers"):
        builder._initialize_code_freeze(
            output=attempt, external_provider_root=external,
            executable=executable.resolve(), code_freeze_commit="a" * 40,
        )
    assert not (attempt / "01_GIT_FREEZE").exists()


@pytest.mark.parametrize(
    "relative",
    [
        "08_FULL_ALGORITHM_RUNS/RUN_TEST/KF_GINS_Navresult.nav",
        "10_INTERNAL_ABLATION_RUNS/RUN_TEST/KF_GINS_STD.txt",
        "08_FULL_ALGORITHM_RUNS/RUN_TEST/CANONICAL541_EXECUTION_PROOF.json",
        "EVALUATOR_FILE_OPEN_TRACE.raw",
    ],
)
def test_attempt_owned_run_or_trace_artifact_blocks_before_freeze_write(tmp_path, relative):
    attempt, external, executable = _freeze_fixture(tmp_path)
    artifact = attempt / relative
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("forbidden before freeze\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="attempt-owned readiness/providers"):
        builder._initialize_code_freeze(
            output=attempt, external_provider_root=external,
            executable=executable.resolve(), code_freeze_commit="a" * 40,
        )
    assert not (attempt / "01_GIT_FREEZE").exists()


@pytest.mark.parametrize(
    "relative",
    [
        "01_COMPACT_READINESS_RUN/COMPACT_READINESS_RUN_REPORT.json",
        ("07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/METHOD_BOUND/AB0000/"
         "METHOD_BOUND_INPUT_MANIFEST.json"),
        ("07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/"
         "SHARED_GNSS_BY_HASH/abc.gnss"),
        "11_OUTPUT_SEAL/OUTPUT_SEAL_JOURNAL.json",
    ],
)
def test_known_attempt_owned_destination_blocks_before_freeze_write(tmp_path, relative):
    attempt, external, executable = _freeze_fixture(tmp_path)
    artifact = attempt / relative
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("pre-freeze artifact\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="attempt-owned readiness/providers"):
        builder._initialize_code_freeze(
            output=attempt, external_provider_root=external,
            executable=executable.resolve(), code_freeze_commit="a" * 40,
        )
    assert not (attempt / "01_GIT_FREEZE").exists()


@pytest.mark.parametrize(
    "name",
    [
        "KF_GINS_Navresult.nav", "KF_GINS_STD.txt", "RUN_MANIFEST.json",
        "CANONICAL541_EXECUTION_PROOF.json", "CANONICAL541_FORMAL_RUN_MANIFEST.json",
        "OUTPUT_HASH_MANIFEST.csv",
        "OUTPUT_SEAL_JOURNAL.json", "SOLVER_READ_LEDGER.json",
        "MISPLACED_FILE_OPEN_TRACE.raw",
    ],
)
def test_misplaced_execution_or_seal_file_blocks_before_freeze_write(tmp_path, name):
    attempt, external, executable = _freeze_fixture(tmp_path)
    artifact = attempt / "MISC_UNEXPECTED" / name
    artifact.parent.mkdir()
    artifact.write_text("misplaced\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="attempt-owned readiness/providers"):
        builder._initialize_code_freeze(
            output=attempt, external_provider_root=external,
            executable=executable.resolve(), code_freeze_commit="a" * 40,
        )
    assert not (attempt / "01_GIT_FREEZE").exists()


@pytest.mark.parametrize("mutation", ["missing", "wrong_finalized", "bad_counts"])
def test_external_provider_gate_must_be_authoritative_and_exact(tmp_path, mutation):
    attempt, external, executable = _freeze_fixture(tmp_path)
    gate_path = external.parent / "06_PROVIDER_READY/PROVIDER_GATE.json"
    if mutation == "missing":
        gate_path.unlink()
    else:
        payload = json.loads(gate_path.read_text())
        if mutation == "wrong_finalized":
            wrong = external.parent / "WRONG_FINALIZED"
            wrong.mkdir()
            payload["finalized_provider_root"] = str(wrong.resolve())
        else:
            payload["provider_ready"] = 540
        gate_path.write_text(json.dumps(payload) + "\n")
    with pytest.raises(SystemExit, match="external provider gate"):
        builder._initialize_code_freeze(
            output=attempt, external_provider_root=external,
            executable=executable.resolve(), code_freeze_commit="a" * 40,
        )
    assert not (attempt / "01_GIT_FREEZE").exists()


@pytest.mark.parametrize(
    "field",
    [
        "schema_version", "stage_id", "protocol_id", "runtime_role",
        "code_freeze_commit", "executable_path", "executable_sha256",
        "provider_generation_count_at_freeze", "formal_solver_run_count_at_freeze",
        "trace_open_count_at_freeze", "degraded_provider_generation_started_before_freeze",
        "formal_solver_run_started_before_freeze", "worktree_clean",
        "attempt_owned_readiness_artifact_count", "attempt_owned_provider_artifact_count",
        "attempt_owned_prepared_input_artifact_count", "attempt_owned_formal_artifact_count",
        "attempt_owned_output_seal_artifact_count",
        "attempt_owned_misplaced_execution_artifact_count",
        "attempt_owned_trace_ledger_count", "passed",
    ],
)
def test_existing_freeze_revalidates_every_required_top_level_field(tmp_path, field):
    attempt, external, executable = _freeze_fixture(tmp_path)
    builder._initialize_code_freeze(
        output=attempt, external_provider_root=external,
        executable=executable.resolve(), code_freeze_commit="a" * 40,
    )
    path = attempt / "01_GIT_FREEZE/CANONICAL541_CODE_FREEZE.json"
    payload = json.loads(path.read_text())
    value = payload[field]
    payload[field] = (not value) if isinstance(value, bool) else (value + 1 if isinstance(value, int) else "tampered")
    path.write_text(json.dumps(payload) + "\n")
    with pytest.raises(SystemExit, match="existing code-freeze evidence differs"):
        builder._initialize_code_freeze(
            output=attempt, external_provider_root=external,
            executable=executable.resolve(), code_freeze_commit="a" * 40,
        )


@pytest.mark.parametrize(
    "field",
    ["path", "finalized_provider_root", "provider_gate_path", "provider_gate_sha256"],
)
def test_existing_freeze_revalidates_external_origin_provenance(tmp_path, field):
    attempt, external, executable = _freeze_fixture(tmp_path)
    builder._initialize_code_freeze(
        output=attempt, external_provider_root=external,
        executable=executable.resolve(), code_freeze_commit="a" * 40,
    )
    path = attempt / "01_GIT_FREEZE/CANONICAL541_CODE_FREEZE.json"
    payload = json.loads(path.read_text())
    payload["external_provider_origin"][field] = "tampered"
    path.write_text(json.dumps(payload) + "\n")
    with pytest.raises(SystemExit, match="existing code-freeze evidence differs"):
        builder._initialize_code_freeze(
            output=attempt, external_provider_root=external,
            executable=executable.resolve(), code_freeze_commit="a" * 40,
        )


def test_existing_partial_pre_fix_freeze_is_rejected(tmp_path):
    attempt, external, executable = _freeze_fixture(tmp_path)
    freeze_root = attempt / "01_GIT_FREEZE"
    freeze_root.mkdir()
    (freeze_root / "CANONICAL541_CODE_FREEZE.json").write_text(json.dumps({
        "code_freeze_commit": "a" * 40,
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "passed": True,
    }) + "\n")
    with pytest.raises(SystemExit, match="existing code-freeze evidence differs"):
        builder._initialize_code_freeze(
            output=attempt, external_provider_root=external,
            executable=executable.resolve(), code_freeze_commit="a" * 40,
        )
