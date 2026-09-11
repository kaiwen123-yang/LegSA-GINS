"""Filesystem behavior tests use only disposable synthetic tmp_path trees."""
from __future__ import annotations

import csv
import base64
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild import storage_purge as mod


P07 = "stages/CLEAN5_DEGSUBSET_BY2/03_RUNS/CLEAN5_DEGSUBSET_CAL/RUN_00001"
CAN = ("stages/CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX/"
       ".attempt_20260808T200855P0800/08_FULL_ALGORITHM_RUNS/RUN_00001")
PARITY = "stages/CLEAN5_BY2_C00_INPUT_PARITY_A04_5HZ_HPPOSECEF/03_PARITY_RUNS/CLEAN5_TEST"


def put(root, relative, data=b"synthetic fixture only\n"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


@pytest.fixture
def world(tmp_path):
    clean, code = tmp_path / "clean", tmp_path / "code"
    (clean / "stages").mkdir(parents=True)
    code.mkdir()
    source_policy = Path(__file__).resolve().parents[2] / "configs/paper_rebuild/clean6/STORAGE_PURGE_POLICY.yaml"
    policy = tmp_path / "policy.yaml"
    policy.write_bytes(source_policy.read_bytes())
    closure = tmp_path / "closure.json"
    closure.write_text(json.dumps(dict(schema_version="clean6.storage_reference_closure.v1",
        keep_files=[], keep_dirs=[], required_paths=[], protected_dir_entries=[],
        superseded_attempt_dirs=[], clean4_nonfinal_attempt_dirs=[], seal_sources=[])))
    audit = clean / "storage_purge/20260911T010203Z"
    class World:
        def utility(self):
            return mod.StoragePurge(clean, code, policy, closure, audit)
        def amend(self, **fields):
            value = json.loads(closure.read_text())
            value.update(fields)
            closure.write_text(json.dumps(value))
        def candidate(self, name="KF_GINS_Navresult.nav", data=b"synthetic fixture only\n"):
            return put(clean, P07 + "/" + name, data)
        def prepare(self):
            utility = self.utility()
            ledger = utility.plan(hash_workers=1)
            utility.gate()
            return utility, ledger
        def c5(self, utility):
            _, binding = utility._ledger()
            path = tmp_path / "c5.json"
            path.write_text(json.dumps(dict(binding, gates={"C5": "PASS"},
                checks={name: "PASS" for name in mod.C5_CHECKS})))
            return path
    result = World()
    result.clean, result.code, result.policy, result.closure, result.audit = clean, code, policy, closure, audit
    return result


def test_plan_does_not_move_and_inventory_totals_reconcile(world):
    candidate = world.candidate()
    record = world.candidate("RUN_MANIFEST.json", b"{}")
    unknown = world.candidate("unclassified.bin", b"unknown")
    utility = world.utility()
    ledger = utility.plan(hash_workers=1)
    assert candidate.exists() and record.exists() and unknown.exists()
    assert not utility.quarantine.exists()
    assert ledger["candidate_count"] == 1
    assert ledger["entries"][0]["sha256"] == hashlib.sha256(candidate.read_bytes()).hexdigest()
    with (world.audit / "STORAGE_INVENTORY.csv").open() as stream:
        groups = list(csv.DictReader(stream))
    assert sum(int(row["regular_files"]) for row in groups) == 3
    assert sum(int(row["BULK_DELETABLE_files"]) for row in groups) == 1
    assert sum(int(row["KEEP_files"]) for row in groups) == 1
    assert sum(int(row["UNKNOWN_files"]) for row in groups) == 1
    assert ledger["candidate_bytes"] == candidate.stat().st_size
    assert str(world.clean) not in (world.audit / "DELETION_LEDGER.json").read_text()


@pytest.mark.parametrize("relative,data", [
    (P07 + "/PORT_GNSS_UPDATE_TRACE.csv", b"small csv"),
    (P07 + "/LegSA_PORT_STD.csv", b"x" * 1048576),
    (P07 + "/RUN_MANIFEST.json", b"x" * 1048577),
    (P07 + "/PROVIDER_DATA/KF_GINS_Navresult.nav", b"provider"),
    ("stages/CLEAN5_CALIBRATED_SENSOR_MODEL/03_RUNS/RUN_1/KF_GINS_Navresult.nav", b"cal"),
    (P07 + "/tmp/small.csv", b"small"),
    (P07 + "/tmp/input_measurements.bin", b"provider ambiguous"),
    (P07 + "/01_RAW_HASH_LOCK/large.csv", b"x" * 1048577),
])
def test_keep_precedence_over_bulk_family(world, relative, data):
    path = put(world.clean, relative, data)
    assert world.utility().classify(relative, path.stat())[0] == "KEEP"


@pytest.mark.parametrize("relative,expected", [
    (P07 + "/LegSA_PORT_STD.csv", "BULK_DELETABLE"),
    (P07 + "/EVAL_NAV.csv", "UNKNOWN"),
    (P07 + "/EXACT_EVALUATOR_INPUT.nav", "BULK_DELETABLE"),
    (P07 + "/EVAL_NAV_V3.nav", "BULK_DELETABLE"),
    (P07 + "/stdout.log", "BULK_DELETABLE"),
    (PARITY + "/stdout.log", "BULK_DELETABLE"),
    (PARITY + "/evaluator_stdout.log", "UNKNOWN"),
    ("stages/unapproved/03_RUNS/RUN_1/KF_GINS_Navresult.nav", "UNKNOWN"),
    (P07 + "/tmp/working.bin", "BULK_DELETABLE"),
    (CAN + "/KF_GINS_STD.txt", "BULK_DELETABLE"),
    ("stages/CLEAN5_DEGSUBSET_BY2/07_EVALUATION/v3/CLEAN5_DEGSUBSET_V2S/RUN_1/evaluator_stdout.log", "BULK_DELETABLE"),
])
def test_family_and_filename_both_required(world, relative, expected):
    path = put(world.clean, relative, b"x" * 1048577)
    assert world.utility().classify(relative, path.stat())[0] == expected


def test_closure_file_subtree_and_directory_only_have_distinct_retention(world):
    a = world.candidate()
    b = put(world.clean, P07 + "/protected/KF_GINS_STD.txt")
    c = put(world.clean, P07 + "/directory_reference/KF_GINS_STD.txt")
    world.amend(keep_files=[a.relative_to(world.clean).as_posix()],
                keep_dirs=[P07 + "/protected"], protected_dir_entries=[P07 + "/directory_reference"])
    ledger = world.utility().plan(hash_workers=1)
    assert [r["original_relative_path"] for r in ledger["entries"]] == [c.relative_to(world.clean).as_posix()]
    assert b.exists()


def test_symlinks_hardlinks_and_unknown_files_are_never_read_or_followed(world, monkeypatch):
    outside = put(world.code, "outside", b"must not read")
    symlink = world.clean / (P07 + "/KF_GINS_Navresult.nav")
    symlink.parent.mkdir(parents=True)
    symlink.symlink_to(outside)
    linked = world.clean / (P07 + "/KF_GINS_STD.txt")
    os.link(outside, linked)
    (world.clean / "stages/linkdir").symlink_to(world.code, target_is_directory=True)
    monkeypatch.setattr(mod, "hash_file", lambda *a, **k: pytest.fail("no eligible payload should be hashed"))
    assert world.utility().plan(hash_workers=1)["candidate_count"] == 0
    assert outside.read_bytes() == b"must not read"


def test_frozen_nonfinal_closure_allows_exact_nonstandard_attempt(world):
    prefix = "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON/GINav.frozen_attempt2_2020"
    relative = prefix + "/KF_GINS_Navresult.nav"
    path = put(world.clean, relative)
    world.amend(clean4_nonfinal_attempt_dirs=[prefix])
    assert world.utility().classify(relative, path.stat())[0] == "BULK_DELETABLE"
    world.amend(clean4_nonfinal_attempt_dirs=[])
    assert world.utility().classify(relative, path.stat())[0] == "UNKNOWN"


def test_json_seal_exact_base_mapping_avoids_candidate_rehash_in_plan(world, monkeypatch):
    candidate = world.candidate()
    sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
    stage = "stages/CLEAN5_DEGSUBSET_BY2"
    seal = put(world.clean, stage + "/04_SEAL/OUTPUT_SEAL.json", json.dumps({"files_sha256": {
        candidate.relative_to(world.clean / stage).as_posix(): sha}}).encode())
    world.amend(seal_sources=[{"path": "<CLEAN_ROOT>/" + seal.relative_to(world.clean).as_posix(),
                              "base": "<CLEAN_ROOT>/" + stage}])
    monkeypatch.setattr(mod, "hash_file", lambda *a, **k: pytest.fail("exact seal map must avoid fresh plan hash"))
    row = world.utility().plan(hash_workers=1)["entries"][0]
    assert row["sha256"] == sha and row["hash_evidence"] == "EXACT_PATH_SEAL_SHA256"
    assert any(p["json_pointer"].startswith("/files_sha256/") for p in row["seal_provenance"])


def test_canonical_csv_seal_joins_run_root_and_relative_path(world, monkeypatch):
    path = put(world.clean, CAN + "/KF_GINS_Navresult.nav")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    seal = put(world.clean, "stages/seals/OUTPUT_HASH_MANIFEST.csv", (
        "run_id,run_root,relative_path,size_bytes,sha256\nRUN_1," + str(path.parent) + "," + path.name
        + "," + str(path.stat().st_size) + "," + sha + "\n").encode())
    world.amend(seal_sources=[{"path": "<CLEAN_ROOT>/" + seal.relative_to(world.clean).as_posix()}])
    monkeypatch.setattr(mod, "hash_file", lambda *a, **k: pytest.fail("CSV seal exact path should avoid fresh plan hash"))
    row = world.utility().plan(hash_workers=1)["entries"][0]
    assert row["hash_evidence"] == "EXACT_PATH_SEAL_SHA256"
    assert row["seal_provenance"][0]["json_pointer"] == "csv_row:2/sha256"


def test_hash_occurrence_without_path_still_requires_fresh_candidate_hash(world, monkeypatch):
    candidate = world.candidate()
    sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
    put(world.clean, "stages/records/OUTPUT_SEAL.json", json.dumps({"unmapped_digest": sha}).encode())
    real_hash, calls = mod.hash_file, []
    def observe(path, **kw):
        calls.append(path)
        return real_hash(path, **kw)
    monkeypatch.setattr(mod, "hash_file", observe)
    row = world.utility().plan(hash_workers=1)["entries"][0]
    assert calls == [candidate]
    assert row["hash_evidence"] == "FRESH_STREAMING_SHA256" and row["seal_provenance"]


def test_conflicting_seal_hashes_fail_before_any_plan_output(world):
    candidate = world.candidate()
    for i, sha in enumerate(["a" * 64, "b" * 64]):
        put(world.clean, f"stages/records/SEAL_{i}.json", json.dumps({str(candidate): sha}).encode())
    with pytest.raises(mod.PurgeError, match="conflicting"):
        world.utility().plan(hash_workers=1)
    assert candidate.exists() and not world.audit.exists()


def test_required_file_candidate_fails_c2_and_nothing_moves(world):
    candidate = world.candidate()
    world.amend(required_paths=[{"path": "<CLEAN_ROOT>/" + candidate.relative_to(world.clean).as_posix(), "kind": "file"}])
    utility = world.utility()
    utility.plan(hash_workers=1)
    with pytest.raises(mod.PurgeError, match="reference selected"):
        utility.gate()
    assert candidate.exists() and not utility.quarantine.exists()


def test_missing_required_record_fails_c2(world):
    world.candidate()
    world.amend(required_paths=[{"path": "<CODE_ROOT>/missing.md", "kind": "file"}])
    utility = world.utility()
    utility.plan(hash_workers=1)
    with pytest.raises(FileNotFoundError):
        utility.gate()


def test_all_gates_exact_move_unlink_and_original_directories_survive(world):
    a = world.candidate()
    b = world.candidate("KF_GINS_STD.txt", b"second")
    kept = world.candidate("RUN_MANIFEST.json", b"{}")
    utility, ledger = world.prepare()
    parents = [a.parent, b.parent]
    result = utility.quarantine_files()
    assert result["gates"] == {"C4": "PASS"} and not a.exists() and not b.exists()
    assert all((world.clean / r["quarantine_relative_path"]).exists() for r in ledger["entries"])
    result = utility.purge(world.c5(utility))
    assert result["purged_files"] == 2 and not utility.quarantine.exists()
    assert kept.exists() and all(p.is_dir() for p in parents)
    journal = [json.loads(line) for line in (world.audit / "JOURNAL.jsonl").read_text().splitlines()]
    assert [r["action"] for r in journal].count("MOVED_HASH_VERIFIED") == 2
    assert [r["action"] for r in journal].count("PURGED") == 2
    assert utility.purge(world.c5(utility)) == result  # Safe completed-phase verification.


@pytest.mark.parametrize("gate", ["C1", "C2", "C3"])
def test_no_move_without_all_pre_move_gates(world, gate):
    candidate = world.candidate()
    utility, _ = world.prepare()
    path = world.audit / "GATE_PRE_MOVE.json"
    value = json.loads(path.read_text())
    value["gates"][gate] = "FAIL"
    path.write_text(json.dumps(value))
    with pytest.raises(mod.PurgeError, match="not PASS"):
        utility.quarantine_files()
    assert candidate.exists()


@pytest.mark.parametrize("mutation", ["change_bytes", "hardlink", "symlink", "collision"])
def test_move_checkpoint_rejects_source_change_and_collision(world, mutation):
    candidate = world.candidate()
    utility, ledger = world.prepare()
    destination = world.clean / ledger["entries"][0]["quarantine_relative_path"]
    if mutation == "change_bytes":
        candidate.write_bytes(b"changed")
    elif mutation == "hardlink":
        os.link(candidate, world.code / "extra_link")
    elif mutation == "symlink":
        candidate.unlink()
        candidate.symlink_to(put(world.code, "outside"))
    else:
        put(world.clean, destination.relative_to(world.clean).as_posix(), b"collision")
    with pytest.raises((mod.PurgeError, OSError)):
        utility.quarantine_files()
    assert candidate.exists()


def test_symlink_parent_rejected_before_any_move(world):
    candidate = world.candidate()
    utility, _ = world.prepare()
    original_parent = candidate.parent
    moved_parent = original_parent.with_name("relocated")
    original_parent.rename(moved_parent)
    original_parent.symlink_to(moved_parent, target_is_directory=True)
    with pytest.raises(OSError):
        utility.quarantine_files()
    assert (moved_parent / candidate.name).exists()


@pytest.mark.parametrize("extra", ["regular", "directory", "symlink"])
def test_unexpected_quarantine_entry_stops_purge(world, extra):
    world.candidate()
    utility, ledger = world.prepare()
    utility.quarantine_files()
    extra_path = utility.quarantine / "unexpected"
    if extra == "regular":
        extra_path.write_text("unplanned")
    elif extra == "directory":
        extra_path.mkdir()
    else:
        extra_path.symlink_to(world.code)
    with pytest.raises(mod.PurgeError, match="quarantine"):
        utility.purge(world.c5(utility))
    assert all((world.clean / r["quarantine_relative_path"]).exists() for r in ledger["entries"])


@pytest.mark.parametrize("change", ["missing_check", "failed_check", "wrong_binding", "missing_gate"])
def test_c5_independent_receipt_is_mandatory_and_bound(world, change):
    world.candidate()
    utility, ledger = world.prepare()
    utility.quarantine_files()
    c5 = world.c5(utility)
    receipt = json.loads(c5.read_text())
    if change == "missing_check":
        receipt["checks"].pop("repository_record_tests")
    elif change == "failed_check":
        receipt["checks"]["aggregate_readability"] = "FAIL"
    elif change == "wrong_binding":
        receipt["ledger_sha256"] = "0" * 64
    else:
        receipt["gates"] = {}
    c5.write_text(json.dumps(receipt))
    with pytest.raises(mod.PurgeError, match="C5"):
        utility.purge(c5)
    assert all((world.clean / r["quarantine_relative_path"]).exists() for r in ledger["entries"])


def test_mid_move_crash_recovers_only_from_durable_prepare(world, monkeypatch):
    world.candidate()
    utility, ledger = world.prepare()
    append = utility._append
    def crash(events, binding, action, row, **extra):
        if action == "MOVED_HASH_VERIFIED":
            raise RuntimeError("simulated process death after rename")
        return append(events, binding, action, row, **extra)
    monkeypatch.setattr(utility, "_append", crash)
    with pytest.raises(RuntimeError):
        utility.quarantine_files()
    destination = world.clean / ledger["entries"][0]["quarantine_relative_path"]
    assert destination.exists()
    utility = world.utility()
    assert utility.quarantine_files()["verified_files"] == 1
    events = utility._journal(utility._ledger()[1])
    assert events[-1]["recovered_after_prepare"] is True


def test_mid_unlink_crash_preserves_journal_and_resumes_exact_set(world, monkeypatch):
    world.candidate()
    utility, _ = world.prepare()
    utility.quarantine_files()
    append = utility._append
    def crash(events, binding, action, row, **extra):
        if action == "PURGED":
            raise RuntimeError("simulated process death after unlink")
        return append(events, binding, action, row, **extra)
    monkeypatch.setattr(utility, "_append", crash)
    c5 = world.c5(utility)
    with pytest.raises(RuntimeError):
        utility.purge(c5)
    utility = world.utility()
    assert utility.purge(c5)["purged_files"] == 1


def test_torn_journal_never_automatically_repaired(world):
    world.candidate()
    utility, _ = world.prepare()
    (world.audit / "JOURNAL.jsonl").write_bytes(b'{"incomplete":')
    with pytest.raises(mod.PurgeError, match="torn journal"):
        utility.quarantine_files()


def test_changed_quarantined_content_stops_before_unlink(world):
    world.candidate()
    utility, ledger = world.prepare()
    utility.quarantine_files()
    destination = world.clean / ledger["entries"][0]["quarantine_relative_path"]
    destination.write_bytes(b"tampered")
    with pytest.raises(mod.PurgeError, match="size changed|hash changed"):
        utility.purge(world.c5(utility))
    assert destination.exists()


def test_policy_and_plan_cannot_change_between_phases(world):
    world.candidate()
    utility, _ = world.prepare()
    world.policy.write_text(world.policy.read_text() + "\n# changed\n")
    with pytest.raises(mod.PurgeError, match="policy or closure changed"):
        world.utility().quarantine_files()


@pytest.mark.parametrize("relative", ["../escape", "/absolute", "stages/a/../b", "stages//x", "stages/./x", "stages\\x"])
def test_noncanonical_closure_paths_rejected(world, relative):
    world.amend(keep_files=[relative])
    with pytest.raises(mod.PurgeError, match="path"):
        world.utility()


def test_raw_payload_hash_guard(world):
    path = put(world.clean, "data/raw/trace_fixture.txt", b"must remain unread")
    with pytest.raises(mod.PurgeError, match="content access forbidden"):
        mod.hash_file(path)


def test_home_aliases_resolve_without_payload_reads(world, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: world.code))
    assert world.utility().alias("<HOME>/package.zip") == world.code / "package.zip"
    assert world.utility().alias("<USER_HOME>/package.zip") == world.code / "package.zip"


