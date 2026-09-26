import csv
import hashlib
import json
from pathlib import Path

import pytest

from legsa_gins.paper_rebuild.canonical541 import preparation


def _csv(path: Path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)


def _fixture(monkeypatch, tmp_path):
    stage = tmp_path / ".attempt_20260809T000000P0800"; stage.mkdir()
    monkeypatch.setattr(preparation, "validate_attempt_root", lambda value: Path(value))
    monkeypatch.setattr(preparation, "METHOD_BOUND_TOTAL", 2)
    monkeypatch.setattr(preparation, "FULL_QUEUE_TOTAL", 2)
    monkeypatch.setattr(preparation, "ABLATION_QUEUE_TOTAL", 1)
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_UNIQUE_COUNT", 2)
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_ALIAS_COUNT", 1)
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_ANNOTATED_COUNT", 1)
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_UNTOUCHED_COUNT", 1)
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_CONFIG_COUNT", 1)
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_CASE_COUNT", 2)
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_PROFILES_PER_CASE", 1)
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_COMMIT", "c" * 40)
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_PIDS", frozenset((99999991, 99999992)))
    registry = stage / "07_FULL_ALGORITHM_REGISTRY"
    for _, relative_root in preparation.PROTECTED_LIVE_ROOTS:
        root = stage / relative_root; root.mkdir(parents=True, exist_ok=True)
        (root / "frozen_evidence.txt").write_text(f"{relative_root}\n")
    _csv(registry / "CANONICAL541_UNIQUE_RUN_REGISTRY.csv", [{"run_id": "RUN_00001"}, {"run_id": "RUN_00002"}])
    _csv(registry / "FULL_ALGORITHM_QUEUE.csv", [
        {"logical_id": "F1", "execution_alias": "false"},
        {"logical_id": "F2", "execution_alias": "false"},
    ])
    _csv(stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv", [
        {"logical_id": "A1", "execution_alias": "true"},
    ])
    (registry / "EXECUTION_PLAN.json").write_text(json.dumps({
        "schema_version": "paper_rebuild.canonical541_execution_plan.v3_repaired",
        "scientific_code_freeze_commit": "c" * 40, "preparation_code_commit": "c" * 40,
        "unique_run_count": 2,
    }) + "\n", encoding="utf-8")
    (registry / "PREPARATION_STATUS.json").write_text("{}\n", encoding="utf-8")
    method_root = registry / "PREPARED_EXECUTION_INPUTS/METHOD_BOUND"
    for index in range(2):
        path = method_root / f"C{index}" / "profile" / "METHOD_BOUND_INPUT_MANIFEST.json"
        path.parent.mkdir(parents=True)
        payload = {"case_id": f"C{index}"}
        if index == 0:
            payload["actual_rendered_runtime_config_sha256"] = "a" * 64
        path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    config = registry / "PREPARED_EXECUTION_INPUTS/RUNTIME_CONFIGS/RUN_00001.yaml"
    config.parent.mkdir(parents=True); config.write_text("stage: test\n", encoding="utf-8")
    (stage / "RUN_SESSION.json").write_text(json.dumps({
        "attempt_root": str(stage), "code_freeze_commit": "c" * 40, "pid": 99999991,
    }) + "\n")
    (stage / "CANONICAL541_STATUS.json").write_text(json.dumps({
        "phase": "PIPELINE_STEP_2_OF_6", "process_pid": 99999992,
        "trace_reads_before_seal": 0,
    }) + "\n")
    logs = stage / "00_PIPELINE_LOGS"; logs.mkdir()
    (logs / "pipeline.stdout.log").write_text("preparation progress\n")
    (logs / "pipeline.stderr.log").write_text("prepared input mutated during hash cache lifetime\n")
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_HASHES", {
        path.name: preparation.sha256_file(path) for path in (
            registry / "EXECUTION_PLAN.json",
            registry / "CANONICAL541_UNIQUE_RUN_REGISTRY.csv",
            registry / "FULL_ALGORITHM_QUEUE.csv",
            stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv",
            registry / "PREPARATION_STATUS.json",
        )
    })
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_SESSION_HASHES", {
        path.name: preparation.sha256_file(path) for path in (
            stage / "RUN_SESSION.json", stage / "CANONICAL541_STATUS.json",
            logs / "pipeline.stdout.log", logs / "pipeline.stderr.log",
        )
    })
    return stage


