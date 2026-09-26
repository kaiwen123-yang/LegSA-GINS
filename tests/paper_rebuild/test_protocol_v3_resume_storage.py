"""Storage/recovery tests use only tiny synthetic files and never launch science."""
import hashlib
import gzip
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.protocol_v3 import resume_storage as rs


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


def sample(*, e=rs.E_MIN, g=rs.G_MIN, scratch=0):
    return dict(e_available_bytes=e, g_available_bytes=g, scratch_bytes=scratch)


def test_storage_pauses_ten_minutes_twice_then_hard_stop(tmp_path):
    sleeps = []
    guard = rs.StorageGuard(tmp_path, tmp_path / "guard", sample=lambda: sample(e=rs.E_MIN - 1), sleeper=sleeps.append)
    with pytest.raises(RuntimeError, match="THREE_CONSECUTIVE"):
        guard.before_batch(3)
    assert sum(sleeps) == 1200
    assert max(sleeps) == 60
    assert len(list((tmp_path / "guard").glob("*.json"))) == 3


def test_storage_recovers_second_check_and_exact_thresholds_pass(tmp_path):
    values = iter([sample(g=rs.G_MIN - 1), sample(scratch=rs.SCRATCH_MAX)])
    sleeps = []
    guard = rs.StorageGuard(tmp_path, tmp_path / "guard", sample=lambda: next(values), sleeper=sleeps.append)
    assert guard.before_batch(2)["passed"]
    assert sum(sleeps) == 600
    assert guard.summary()["scratch_peak_bytes"] == rs.SCRATCH_MAX
    assert (rs.E_MIN, rs.G_MIN, rs.SCRATCH_MAX) == (40_000_000_000, 30_000_000_000, 20_000_000_000)


def test_df_measures_real_mount_and_refuses_missing_mount(monkeypatch):
    commands = []
    monkeypatch.setattr(rs.os.path, "ismount", lambda p: str(p) == "/mnt/e")
    def output(command, **kwargs):
        commands.append(command)
        return "Avail\n43210000000\n"
    monkeypatch.setattr(rs.subprocess, "check_output", output)
    assert rs.df_available("/mnt/e") == 43210000000
    assert commands == [["df", "--block-size=1", "--output=avail", "/mnt/e"]]
    with pytest.raises(RuntimeError, match="MOUNT_MISSING"):
        rs.df_available("/mnt/g")


def test_reconciliation_requires_consumed_slot_and_separate_recovery():
    manifest = dict(reused_runs=[dict(run_id="a")], identity_native_only=[dict(run_id="i")], recovery_runs=[dict(run_id="b")])
    groups = rs.admission_sets(manifest, ["a", "b", "c", "i"], {"a", "b", "i"})
    assert set(groups["recovery_runs"]) == {"b"}
    with pytest.raises(RuntimeError, match="WITHOUT_RECONCILIATION"):
        rs.admission_sets(manifest, ["a", "b", "c", "i"], {"a", "b", "c", "i"})
    manifest["recovery_runs"].append(dict(run_id="a"))
    with pytest.raises(RuntimeError, match="COVERAGE"):
        rs.admission_sets(manifest, ["a", "b", "i"], {"a", "b", "i"})


@pytest.mark.parametrize("role", ["nav", "std"])
def test_recovery_hash_mismatch_stops_before_evaluation(role):
    rs.check_recovery_hashes({role + "_sha256": "a"}, {"expected_" + role + "_sha256": "a"})
    with pytest.raises(RuntimeError, match="HASH_MISMATCH"):
        rs.check_recovery_hashes({role + "_sha256": "a"}, {"expected_" + role + "_sha256": "b"})
    with pytest.raises(RuntimeError, match="HASH_MISMATCH"):
        rs.check_recovery_hashes({}, {"expected_" + role + "_sha256": "b"})


def source_tree(tmp_path):
    scratch = tmp_path / "scratch"
    source = scratch / rs.CONTINUATION / "04_EVALUATION/RUN_1/v3"
    source.mkdir(parents=True)
    payloads = {"EVAL_NAV_V3.nav": b"nav discarded\n", "KF_GINS_STD.txt": b"std discarded\n",
        "NATIVE_OPENAT.strace": b"large tracing\n", "stdout.log": b"old log\n",
        "EVALUATION_RESULT.json": b'{"row":{"run_id":"RUN_1"}}',
        "FROZEN_EVALUATOR/error_series.csv": b"time,error\n1,2\n",
        "FROZEN_EVALUATOR/MATCHED_TRAJECTORY.csv.gz": b"kept truth export"}
    for name, payload in payloads.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
    write(source / "OUTPUT_SEAL.json", dict(status="SEALED", files={p: digest(source / p) for p in payloads}))
    return scratch, source, payloads


def test_compact_archive_preserves_seals_series_truth_and_releases_exact_payload(tmp_path):
    scratch, source, payloads = source_tree(tmp_path)
    destination = tmp_path / "archive/result"
    original_seal = (source / "OUTPUT_SEAL.json").read_bytes()
    receipt = rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert receipt["status"] == "ARCHIVE_VERIFIED"
    assert (destination / "OUTPUT_SEAL.json").read_bytes() == original_seal
    for name, payload in payloads.items():
        if rs.retained(name):
            assert (destination / name).read_bytes() == payload
            assert receipt["files"][name]["source_sha256"] == hashlib.sha256(payload).hexdigest()
        else:
            assert not (destination / name).exists()
            assert name in receipt["discarded_payloads"]
        assert not (source / name).exists()
    assert (destination / "COMPACT_RELEASE.json").is_file()
    assert not any(p.is_file() for p in source.rglob("*"))


def test_archive_copy_failure_never_releases_source(tmp_path, monkeypatch):
    scratch, source, payloads = source_tree(tmp_path)
    def fail(*args, **kwargs):
        raise OSError("simulated disk I/O failure")
    monkeypatch.setattr(rs, "stream_copy", fail)
    with pytest.raises(OSError):
        rs.compact_archive(source, tmp_path / "archive", scratch_root=scratch, batch=1)
    assert all((source / name).read_bytes() == payload for name, payload in payloads.items())
    assert not (source / "COMPACT_RELEASE.json").exists()


def test_archive_bad_seal_no_copy_and_symlink_refused(tmp_path):
    scratch, source, _ = source_tree(tmp_path)
    (source / "EVAL_NAV_V3.nav").write_bytes(b"changed")
    with pytest.raises(RuntimeError, match="SOURCE_SEAL"):
        rs.compact_archive(source, tmp_path / "archive", scratch_root=scratch, batch=1)
    assert not (tmp_path / "archive").exists()
    (source / "linked").symlink_to(source / "EVAL_NAV_V3.nav")
    with pytest.raises((ValueError, RuntimeError)):
        rs.compact_archive(source, tmp_path / "archive", scratch_root=scratch, batch=1)


def test_compact_receipt_is_compatible_with_frozen_report_member(tmp_path):
    from legsa_gins.paper_rebuild.protocol_v3.reporting import RuntimeResults, Sources
    scratch, source, _ = source_tree(tmp_path)
    destination = tmp_path / "archive"
    receipt = rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    result = RuntimeResults.__new__(RuntimeResults)
    key = "RUN_1", "v3"
    result.folders = {key: destination}
    result.seals = {key: rs.read_json(destination / "OUTPUT_SEAL.json")}
    result.archives = {key: receipt}
    result.sources = Sources({"clean_root": str(tmp_path)})
    content, actual_path = result.member(key, "FROZEN_EVALUATOR/error_series.csv")
    assert content == b"time,error\n1,2\n"
    assert actual_path == str(destination / "FROZEN_EVALUATOR/error_series.csv")


def test_reused_identity_calls_no_native(monkeypatch, tmp_path):
    nav, std = tmp_path / "a.nav", tmp_path / "a.std"
    nav.write_bytes(b"nav")
    std.write_bytes(b"std")
    record = dict(run_id="i", status="COMPLETED", nav_path=str(nav), std_path=str(std),
        nav_sha256=digest(nav), std_sha256=digest(std))
    ctx = rs.ResumeContext.__new__(rs.ResumeContext)
    ctx.identity = {"i": {}}
    ctx.progress = SimpleNamespace(native=lambda r: None)
    ctx._load_reused = lambda item: (record, [])
    monkeypatch.setattr(rs.runtime, "run_native", lambda *a, **kw: pytest.fail("identity rerun"))
    assert ctx._native(dict(run_id="i")) == record