@pytest.mark.parametrize("filename", ["imu.txt", "gnss.txt", "go2_attitude.csv"])
def test_ambiguous_provider_payload_inside_tmp_is_retained(world, filename):
    relative = P07 + "/tmp/" + filename
    path = put(world.clean, relative, b"x" * 1048577)
    assert world.utility().classify(relative, path.stat())[0] == "KEEP"


@pytest.mark.parametrize("git_kind", ["file", "directory", "symlink"])
def test_embedded_git_worktree_is_conservatively_kept(world, git_kind, monkeypatch):
    candidate = world.candidate()
    git = candidate.parent / ".git"
    if git_kind == "file":
        git.write_text("gitdir: fixture")
    elif git_kind == "directory":
        git.mkdir()
    else:
        git.symlink_to(world.code)
    monkeypatch.setattr(mod, "hash_file", lambda *a, **k: pytest.fail("embedded worktree payload hashed"))
    assert world.utility().plan(hash_workers=1)["candidate_count"] == 0
    assert world.utility().classify(candidate.relative_to(world.clean).as_posix(), candidate.stat())[0] == "KEEP"


@pytest.mark.parametrize("field,alias", [("source_documents_sha256", "AGENTS.md"),
                                        ("frozen_source_sha256", "<CODE_ROOT>/AGENTS.md")])