def test_known_3981_recovery_preserves_bytes_resets_only_rendered_field_and_is_idempotent(monkeypatch, tmp_path):
    stage = _fixture(monkeypatch, tmp_path)
    result = preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    assert result["terminal_status"] == "RECOVERY_COMPLETE"
    recovery = stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_RECOVERY_KNOWN_3981"
    ledger = json.loads((recovery / "RESET_LEDGER.json").read_text(encoding="utf-8"))
    assert len(ledger["reset_rows"]) == 1
    for row in ledger["reset_rows"]:
        assert hashlib.sha256(Path(row["preserved_path"]).read_bytes()).hexdigest() == row["original_sha256"]
        payload = json.loads(Path(row["path"]).read_text(encoding="utf-8"))
        original = json.loads(Path(row["preserved_path"]).read_text(encoding="utf-8"))
        assert set(original) - set(payload) == {"actual_rendered_runtime_config_sha256"}
        assert all(original[key] == value for key, value in payload.items())
    assert preparation.recover_known_3981_preparation(stage, explicitly_authorized=True) == result
    assert (recovery / "RECOVERY_COMPLETE.json").stat().st_mtime_ns >= (recovery / "RESET_LEDGER.json").stat().st_mtime_ns


def test_known_3981_recovery_rejects_any_formal_activity_before_write(monkeypatch, tmp_path):
    stage = _fixture(monkeypatch, tmp_path)
    proof = stage / "08_FULL_ALGORITHM_RUNS/RUN_00001/RUN_PROOF.json"
    proof.parent.mkdir(parents=True); proof.write_text("{}\n", encoding="utf-8")
    with pytest.raises(preparation.PreparationError, match="zero formal"):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    assert not (stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_RECOVERY_KNOWN_3981").exists()


def test_known_3981_recovery_rejects_foreign_lock(monkeypatch, tmp_path):
    stage = _fixture(monkeypatch, tmp_path)
    (stage / "runner.lock").write_text(json.dumps({
        "pid": 99999999, "stage_root": "/foreign", "code_freeze_commit": "c" * 40,
    }) + "\n", encoding="utf-8")
    with pytest.raises(preparation.PreparationError, match="foreign"):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)