def test_core_non_f01_progress_is_separate_and_heartbeat_operational(tmp_path):
    specs = [dict(run_id="a", domain="CORE", method_id="F04"),
        dict(run_id="b", domain="CORE", method_id="F01"),
        dict(run_id="c", domain="SEQUENCE", method_id="F04"),
        dict(run_id="d", domain="ADDENDUM", method_id="F04")]
    counts = rs.progress_counts(specs, {"a", "b"}, {"a__v3", "a__v2"})
    assert counts["core_non_f01"] == dict(solver_done=1, solver_total=1, evaluator_done=2, evaluator_total=2)
    assert counts["total_queue"]["solver_total"] == 4
    guard = rs.StorageGuard(tmp_path, tmp_path / "storage", sample=lambda: sample())
    heartbeat = rs.Heartbeat(tmp_path / "control", guard, specs, 2)
    heartbeat.native(dict(run_id="a", status="COMPLETED"))
    heartbeat.phase = "MATRIX"
    state = heartbeat.flush()
    assert state["progress"]["core_non_f01"]["solver_done"] == 1
    assert (tmp_path / "control/STATE.json").is_file()
    assert "solver=1/1" in (tmp_path / "control/PROGRESS.txt").read_text()
    heartbeat.phase = "DONE"
    assert heartbeat.flush()["phase"] == "DONE"
    assert len(list((tmp_path / "control/HEARTBEATS").glob("*.json"))) == 2


def test_existing_continuation_slot_never_silently_reexecutes(tmp_path):
    ctx = rs.ResumeContext.__new__(rs.ResumeContext)
    ctx.identity = {}
    ctx.work = tmp_path
    (tmp_path / "03_NATIVE/r").mkdir(parents=True)
    with pytest.raises(RuntimeError, match="NO_RETRY"):
        ctx._native(dict(run_id="r"))


def test_persist_refuses_changed_existing_evidence(tmp_path):
    path = tmp_path / "record.json"
    rs.persist(path, {"status": "PASS"})
    rs.persist(path, {"status": "PASS"})
    with pytest.raises(RuntimeError, match="CHECKPOINT_CHANGED"):
        rs.persist(path, {"status": "OTHER"})


def test_parallel_workers_are_fixed_to_22(monkeypatch):
    observed = []
    original = rs.ThreadPoolExecutor
    def executor(*args, **kwargs):
        observed.append(kwargs["max_workers"])
        return original(*args, **kwargs)
    monkeypatch.setattr(rs, "ThreadPoolExecutor", executor)
    assert sorted(rs.parallel_bounded([3, 1, 2], lambda value: value * 2)) == [2, 4, 6]
    assert observed == [22]
    assert rs.BATCH_SIZE == 22


def freeze_fixture(tmp_path, monkeypatch):
    science, continuation = "a" * 40, "b" * 40
    names = ["src/science.py", "src/legsa_gins/paper_rebuild/protocol_v3/resume_storage.py",
        "scripts/paper_rebuild/v3_resume_storage.py", "tests/paper_rebuild/test_protocol_v3_resume_storage.py"]
    objects = {}
    for index, name in enumerate(names):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        content = ("# pinned " + str(index) + "\n").encode()
        path.write_bytes(content)
        objects[name] = content
    def git(command, **kwargs):
        if command[1] == "ls-remote":
            return (continuation + "\trefs/heads/stage/clean3-math-repair\n").encode()
        if command[1] == "rev-parse":
            return (continuation + "\n").encode()
        if command[1] == "merge-base":
            return b""
        if command[1] == "show":
            return objects[command[2].split(":", 1)[1]]
        raise AssertionError(command)
    monkeypatch.setattr(rs.subprocess, "check_output", git)
    receipt = dict(status="PASS_PUSHED_CODE_FREEZE", code_freeze=science, remote_commit=science,
        source_sha256={"src/science.py": digest(tmp_path / "src/science.py")})
    return science, continuation, receipt, git


def test_continuation_freeze_checks_original_science_without_faking_old_head(tmp_path, monkeypatch):
    science, continuation, receipt, _ = freeze_fixture(tmp_path, monkeypatch)
    result = rs.continuation_freeze(tmp_path, science, continuation, receipt)
    assert result["science_freeze"] == science
    assert result["continuation_commit"] == continuation
    assert result["original_freeze_receipt_rewritten"] is False
    (tmp_path / "src/science.py").write_text("changed\n")
    with pytest.raises(RuntimeError, match="SCIENCE_SOURCE_CHANGED"):
        rs.continuation_freeze(tmp_path, science, continuation, receipt)


def test_continuation_freeze_requires_pushed_current_commit(tmp_path, monkeypatch):
    science, continuation, receipt, git = freeze_fixture(tmp_path, monkeypatch)
    def wrong_remote(command, **kwargs):
        return b"c refs/heads/stage/clean3-math-repair" if command[1] == "ls-remote" else git(command, **kwargs)
    monkeypatch.setattr(rs.subprocess, "check_output", wrong_remote)
    with pytest.raises(RuntimeError, match="NOT_CURRENT_AND_PUSHED"):
        rs.continuation_freeze(tmp_path, science, continuation, receipt)


def test_complete_matrix_state_reentry_never_calls_solver_or_evaluator(tmp_path, monkeypatch):
    ctx = rs.ResumeContext.__new__(rs.ResumeContext)
    ctx.archive = tmp_path
    ctx.code_freeze = "science"
    ctx.allowed = ["r"]
    ctx.eval_allowed = ["r__v3", "r__v2"]
    records = [dict(run_id="r", status="COMPLETED")]
    payloads = [dict(row=dict(run_id="r", evaluator_contract="evaluator_contract_" + v,
        evaluation_status="COMPLETED")) for v in ("v3", "v2")]
    write(tmp_path / "FINAL_RUN_RECORDS.json", records)
    write(tmp_path / "FINAL_EVALUATION_RECORDS.json", payloads)
    status = dict(status="PASS_V3_EXECUTION_COMPLETE", science_freeze="science",
        final_run_records_sha256=digest(tmp_path / "FINAL_RUN_RECORDS.json"),
        final_evaluation_records_sha256=digest(tmp_path / "FINAL_EVALUATION_RECORDS.json"))
    write(tmp_path / "STATUS.json", status)
    guard = rs.StorageGuard(tmp_path, tmp_path / "storage", sample=lambda: sample())
    ctx.progress = rs.Heartbeat(tmp_path / "control", guard,
        [dict(run_id="r", domain="CORE", method_id="F04")], 1)
    monkeypatch.setattr(rs.runtime, "run_native", lambda *a, **kw: pytest.fail("native rerun"))
    monkeypatch.setattr(rs.runtime, "evaluate_native", lambda *a, **kw: pytest.fail("evaluator rerun"))
    assert ctx.matrix() == status
    assert ctx.progress.completed == 1
    assert ctx.progress.eval_ids == {"r__v3", "r__v2"}


def test_compact_archive_kill_after_delete_resumes_from_durable_intent(tmp_path, monkeypatch):
    scratch, source, payloads = source_tree(tmp_path)
    destination = tmp_path / "archive"
    original = rs.retry_io
    interrupted = False
    def interrupt_after_unlink(function, **kwargs):
        nonlocal interrupted
        result = original(function, **kwargs)
        if kwargs["operation"] == "v3r_exact_scratch_release" and not interrupted:
            interrupted = True
            raise SystemExit("simulated kill after unlink before done checkpoint")
        return result
    monkeypatch.setattr(rs, "retry_io", interrupt_after_unlink)
    with pytest.raises(SystemExit):
        rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert (destination / "ARCHIVE_RECEIPT.json").is_file()
    assert not (destination / "COMPACT_RELEASE.json").exists()
    assert any(not (source / name).exists() for name in payloads)
    journal = next(tmp_path.rglob("RELEASE_JOURNAL.jsonl"))
    assert [json.loads(line)["event"] for line in journal.read_text().splitlines()] == ["INTENT"]
    monkeypatch.setattr(rs, "retry_io", original)
    receipt = rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert (destination / "COMPACT_RELEASE.json").is_file()
    assert not any(path.is_file() for path in source.rglob("*"))
    journal_bytes = journal.read_bytes()
    assert rs.compact_archive(source, destination, scratch_root=scratch, batch=1) == receipt
    assert journal.read_bytes() == journal_bytes
    events = [json.loads(line) for line in journal_bytes.splitlines()]
    assert len(events) == 2 * len(payloads) + 2  # original payloads and OUTPUT_SEAL
    assert [row["event"] for row in events] == ["INTENT", "DONE"] * (len(payloads) + 1)
    assert sorted(p.name for p in journal.parent.rglob("*") if p.is_file()) == ["COMPACT_PLAN.json", "RELEASE_JOURNAL.jsonl"]
    assert len(list(tmp_path.rglob("RELEASE_JOURNAL.jsonl"))) == 1
    assert not list(tmp_path.rglob("RELEASE_INTENTS"))
    assert not list(tmp_path.rglob("RELEASE_DONE"))


def test_release_journal_intent_before_unlink_can_resume(tmp_path, monkeypatch):
    scratch, source, payloads = source_tree(tmp_path)
    destination = tmp_path / "archive"
    original = rs.retry_io
    def interrupt_before_unlink(function, **kwargs):
        if kwargs["operation"] == "v3r_exact_scratch_release":
            raise SystemExit("simulated kill after fsynced intent before unlink")
        return original(function, **kwargs)
    monkeypatch.setattr(rs, "retry_io", interrupt_before_unlink)
    with pytest.raises(SystemExit):
        rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert all((source / name).read_bytes() == payload for name, payload in payloads.items())
    journal = next(tmp_path.rglob("RELEASE_JOURNAL.jsonl"))
    assert len(journal.read_text().splitlines()) == 1
    monkeypatch.setattr(rs, "retry_io", original)
    rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert not any(path.is_file() for path in source.rglob("*"))
    assert len(journal.read_text().splitlines()) == 2 * (len(payloads) + 1)