def test_closure_source_hash_change_stops_quarantine(world, field, alias):
    source = put(world.code, "AGENTS.md", b"pinned document")
    world.amend(**{field: {alias: hashlib.sha256(source.read_bytes()).hexdigest()}})
    candidate = world.candidate()
    utility, _ = world.prepare()
    source.write_bytes(b"new reference added after planning")
    with pytest.raises(mod.PurgeError, match="source.*changed"):
        utility.quarantine_files()
    assert candidate.exists()


def test_cross_filesystem_syscall_failure_has_no_copy_fallback(world, monkeypatch):
    candidate = world.candidate()
    utility, ledger = world.prepare()
    class Rename:
        def __call__(self, *args):
            ctypes.set_errno(errno.EXDEV)
            return -1
    class Libc:
        renameat2 = Rename()
    monkeypatch.setattr(mod.ctypes, "CDLL", lambda *a, **k: Libc())
    with pytest.raises(OSError) as error:
        utility.quarantine_files()
    assert error.value.errno == errno.EXDEV and candidate.exists()
    assert not (world.clean / ledger["entries"][0]["quarantine_relative_path"]).exists()


def test_concurrent_physical_phase_is_rejected(world):
    world.candidate()
    first, _ = world.prepare()
    with first._operation_lock():
        with pytest.raises(mod.PurgeError, match="operation lock"):
            world.utility().quarantine_files()


