"""Destructive-policy tests use isolated synthetic files only."""
import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest

from legsa_gins.paper_rebuild.protocol_v3 import purge


def put(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return path


def doc(path, value):
    return put(path, (json.dumps(value) + "\n").encode())


def hashed(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def world(tmp_path):
    stages = tmp_path / "project" / "clean_rebuild_202607" / "stages"
    stage = stages / "CLEAN7_T5BC_V3_CANDIDATE_PILOT"
    run = stage / "05_NATIVE_SUBSET61" / "D01_seed_00" / "R5"
    nav = put(run / "KF_GINS_Navresult.nav", b"N" * purge.MIN_BYTES)
    std = put(run / "KF_GINS_STD.txt", b"S" * purge.MIN_BYTES)
    doc(run / "OUTPUT_SEAL.json", {"status": "SEALED", "files": {nav.name: hashed(nav), std.name: hashed(std)}})
    completion = doc(stage / "FINAL_SUMMARY_V2.json", {"status": "PASS_T5BCR_COMPLETE"})
    validation = doc(tmp_path / "project" / "handoff" / "validation.json", {"passed": True})
    verifier = put(tmp_path / "verifier.py", (
        "import hashlib,json,sys\nfrom pathlib import Path\n"
        "index=Path(sys.argv[1]).parent/'PROTECTION_INDEX.json'\n"
        "count=len(json.loads(index.read_text())['verification_pins'])\n"
        "Path(sys.argv[1]).write_text(json.dumps({'status':'PASS','verification_complete':True,'failed':0,"
        "'total':count,'verified':count,'index_sha256':hashlib.sha256(index.read_bytes()).hexdigest()}))\n"
    ).encode())
    policy = {"stages_root": str(stages), "quarantine_root": str(tmp_path / "project" / "_QUARANTINE_20260919"),
              "output_root": str(stages / "CLEAN8_PROTOCOL_V3" / "V3R_PURGE"),
              "verifier_command": [sys.executable, str(verifier), "{receipt}"], "stages": [{
                  "path": str(stage), "completion_record": str(completion), "completion_sha256": hashed(completion),
                  "completion_checks": {"status": "PASS_T5BCR_COMPLETE"},
                  "handoff_validation_record": str(validation), "handoff_validation_sha256": hashed(validation),
                  "handoff_checks": {"passed": True}, "bulk_dirs": ["05_NATIVE_SUBSET61"]}]}
    protection = {"references_complete": True, "protected_paths": [],
                  "protected_root_objects": [str(stages.parent)], "reference_sources": [],
                  "verification_pins": [{"path": str(completion), "sha256": hashed(completion)}]}
    return dict(stages=stages, stage=stage, run=run, nav=nav, std=std,
                policy=policy, protection=protection, tmp=tmp_path, verifier=verifier)


def make_plan(w):
    path = doc(w["tmp"] / "policy.json", w["policy"])
    index = doc(w["tmp"] / "protection.json", w["protection"])
    return purge.plan(path, index)


def runner(w):
    return purge.Purge(w["policy"]["output_root"])


def test_plan_never_hashes_payload_and_counts(world, monkeypatch):
    original = purge.digest
    def forbid(path):
        assert Path(path) not in (world["nav"], world["std"])
        return original(path)
    monkeypatch.setattr(purge, "digest", forbid)
    result = make_plan(world)
    assert result["counts"]["CANDIDATE"] == 2
    assert result["counts"]["CANDIDATE_bytes"] == 2 * purge.MIN_BYTES
    assert result["candidate_payload_hash_reads"] == 0


@pytest.mark.parametrize("name", ["state.json", "README.md", "contract.yaml", "plot.pdf", "plot.svg",
                                  "plot.png", "RESULT_SUMMARY.csv", "HASHES.txt", "RENDER_MANIFEST.csv"])
def test_permanent_types_never_candidates(world, name):
    candidate = put(world["run"] / name, b"X" * purge.MIN_BYTES)
    seal = world["run"] / "OUTPUT_SEAL.json"
    payload = json.loads(seal.read_text()); payload["files"][name] = hashed(candidate); doc(seal, payload)
    result = make_plan(world)
    assert result["counts"]["CANDIDATE"] == 2
    assert result["skipped_reasons"]["PERMANENT_RECORD_OR_FIGURE"] >= 1


@pytest.mark.parametrize("directory", ["00_RAW", "01_INPUTS", "02_CONFIG", "03_PROVIDER_TABLES", "RETAINED_RUNS"])
def test_input_subtrees_never_candidates(world, directory):
    candidate = put(world["run"] / directory / "hidden.nav", b"X" * purge.MIN_BYTES)
    doc(candidate.parent / "OUTPUT_SEAL.json", {"files": {candidate.name: hashed(candidate)}})
    result = make_plan(world)
    assert result["counts"]["CANDIDATE"] == 2


def test_concrete_reference_protected_but_root_alias_not_subtree(world):
    world["protection"]["protected_paths"] = [str(world["nav"])]
    assert make_plan(world)["counts"]["CANDIDATE"] == 1


def test_small_and_unproven_skipped(world):
    put(world["run"] / "unknown.nav", b"U" * purge.MIN_BYTES)
    put(world["run"] / "small.nav", b"S")
    result = make_plan(world)
    assert result["skipped_reasons"]["NO_EXISTING_EXACT_PATH_OR_HASH_EVIDENCE"] == 1
    assert result["skipped_reasons"]["SMALLER_THAN_1_MB"] >= 1


def test_invalid_output_seal_gives_no_deletion_evidence(world):
    (world["run"] / "OUTPUT_SEAL.json").write_text('{"files":')
    result = make_plan(world)
    assert result["counts"].get("CANDIDATE", 0) == 0
    assert result["skipped_reasons"]["NO_EXISTING_EXACT_PATH_OR_HASH_EVIDENCE"] == 2


def test_symlink_inventory_does_not_follow(world):
    target = world["tmp"] / "outside"; target.mkdir()
    put(target / "big.nav", b"X" * purge.MIN_BYTES)
    (world["run"] / "linked").symlink_to(target, target_is_directory=True)
    result = make_plan(world)
    assert result["skipped_reasons"]["SYMLINK_SPECIAL_OR_MULTILINK"] == 1
    assert result["counts"]["CANDIDATE"] == 2


def test_missing_protection_assertion_rejected(world):
    world["protection"]["references_complete"] = False
    with pytest.raises(RuntimeError, match="complete DATA_PATHS"): make_plan(world)


def test_pin_and_completion_failure_prevent_plan(world):
    world["policy"]["stages"][0]["completion_checks"] = {"status": "PASS_FAKE"}
    with pytest.raises(RuntimeError, match="record check mismatch"): make_plan(world)


def test_unregistered_stage_and_directory_skipped(world):
    put(world["stages"] / "CLEAN5_OLD" / "RUNS" / "x.nav", b"X" * purge.MIN_BYTES)
    put(world["stage"] / "other" / "x.nav", b"X" * purge.MIN_BYTES)
    result = make_plan(world)
    assert result["counts"]["CANDIDATE"] == 2
    assert result["skipped_reasons"]["STAGE_NOT_REGISTERED_COMPLETED_WITH_VERIFIED_HANDOFF"] == 2
    assert result["skipped_reasons"]["OUTSIDE_REGISTERED_PER_CASE_OUTPUT_DIRECTORY"] == 1


def test_inventory_prunes_unregistered_trees_but_reaches_nested_registered_stage(world, monkeypatch):
    old = world["stages"] / "CLEAN2_OLD"
    put(old / "PROVIDERS" / "huge.nav", b"X" * purge.MIN_BYTES)
    parent = world["stages"] / "CLEAN7_T5A_HEADING_SENSITIVITY"
    excluded = parent / "OLD_FAILED_RUNS"
    put(excluded / "huge.nav", b"X" * purge.MIN_BYTES)
    nested = parent / "T5A_R"
    run = nested / "03_NATIVE" / "BY2" / "R5"
    nav = put(run / "new.nav", b"N" * purge.MIN_BYTES)
    doc(run / "OUTPUT_SEAL.json", {"files": {nav.name: hashed(nav)}})
    entry = dict(world["policy"]["stages"][0], path=str(nested), bulk_dirs=["03_NATIVE"])
    world["policy"]["stages"].append(entry)
    original = purge.os.scandir
    def guarded(path):
        assert Path(path) not in (old, excluded), "excluded directory must not be enumerated"
        return original(path)
    monkeypatch.setattr(purge.os, "scandir", guarded)
    result = make_plan(world)
    assert result["counts"]["CANDIDATE"] == 3
    assert result["excluded_directories"] == 3  # Includes the CLEAN8 audit stage.
    assert result["excluded_directory_bytes"] is None
    with (Path(world["policy"]["output_root"]) / "SKIPPED.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    excluded_rows = [row for row in rows if row["row_type"] == "EXCLUDED_DIRECTORY_UNENUMERATED"]
    assert len(excluded_rows) == 3
    assert all(row["size_bytes"] == "UNAVAILABLE_NOT_ENUMERATED" for row in excluded_rows)
    assert not any(row["path"].endswith("huge.nav") for row in rows)
    assert result["skipped_files"] == sum(row["row_type"] == "REGULAR_FILE" for row in rows)


def test_inventory_prunes_p2_and_nonbulk_trees_but_enumerates_all_ordinary_bulk(world, monkeypatch):
    protected = [world["run"] / name for name in
                 ("RETAINED_RUNS", "03_PROVIDER_TABLES", "00_RAW", "01_CONFIG", "02_INPUTS", "INPUTS", "HANDOFF")]
    outside = world["stage"] / "13_AGGREGATE"
    for directory in (*protected, outside):
        put(directory / "hidden.nav", b"X" * purge.MIN_BYTES)
    ordinary = world["run"] / "ordinary" / "run"
    nav = put(ordinary / "nested.nav", b"N" * purge.MIN_BYTES)
    doc(ordinary / "OUTPUT_SEAL.json", {"files": {nav.name: hashed(nav)}})
    original = purge.os.scandir
    visited = []
    def guarded(path):
        path = Path(path)
        assert path not in (*protected, outside), "P2/nonbulk directory must not be enumerated"
        visited.append(path)
        return original(path)
    monkeypatch.setattr(purge.os, "scandir", guarded)
    result = make_plan(world)
    assert result["counts"]["CANDIDATE"] == 3
    assert ordinary in visited
    with (Path(world["policy"]["output_root"]) / "SKIPPED.csv").open() as stream:
        skipped = {row["path"]: row for row in csv.DictReader(stream)}
    for directory in protected:
        assert skipped[str(directory)]["basis"] == "INPUT_PROVIDER_RETAINED_OR_HANDOFF_DIRECTORY"
        assert skipped[str(directory)]["row_type"] == "EXCLUDED_DIRECTORY_UNENUMERATED"
    assert skipped[str(outside)]["basis"] == "OUTSIDE_REGISTERED_PER_CASE_OUTPUT_DIRECTORY"


def test_success_exact_quarantine_and_purge(world):
    make_plan(world)
    run = runner(world)
    assert run.quarantine_files()["status"] == "QUARANTINE_COMPLETE"
    assert not world["nav"].exists()
    assert run.destination(run.rows[0]).exists()
    assert run.verify_purge()["deleted_bytes"] == 2 * purge.MIN_BYTES
    assert not run.quarantine.exists()
    assert (world["run"] / "OUTPUT_SEAL.json").exists()
    assert run.verify_purge()["status"] == "PASS_LEDGERED_PURGE_COMPLETE"


def test_failed_verifier_rolls_back_every_file(world):
    world["policy"]["verifier_command"] = [sys.executable, "-c", "import sys;sys.exit(7)", "{receipt}"]
    make_plan(world); run = runner(world); run.quarantine_files()
    with pytest.raises(RuntimeError, match="registered verifier failed"): run.verify_purge()
    assert world["nav"].read_bytes() == b"N" * purge.MIN_BYTES
    assert world["std"].read_bytes() == b"S" * purge.MIN_BYTES
    assert run.events()[-1]["action"] == "ROLLED_BACK"


def test_exit_zero_without_full_pass_rolls_back(world):
    world["policy"]["verifier_command"] = [sys.executable, "-c",
        "import sys;open(sys.argv[1],'w').write('{\"status\":\"PASS\"}')", "{receipt}"]
    make_plan(world); run = runner(world); run.quarantine_files()
    with pytest.raises(RuntimeError, match="complete PASS"): run.verify_purge()
    assert world["nav"].exists()


def test_reference_change_after_quarantine_rolls_back(world):
    source = doc(world["tmp"] / "contract.json", {"identity": 1})
    world["protection"]["reference_sources"] = [{"path": str(source), "sha256": hashed(source)}]
    make_plan(world); run = runner(world); run.quarantine_files()
    doc(source, {"identity": 2})
    resumed = runner(world)
    with pytest.raises(RuntimeError, match="record pin mismatch"): resumed.verify_purge()
    assert world["nav"].exists()


def test_source_metadata_change_prevents_move(world):
    make_plan(world); run = runner(world)
    world["nav"].write_bytes(b"Z" * purge.MIN_BYTES)
    with pytest.raises(RuntimeError, match="source metadata changed"): run.quarantine_files()
    assert world["nav"].exists() and world["std"].exists()


def test_interrupted_rename_resumes_without_candidate_hash(world):
    make_plan(world); run = runner(world); row = run.rows[0]
    source, target = Path(row["path"]), run.destination(row)
    run.event("MOVE_INTENT", path=str(source))
    purge._plain_rename(source, target, source.stat())
    resumed = runner(world)
    resumed.quarantine_files()
    assert not world["nav"].exists() and not world["std"].exists()
    resumed.rollback()
    assert world["nav"].exists() and world["std"].exists()


def test_verified_resume_does_not_repeat_verifier(world):
    make_plan(world); run = runner(world); run.quarantine_files(); run._verify()
    world["verifier"].write_text("raise AssertionError('verifier must not rerun')\n")
    assert runner(world).verify_purge()["status"] == "PASS_LEDGERED_PURGE_COMPLETE"


def test_interrupted_verifier_preserves_old_receipt_and_rechecks(world):
    make_plan(world); run = runner(world); run.quarantine_files()
    receipt = run.output / "P4_VERIFIER_RECEIPT_0001.json"
    run.event("VERIFY_INTENT", receipt=str(receipt))
    doc(receipt, {"status": "PASS", "verification_complete": True, "failed": 0})
    prior_hash = hashed(receipt)
    assert runner(world).verify_purge()["status"] == "PASS_LEDGERED_PURGE_COMPLETE"
    assert hashed(receipt) == prior_hash
    assert (run.output / "P4_VERIFIER_RECEIPT_0002.json").exists()


def test_partial_verified_record_is_preserved_and_verifier_rechecks(world):
    make_plan(world); run = runner(world); run.quarantine_files()
    partial = put(run.output / "P4_VERIFIED.json", b'{"status":')
    before = hashed(partial)
    assert run.verify_purge()["status"] == "PASS_LEDGERED_PURGE_COMPLETE"
    assert hashed(partial) == before
    assert (run.output / "P4_VERIFIED_0002.json").exists()


def test_empty_verification_pins_rejected(world):
    world["protection"]["verification_pins"] = []
    with pytest.raises(RuntimeError, match="nonempty P4 verification pins"): make_plan(world)


def test_wrong_index_verifier_pass_is_rejected_and_rolls_back(world):
    world["verifier"].write_text(world["verifier"].read_text().replace(
        "hashlib.sha256(index.read_bytes()).hexdigest()", "'0'*64"))
    make_plan(world); run = runner(world); run.quarantine_files()
    with pytest.raises(RuntimeError, match="frozen index binding"): run.verify_purge()
    assert world["nav"].exists()


def test_committed_verifier_receipt_tamper_before_delete_rolls_back(world):
    make_plan(world); run = runner(world); run.quarantine_files(); value = run._verify()
    Path(value["receipt_path"]).write_text("{}")
    with pytest.raises(RuntimeError, match="record pin mismatch"): run.verify_purge()
    assert world["nav"].exists() and world["std"].exists()


def test_interrupted_delete_resumes_only_with_intent(world):
    make_plan(world); run = runner(world); run.quarantine_files(); run._verify()
    row = run.rows[0]
    run.event("DELETE_INTENT", path=row["path"])
    run.destination(row).unlink()
    assert runner(world).verify_purge()["files"] == 2


def test_missing_quarantined_file_without_delete_intent_hard_stops(world):
    make_plan(world); run = runner(world); run.quarantine_files(); run._verify()
    run.destination(run.rows[0]).unlink()
    with pytest.raises(RuntimeError, match="missing without delete intent"): run.verify_purge()


def test_rollback_never_overwrites_resurrected_source(world):
    make_plan(world); run = runner(world); run.quarantine_files()
    put(world["nav"], b"new user data")
    with pytest.raises(RuntimeError, match="rollback collision"): run.rollback()
    assert world["nav"].read_bytes() == b"new user data"


def test_quarantine_collision_preserves_unknown_file(world):
    make_plan(world); run = runner(world)
    target = run.destination(run.rows[0]); put(target, b"unknown")
    with pytest.raises(RuntimeError): run.quarantine_files()
    assert target.read_bytes() == b"unknown"
    assert world["nav"].exists() and world["std"].exists()


def test_ledger_tampering_rejected_before_mutation(world):
    make_plan(world)
    path = Path(world["policy"]["output_root"]) / "PURGE_LEDGER.csv"
    path.write_text(path.read_text().replace("KF_GINS_Navresult.nav", "someone_else.nav"))
    with pytest.raises(RuntimeError, match="record pin mismatch"): runner(world)


def test_symlink_parent_inserted_after_plan_is_rejected(world):
    make_plan(world)
    world["run"].rename(world["run"].with_name("moved"))
    world["run"].symlink_to(world["run"].with_name("moved"), target_is_directory=True)
    with pytest.raises(RuntimeError, match="symlink forbidden"): runner(world)