def test_known_3981_recovery_resumes_after_quarantine_crash(monkeypatch, tmp_path):
    stage = _fixture(monkeypatch, tmp_path)
    original_replace = preparation.os.replace
    crashed = {"value": False}
    def crash_once(source, destination):
        if Path(source).name == "FULL_ALGORITHM_QUEUE.csv" and not crashed["value"]:
            crashed["value"] = True
            raise OSError("injected rename crash")
        return original_replace(source, destination)
    monkeypatch.setattr(preparation.os, "replace", crash_once)
    with pytest.raises(OSError, match="injected"):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    monkeypatch.setattr(preparation.os, "replace", original_replace)
    result = preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    assert result["terminal_status"] == "RECOVERY_COMPLETE"
    phases = json.loads((stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_RECOVERY_KNOWN_3981/RECOVERY_PHASES.json").read_text())
    assert phases["phases"] == [
        "BOOTSTRAP_DURABLE", "PREINVENTORY_DURABLE", "ORIGINALS_PRESERVED",
        "RENDERED_FIELDS_RESET", "PROTECTED_ARTIFACTS_QUARANTINED", "POSTINVENTORY_VALIDATED",
        "RECOVERY_COMPLETE",
    ]


def test_completed_recovery_revalidates_all_manifest_bytes(monkeypatch, tmp_path):
    stage = _fixture(monkeypatch, tmp_path)
    preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    manifest = next((stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/METHOD_BOUND").rglob("METHOD_BOUND_INPUT_MANIFEST.json"))
    payload = json.loads(manifest.read_text()); payload["foreign"] = True
    manifest.write_text(json.dumps(payload) + "\n")
    with pytest.raises(preparation.PreparationError):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)


def test_known_3981_fixed_hash_tamper_fails_before_recovery_root(monkeypatch, tmp_path):
    stage = _fixture(monkeypatch, tmp_path)
    plan = stage / "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json"
    plan.write_text(plan.read_text() + " ")
    with pytest.raises(preparation.PreparationError, match="signature/hash"):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    assert not (stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_RECOVERY_KNOWN_3981").exists()


def test_recovery_requires_explicit_invocation(monkeypatch, tmp_path):
    stage = _fixture(monkeypatch, tmp_path)
    with pytest.raises(preparation.PreparationError, match="explicit invocation"):
        preparation.recover_known_3981_preparation(stage)


def test_recovery_rejects_session_status_or_log_mutation(monkeypatch, tmp_path):
    stage = _fixture(monkeypatch, tmp_path)
    status = stage / "CANONICAL541_STATUS.json"; status.write_text(status.read_text() + " ")
    with pytest.raises(preparation.PreparationError, match="session/status/log hash"):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)


@pytest.mark.parametrize("pid_value", ["99999991", 99999990])
def test_recovery_requires_exact_integer_pid_set(monkeypatch, tmp_path, pid_value):
    stage = _fixture(monkeypatch, tmp_path)
    session = stage / "RUN_SESSION.json"; payload = json.loads(session.read_text()); payload["pid"] = pid_value
    session.write_text(json.dumps(payload) + "\n")
    hashes = dict(preparation.KNOWN_RECOVERY_SESSION_HASHES); hashes["RUN_SESSION.json"] = preparation.sha256_file(session)
    monkeypatch.setattr(preparation, "KNOWN_RECOVERY_SESSION_HASHES", hashes)
    with pytest.raises(preparation.PreparationError, match="PID identity/type"):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)


@pytest.mark.parametrize("variant", ["uppercase", "single_space", "wrong_name", "no_lf"])
def test_complete_rejects_noncanonical_sidecar_bytes(monkeypatch, tmp_path, variant):
    stage = _fixture(monkeypatch, tmp_path)
    preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    recovery = stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_RECOVERY_KNOWN_3981"
    artifact = recovery / "RECOVERY_COMPLETE.json"; digest = preparation.sha256_file(artifact)
    values = {
        "uppercase": f"{digest.upper()}  {artifact.name}\n",
        "single_space": f"{digest} {artifact.name}\n",
        "wrong_name": f"{digest}  WRONG.json\n",
        "no_lf": f"{digest}  {artifact.name}",
    }
    (recovery / "RECOVERY_COMPLETE.json.sha256").write_bytes(values[variant].encode("ascii"))
    with pytest.raises(preparation.PreparationError, match="sidecar"):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)


def test_pre_scan_rejects_unexpected_method_file(monkeypatch, tmp_path):
    stage = _fixture(monkeypatch, tmp_path)
    extra = stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/METHOD_BOUND/C0/profile/EXTRA.json"
    extra.write_text("{}\n")
    with pytest.raises(preparation.PreparationError, match="exactly 5951"):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)