def test_unresolved_reference_closure_fails_gate(world):
    world.candidate()
    world.amend(unresolved_required_paths=["<CODE_ROOT>/missing.md"])
    utility = world.utility()
    utility.plan(hash_workers=1)
    with pytest.raises(mod.PurgeError, match="unresolved"):
        utility.gate()


def test_seal_source_change_after_plan_stops_gate(world):
    path = world.candidate()
    seal = put(world.clean, "stages/records/OUTPUT_SEAL.json", json.dumps(
        {str(path): hashlib.sha256(path.read_bytes()).hexdigest()}).encode())
    utility = world.utility()
    utility.plan(hash_workers=1)
    seal.write_text("{}")
    with pytest.raises(mod.PurgeError, match="seal provenance metadata changed"):
        utility.gate()


def test_special_fifo_is_rejected_without_blocking_hash(world):
    path = world.clean / "fifo"
    os.mkfifo(path)
    with pytest.raises(mod.PurgeError, match="regular"):
        mod.hash_file(path)


def test_parallel_plan_matches_sequential_inventory_and_parent_git_retention(world, monkeypatch):
    world.candidate()
    for index in range(20):
        put(world.clean, P07 + f"/working_{index}/unclassified.bin", bytes([index]))
    git_root = P07 + "/nested_repository"
    put(world.clean, git_root + "/.git", b"gitdir: synthetic")
    protected = put(world.clean, git_root + "/child/deeper/KF_GINS_Navresult.nav", b"protected")
    (world.clean / (P07 + "/outside_link")).symlink_to(world.code, target_is_directory=True)
    sequential = world.utility()
    monkeypatch.setattr(sequential, "_walk_plan", lambda root, **kwargs: sequential._walk(root))
    first = sequential.plan(hash_workers=1)
    parallel = mod.StoragePurge(world.clean, world.code, world.policy, world.closure,
                               world.clean / "storage_purge/20260911T010204Z")
    owner_thread = threading.get_ident()
    class OwnerSet(set):
        def add(self, value):
            assert threading.get_ident() == owner_thread
            return super().add(value)
    parallel.embedded_git_roots = OwnerSet()
    second = parallel.plan(hash_workers=1, metadata_workers=8)
    for name in ["FILE_INVENTORY.csv", "STORAGE_INVENTORY.csv", "UNKNOWN_FILES.csv"]:
        assert (sequential.audit / name).read_bytes() == (parallel.audit / name).read_bytes()
    assert first["candidate_count"] == second["candidate_count"] == 1
    assert protected.exists()
    assert git_root in parallel.embedded_git_roots


