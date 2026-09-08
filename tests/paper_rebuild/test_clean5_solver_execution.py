"""Synthetic-only C-04 orchestration tests; no frozen executable or real data."""
import json
from hashlib import sha256
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest
import yaml

from legsa_gins.paper_rebuild.clean5_sequence import solver_runner as runner
from legsa_gins.paper_rebuild.clean5_sequence.runtime_config import METHODS, NATIVE_IDENTITY, PATH_ROLES, frozen_parameter_hash
from legsa_gins.paper_rebuild.clean5_sequence.solver_validation import COUNTER_SOURCES


def test_executable_hash_mismatch_refuses(tmp_path):
    binary = tmp_path / runner.EXECUTABLE_RELATIVE
    binary.parent.mkdir(parents=True)
    binary.write_text("synthetic-not-the-frozen-executable")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        runner.verify_executable(binary, tmp_path)


def test_executable_requires_original_absolute_path(tmp_path):
    with pytest.raises(RuntimeError, match="absolute path"):
        runner.verify_executable(Path("arbitrary-demo"), tmp_path)


def test_provider_hash_mismatch_refuses(tmp_path):
    data = tmp_path / "provider.csv"
    data.write_text("synthetic fixture\n")
    artifacts = {role: {"path": str(data), "sha256": "0" * 64}
                 for role in set(PATH_ROLES.values()) | {"source_quality_metadata"}}
    with pytest.raises(RuntimeError, match="Provider .* SHA-256 mismatch"):
        runner.verify_provider_files(tmp_path, {"artifacts": artifacts})


@pytest.mark.parametrize("path,flags,expected", [
    ("raw/trace_fixture.csv", "O_RDONLY", "trace"),
    ("elsewhere/fixture.bag", "O_RDONLY", "bag"),
    ("elsewhere/fixture.fpl", "O_RDONLY", "fpl"),
    ("raw/observation.csv", "O_RDONLY", "raw"),
    ("elsewhere/escape.txt", "O_WRONLY|O_CREAT|O_TRUNC", "write"),
])
def test_solver_strace_rejects_forbidden_opens(tmp_path, path, flags, expected):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    raw = tmp_path / "raw"
    raw.mkdir()
    log = run_dir / "audit.strace"
    log.write_text(f'123 openat(AT_FDCWD, "{tmp_path / path}", {flags}) = 3\n')
    audit = runner.audit_solver_openat(log, cwd=tmp_path, raw_root=raw, run_dir=run_dir)
    assert not audit["pass"]
    if expected in ("trace", "bag", "fpl"):
        assert audit["forbidden_open_counts"][expected] == 1
    elif expected == "raw":
        assert audit["raw_open_count"] == 1
    else:
        assert audit["outside_run_write_open_count"] == 1