@pytest.mark.parametrize("tamper", ["omitted_root", "manifest_path"])
def test_resume_rejects_coherently_rehashed_preinventory_tamper(monkeypatch, tmp_path, tamper):
    stage = _fixture(monkeypatch, tmp_path)
    original_copy = preparation.shutil.copy2
    monkeypatch.setattr(preparation.shutil, "copy2", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("stop")))
    with pytest.raises(OSError, match="stop"):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    monkeypatch.setattr(preparation.shutil, "copy2", original_copy)
    recovery = stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_RECOVERY_KNOWN_3981"
    inventory_path = recovery / "PREINVENTORY.json"
    inventory = json.loads(inventory_path.read_text())
    if tamper == "omitted_root":
        inventory["protected_live_pre"]["roots"].pop()
    else:
        inventory["manifest_rows"][0]["path"] = inventory["manifest_rows"][1]["path"]
    inventory_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    (recovery / "PREINVENTORY.json.sha256").write_bytes(
        preparation._canonical_sidecar_bytes(inventory_path)
    )
    with pytest.raises(preparation.PreparationError):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)


def test_post_complete_rejects_git_freeze_mutation(monkeypatch, tmp_path):
    stage = _fixture(monkeypatch, tmp_path)
    preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    freeze = stage / "01_GIT_FREEZE/frozen_evidence.txt"; freeze.write_text("mutated\n")
    with pytest.raises(preparation.PreparationError, match="COMPLETE rescan"):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)


@pytest.mark.parametrize("tamper", ["duplicate", "omitted"])
def test_post_complete_rejects_coherent_manifest_row_set_tamper(monkeypatch, tmp_path, tamper):
    stage = _fixture(monkeypatch, tmp_path)
    preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    recovery = stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_RECOVERY_KNOWN_3981"
    inventory_path = recovery / "PREINVENTORY.json"
    inventory = json.loads(inventory_path.read_text())
    if tamper == "duplicate":
        inventory["manifest_rows"][1] = dict(inventory["manifest_rows"][0])
    else:
        inventory["manifest_rows"].pop()
    inventory_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n")
    (recovery / "PREINVENTORY.json.sha256").write_bytes(preparation._canonical_sidecar_bytes(inventory_path))
    complete_path = recovery / "RECOVERY_COMPLETE.json"
    complete = json.loads(complete_path.read_text())
    complete["preinventory_sha256"] = preparation.sha256_file(inventory_path)
    complete_path.write_text(json.dumps(complete, indent=2, sort_keys=True) + "\n")
    (recovery / "RECOVERY_COMPLETE.json.sha256").write_bytes(preparation._canonical_sidecar_bytes(complete_path))
    with pytest.raises(preparation.PreparationError):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)