def test_parallel_metadata_worker_count_is_bounded(world, monkeypatch):
    for index in range(16):
        put(world.clean, f"stages/d{index}/fixture.bin", b"fixture")
    utility = world.utility()
    original = utility._directory_metadata
    lock, release = threading.Lock(), threading.Event()
    active = peak = 0
    def measured(directory):
        nonlocal active, peak
        if directory == world.clean / "stages":
            return original(directory)
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 4:
                release.set()
        assert release.wait(2), "four directory workers should be concurrently active"
        try:
            return original(directory)
        finally:
            with lock:
                active -= 1
    monkeypatch.setattr(utility, "_directory_metadata", measured)
    rows = list(utility._walk_plan(world.clean / "stages", workers=4))
    assert len(rows) == 32 and peak == 4 and active == 0
    with pytest.raises(mod.PurgeError, match="1..16"):
        list(utility._walk_plan(world.clean / "stages", workers=17))


def test_inventory_groups_partition_explicit_and_nested_attempts(world):
    stage = "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
    frozen = stage + "/GINav.frozen_attempt2_2020"
    partial = stage + "/GINav.partial_2020"
    nested = stage + "/.attempt_evidence/FAILED_REGISTRY"
    world.amend(clean4_nonfinal_attempt_dirs=[frozen, partial, nested])
    utility = world.utility()
    assert utility._inventory_group(frozen + "/a.txt") == frozen
    assert utility._inventory_group(partial + "/b.txt") == partial
    assert utility._inventory_group(nested + "/deeper/c.txt") == nested
    assert utility._inventory_group(stage + "/remainder.txt") == stage
    assert utility._inventory_group(CAN + "/KF_GINS_STD.txt") == CAN.split("/08_FULL")[0]