def test_release_journal_durable_done_never_redeletes_after_process_interruption(tmp_path, monkeypatch):
    scratch, source, _ = source_tree(tmp_path)
    destination = tmp_path / "archive"
    original_bytes, original_retry = rs._metadata_bytes, rs.retry_io
    first_done = []
    def kill_after_done(path, payload, **kwargs):
        result = original_bytes(path, payload, **kwargs)
        if Path(path).name == "RELEASE_JOURNAL.jsonl" and b'"event":"DONE"' in payload and not first_done:
            first_done.append(json.loads(payload)["relative_path"])
            raise SystemExit("simulated kill after durable DONE before in-memory update")
        return result
    monkeypatch.setattr(rs, "_metadata_bytes", kill_after_done)
    with pytest.raises(SystemExit):
        rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert len(first_done) == 1
    monkeypatch.setattr(rs, "_metadata_bytes", original_bytes)
    releases = []
    def observed_retry(function, **kwargs):
        if kwargs["operation"] == "v3r_exact_scratch_release":
            releases.append(str(kwargs["source"]))
        return original_retry(function, **kwargs)
    monkeypatch.setattr(rs, "retry_io", observed_retry)
    rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert str(source / first_done[0]) not in releases
    count = len(releases)
    rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert len(releases) == count


@pytest.mark.parametrize("change", ["done_first", "relative", "hash", "action", "extra", "duplicate_intent", "duplicate_done"])
def test_release_journal_rejects_scope_order_and_duplicate_records(tmp_path, change):
    inventory = {"a.nav": dict(source_sha256="a" * 64)}
    intent = dict(relative_path="a.nav", sha256="a" * 64, action="DELETE_VERIFIED_SCRATCH_FILE", event="INTENT")
    done = {**intent, "event": "DONE"}
    rows = [dict(intent)]
    if change == "done_first":
        rows = [done]
    elif change == "relative":
        rows[0]["relative_path"] = "../outside"
    elif change == "hash":
        rows[0]["sha256"] = "b" * 64
    elif change == "action":
        rows[0]["action"] = "UNREGISTERED_ACTION"
    elif change == "extra":
        rows[0]["unregistered"] = True
    elif change == "duplicate_intent":
        rows.append(intent)
    else:
        rows.extend([done, done])
    path = tmp_path / "RELEASE_JOURNAL.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    with pytest.raises(RuntimeError, match="RELEASE_JOURNAL"):
        rs.ReleaseJournal(path, inventory)


def test_release_journal_done_source_reappearance_is_preserved_and_stops(tmp_path):
    scratch, source, payloads = source_tree(tmp_path)
    destination = tmp_path / "archive"
    rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    restored = source / "EVAL_NAV_V3.nav"
    restored.write_bytes(payloads["EVAL_NAV_V3.nav"])
    with pytest.raises(RuntimeError, match="RELEASED_SOURCE_REAPPEARED"):
        rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert restored.read_bytes() == payloads["EVAL_NAV_V3.nav"]


def test_release_journal_rejects_partial_tail_and_duplicate_json_keys(tmp_path):
    inventory = {"a.nav": dict(source_sha256="a" * 64)}
    path = tmp_path / "RELEASE_JOURNAL.jsonl"
    path.write_bytes(b'{"event":"INTENT"')
    with pytest.raises(RuntimeError, match="UNTERMINATED_RECORD"):
        rs.ReleaseJournal(path, inventory)
    path.write_bytes(b'{"event":"DONE","event":"INTENT"}\n')
    with pytest.raises(RuntimeError, match="JOURNAL_SCHEMA"):
        rs.ReleaseJournal(path, inventory)


def test_release_journal_fsync_retry_does_not_duplicate_intent(tmp_path, monkeypatch):
    import errno
    from legsa_gins.paper_rebuild.clean6_canonical_v2 import io_recovery
    original_retry, original_fsync = io_recovery.retry_io, rs.os.fsync
    failures = []
    def no_sleep_retry(function, **kwargs):
        return original_retry(function, **kwargs, sleep=lambda delay: None)
    def fail_once(fd):
        if not failures:
            failures.append("journal fsync after row write")
            raise OSError(errno.EIO, "simulated journal durability error")
        return original_fsync(fd)
    monkeypatch.setattr(io_recovery, "retry_io", no_sleep_retry)
    monkeypatch.setattr(rs.os, "fsync", fail_once)
    path = tmp_path / "RELEASE_JOURNAL.jsonl"
    inventory = {"a.nav": dict(source_sha256="a" * 64)}
    journal = rs.ReleaseJournal(path, inventory)
    journal.append("a.nav", "INTENT")
    assert len(path.read_text().splitlines()) == 1
    resumed = rs.ReleaseJournal(path, inventory)
    assert resumed.states == {"a.nav": "INTENT"}
    resumed.append("a.nav", "DONE")
    assert [json.loads(line)["event"] for line in path.read_text().splitlines()] == ["INTENT", "DONE"]


def test_compact_archive_owned_partial_copy_replays_without_new_science(tmp_path, monkeypatch):
    scratch, source, _ = source_tree(tmp_path)
    destination = tmp_path / "archive"
    original = rs.stream_copy
    def interrupted_copy(src, target, **kwargs):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"partial")
        raise SystemExit("simulated kill during G copy")
    monkeypatch.setattr(rs, "stream_copy", interrupted_copy)
    with pytest.raises(SystemExit):
        rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert not (destination / "ARCHIVE_RECEIPT.json").exists()
    monkeypatch.setattr(rs, "stream_copy", original)
    rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert (destination / "COMPACT_RELEASE.json").is_file()
    assert not any(path.is_file() for path in source.rglob("*"))


def test_compact_archive_missing_source_without_release_intent_is_rejected(tmp_path, monkeypatch):
    scratch, source, _ = source_tree(tmp_path)
    destination = tmp_path / "archive"
    original = rs.persist
    def stop_before_release(path, value):
        result = original(path, value)
        if Path(path).name == "ARCHIVE_RECEIPT.json":
            raise SystemExit("simulated kill before release intent")
        return result
    monkeypatch.setattr(rs, "persist", stop_before_release)
    with pytest.raises(SystemExit):
        rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    (source / "stdout.log").unlink()
    monkeypatch.setattr(rs, "persist", original)
    with pytest.raises(RuntimeError, match="WITHOUT_RELEASE_INTENT"):
        rs.compact_archive(source, destination, scratch_root=scratch, batch=1)


def test_duplicate_error_series_stored_once_with_compatible_seal_mapping(tmp_path):
    from legsa_gins.paper_rebuild.protocol_v3.reporting import RuntimeResults, Sources
    scratch, source, payloads = source_tree(tmp_path)
    plain = "FROZEN_EVALUATOR/error_series.csv"
    payloads[plain + ".gz"] = gzip.compress(payloads[plain], mtime=0)
    payloads["EVAL_NAV.csv"] = b"large nav csv"
    payloads["KF_GINS_IMU_ERR.txt"] = b"large imu diagnostic"
    payloads["KF_GINS_Navresult.nav.gz"] = b"compressed nav"
    for name, payload in payloads.items():
        (source / name).write_bytes(payload)
    write(source / "OUTPUT_SEAL.json", dict(status="SEALED", files={p: digest(source / p) for p in payloads}))
    destination = tmp_path / "archive"
    receipt = rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert not (destination / plain).exists()
    assert (destination / (plain + ".gz")).is_file()
    assert not (destination / "EVAL_NAV.csv").exists()
    assert not (destination / "KF_GINS_IMU_ERR.txt").exists()
    assert not (destination / "KF_GINS_Navresult.nav.gz").exists()
    result = RuntimeResults.__new__(RuntimeResults)
    key = "RUN_1", "v3"
    result.folders = {key: destination}
    result.seals = {key: rs.read_json(destination / "OUTPUT_SEAL.json")}
    result.archives = {key: receipt}
    result.sources = Sources({"clean_root": str(tmp_path)})
    series, _ = result.series(dict(run_id="RUN_1", evaluator_version="v3"))
    assert series.to_dict("records") == [{"time": 1, "error": 2}]