@pytest.mark.parametrize(
    "fault", ["bootstrap", "preinventory", "copy", "reset", "quarantine", "configs", "post", "complete"],
)
def test_known_recovery_resumes_from_every_durable_phase(monkeypatch, tmp_path, fault):
    stage = _fixture(monkeypatch, tmp_path)
    original_json = preparation._atomic_json
    original_copy = preparation.shutil.copy2
    original_replace = preparation.os.replace
    fired = {"value": False}

    def fail():
        fired["value"] = True
        raise OSError(f"fault:{fault}")

    def guarded_json(path, payload):
        name = Path(path).name
        matches = {
            "bootstrap": name == "RECOVERY_BOOTSTRAP.json",
            "preinventory": name == "PREINVENTORY.json",
            "reset": name == "METHOD_BOUND_INPUT_MANIFEST.json",
            "post": name == "POSTINVENTORY.json",
            "complete": name == "RECOVERY_COMPLETE.json",
        }
        if matches.get(fault, False) and not fired["value"]:
            fail()
        return original_json(path, payload)

    def guarded_copy(source, destination):
        if fault == "copy" and not fired["value"]:
            fail()
        return original_copy(source, destination)

    def guarded_replace(source, destination):
        name = Path(source).name
        if not fired["value"] and (
            (fault == "quarantine" and name == "FULL_ALGORITHM_QUEUE.csv")
            or (fault == "configs" and name == "RUNTIME_CONFIGS")
        ):
            fail()
        return original_replace(source, destination)

    monkeypatch.setattr(preparation, "_atomic_json", guarded_json)
    monkeypatch.setattr(preparation.shutil, "copy2", guarded_copy)
    monkeypatch.setattr(preparation.os, "replace", guarded_replace)
    with pytest.raises(OSError, match=f"fault:{fault}"):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    if fault == "preinventory":
        manifests = list((stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/METHOD_BOUND").rglob("METHOD_BOUND_INPUT_MANIFEST.json"))
        assert sum("actual_rendered_runtime_config_sha256" in json.loads(path.read_text()) for path in manifests) == 1
        assert not (stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_RECOVERY_KNOWN_3981/ORIGINAL_METHOD_MANIFESTS").exists()
    monkeypatch.setattr(preparation, "_atomic_json", original_json)
    monkeypatch.setattr(preparation.shutil, "copy2", original_copy)
    monkeypatch.setattr(preparation.os, "replace", original_replace)
    assert preparation.recover_known_3981_preparation(
        stage, explicitly_authorized=True,
    )["terminal_status"] == "RECOVERY_COMPLETE"


@pytest.mark.parametrize(
    "tamper", ["extra", "symlink", "method_symlink", "missing_original", "missing_config",
               "missing_moved", "stale_config", "coherent_reset", "output", "trace"],
)
def test_complete_independent_rescan_rejects_protected_tree_tamper(monkeypatch, tmp_path, tamper):
    stage = _fixture(monkeypatch, tmp_path)
    preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
    recovery = stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_RECOVERY_KNOWN_3981"
    if tamper == "extra":
        (recovery / "UNKNOWN.bin").write_bytes(b"x")
    elif tamper == "symlink":
        (recovery / "FOREIGN_LINK").symlink_to(stage / "RUN_SESSION.json")
    elif tamper == "method_symlink":
        target = next((stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/METHOD_BOUND").rglob("METHOD_BOUND_INPUT_MANIFEST.json"))
        target.unlink(); target.symlink_to(stage / "RUN_SESSION.json")
    elif tamper == "missing_original":
        next((recovery / "ORIGINAL_METHOD_MANIFESTS").rglob("METHOD_BOUND_INPUT_MANIFEST.json")).unlink()
    elif tamper == "missing_config":
        next((recovery / "SUPERSEDED_PREPARATION_ARTIFACTS/07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/RUNTIME_CONFIGS").rglob("*.yaml")).unlink()
    elif tamper == "missing_moved":
        (recovery / "SUPERSEDED_PREPARATION_ARTIFACTS/07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json").unlink()
    elif tamper == "stale_config":
        stale = stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/RUNTIME_CONFIGS/stale.yaml"
        stale.parent.mkdir(parents=True); stale.write_text("stale: true\n")
    elif tamper == "coherent_reset":
        reset_path = recovery / "RESET_LEDGER.json"
        reset = json.loads(reset_path.read_text()); reset["reset_rows"][0]["reset_sha256"] = "0" * 64
        reset_path.write_text(json.dumps(reset, indent=2, sort_keys=True) + "\n")
        complete_path = recovery / "RECOVERY_COMPLETE.json"
        complete = json.loads(complete_path.read_text()); complete["reset_ledger_sha256"] = preparation.sha256_file(reset_path)
        complete_path.write_text(json.dumps(complete, indent=2, sort_keys=True) + "\n")
        (recovery / "RECOVERY_COMPLETE.json.sha256").write_text(
            preparation.sha256_file(complete_path) + "  RECOVERY_COMPLETE.json\n"
        )
    elif tamper == "output":
        output = stage / "08_FULL_ALGORITHM_RUNS/RUN_00001/KF_GINS_STD.txt"
        output.parent.mkdir(parents=True); output.write_text("x\n")
    else:
        (stage / "REFERENCE_TRACE_READ_LEDGER.json").write_text("{}\n")
    with pytest.raises(preparation.PreparationError):
        preparation.recover_known_3981_preparation(stage, explicitly_authorized=True)