def test_solver_strace_allows_run_owned_writes(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    log = run_dir / "audit.strace"
    log.write_text(f'123 openat(AT_FDCWD, "{run_dir / "out.nav"}", O_WRONLY|O_CREAT|O_TRUNC, 0666) = 3\n')
    audit = runner.audit_solver_openat(log, cwd=tmp_path, raw_root=tmp_path / "raw", run_dir=run_dir)
    assert audit["pass"] and audit["write_open_count"] == 1


def test_solver_strace_empty_is_not_zero_read_proof(tmp_path):
    log = tmp_path / "empty.strace"
    log.write_text("")
    audit = runner.audit_solver_openat(log, cwd=tmp_path, raw_root=tmp_path / "raw", run_dir=tmp_path)
    assert not audit["pass"]


@pytest.mark.parametrize("phase", ["pre_run", "post_run"])
def test_raw_checkpoint_hashes_22_synthetic_files_with_run_phase(tmp_path, monkeypatch, phase):
    raw, audit = tmp_path / "raw", tmp_path / "audit"
    raw.mkdir()
    audit.mkdir()
    names = ["trace_fixture.csv", "fixture.bag", "fixture.fpl"] + [f"raw_{i}.csv" for i in range(19)]
    rows = {}
    for name in names:
        data = ("synthetic hash-only fixture " + name).encode()
        (raw / name).write_bytes(data)
        rows[name] = {"sha256": sha256(data).hexdigest(), "size_bytes": str(len(data))}
    lock = {"rows": rows, "sha256": "synthetic-lock"}
    monkeypatch.setattr(runner, "selected_lock", lambda *_: lock)
    checkpoint = runner.raw_checkpoint_worker(SimpleNamespace(raw_root=raw), SimpleNamespace(dataset_id="BY2H"), phase, audit)
    assert checkpoint["audit_phase"] == phase
    assert checkpoint["expected"] == checkpoint["verified"] == 22
    assert checkpoint["trace_read_role"] == "outer_raw_integrity_hash_audit_only"
    assert checkpoint["verified_hashes"] == {key: row["sha256"] for key, row in rows.items()}
    assert (audit / f"{phase}_CHECKPOINT.json").is_file()


def _counter_fixture(profile, count):
    values = {source: 0 for source in COUNTER_SOURCES.values()}
    values["position_update_count"] = values["receiver_velocity_update_count"] = count
    if profile != "single_antenna_EKF":
        for key in ("dual_yaw_attempt_count", "yaw_NORMAL", "dual_yaw_accepted_count"):
            values[key] = count
    if profile in ("AB1011", "AB1111"):
        for key in ("raw_doppler_update_count", "go2_roll_pitch_update_count", "go2_horizontal_velocity_update_count"):
            values[key] = count
    if profile == "AB1111":
        values["source_aware_evaluation_count"] = count
        values["source_aware_weight_changed_count"] = 1
    return values


@pytest.mark.skipif(shutil.which("strace") is None, reason="strace required for synthetic fake-process integration")
def test_failed_fake_executable_does_not_block_following_profiles(tmp_path, monkeypatch):
    raw, code, stage = (tmp_path / name for name in ("raw", "code", "stage"))
    for root in (raw, code, stage / "04_SOLVER_RUNS"):
        root.mkdir(parents=True)
    fake = tmp_path / "fake-solver"
    gnss_provider = stage / "gnss.txt"
    gnss_provider.write_text("".join(" ".join(map(str, [t]+[0]*14))+"\n" for t in (1,2,3)))
    imu_provider = stage / "imu.txt"
    imu_provider.write_text("".join(" ".join(map(str, [t]+[0]*6))+"\n" for t in (0,1,2,3,4)))
    counter_map = {profile: _counter_fixture(profile, 3) for profile in METHODS.values()}
    fake.write_text("#!/usr/bin/python3\nimport json,sys,yaml\nfrom pathlib import Path\n"
                    "cfg=yaml.safe_load(Path(sys.argv[sys.argv.index('--config')+1]).read_text())\n"
                    "root=Path(cfg['outputpath'])\n"
                    "if cfg['algorithm_id']=='basic_dual_yaw_EKF':\n"
                    " print('synthetic failure after F01',file=sys.stderr)\n sys.exit(42)\n"
                    f"counters={counter_map!r}\n"
                    "(root/'RUN_MANIFEST.json').write_text(json.dumps(counters[cfg['algorithm_id']]))\n"
                    "(root/'PORT_INPUT_TIMELINE_SNAPSHOT.json').write_text(json.dumps(dict(config_starttime=0.0,config_endtime=4.0,effective_starttime=0.0,effective_endtime=3.0,first_imu_time=0.0,last_imu_time=4.0,first_gnss_time=1.0,last_gnss_time=3.0,gnss_rows_after_start_before_end=3,gnss_rows_in_overlap=3,gnss_row_count=3,overlap_start=0.0,overlap_end=3.0,trace_solver_input=False,final_v23_output_solver_input=False,paper_performance_claim=False)))\n"
                    "nav=''.join(' '.join(map(str,[t]+[0]*9))+'\\n' for t in [1,2,3])\n"
                    "(root/'KF_GINS_Navresult.nav').write_text(nav)\n"
                    "(root/'KF_GINS_STD.txt').write_text(nav)\n"
                    "print(cfg['run_id'])\n")
    fake.chmod(0o755)
    configurations = {}
    for method, profile in METHODS.items():
        text = yaml.safe_dump({**NATIVE_IDENTITY, "algorithm_id": profile,
                               "run_id": f"CLEAN5_BY2H_{method}_{profile}",
                               "outputpath": str(stage / "old"), "starttime": 0, "endtime": 4,
                               "gnsspath": str(gnss_provider), "imupath": str(imu_provider)})
        configurations[method] = {"text": text, "profile": {"frozen_parameter_hash": frozen_parameter_hash(text)},
                                  "identity": {"path": "synthetic-config", "sha256": "synthetic"}}
    prepared = {"stage": stage, "configurations": configurations, "provider_checks": {},
                "frozen_metadata_checks": {"02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json": {"sha256": "synthetic"}},
                "provider_manifest": {"raw_source_hashes": {}},
                "contract": {"window_contract": {"t_start": 0, "t_end": 4}}}
    state = {"code_freeze_commit": "synthetic-test-only"}
    monkeypatch.setattr(runner, "execution_state", lambda *_: state)
    # Native-manifest semantics are independently exercised by the validation tests.
    monkeypatch.setattr(runner, "validate_clean5_manifest", lambda *_: {})
    registry = SimpleNamespace(code_root=code, raw_root=raw)
    sequence = SimpleNamespace(dataset_id="BY2H", stage_id="SYNTHETIC_TEST_ONLY", data_mode="synthetic_test")
    records = runner.run_profiles(registry=registry, sequence=sequence, prepared=prepared,
                                  executable={"path": str(fake), "sha256": "synthetic"}, state=state)
    assert [row["method_id"] for row in records] == list(METHODS)
    assert [row["terminal_status"] for row in records] == ["COMPLETED", "technical_failure", "COMPLETED", "COMPLETED", "COMPLETED"]
    assert records[1]["exit_code"] == 42
    assert "synthetic failure" in records[1]["stderr_tail"]
    assert records[1]["nav_rows"] is None and records[1]["counters"] == {}
    assert records[2]["counters"]["position_update_count"] == 3
    assert all(row["strace_audit"]["pass"] for row in records)
    assert all(row["native_config_run_id"] == "CLEAN5_" + row["run_id"] for row in records)
    assert all((Path(row["run_dir"]) / "CLEAN5_FORMAL_RUN_MANIFEST.json").is_file() for row in records)
