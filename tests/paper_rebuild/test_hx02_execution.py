"""HX-02 controller pieces: open audit, provenance, ledger replay, archive, evaluator children."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from legsa_gins.paper_rebuild.hext import hx02_evaluation_process, hx02_execution as ex, hx02_params_echo

REPO = Path(__file__).resolve().parents[2]
FORBIDDEN_FALSE = ("synthetic_data_used", "semisynthetic_data_used", "trace_used_online", "receiver_imu_as_body_imu",
                   "final_v23_output_solver_input", "LegSA_output_solver_input", "per_case_tuning",
                   "output_only_correction", "epoch_deleted_for_metric")


def _roots(tmp_path, contract=None):
    clean = tmp_path / "clean"
    stage = clean / "stages/CLEAN9_EXTERNAL_COMPARISON/HX02_FIVE_CATEGORY"
    for path in (clean, stage, tmp_path / "raw", tmp_path / "scratch"):
        path.mkdir(parents=True, exist_ok=True)
    return ex.Roots(code=REPO, clean=clean, raw=tmp_path / "raw", external=tmp_path / "external", stage=stage,
                    scratch=tmp_path / "scratch", paths_config=tmp_path / "local.yaml",
                    contract=contract or {"sequences": {"BY2": {"case": "C00"}}})


def test_run_ids_follow_the_registered_naming():
    assert ex.run_id("BY2", "EXT01") == "BY2__EXT01__LIT__C00__NA"
    assert ex.run_id("BY2H", "HARTLEY_S") == "BY2H__HARTLEY_S__S__CONTRACT_START__NA"
    assert ex.run_id("BY2O", "GINAV") == "BY2O__GINAV__NONE__FILE_START__NA"
    assert len({ex.run_id(s, m) for s in ex.SEQUENCES for m in ex.METHODS}) == 24


def test_provenance_carries_every_required_flag():
    seq = SimpleNamespace(data_mode="real_raw", raw_hash_lock="/c/01_RAW_HASH_LOCK/L.csv", clean_root="/c",
                          raw_hash_lock_sha256="ab" * 32)
    record = ex.provenance(seq, code_commit="c" * 40, old_runtime_input_count=0)
    assert all(record[key] is False for key in FORBIDDEN_FALSE)
    assert record["old_runtime_input_count"] == 0 and record["data_mode"] == "real_raw"
    assert record["code_commit"] == "c" * 40 and len(record["config_hash"]) == 64
    assert record["raw_hash_lock"]["path"] == "<CLEAN_ROOT>/01_RAW_HASH_LOCK/L.csv"


def test_native_open_audit_flags_reference_and_old_runtime_opens(tmp_path):
    roots = _roots(tmp_path)
    trace = tmp_path / "raw/fix/trace_vrtk2_x.csv"
    gnss1 = tmp_path / "raw/fix/gnss1-raw.csv"
    seq = SimpleNamespace(trace_path_evaluator_only=str(trace))
    lines = [
        f'101 openat(AT_FDCWD, "{gnss1}", O_RDONLY|O_CLOEXEC) = 3</x>',
        f'101 openat(AT_FDCWD, "{roots.clean}/01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv", O_RDONLY) = 4',
        f'101 openat(AT_FDCWD, "{roots.stage}/01_INPUT_PINS/INPUT_PINS.json", O_RDONLY) = 5',
        f'101 openat(AT_FDCWD, "{roots.clean}/stages/CLEAN4_X", O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_DIRECTORY) = 6',
        f'101 openat(AT_FDCWD, "{roots.clean}/stages/CLEAN4_X/missing.json", O_RDONLY) = -1 ENOENT (No such file)',
        '101 execve("/usr/bin/python3", ["python3"], 0x0 /* 1 vars */) = 0',
    ]
    log = tmp_path / "clean.strace"
    log.write_text("\n".join(lines) + "\n")
    audit = ex.audit_native_strace(log, roots, seq, [str(gnss1)])
    assert audit["reference_open_count"] == 0 and audit["old_runtime_input_count"] == 0
    assert audit["raw_paths_opened"] == [str(gnss1)] and audit["undeclared_raw_paths"] == []
    assert audit["executed_programs"] == ["/usr/bin/python3"]
    log.write_text("\n".join(lines + [
        f'102 openat(AT_FDCWD, "{trace}", O_RDONLY) = 7',
        f'102 openat(AT_FDCWD, "{roots.clean}/stages/CLEAN4_X/NAV.nav", O_RDONLY) = 8',
        f'102 openat(AT_FDCWD, "{tmp_path}/raw/x.bag", O_RDONLY) = 9']) + "\n")
    audit = ex.audit_native_strace(log, roots, seq, [str(gnss1)])
    assert audit["reference_open_count"] == 2
    assert audit["old_runtime_input_paths"] == [f"{roots.clean}/stages/CLEAN4_X/NAV.nav"]
    assert set(audit["undeclared_raw_paths"]) == {str(trace), f"{tmp_path}/raw/x.bag"}


def test_failure_classes():
    assert ex.classify({"environment_failure": True, "native_complete": True}) == "RUN_FAILED_ENVIRONMENT"
    assert ex.classify({"native_complete": True, "returncode": 0}) == "COMPLETED"
    assert ex.classify({"native_complete": True, "returncode": 2}) == "COMPLETED_ABNORMAL_EXIT"
    assert ex.classify({"native_complete": False, "returncode": 0}) == "NO_OUTPUT"
    assert ex.classify({"native_complete": False, "returncode": 2}) == "ABNORMAL_EXIT"
    assert ex.classify({"native_complete": False, "returncode": -9}) == "ABNORMAL_EXIT"


def test_ledger_replay_restores_state_and_counters(tmp_path):
    roots = _roots(tmp_path)
    control = ex.Control(roots)
    control.event("NATIVE_LAUNCH", run="R1", state={"status": "NATIVE_RUNNING"}, counters={"native_calls": 1})
    control.event("NATIVE_DONE", run="R1", state={"status": "NATIVE_COMPLETED"})
    control.event("EVALUATOR_LAUNCH", run="R1", counters={"evaluator_calls": 1})
    replayed = ex.Control(roots)
    assert replayed.status("R1") == "NATIVE_COMPLETED" and replayed.status("R2") == "PENDING"
    assert replayed.state["counters"]["native_calls"] == 1 and replayed.state["counters"]["evaluator_calls"] == 1
    assert replayed.state["counters"]["legsa_native_calls"] == 0 == replayed.state["counters"]["legsa_evaluator_calls"]
    assert (roots.control / "PROGRESS.txt").read_text().count("\n") == 3


def _run_dir(roots, name="BY2__EXT01__LIT__C00__NA"):
    run_dir = roots.scratch / "RUNS" / name
    (run_dir / "native" / "sub").mkdir(parents=True)
    (run_dir / "eval").mkdir()
    (run_dir / "native" / "a.txt").write_text("alpha")
    (run_dir / "native" / "sub" / "b.bin").write_bytes(b"\x00" * 1000)
    (run_dir / "DONE.json").write_text("{}")
    return run_dir


def test_archive_verifies_every_file_then_removes_scratch(tmp_path):
    roots = _roots(tmp_path)
    control = ex.Control(roots)
    run_dir = _run_dir(roots)
    manifest = ex.archive_run(control, roots, run_dir)
    destination = roots.stage / "RUNS" / run_dir.name
    assert not run_dir.exists() and manifest["file_count"] == 3
    assert json.loads((destination / "ARCHIVE_MANIFEST.json").read_text())["files"][0]["verified"] is True
    assert control.status(run_dir.name) == "ARCHIVED"


def test_interrupted_archive_is_completed_in_place_and_foreign_files_stop(tmp_path):
    roots = _roots(tmp_path)
    control = ex.Control(roots)
    run_dir = _run_dir(roots)
    destination = roots.stage / "RUNS" / run_dir.name
    (destination / "native").mkdir(parents=True)
    (destination / "native" / "a.txt").write_text("alpha")          # already copied, same hash
    (destination / "DONE.json").write_text("truncated")              # partial copy, differing hash
    manifest = ex.archive_run(control, roots, run_dir)
    assert manifest["file_count"] == 3 and (destination / "DONE.json").read_text() == "{}"
    run_dir = _run_dir(roots, "BY2__EXT02__LIT__C00__NA")
    stray = roots.stage / "RUNS" / run_dir.name / "stray.txt"
    stray.parent.mkdir(parents=True)
    stray.write_text("x")
    with pytest.raises(ex.HardStop, match="absent from the run directory"):
        ex.archive_run(control, roots, run_dir)
    assert run_dir.exists()


def test_partial_evaluation_is_set_aside_on_resume(tmp_path):
    roots = _roots(tmp_path)
    control = ex.Control(roots)
    run_dir = _run_dir(roots)
    (run_dir / "native" / "HX02_HEADING_TABLES").mkdir()
    (run_dir / "eval" / "CONVENTION_DIAGNOSTIC.json").write_text("{}")
    ex.set_aside_partial_evaluation(control, run_dir)
    assert not (run_dir / "native" / "HX02_HEADING_TABLES").exists() and not (run_dir / "DONE.json").exists()
    assert (run_dir / "eval").is_dir() and not any((run_dir / "eval").iterdir())
    moved = [p for p in run_dir.iterdir() if p.name.startswith("INTERRUPTED_EVALUATION_")]
    assert len(moved) == 1 and (moved[0] / "eval" / "CONVENTION_DIAGNOSTIC.json").is_file()


def test_input_pins_must_match_the_registered_digest(tmp_path):
    roots = _roots(tmp_path, contract={"sequences": {}})
    roots.pins.mkdir(parents=True)
    (roots.pins / "INPUT_PINS.json").write_text("{}")
    with pytest.raises(ex.HardStop):
        ex.load_pins(roots)
    registered = hashlib.sha256(b"{}").hexdigest()
    roots = _roots(tmp_path, contract={"sequences": {}, "input_pins_sha256": registered})
    assert ex.load_pins(roots) == {}


def test_parameter_echo_comparison_is_item_by_item():
    same = hx02_params_echo.compare({"a": [1, 2], "b": {"x": 1}}, {"b": {"x": 1}, "a": [1, 2]})
    assert same["all_equal"] and same["item_count"] == 2
    differ = hx02_params_echo.compare({"a": [1, 2]}, {"a": [1, 3], "c": 0})
    assert not differ["all_equal"] and differ["differing_items"] == ["a", "c"]


def _traced() -> bool:
    status = Path("/proc/self/status").read_text()
    return any(line.startswith("TracerPid:") and line.split()[1] != "0" for line in status.splitlines())


@pytest.mark.skipif(_traced(), reason="ptrace cannot nest: the child audit needs its own strace")
def test_registered_children_pass_their_open_audit(tmp_path):
    raw = tmp_path / "raw" / "fix"
    raw.mkdir(parents=True)
    trace = raw / "trace_vrtk2_synthetic.csv"
    base = 1_700_000_000.0
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["time", "lat", "lon", "height", "processed_lat", "processed_lon", "processed_height",
                     "yaw", "pitch", "roll"])
    for k in range(0, 300):
        writer.writerow([repr(base + 0.1 * k), "40", "116", "30", "40", "116", "30", "45.0", "0", "0"])
    trace.write_bytes(out.getvalue().encode())
    table = tmp_path / "scratch" / "HX02_HEADING_TABLE_X.csv"
    table.parent.mkdir(parents=True)
    with table.open("w", newline="") as handle:
        rows = csv.writer(handle, lineterminator="\n")
        rows.writerow(["epoch_index", "gps_week", "gps_tow_seconds", "time_unix_s", "valid", "body_yaw_deg"])
        for k in range(100):
            rows.writerow([k, 2408, 1.0 + 0.2 * k, repr(base + 1.0 + 0.2 * k), 1, "46.0"])
    common = dict(code_root=REPO, raw_root=tmp_path / "raw", clean_root=tmp_path / "clean")
    result = hx02_evaluation_process.run_child(
        "HEADING", {"method_id": "X", "sequence_id": "SYN", "base_time": base, "window": [2.0, 20.0],
                    "trace": str(trace), "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(),
                    "variants": [{"label": "X", "heading_table": str(table),
                                  "heading_table_sha256": hashlib.sha256(table.read_bytes()).hexdigest()}]},
        workdir=tmp_path / "eval" / "HEADING", trace=trace, **common)
    assert result["audit"]["passed"] and result["audit"]["trace_open_count"] == 1
    metrics = json.loads((Path(result["outdir"]) / "HEADING_METRICS.json").read_text())
    assert metrics["variants"]["X"]["valid"]["rmse_deg"] == pytest.approx(1.0)
    nav = tmp_path / "scratch" / "GINAV_NATIVE_NAV11.nav"
    nav.write_text("2408 66.0 40 116 30 0 0 0 0 0 0\n2408 67.0 40 116 30 0 0 0 0 0 0\n")
    coverage = hx02_evaluation_process.run_child(
        "COVERAGE", {"sequence_id": "SYN", "window": [66.0, 340.0], "nav": str(nav),
                     "nav_sha256": hashlib.sha256(nav.read_bytes()).hexdigest()},
        workdir=tmp_path / "eval" / "COVERAGE", trace=None, **common)
    assert coverage["audit"]["passed"] and coverage["audit"]["trace_open_count"] == 0
    with pytest.raises(hx02_evaluation_process.EvaluationProcessError, match="registered as reference-free"):
        hx02_evaluation_process.run_child(
            "HEADING", {"method_id": "X", "sequence_id": "SYN", "base_time": base, "window": [2.0, 20.0],
                        "trace": str(trace), "trace_sha256": hashlib.sha256(trace.read_bytes()).hexdigest(),
                        "variants": [{"label": "X", "heading_table": str(table),
                                      "heading_table_sha256": hashlib.sha256(table.read_bytes()).hexdigest()}]},
            workdir=tmp_path / "eval" / "HEADING_UNREGISTERED_READ", trace=None, **common)


def test_runner_terminal_status_is_read_from_the_native_stdout(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "native").mkdir(parents=True)
    assert ex.runner_terminal_status(run_dir) is None
    (run_dir / "native" / "NATIVE_stdout.log").write_text(
        'progress\n{"a": 1, "terminal_status": "BLOCKED_X"}\n{"terminal_status": "PASS_Y", "b": 2}\n')
    assert ex.runner_terminal_status(run_dir) == "PASS_Y"


def test_controller_self_audit_requires_its_log_and_stops_on_reference_opens(tmp_path, monkeypatch):
    roots = _roots(tmp_path)
    fake = SimpleNamespace(trace_path_evaluator_only=str(tmp_path / "raw/fix/trace_vrtk2_x.csv"))
    monkeypatch.setattr(ex.hx02_sequence, "load_sequence", lambda sequence, contract=None: fake)
    monkeypatch.delenv(ex.CONTROLLER_STRACE_ENV, raising=False)
    with pytest.raises(ex.HardStop, match="own openat audit"):
        ex.controller_self_audit(roots, "start")
    log = tmp_path / "controller.strace"
    log.write_text('openat(AT_FDCWD, "/x/INPUT_PINS.json", O_RDONLY) = 3\n'
                   'openat(AT_FDCWD, "/r/fix/\\346\\225\\260/gnss1-raw.csv", O_RDONLY) = 4\n')
    assert ex.controller_self_audit(roots, "start", str(log))["openat_lines"] == 2
    log.write_text(log.read_text() + f'openat(AT_FDCWD, "{fake.trace_path_evaluator_only}", O_RDONLY) = 5\n')
    with pytest.raises(ex.HardStop, match="controller process opened a reference"):
        ex.controller_self_audit(roots, "later", str(log))


def test_pair_event_updates_both_runs_in_one_ledger_line(tmp_path):
    roots = _roots(tmp_path)
    control = ex.Control(roots)
    control.event("NATIVE_DONE", run="S", state={"status": "NATIVE_COMPLETED"})
    control.event("NATIVE_DONE", run="LIT", state={"status": "NATIVE_COMPLETED"})
    control.event("EVALUATED_PAIR", runs_state={"S": {"status": "EVALUATED"}, "LIT": {"status": "EVALUATED"}})
    lines = (roots.control / "LEDGER.jsonl").read_text().splitlines()
    assert len(lines) == 3 and json.loads(lines[-1])["runs_state"] == {"S": {"status": "EVALUATED"},
                                                                         "LIT": {"status": "EVALUATED"}}
    replayed = ex.Control(roots)
    assert replayed.status("S") == replayed.status("LIT") == "EVALUATED"