def dense_fixture(world, *, extra=None):
    directory = world.clean / P07
    rows = []
    for index in range(1000):
        name = f"metadata_{index:04d}.json"
        put(directory, name, b"{}")
        rows.append(dict(name=name, size=2, attributes=32))
    if extra:
        name, content, attributes = extra
        put(directory, name, content)
        rows.append(dict(name=name, size=len(content), attributes=attributes))
    return directory, {"directory_attributes": 16, "rows": rows}


def test_native_dense_independent_keep_has_explicit_unqueried_identity(world, monkeypatch):
    directory, native = dense_fixture(world)
    utility = world.utility()
    calls = []
    def native_query(path):
        calls.append(path)
        assert path == directory
        return native
    monkeypatch.setattr(utility, "_native_directory_listing", native_query)
    monkeypatch.setattr(mod, "hash_file", lambda *a, **k: pytest.fail("independent KEEP payload must not be hashed"))
    ledger = utility.plan(hash_workers=1, native_dense_keep=True)
    assert calls == [directory] and ledger["candidate_count"] == 0
    assert ledger["native_independent_keep_count"] == 1000
    with (utility.audit / "FILE_INVENTORY.csv").open() as stream:
        rows = [r for r in csv.DictReader(stream) if r["file_type"] == "regular"]
    assert len(rows) == 1000
    assert all(r["classification"] == "KEEP" and r["identity_status"] == "UNQUERIED" for r in rows)
    assert all(r[k] == "" for r in rows for k in ["nlink", "device", "inode", "mtime_ns"])


def test_native_mixed_directory_falls_back_for_every_file(world, monkeypatch):
    directory, native = dense_fixture(world, extra=("KF_GINS_Navresult.nav", b"NAV fixture", 32))
    utility = world.utility()
    monkeypatch.setattr(utility, "_native_directory_listing", lambda path: native)
    results = utility._dense_directory_metadata(directory)
    assert len(results) == 1001 and all(not isinstance(s, mod.NativeKeepMetadata) for _, s in results)
    candidate = next((p, s) for p, s in results if p.suffix == ".nav")
    assert candidate[1].st_nlink == 1
    assert utility.classify(candidate[0].relative_to(world.clean).as_posix(), candidate[1])[0] == "BULK_DELETABLE"