def large_csv_tree(tmp_path, size=1_000_000):
    scratch, source, payloads = source_tree(tmp_path)
    name = "PORT_RUNTIME_LOOP_TRACE.csv"
    payload = (b"time,diagnostic\n" + b"1.00,1.23456789\n" * (size // 15 + 1))[:size]
    payloads[name] = payload
    (source / name).write_bytes(payload)
    write(source / "OUTPUT_SEAL.json", dict(status="SEALED", files={p: digest(source / p) for p in payloads}))
    return scratch, source, name, payload


def test_large_retained_csv_is_deterministic_lossless_gzip_and_frozen_member_compatible(tmp_path):
    from legsa_gins.paper_rebuild.protocol_v3.reporting import RuntimeResults, Sources
    scratch, source, name, payload = large_csv_tree(tmp_path)
    destination = tmp_path / "archive"
    seal_bytes = (source / "OUTPUT_SEAL.json").read_bytes()
    receipt = rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    item = receipt["files"][name]
    assert item["source_sha256"] == hashlib.sha256(payload).hexdigest()
    assert item["source_size_bytes"] == 1_000_000
    assert item["compression_profile"] == dict(compresslevel=6, filename="", mtime=0)
    assert item["compression"] == "gzip"
    assert item["storage_relative_path"] == name + ".gz"
    assert not (destination / name).exists()
    stored = destination / item["storage_relative_path"]
    expected = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=expected, compresslevel=6, mtime=0) as writer:
        writer.write(payload)
    assert stored.read_bytes() == expected.getvalue()
    assert digest(stored) == item["sha256"]
    assert gzip.decompress(stored.read_bytes()) == payload
    assert (destination / "OUTPUT_SEAL.json").read_bytes() == seal_bytes
    assert name not in receipt["discarded_payloads"]
    result = RuntimeResults.__new__(RuntimeResults)
    key = "RUN_1", "v3"
    result.folders = {key: destination}
    result.seals = {key: rs.read_json(destination / "OUTPUT_SEAL.json")}
    result.archives = {key: receipt}
    result.sources = Sources({"clean_root": str(tmp_path)})
    restored, path = result.member(key, name)
    assert restored == payload
    assert path == str(stored)
    assert not any(path.is_file() for path in source.rglob("*"))


def test_retained_csv_below_one_decimal_mb_stays_identity(tmp_path):
    scratch, source, name, payload = large_csv_tree(tmp_path, size=999_999)
    destination = tmp_path / "archive"
    receipt = rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert receipt["files"][name]["compression"] == "identity"
    assert (destination / name).read_bytes() == payload
    assert not (destination / (name + ".gz")).exists()


def test_large_csv_owned_partial_gzip_write_recovers(tmp_path, monkeypatch):
    scratch, source, name, payload = large_csv_tree(tmp_path)
    destination = tmp_path / "archive"
    original = rs.retry_io
    def partial_gzip(function, **kwargs):
        if kwargs["operation"] == "v3r_gzip_copy":
            target = Path(kwargs["destination"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"\x1f\x8b\x08\x00")
            raise SystemExit("simulated kill during bounded-memory G gzip write")
        return original(function, **kwargs)
    monkeypatch.setattr(rs, "retry_io", partial_gzip)
    with pytest.raises(SystemExit):
        rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert (source / name).read_bytes() == payload
    assert not (destination / "ARCHIVE_RECEIPT.json").exists()
    monkeypatch.setattr(rs, "retry_io", original)
    receipt = rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert gzip.decompress((destination / (name + ".gz")).read_bytes()) == payload
    assert receipt["files"][name]["source_sha256"] == hashlib.sha256(payload).hexdigest()
    assert not any(path.is_file() for path in source.rglob("*"))


def test_large_csv_deleted_source_resumes_using_sealed_gzip_and_journal(tmp_path, monkeypatch):
    scratch, source, name, payload = large_csv_tree(tmp_path)
    destination = tmp_path / "archive"
    original = rs.retry_io
    def kill_after_csv_delete(function, **kwargs):
        result = original(function, **kwargs)
        if kwargs["operation"] == "v3r_exact_scratch_release" and Path(kwargs["source"]) == source / name:
            raise SystemExit("simulated kill after CSV delete before journal DONE")
        return result
    monkeypatch.setattr(rs, "retry_io", kill_after_csv_delete)
    with pytest.raises(SystemExit):
        rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert not (source / name).exists()
    expected_receipt = rs.read_json(destination / "ARCHIVE_RECEIPT.json")
    monkeypatch.setattr(rs, "retry_io", original)
    monkeypatch.setattr(rs, "_gzip_copy", lambda *a, **kw: pytest.fail("recompressed an already released CSV"))
    receipt = rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert receipt == expected_receipt
    assert gzip.decompress((destination / (name + ".gz")).read_bytes()) == payload
    assert not any(path.is_file() for path in source.rglob("*"))
    assert rs.compact_archive(source, destination, scratch_root=scratch, batch=1) == receipt


def test_large_csv_gzip_fsync_retries_owned_stream_with_same_bytes(tmp_path, monkeypatch):
    import errno
    scratch, source, name, payload = large_csv_tree(tmp_path)
    destination = tmp_path / "archive"
    original_retry, original_fsync = rs.retry_io, rs.os.fsync
    failures = []
    def no_sleep_retry(function, **kwargs):
        return original_retry(function, **kwargs, sleep=lambda delay: None)
    def gzip_fsync_failure(fd):
        if not failures and rs.os.readlink("/proc/self/fd/" + str(fd)) == str(destination / (name + ".gz")):
            failures.append("gzip bytes already written")
            raise OSError(errno.EIO, "simulated G gzip durability failure")
        return original_fsync(fd)
    monkeypatch.setattr(rs, "retry_io", no_sleep_retry)
    monkeypatch.setattr(rs.os, "fsync", gzip_fsync_failure)
    receipt = rs.compact_archive(source, destination, scratch_root=scratch, batch=1)
    assert failures == ["gzip bytes already written"]
    stored = destination / receipt["files"][name]["storage_relative_path"]
    assert gzip.decompress(stored.read_bytes()) == payload
    assert digest(stored) == receipt["files"][name]["sha256"]


@pytest.mark.parametrize("interrupt_at", [1, 2])
def test_batch_terminal_checkpoint_resumes_archive_only(tmp_path, monkeypatch, interrupt_at):
    ctx = rs.ResumeContext.__new__(rs.ResumeContext)
    ctx.archive, ctx.scratch, ctx.work, ctx.code = tmp_path / "g", tmp_path / "scratch", tmp_path / "scratch/work", tmp_path
    ctx.archive.mkdir()
    ctx.control = ctx.archive / "00_CONTROL" / rs.CONTINUATION
    ctx.code_freeze, ctx.continuation_commit = "science", "continuation"
    ctx.allowed, ctx.eval_allowed = ["r"], ["r__v3", "r__v2"]
    ctx.retention, ctx.capacity = {"r": None}, None
    ctx.specs = [dict(run_id="r", domain="CORE", method_id="F04")]
    ctx.reused, ctx.identity, ctx.recovery = {}, {}, {}
    ctx.gates, ctx.parent_raw_opens = {"2c": {}}, []
    ctx.freeze = {"source_sha256": {}}
    ctx.contract = {"frozen": {"executable": {}, "evaluator": {}}}
    ctx._verify_admissions = lambda: None
    ctx.guard = rs.StorageGuard(ctx.scratch, ctx.control / "STORAGE", sample=lambda: sample())
    ctx.progress = rs.Heartbeat(ctx.archive / "00_CONTROL", ctx.guard, ctx.specs, 1)
    ctx.progress.start = lambda: None
    record = dict(run_id="r", status="COMPLETED", output_root=str(ctx.work / "03_NATIVE/r"),
        effective_echo_gate={"passed": True})
    payloads = [dict(row=dict(run_id="r", evaluator_contract="evaluator_contract_" + v,
        evaluation_status="COMPLETED")) for v in ("v3", "v2")]
    calls = []
    def execute(items, function):
        calls.append(function.__name__)
        return [record] if function.__name__ == "_native" else payloads
    monkeypatch.setattr(rs, "parallel_bounded", execute)
    archives = []
    def archive(source, destination, **kwargs):
        archives.append(str(destination))
        if len(archives) == interrupt_at:
            raise SystemExit("simulated kill during archive batch")
        return dict(archive_root=str(destination))
    monkeypatch.setattr(rs, "compact_archive", archive)
    with pytest.raises(SystemExit):
        ctx.matrix()
    assert calls == ["_native", "_evaluate"]
    assert (ctx.control / "BATCHES/BATCH_0001/BATCH_TERMINALS.json").is_file()
    assert not (ctx.control / "BATCHES/BATCH_0001/BATCH_COMPLETE.json").exists()
    monkeypatch.setattr(rs, "parallel_bounded", lambda *a: pytest.fail("science invoked during archive resume"))
    monkeypatch.setattr(rs.runtime, "verify_pin", lambda pin, **kw: Path(pin.get("path", tmp_path)))
    result = ctx.matrix()
    assert result["status"] == "PASS_V3_EXECUTION_COMPLETE"
    assert (ctx.control / "BATCHES/BATCH_0001/BATCH_COMPLETE.json").is_file()


def test_reservation_fixed_offset_fsync_retry_consumes_one_slot(tmp_path, monkeypatch):
    import errno
    from legsa_gins.paper_rebuild.clean6_canonical_v2 import io_recovery
    original_retry, original_fsync = io_recovery.retry_io, rs.os.fsync
    failures = []
    def no_sleep_retry(function, **kwargs):
        return original_retry(function, **kwargs, sleep=lambda delay: None)
    def fail_once(fd):
        if not failures:
            failures.append("fsync failed after row bytes were written")
            raise OSError(errno.EIO, "simulated fsync error")
        return original_fsync(fd)
    monkeypatch.setattr(io_recovery, "retry_io", no_sleep_retry)
    monkeypatch.setattr(rs.os, "fsync", fail_once)
    ledger = tmp_path / "NATIVE_RESERVATIONS.jsonl"
    row = rs.reserve_slot_with_retry(ledger, "a", ["a", "b"], kind="native")
    assert row["ordinal"] == 1
    assert [json.loads(line) for line in ledger.read_text().splitlines()] == [row]
    with pytest.raises(RuntimeError, match="ALREADY_RESERVED_NO_RETRY"):
        rs.reserve_slot_with_retry(ledger, "a", ["a", "b"], kind="native")
    with pytest.raises(PermissionError, match="UNREGISTERED_RESERVATION"):
        rs.reserve_slot_with_retry(ledger, "other", ["a", "b"], kind="native")
    with pytest.raises(RuntimeError, match="RESERVATION_SCOPE"):
        rs.reserve_slot_with_retry(ledger, "b", ["a", "b"], kind="evaluator")


def test_admitted_identity_counts_before_its_batch_without_duplicate_final_records(tmp_path, monkeypatch):
    ctx = rs.ResumeContext.__new__(rs.ResumeContext)
    ctx.archive, ctx.scratch, ctx.work, ctx.code = tmp_path / "g", tmp_path / "scratch", tmp_path / "scratch/work", tmp_path
    ctx.archive.mkdir()
    ctx.control = ctx.archive / "00_CONTROL" / rs.CONTINUATION
    ctx.code_freeze, ctx.continuation_commit = "science", "continuation"
    ctx.allowed = ["reused", "identity"]
    ctx.retention, ctx.capacity = {"reused": None, "identity": None}, None
    ctx.eval_allowed = [rid + "__" + version for rid in ctx.allowed for version in rs.VERSIONS]
    ctx.specs = [dict(run_id="reused", domain="CORE", method_id="F04"),
        dict(run_id="identity", domain="SEQUENCE", method_id="F01")]
    ctx.reused = {"reused": dict(run_id="reused")}
    ctx.identity = {"identity": dict(run_id="identity", evaluations={"v3": {}})}
    ctx.recovery, ctx.gates, ctx.parent_raw_opens = {}, {"2c": {}}, []
    ctx.freeze = {"source_sha256": {}}
    ctx.contract = {"frozen": {"executable": {}, "evaluator": {}}}
    ctx._verify_admissions = lambda: None
    ctx.guard = rs.StorageGuard(ctx.scratch, ctx.control / "STORAGE", sample=lambda: sample())
    ctx.progress = rs.Heartbeat(ctx.archive / "00_CONTROL", ctx.guard, ctx.specs, 1)
    ctx.progress.start = lambda: None
    records = {rid: dict(run_id=rid, status="COMPLETED", output_root=str(ctx.work / "03_NATIVE" / rid),
        effective_echo_gate={"passed": True}) for rid in ctx.allowed}
    payloads = {rid: [dict(row=dict(run_id=rid, evaluator_contract="evaluator_contract_" + version,
        evaluation_status="COMPLETED")) for version in rs.VERSIONS] for rid in ctx.allowed}
    ctx._load_reused = lambda item: (records[item["run_id"]], payloads[item["run_id"]]
        if item["run_id"] == "reused" else payloads["identity"][:1])
    checked = []
    def before_batch(number):
        counts = rs.progress_counts(ctx.specs, ctx.progress.native_ids, ctx.progress.eval_ids)
        assert counts["total_queue"] == dict(solver_done=2, solver_total=2, evaluator_done=3, evaluator_total=4)
        assert counts["three_sequence_unique_extra"]["solver_done"] == 1
        checked.append(number)
    ctx.guard.before_batch = before_batch
    def execute(items, function):
        if function.__name__ == "_native":
            assert [item["run_id"] for item in items] == ["identity"]
            ctx.progress.native(records["identity"])
            return [records["identity"]]
        assert {record["run_id"] for record, _ in items} == {"identity"}
        for payload in payloads["identity"]:
            ctx.progress.evaluation(payload)
        return payloads["identity"]
    monkeypatch.setattr(rs, "parallel_bounded", execute)
    monkeypatch.setattr(rs, "compact_archive", lambda source, destination, **kw: dict(archive_root=str(destination)))
    monkeypatch.setattr(rs.runtime, "verify_pin", lambda pin, **kw: Path(pin.get("path", tmp_path)))
    monkeypatch.setattr(rs.runtime, "run_native", lambda *a, **kw: pytest.fail("native invocation"))
    monkeypatch.setattr(rs.runtime, "evaluate_native", lambda *a, **kw: pytest.fail("evaluator invocation"))
    monkeypatch.setattr(rs, "reserve_slot_with_retry", lambda *a, **kw: pytest.fail("reservation consumed"))
    result = ctx.matrix()
    assert checked == [1]
    assert result["native_terminal_count"] == 2
    assert result["evaluator_terminal_count"] == 4
    final_records = rs.read_json(ctx.archive / "FINAL_RUN_RECORDS.json")
    assert [record["run_id"] for record in final_records] == ["identity", "reused"]
    final_evaluations = rs.read_json(ctx.archive / "FINAL_EVALUATION_RECORDS.json")
    assert len({(p["row"]["run_id"], p["row"]["evaluator_contract"]) for p in final_evaluations}) == 4


def test_report_io_preserves_frozen_serialized_bytes_and_restores_scope(tmp_path):
    import numpy as np
    from legsa_gins.paper_rebuild.protocol_v3 import reporting
    reference, stage = tmp_path / "reference", tmp_path / "stage"
    reference.mkdir()
    output = stage / "07_AGGREGATE"
    output.mkdir(parents=True)
    value = dict(number=np.float64(0.125), text="航向", unavailable="UNAVAILABLE")
    rows = [dict(value=1.234, array=[1, 2], text="a,b"), dict(value="UNAVAILABLE", array=[], text="航向")]
    reporting.write_json(reference / "record.json", value)
    reporting.write_csv(reference / "table.csv", rows)
    original = reporting.write_json
    original_text = Path.write_text
    with rs.report_output_io(stage):
        reporting.write_json(output / "record.json", value)
        reporting.write_csv(output / "table.csv", rows)
        assert (output / "note.md").write_text("exact method text\n", encoding="utf-8") == 18
        assert (reference / "record.json").read_bytes() == (output / "record.json").read_bytes()
        with pytest.raises(PermissionError, match="OUTSIDE_OUTPUT_ROOTS"):
            reporting.write_json(tmp_path / "unapproved.json", value)
    assert reporting.write_json is original
    assert Path.write_text is original_text
    assert (output / "table.csv").read_bytes() == (reference / "table.csv").read_bytes()
    assert not (tmp_path / "unapproved.json").exists()


def test_figure_io_preserves_png_and_allows_owned_dpi_refinement(tmp_path):
    from matplotlib.figure import Figure
    figure = Figure(figsize=(1, 1))
    figure.subplots().plot([0, 1], [1, 0])
    original = Figure.savefig
    reference = tmp_path / "reference.png"
    figure.savefig(reference, dpi=50)
    output = tmp_path / "stage/08_FIGURES/MFIG00/MFIG00.png"
    with rs.report_output_io(tmp_path / "stage"):
        figure.savefig(output, dpi=50)
        assert output.read_bytes() == reference.read_bytes()
        figure.savefig(output, dpi=100)
        assert output.read_bytes() != reference.read_bytes()
        with pytest.raises(PermissionError, match="OUTSIDE_OUTPUT_ROOTS"):
            figure.savefig(tmp_path / "outside.png")
    assert Figure.savefig is original
    assert not (tmp_path / "outside.png").exists()


def retention_specs():
    cases = ["C00_clean_normal"] + [f"D{i:02d}_seed_{seed:02d}" for i in range(1, 61) for seed in range(9)]
    specs = []
    for domain, sequence, names in (("CORE", "BY2", cases), ("SEQUENCE", "BY2H", ["C00_clean_normal"]),
            ("SEQUENCE", "BY2O", ["C00_clean_normal"]), ("ADDENDUM", "BY2", [f"A1_{i}" for i in range(45)])):
        for case in names:
            for method in range(11):
                specs.append(dict(run_id=f"r{len(specs)}", domain=domain, sequence_id=sequence,
                    case_id=case, method_id=f"M{method:02d}"))
    return specs


def capacity_fixture(tmp_path, *, triggered=True):
    control = tmp_path / "control"
    control.mkdir()
    (control / "CAPACITY_SAMPLE_8_BATCHES.csv").write_bytes(b"synthetic storage fixture\n")
    specs = retention_specs()
    forecast = dict(schema="V3R_CAPACITY_FORECAST_V1", storage_provenance_only=True,
        native_calls=0, evaluator_calls=0, registry_sha256="registry", sample_batches=8,
        threshold_fraction=0.6, g_available_bytes_at_forecast=186261962752, threshold_bytes=111757177651.2,
        matrix_aggregate_remaining_allocated_bytes=166798532608 if triggered else 100000000000,
        conditional_retention_triggered=triggered, retained_native_slots=1188, retained_evaluator_slots=2376,
        omitted_evaluator_slots=10560, conditional_matrix_aggregate_remaining_allocated_bytes=109706047488,
        matrix_aggregate_remaining_apparent_bytes=94713775850,
        conditional_matrix_aggregate_remaining_apparent_bytes=39015222764,
        samples=dict(native=dict(mean_allocated_bytes=4979712.0, mean_apparent_bytes=873611.451171875),
            evaluator=dict(mean_allocated_bytes=9833728.0, mean_apparent_bytes=5835337.982421875)),
        aggregate_control_allowance_bytes=20000000000, existing_sample_reclaimable_allocated_bytes=5190189056,
        projection_assumption="synthetic fixture", sample_csv_sha256=digest(control / "CAPACITY_SAMPLE_8_BATCHES.csv"))
    write(control / "CAPACITY_FORECAST.json", forecast)
    return control, forecast, specs


def test_conditional_retention_exact_6468_index_and_forecast_binding(tmp_path):
    import csv
    control, forecast, specs = capacity_fixture(tmp_path)
    decisions, numbers = rs.capacity_admission(control, digest(control / "CAPACITY_FORECAST.json"), "registry", specs)
    assert len(decisions) == 6468
    assert sum(d["retain_error_series"] for d in decisions.values()) == 1188
    assert all(d["retain_error_series"] for d in decisions.values() if d["domain"] != "CORE")
    assert all(d["retain_error_series"] == (d["case_id"] in rs.KEEP_CORE_CASES)
        for d in decisions.values() if d["domain"] == "CORE")
    assert len(list(csv.DictReader((control / "RETENTION_INDEX.csv").open()))) == 6468
    assert str(tmp_path) not in (control / "RETENTION_INDEX.csv").read_text()
    policy = rs.read_json(control / "RETENTION_POLICY.json")
    assert policy["index"]["sha256"] == digest(control / "RETENTION_INDEX.csv")
    assert policy["forecast"]["sha256"] == digest(control / "CAPACITY_FORECAST.json")
    assert numbers["conditional_matrix_aggregate_remaining_allocated_bytes"] == 109706047488
    assert rs.capacity_admission(control, digest(control / "CAPACITY_FORECAST.json"), "registry", specs) == (decisions, numbers)
    with pytest.raises(RuntimeError, match="FORECAST_IDENTITY"):
        rs.capacity_admission(control, digest(control / "CAPACITY_FORECAST.json"), "changed-registry", specs)


def test_threshold_not_triggered_retains_all_and_false_decision_is_rejected(tmp_path):
    control, forecast, specs = capacity_fixture(tmp_path, triggered=False)
    decisions, _ = rs.capacity_admission(control, digest(control / "CAPACITY_FORECAST.json"), "registry", specs)
    assert all(d["retain_error_series"] for d in decisions.values())
    forecast["conditional_retention_triggered"] = True
    write(control / "CAPACITY_FORECAST.json", forecast)
    with pytest.raises(RuntimeError, match="THRESHOLD_MISMATCH"):
        rs.capacity_admission(control, digest(control / "CAPACITY_FORECAST.json"), "registry", specs)


def test_new_compact_omits_only_unretained_error_series_and_binds_policy(tmp_path):
    scratch, source, _ = source_tree(tmp_path)
    seal_bytes = (source / "OUTPUT_SEAL.json").read_bytes()
    decision = dict(run_id="RUN_1", domain="CORE", case_id="D01_seed_01", retain_error_series=False,
        policy=dict(path="frozen-policy", sha256="policy-digest"))
    target = tmp_path / "archive/result"
    result = rs.compact_archive(source, target, scratch_root=scratch, batch=1, retention=decision)
    assert "FROZEN_EVALUATOR/error_series.csv" in result["discarded_payloads"]
    assert not (target / "FROZEN_EVALUATOR/error_series.csv").exists()
    assert "FROZEN_EVALUATOR/MATCHED_TRAJECTORY.csv.gz" in result["files"]
    assert (target / "EVALUATION_RESULT.json").is_file()
    assert (target / "OUTPUT_SEAL.json").read_bytes() == seal_bytes
    assert rs.compact_archive(source, target, scratch_root=scratch, batch=1, retention=decision) == result
    with pytest.raises(RuntimeError, match="ARCHIVE_PLAN_CHANGED"):
        rs.compact_archive(source, target, scratch_root=scratch, batch=1,
            retention={**decision, "retain_error_series": True})


def existing_retention_fixture(tmp_path):
    scratch, source, _ = source_tree(tmp_path)
    row = dict(run_id="RUN_1", evaluator_contract="evaluator_contract_v3")
    write(source / "EVALUATION_RESULT.json", dict(row=row, metric=0.123))
    error = source / "FROZEN_EVALUATOR/error_series.csv"
    twin = error.with_suffix(".csv.gz")
    twin.write_bytes(gzip.compress(error.read_bytes(), mtime=0))
    seal = rs.read_json(source / "OUTPUT_SEAL.json")
    seal["files"]["EVALUATION_RESULT.json"] = digest(source / "EVALUATION_RESULT.json")
    seal["files"][twin.relative_to(source).as_posix()] = digest(twin)
    write(source / "OUTPUT_SEAL.json", seal)
    archive = tmp_path / "g"
    root = archive / "04_EVALUATION/RUN_1/v3"
    receipt = rs.compact_archive(source, root, scratch_root=scratch, batch=1)
    payload = rs.evaluation_archived(rs.read_json(root / "EVALUATION_RESULT.json"), receipt)
    record = root / "V3R_EVALUATION_RECORD.json"
    write(record, payload)
    evaluation_pin = dict(path=str(record), sha256=digest(record))
    reconciliation = archive / "00_CONTROL/RECONCILIATION_MANIFEST.json"
    write(reconciliation, dict(status="PASS_ARCHIVE_RECONCILIATION", reused_runs=[dict(run_id="RUN_1",
        evaluations=dict(v3=evaluation_pin))]))
    policy = archive / "00_CONTROL/RETENTION_POLICY.json"
    write(policy, dict(test_fixture=True))
    decision = dict(run_id="RUN_1", domain="CORE", case_id="D01_seed_01", retain_error_series=False,
        policy=dict(path=str(policy), sha256=digest(policy)))
    arguments = dict(archive=archive, control=archive / "00_CONTROL" / rs.CONTINUATION,
        decision=decision, reconciliation_pin=dict(path=str(reconciliation), sha256=digest(reconciliation)),
        evaluation_pin=evaluation_pin)
    return payload, root, arguments


def test_existing_retention_preserves_b2_pins_deduplicates_alias_and_reenters(tmp_path, monkeypatch):
    payload, root, args = existing_retention_fixture(tmp_path)
    preserved = {p: p.read_bytes() for p in root.iterdir() if p.is_file()}
    unlinks = []
    original = Path.unlink
    def record_unlink(path, *a, **kw):
        unlinks.append(path)
        return original(path, *a, **kw)
    monkeypatch.setattr(Path, "unlink", record_unlink)
    monkeypatch.setattr(rs.runtime, "run_native", lambda *a, **k: pytest.fail("native rerun"))
    monkeypatch.setattr(rs.runtime, "evaluate_native", lambda *a, **k: pytest.fail("evaluator rerun"))
    derived = rs.apply_existing_retention(payload, **args)
    assert unlinks == [root / "FROZEN_EVALUATOR/error_series.csv.gz"]
    assert {p: p.read_bytes() for p in preserved} == preserved
    assert {k: v for k, v in derived.items() if k != "archive_receipt"} == {
        k: v for k, v in payload.items() if k != "archive_receipt"}
    overlay = rs.read_json(derived["archive_receipt"])
    assert not any(rs.error_series_member(name) for name in overlay["files"])
    assert len([name for name in overlay["discarded_payloads"] if rs.error_series_member(name)]) == 2
    slot = Path(derived["archive_receipt"]).parent
    journal = slot / "RELEASE_JOURNAL.jsonl"
    prior = journal.read_bytes()
    assert len(prior.splitlines()) == 2
    assert rs.apply_existing_retention(payload, **args) == derived
    assert journal.read_bytes() == prior
    assert len(unlinks) == 1
    assert not list(slot.glob("RELEASE_INTENTS/*"))


@pytest.mark.parametrize("moment", ["before_unlink", "after_unlink", "after_done"])
def test_existing_retention_recovers_each_durable_deletion_window(tmp_path, monkeypatch, moment):
    payload, root, args = existing_retention_fixture(tmp_path)
    target = root / "FROZEN_EVALUATOR/error_series.csv.gz"
    original_unlink, original_append = Path.unlink, rs.ReleaseJournal.append
    def interrupt_unlink(path, *a, **kw):
        if path == target and moment == "before_unlink":
            raise SystemExit("kill after INTENT")
        value = original_unlink(path, *a, **kw)
        if path == target and moment == "after_unlink":
            raise SystemExit("kill after unlink")
        return value
    def interrupt_append(journal, name, event):
        value = original_append(journal, name, event)
        if event == "DONE" and moment == "after_done":
            raise SystemExit("kill after DONE")
        return value
    monkeypatch.setattr(Path, "unlink", interrupt_unlink)
    monkeypatch.setattr(rs.ReleaseJournal, "append", interrupt_append)
    with pytest.raises(SystemExit):
        rs.apply_existing_retention(payload, **args)
    monkeypatch.setattr(Path, "unlink", original_unlink)
    monkeypatch.setattr(rs.ReleaseJournal, "append", original_append)
    derived = rs.apply_existing_retention(payload, **args)
    assert not target.exists()
    complete = rs.read_json(Path(derived["archive_receipt"]).parent / "RETENTION_COMPLETE.json")
    assert complete["physical_files_deleted"] == 1
    assert complete["release_journal"]["records"] == 2


@pytest.mark.parametrize("problem", ["missing", "storage_hash", "decompressed_source_hash", "b2_incomplete"])
def test_existing_retention_fail_closed_before_any_delete(tmp_path, monkeypatch, problem):
    payload, root, args = existing_retention_fixture(tmp_path)
    target = root / "FROZEN_EVALUATOR/error_series.csv.gz"
    if problem == "missing":
        target.unlink()
    elif problem == "storage_hash":
        target.write_bytes(b"changed stored bytes")
    elif problem == "decompressed_source_hash":
        receipt = rs.read_json(root / "ARCHIVE_RECEIPT.json")
        receipt["files"]["FROZEN_EVALUATOR/error_series.csv"]["source_sha256"] = "f" * 64
        write(root / "ARCHIVE_RECEIPT.json", receipt)
    else:
        rec = Path(args["reconciliation_pin"]["path"])
        value = rs.read_json(rec)
        value["status"] = "IN_PROGRESS"
        write(rec, value)
        args["reconciliation_pin"]["sha256"] = digest(rec)
    monkeypatch.setattr(Path, "unlink", lambda *a, **k: pytest.fail("deletion after failed admission"))
    with pytest.raises(RuntimeError):
        rs.apply_existing_retention(payload, **args)
    assert not list(args["control"].rglob("RELEASE_JOURNAL.jsonl"))


def test_retention_kept_case_never_changes_existing_payload(tmp_path, monkeypatch):
    payload, root, args = existing_retention_fixture(tmp_path)
    args["decision"]["retain_error_series"] = True
    monkeypatch.setattr(Path, "unlink", lambda *a, **k: pytest.fail("kept case deletion"))
    assert rs.apply_existing_retention(payload, **args) is payload
    assert (root / "FROZEN_EVALUATOR/error_series.csv.gz").is_file()


@pytest.mark.parametrize("domain,case", [("CORE", "C00_clean_normal"), ("CORE", "D60_seed_00"),
    ("SEQUENCE", "C00_clean_normal"), ("ADDENDUM", "A1")])
def test_bad_direct_decision_cannot_omit_a_required_series(domain, case):
    with pytest.raises(RuntimeError, match="PROTECTED_CASE"):
        rs.validate_retention_decision(dict(domain=domain, case_id=case, run_id="r",
            retain_error_series=False, policy={"sha256": "policy"}))


def purge_prime_fixture(tmp_path, monkeypatch):
    archive = tmp_path / "g"
    audit = archive / "V3R_PURGE/PROTOCOL_V2_RETAINED"
    pins = [dict(path=f"/synthetic/frozen/{i}", sha256=f"{i:064x}") for i in range(16411)]
    index = dict(verification_pins=pins)
    write(audit / "PROTECTION_INDEX.json", index)
    write(archive / "V3R_PURGE/PROTECTION_INDEX.json", index)
    monkeypatch.setattr(rs, "PROTECTION_INDEX_SHA256", digest(audit / "PROTECTION_INDEX.json"))
    (audit / "PURGE_LEDGER.csv").write_bytes(b"synthetic zero candidate ledger\n")
    ledger = digest(audit / "PURGE_LEDGER.csv")
    receipt = audit / "P4_VERIFIER_RECEIPT_0001.json"
    write(receipt, dict(status="PASS", verification_complete=True, failed=0, verified=16411, total=16411,
        index_sha256=rs.PROTECTION_INDEX_SHA256, ledger_sha256=ledger,
        checks=[{**pin, "status": "PASS", "actual_sha256": pin["sha256"]} for pin in pins]))
    record = audit / "P4_VERIFIED.json"
    write(record, dict(status="PASS", ledger_sha256=ledger, receipt_path=str(receipt), receipt_sha256=digest(receipt)))
    write(audit / "PURGE_RESULT.json", dict(status="PASS_LEDGERED_PURGE_COMPLETE", files=0, no_op=True))
    events = [dict(action="VERIFY_EXIT", returncode=0, receipt=str(receipt)),
        dict(action="VERIFIED", record_path=str(record), record_sha256=digest(record)), dict(action="PURGE_COMPLETE")]
    (audit / "OPERATIONS.jsonl").write_text("".join(json.dumps(row) + "\n" for row in events))
    return archive, audit, dict(path=str(record), sha256=digest(record)), events


def test_purge_prime_requires_committed_current_16411_checks(tmp_path, monkeypatch):
    archive, audit, pin, events = purge_prime_fixture(tmp_path, monkeypatch)
    assert rs.purge_prime_admission(archive, pin)["verification_count"] == 16411
    (audit / "OPERATIONS.jsonl").write_text("".join(json.dumps(row) + "\n" for row in events if row["action"] != "VERIFIED"))
    with pytest.raises(RuntimeError, match="NOT_COMMITTED_COMPLETE"):
        rs.purge_prime_admission(archive, pin)


def test_purge_prime_rejects_claimed_count_with_missing_check(tmp_path, monkeypatch):
    archive, audit, pin, events = purge_prime_fixture(tmp_path, monkeypatch)
    receipt = audit / "P4_VERIFIER_RECEIPT_0001.json"
    value = rs.read_json(receipt)
    value["checks"].pop()
    write(receipt, value)
    record = rs.read_json(pin["path"])
    record["receipt_sha256"] = digest(receipt)
    write(Path(pin["path"]), record)
    pin["sha256"] = digest(Path(pin["path"]))
    events[1]["record_sha256"] = pin["sha256"]
    (audit / "OPERATIONS.jsonl").write_text("".join(json.dumps(row) + "\n" for row in events))
    with pytest.raises(RuntimeError, match="CHECK_COVERAGE"):
        rs.purge_prime_admission(archive, pin)


def test_capacity_key_numbers_appear_in_every_heartbeat(tmp_path):
    control, forecast, specs = capacity_fixture(tmp_path)
    _, capacity = rs.capacity_admission(control, digest(control / "CAPACITY_FORECAST.json"), "registry", specs)
    policy_before = (control / "RETENTION_POLICY.json").read_bytes()
    index_before = (control / "RETENTION_INDEX.csv").read_bytes()
    guard = rs.StorageGuard(tmp_path, tmp_path / "storage", sample=lambda: sample())
    heartbeat = rs.Heartbeat(control, guard, [], 1)
    heartbeat.capacity = capacity
    for phase in ("GATES", "MATRIX", "AGGREGATE"):
        heartbeat.phase = phase
        state = heartbeat.flush()
        assert state["capacity_forecast"] == heartbeat.capacity
        assert all(state["capacity_forecast"][key] == value for key, value in forecast.items())
        assert rs.read_json(control / "STATE.json")["capacity_forecast"] == capacity
        text = (heartbeat.control / "PROGRESS.txt").read_text()
        assert "baseline MATRIX+AGGREGATE bytes: allocated=166798532608 apparent=94713775850" in text
        assert "conditional MATRIX+AGGREGATE bytes: allocated=109706047488 apparent=39015222764" in text
        assert "native allocated=4979712.0 apparent=873611.451171875" in text
        assert "evaluator allocated=9833728.0 apparent=5835337.982421875" in text
        assert "at_forecast=186261962752 current=30000000000" in text
        assert digest(control / "CAPACITY_FORECAST.json") in text
    assert (control / "RETENTION_POLICY.json").read_bytes() == policy_before
    assert (control / "RETENTION_INDEX.csv").read_bytes() == index_before


def startup_fixture(tmp_path, monkeypatch):
    scratch = tmp_path / "LegSA-GINS-SCRATCH" / rs.STAGE
    archive = tmp_path / "g/clean/stages" / rs.STAGE
    archive.mkdir(parents=True)
    write(scratch / "00_PREREGISTRATION/EXECUTION_FREEZE.json", {})
    config = tmp_path / "local.yaml"
    config.write_text(rs.yaml.safe_dump(dict(paths=dict(code_root=str(tmp_path / "code"),
        clean_root=str(archive.parent.parent), protocol_v3_scratch=str(scratch)))))
    # Exercise the real constructor's root checks without accessing the real G:.
    real_path = rs.Path
    monkeypatch.setattr(rs, "Path", lambda value: tmp_path / "g" if str(value) == "/mnt/g" else real_path(value))
    argv = ["--local-config", str(config), "--contract", str(tmp_path / "contract.yaml"),
        "--science-freeze", "science", "--continuation-commit", "continuation",
        "--reconciliation", str(tmp_path / "reconciliation.json"), "--reconciliation-sha256", "reconciliation-pin",
        "--capacity-forecast-sha256", "forecast-pin", "--purge-prime-receipt", str(tmp_path / "p4.json"),
        "--purge-prime-sha256", "p4-pin"]
    monkeypatch.setattr(rs.ResumeContext, "matrix", lambda *a: pytest.fail("matrix called after startup stop"))
    monkeypatch.setattr(rs.ResumeContext, "finish_reports", lambda *a: pytest.fail("aggregate called after startup stop"))
    return scratch, archive, argv


def test_startup_pin_failure_before_heartbeat_persists_stop_before_status(tmp_path, monkeypatch):
    _, archive, argv = startup_fixture(tmp_path, monkeypatch)
    def bad_pin(*args):
        raise RuntimeError("HARD_STOP_V3R_SCIENCE_SOURCE_CHANGED: pinned source")
    monkeypatch.setattr(rs, "continuation_freeze", bad_pin)
    events = []
    real_persist, real_operational = rs.persist, rs.Heartbeat._replace_operational
    def persist(path, value):
        events.append(Path(path).name)
        return real_persist(path, value)
    def operational(path, payload):
        events.append(Path(path).name)
        return real_operational(path, payload)
    monkeypatch.setattr(rs, "persist", persist)
    monkeypatch.setattr(rs.Heartbeat, "_replace_operational", staticmethod(operational))
    with pytest.raises(RuntimeError, match="SCIENCE_SOURCE_CHANGED"):
        rs.main(argv)
    control = archive / "00_CONTROL"
    stop = rs.read_json(control / rs.CONTINUATION / "HARD_STOP.json")
    state = rs.read_json(control / "STATE.json")
    assert stop["automatic_retry"] is False and stop["phase"] == "GATES"
    assert state["status"] == "HARD_STOP" and state["phase"] == "GATES"
    assert state["latest_hard_stop"] == stop
    assert "SCIENCE_SOURCE_CHANGED" in (control / "PROGRESS.txt").read_text()
    assert events[:3] == ["HARD_STOP.json", "STATE.json", "PROGRESS.txt"]


def test_admission_failure_after_heartbeat_persists_stop_and_stops_thread(tmp_path, monkeypatch):
    scratch, archive, argv = startup_fixture(tmp_path, monkeypatch)
    contexts = []
    def partial_init(ctx, *args):
        ctx.archive, ctx.scratch = archive, scratch
        ctx.control = archive / "00_CONTROL" / rs.CONTINUATION
        ctx.storage_roots_validated = True
        ctx.guard = rs.StorageGuard(scratch, ctx.control / "STORAGE", sample=lambda: sample())
        ctx.progress = rs.Heartbeat(archive / "00_CONTROL", ctx.guard, [], 0)
        contexts.append(ctx)
        ctx.progress.start()
        ctx._verify_admissions()
    def admission_failure(ctx):
        raise RuntimeError("HARD_STOP_V3R_PROVIDER_ADMISSION_CHANGED")
    monkeypatch.setattr(rs.ResumeContext, "__init__", partial_init)
    monkeypatch.setattr(rs.ResumeContext, "_verify_admissions", admission_failure)
    with pytest.raises(RuntimeError, match="PROVIDER_ADMISSION_CHANGED"):
        rs.main(argv)
    assert not contexts[0].progress.thread.is_alive()
    stop = rs.read_json(contexts[0].control / "HARD_STOP.json")
    state = rs.read_json(archive / "00_CONTROL/STATE.json")
    assert state["status"] == "HARD_STOP" and state["latest_hard_stop"] == stop
    assert "PROVIDER_ADMISSION_CHANGED" in (archive / "00_CONTROL/PROGRESS.txt").read_text()


@pytest.mark.parametrize("original", [
    b'{"status":"HARD_STOP", "error":"original failed gate", "automatic_retry":false}\n', b'null\n', b'[]\n'])
def test_prior_startup_stop_rejects_reentry_without_calls_or_overwrite(tmp_path, monkeypatch, original):
    _, archive, argv = startup_fixture(tmp_path, monkeypatch)
    control = archive / "00_CONTROL"
    stop_path = control / rs.CONTINUATION / "HARD_STOP.json"
    stop_path.parent.mkdir(parents=True)
    stop_path.write_bytes(original)
    write(control / "STATE.json", dict(phase="MATRIX", status="ACTIVE", latest_hard_stop=None))
    monkeypatch.setattr(rs, "continuation_freeze", lambda *a: pytest.fail("freeze work on persisted stop"))
    monkeypatch.setattr(rs.runtime, "verify_pin", lambda *a, **kw: pytest.fail("pin work on persisted stop"))
    monkeypatch.setattr(rs.runtime, "run_native", lambda *a, **kw: pytest.fail("native on persisted stop"))
    monkeypatch.setattr(rs.runtime, "evaluate_native", lambda *a, **kw: pytest.fail("evaluator on persisted stop"))
    with pytest.raises(RuntimeError, match="PERSISTED_CONTINUATION_STOP"):
        rs.main(argv)
    assert stop_path.read_bytes() == original
    state = rs.read_json(control / "STATE.json")
    assert state["phase"] == "GATES" and state["status"] == "HARD_STOP"
    if original in (b'null\n', b'[]\n'):
        assert state["latest_hard_stop"]["error"] == "PERSISTED_HARD_STOP_INVALID_SCHEMA_PRESERVED"
        assert state["latest_hard_stop"]["original_sha256"] == hashlib.sha256(original).hexdigest()
    else:
        assert state["latest_hard_stop"]["error"] == "original failed gate"
    assert "PERSISTED_CONTINUATION_STOP" in state["current_failure"]


def test_b2_counts_are_seeded_before_first_heartbeat_without_retention_or_science(tmp_path, monkeypatch):
    ctx = rs.ResumeContext.__new__(rs.ResumeContext)
    ctx.archive, ctx.code_freeze = tmp_path / "g", "science"
    ctx.control = ctx.archive / "00_CONTROL" / rs.CONTINUATION
    ctx.reused, ctx.identity, ctx.specs = {}, {}, []
    natives, payloads = {}, {}
    for n in range(514):
        rid = f"r{n:04d}"
        native = dict(run_id=rid, code_commit="science", status="COMPLETED")
        natives[rid] = native
        root = ctx.archive / "B2" / rid
        write(root / "NATIVE.json", native)
        item = dict(run_id=rid, native_record=dict(path=str(root / "NATIVE.json"), sha256=digest(root / "NATIVE.json")), evaluations={})
        payloads[rid] = [dict(row=dict(run_id=rid, evaluator_contract="evaluator_contract_" + v)) for v in rs.VERSIONS]
        if n < 512:
            for version, payload in zip(rs.VERSIONS, payloads[rid]):
                path = root / (version + ".json")
                write(path, payload)
                item["evaluations"][version] = dict(path=str(path), sha256=digest(path))
        (ctx.reused if n < 512 else ctx.identity)[rid] = item
        ctx.specs.append(dict(run_id=rid, domain="CORE" if n < 512 else "SEQUENCE", method_id="F04"))
    ctx.guard = rs.StorageGuard(tmp_path / "scratch", ctx.control / "STORAGE", sample=lambda: sample())
    ctx.progress = rs.Heartbeat(ctx.archive / "00_CONTROL", ctx.guard, ctx.specs, 9, original_batches=8)
    ctx._load_reused = lambda *a: pytest.fail("seeding must not invoke reuse/archive loader")
    monkeypatch.setattr(rs, "apply_existing_retention", lambda *a, **k: pytest.fail("retention during progress seeding"))
    monkeypatch.setattr(rs.runtime, "run_native", lambda *a, **k: pytest.fail("native during progress seeding"))
    monkeypatch.setattr(rs.runtime, "evaluate_native", lambda *a, **k: pytest.fail("evaluation during progress seeding"))
    ctx._seed_admitted_progress()
    try:
        ctx.progress.start()
        first = rs.read_json(ctx.archive / "00_CONTROL/STATE.json")
    finally:
        ctx.progress.stop()
    assert first["progress"]["total_queue"] == dict(solver_done=514, solver_total=514,
        evaluator_done=1024, evaluator_total=1028)
    assert first["completed_batches"] == 8
    # A reentry may also have fully sealed continuation batches. Admit their
    # pinned terminals once, without counting in-progress or unchecked slots.
    batch = ctx.control / "BATCHES/BATCH_0001"
    ids = list(ctx.identity)
    write(batch / "RUN_RECORDS.json", [natives[rid] for rid in ids])
    write(batch / "EVALUATION_RECORDS.json", [p for rid in ids for p in payloads[rid]])
    write(batch / "BATCH_COMPLETE.json", dict(status="PASS_COMPACT_BATCH_COMPLETE", run_ids=ids,
        native_records=dict(path=str(batch / "RUN_RECORDS.json"), sha256=digest(batch / "RUN_RECORDS.json")),
        evaluation_records=dict(path=str(batch / "EVALUATION_RECORDS.json"), sha256=digest(batch / "EVALUATION_RECORDS.json"))))
    ctx._seed_admitted_progress()
    ctx._seed_admitted_progress()
    assert len(ctx.progress.native_ids) == 514 and len(ctx.progress.eval_ids) == 1028
    assert ctx.progress.completed == 9 and ctx.progress.completed_continuation_batches == {1}