@pytest.mark.parametrize("kind", ["missing_name", "duplicate_name", "wrong_type", "negative_size", "size_not_integer", "root_reparse"])
def test_native_metadata_mismatch_stops_without_candidates(world, monkeypatch, kind):
    directory, native = dense_fixture(world)
    if kind == "missing_name":
        native["rows"].pop()
    elif kind == "duplicate_name":
        native["rows"][-1]["name"] = native["rows"][0]["name"]
    elif kind == "wrong_type":
        native["rows"][0]["attributes"] = 16
    elif kind == "negative_size":
        native["rows"][0]["size"] = -1
    elif kind == "size_not_integer":
        native["rows"][0]["size"] = "2"
    else:
        native["directory_attributes"] = 16 | 1024
    utility = world.utility()
    monkeypatch.setattr(utility, "_native_directory_listing", lambda path: native)
    with pytest.raises(mod.PurgeError, match="native"):
        utility._dense_directory_metadata(directory)
    assert not utility.audit.exists() and not utility.quarantine.exists()


def test_identity_free_native_metadata_can_never_classify_bulk_or_unknown(world):
    utility = world.utility()
    for filename in ["KF_GINS_Navresult.nav", "unknown.dat", "error_series.csv"]:
        with pytest.raises(mod.PurgeError, match="cannot classify"):
            utility.classify(P07 + "/" + filename, mod.NativeKeepMetadata(1048577, 32))
    with pytest.raises(mod.PurgeError, match="invalid native"):
        utility.classify(P07 + "/record.json", mod.NativeKeepMetadata(2, 1024))


def test_native_reparse_entry_falls_back_and_never_follows(world, monkeypatch):
    directory, native = dense_fixture(world)
    link = directory / "link.json"
    link.symlink_to(world.code, target_is_directory=True)
    native["rows"].append(dict(name="link.json", size=0, attributes=16 | 1024))
    utility = world.utility()
    monkeypatch.setattr(utility, "_native_directory_listing", lambda path: native)
    results = utility._dense_directory_metadata(directory)
    link_stat = next(s for p, s in results if p == link)
    assert mod.stat.S_ISLNK(link_stat.st_mode)
    assert all(not isinstance(s, mod.NativeKeepMetadata) for _, s in results)
    assert utility.classify(link.relative_to(world.clean).as_posix(), link_stat)[0] == "KEEP"
    symlink_directory = directory.with_name("linked_directory")
    symlink_directory.symlink_to(directory, target_is_directory=True)
    with pytest.raises(OSError):
        utility._dense_directory_metadata(symlink_directory)


def test_native_listing_uses_exact_wslpath_encoded_literal_and_no_recursion(world, monkeypatch):
    directory = world.clean / "stages/literal's directory"
    directory.mkdir()
    captured = {}
    def wslpath(args, **kwargs):
        assert args == ["wslpath", "-w", str(directory)]
        return "G:\\literal's directory\n"
    def powershell(args, **kwargs):
        captured["script"] = base64.b64decode(args[-1]).decode("utf-16le")
        assert args[0] == "powershell.exe" and args[-2] == "-EncodedCommand"
        return SimpleNamespace(stdout=b'{"directory_attributes":16,"rows":[]}')
    monkeypatch.setattr(mod.subprocess, "check_output", wslpath)
    monkeypatch.setattr(mod.subprocess, "run", powershell)
    assert world.utility()._native_directory_listing(directory)["rows"] == []
    assert "'G:\\literal''s directory'" in captured["script"]
    assert ".EnumerateFileSystemInfos()" in captured["script"]
    assert "-Recurse" not in captured["script"] and "ReadAll" not in captured["script"]


def test_lexical_seal_resolution_matches_previous_valid_candidate_mapping(world):
    candidate = world.candidate()
    utility = world.utility()
    relative = candidate.relative_to(world.clean).as_posix()
    parent_relative = candidate.parent.relative_to(world.clean).as_posix()
    examples = [(str(candidate), None), ("<CLEAN_ROOT>/" + relative, None), (relative, None),
                (candidate.name, str(candidate.parent)),
                (candidate.name, "<CLEAN_ROOT>/" + parent_relative)]
    for value, base in examples:
        if value.startswith(("<CLEAN_ROOT>/", "stages/")) or Path(value).is_absolute():
            old = utility.alias(value)
        else:
            old = utility.alias(base) / mod._relative(value)
        assert utility._seal_record_relative(value, base=base) == old.relative_to(world.clean).as_posix() == relative


@pytest.mark.parametrize("value,base", [
    ("../escape.nav", "<CLEAN_ROOT>/stages/base"),
    ("child/../escape.nav", "<CLEAN_ROOT>/stages/base"),
    ("child//file.nav", "<CLEAN_ROOT>/stages/base"),
    ("child/./file.nav", "<CLEAN_ROOT>/stages/base"),
    ("child/file.nav/", "<CLEAN_ROOT>/stages/base"),
    ("<CLEAN_ROOT>//stages/run/file.nav", None),
    ("/outside/root/file.nav", "<CLEAN_ROOT>/stages/base"),
    ("<CODE_ROOT>/file.nav", "<CLEAN_ROOT>/stages/base"),
    ("C:/outside/file.nav", "<CLEAN_ROOT>/stages/base"),
    ("C:\\outside\\file.nav", "<CLEAN_ROOT>/stages/base"),
    ("file.nav", "C:/outside"),
    ("file.nav", "<CLEAN_ROOT>/stages/base/.."),
    ("file.nav", None),
])
def test_invalid_seal_record_strings_never_enter_exact_evidence(world, value, base):
    assert world.utility()._seal_record_relative(value, base=base) is None


def test_seal_record_resolution_never_opens_or_stats_recorded_paths(world, monkeypatch):
    utility = world.utility()
    relative = P07 + "/KF_GINS_Navresult.nav"
    recorded = str(world.clean / relative)
    def forbidden(*args, **kwargs):
        pytest.fail("record string parsing must not access the filesystem")
    with monkeypatch.context() as guard:
        for name in ["open", "stat", "lstat", "scandir"]:
            guard.setattr(mod.os, name, forbidden)
        guard.setattr(Path, "stat", forbidden)
        guard.setattr(Path, "lstat", forbidden)
        guard.setattr(mod, "_read", forbidden)
        guard.setattr(utility, "alias", forbidden)
        for _ in range(100):
            assert utility._seal_record_relative(recorded) == relative
            assert utility._seal_record_relative("KF_GINS_Navresult.nav", base="<CLEAN_ROOT>/" + P07) == relative
            assert utility._seal_record_relative(str(world.clean) + "//" + relative) is None
            assert utility._seal_record_relative(str(world.clean) + "_external/escape.nav") is None


def test_seal_index_only_stores_exact_paths_intersecting_real_candidates(world, monkeypatch):
    candidate = world.candidate()
    relative = candidate.relative_to(world.clean).as_posix()
    sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
    noncandidate = put(world.clean, P07 + "/unknown.bin")
    seal = put(world.clean, "stages/records/OUTPUT_SEAL.json", json.dumps({
        str(candidate): sha, str(noncandidate): "a" * 64,
        str(world.clean) + "/stages/../" + relative: "b" * 64,
        "/outside/root/file.nav": "c" * 64,
    }).encode())
    utility = world.utility()
    by_path, by_hash = utility._seal_index([seal], {relative})
    assert set(by_path) == {relative} and set(by_path[relative]) == {sha}
    assert "a" * 64 in by_hash and "b" * 64 in by_hash  # Occurrence is not exact-path evidence.


def test_csv_index_does_not_route_recorded_run_roots_through_live_alias(world, monkeypatch):
    candidate = world.candidate()
    relative = candidate.relative_to(world.clean).as_posix()
    sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
    seal = put(world.clean, "stages/records/OUTPUT_HASH_MANIFEST.csv", (
        "run_root,relative_path,sha256\n" + str(candidate.parent) + "," + candidate.name + "," + sha + "\n"
        + str(candidate.parent) + ",../escape.nav," + "a" * 64 + "\n").encode())
    alias = "<CLEAN_ROOT>/" + seal.relative_to(world.clean).as_posix()
    world.amend(seal_sources=[{"path": alias}])
    utility = world.utility()
    original_alias = utility.alias
    def source_alias_only(value):
        assert value == alias, "recorded CSV paths must remain lexical strings"
        return original_alias(value)
    monkeypatch.setattr(utility, "alias", source_alias_only)
    by_path, _ = utility._seal_index([], {relative})
    assert set(by_path) == {relative}
    assert by_path[relative][sha][0]["json_pointer"] == "csv_row:2/sha256"


def test_parallel_seal_source_reads_are_bounded_and_merge_in_sorted_order(world, monkeypatch):
    candidate = world.candidate()
    relative = candidate.relative_to(world.clean).as_posix()
    sha = hashlib.sha256(candidate.read_bytes()).hexdigest()
    sources = [put(world.clean, f"stages/records/OUTPUT_SEAL_{index:02d}.json",
                   json.dumps({str(candidate): sha}).encode()) for index in range(16)]
    utility = world.utility()
    sequential = utility._seal_index(sources, {relative}, source_workers=1)
    real_read = mod._read
    active = peak = 0
    lock, release = threading.Lock(), threading.Event()
    def observed(path):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
            if active == 4:
                release.set()
        assert release.wait(2), "four independent metadata readers should overlap"
        try:
            return real_read(path)
        finally:
            with lock:
                active -= 1
    monkeypatch.setattr(mod, "_read", observed)
    parallel = utility._seal_index(list(reversed(sources)), {relative}, source_workers=4)
    assert parallel == sequential and peak == 4 and active == 0
    assert len(parallel[0][relative][sha]) == 3


def test_real_seal_source_symlink_guard_remains_active(world):
    candidate = world.candidate()
    source = put(world.code, "outside.json", b"{}")
    seal = world.clean / "stages/records/OUTPUT_SEAL.json"
    seal.parent.mkdir(parents=True)
    seal.symlink_to(source)
    with pytest.raises(OSError):
        world.utility()._seal_index([seal], {candidate.relative_to(world.clean).as_posix()})
