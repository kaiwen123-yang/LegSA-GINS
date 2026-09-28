"""Synthetic C-04 contracts and fake executables; no real sequence execution."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from legsa_gins.paper_rebuild.clean5_sequence import runtime_config as rc
from legsa_gins.paper_rebuild.clean5_sequence import solver_runner as runner
from legsa_gins.paper_rebuild.clean5_sequence import solver_seal as seal
from legsa_gins.paper_rebuild.clean5_sequence import solver_validation as validation
from legsa_gins.paper_rebuild.manifest import sha256_file
from legsa_gins.paper_rebuild.subprocess_guard import run_process_group


def native_counters(profile, n=3, receiver=None):
    result = {source: 0 for source in validation.COUNTER_SOURCES.values()}
    result["position_update_count"] = n
    result["receiver_velocity_update_count"] = (0 if profile == "basic_dual_yaw_EKF" else n) if receiver is None else receiver
    if profile != "single_antenna_EKF":
        result.update(dual_yaw_attempt_count=n, dual_yaw_accepted_count=n, yaw_NORMAL=n)
    if profile in {"AB1011", "AB1111"}:
        result.update(raw_doppler_update_count=1, go2_roll_pitch_update_count=2,
                      go2_horizontal_velocity_update_count=2)
    if profile == "AB1111":
        result.update(source_aware_evaluation_count=8, source_aware_weight_changed_count=5)
    return result


def synthetic_config(profile="AB0000"):
    result = {**rc.NATIVE_IDENTITY, "algorithm_id": profile, "run_id": "synthetic_native_id",
        "outputpath": "/synthetic/old", "starttime": 1, "endtime": 3, "initpos": [0, 0, 0],
        "initatt": [0, 0, 0], "gain": 0.1, "imupath": "/synthetic/imu", "gnsspath": "/synthetic/gnss",
        "raw_doppler_factor_path": "/synthetic/rd", "go2_attitude_prior_path": "/synthetic/rp",
        "go2_horizontal_velocity_prior_path": "/synthetic/hv", "enable_dual_yaw": profile != "single_antenna_EKF",
        "enable_receiver_velocity": profile != "basic_dual_yaw_EKF", "enable_raw_doppler": profile in {"AB1011", "AB1111"},
        "enable_source_aware": profile == "AB1111", "enable_go2_roll_pitch_prior": profile in {"AB1011", "AB1111"},
        "enable_go2_horizontal_velocity_prior": profile in {"AB1011", "AB1111"},
        "raw_doppler_backend_source_files": ["fixture/gnss1.csv"],
        "raw_doppler_backend_source_hashes": {"fixture/gnss1.csv": "a" * 64},
        **{key: "a" * 64 for key in rc.BACKEND_PROVENANCE_KEYS if not key.startswith("raw_doppler_backend_source_")}}
    return result


def native_manifest(config):
    result = {key: config[key] for key in (*rc.NATIVE_IDENTITY, "algorithm_id", "run_id")}
    result.update(clean_final_v23_parity_mode=True, clean1_formal_mode=True,
                  phase=config["stage_id"], port_role="clean2r2a_formal_clean_ablation_solver")
    result.update({key: False for key in validation.FORBIDDEN_FLAGS})
    result.update({key: 0 for key in validation.ZERO_INPUT_COUNTS})
    result.update({native: config[key] for key, native in validation.CONFIG_FLAG_TO_MANIFEST.items()})
    result.update(actual_solver_input_paths={"propagation_imu": config["imupath"],
        "gnss_position_receiver_velocity_dual_yaw": config["gnsspath"]},
        actual_solver_input_roles={"propagation_imu": "source_backed_propagation",
        "gnss_position_receiver_velocity_dual_yaw": "validity_gated_measurements"})
    for flag, role, path, purpose in (
        ("enable_raw_doppler", "raw_doppler_velocity", "raw_doppler_factor_path", "source_backed_auxiliary_velocity"),
        ("enable_go2_roll_pitch_prior", "go2_roll_pitch_weak_prior", "go2_attitude_prior_path", "weak_prior_not_truth"),
        ("enable_go2_horizontal_velocity_prior", "go2_horizontal_velocity_weak_prior", "go2_horizontal_velocity_prior_path", "horizontal_weak_prior_not_truth"),
    ):
        if config[flag]:
            result["actual_solver_input_paths"][role] = config[path]
            result["actual_solver_input_roles"][role] = purpose
    for key in rc.BACKEND_PROVENANCE_KEYS:
        result[key] = validation.native_loader_string(config, key)
    result["raw_doppler_backend_lineage_proven"] = config["enable_raw_doppler"]
    return result


@pytest.mark.parametrize("profile", rc.METHODS.values())
def test_five_profile_counter_rules(profile):
    counts = native_counters(profile)
    assert validation.validate_profile_counters(profile, counts, 3)["position_update_count"] == 3
    counts["position_update_count"] = 2
    with pytest.raises(validation.CounterMismatch, match="position_update") as failure:
        validation.validate_profile_counters(profile, counts, 3)
    assert failure.value.counters["position_update_count"] == 2


@pytest.mark.parametrize("key,value", [("raw_doppler_update_count", 1), ("source_aware_evaluation_count", 1),
    ("source_aware_weight_changed_count", 1), ("go2_roll_pitch_update_count", 1),
    ("go2_horizontal_velocity_update_count", 1), ("nine_factor_fgo_update_count", 1),
    ("multi_state_qm_update_count", 1), ("qa_fallback_count", 1), ("contact_fk_update_count", 1)])
def test_disabled_and_forbidden_counters_rejected(key, value):
    counts = native_counters("AB0000")
    counts[key] = value
    with pytest.raises(validation.CounterMismatch):
        validation.validate_profile_counters("AB0000", counts, 3)


@pytest.mark.parametrize("bad", [True, 3.0, 3.7, "3", -1, None])
def test_counter_requires_present_nonnegative_integer(bad):
    counts = native_counters("AB0000")
    counts["position_update_count"] = bad
    with pytest.raises(validation.CounterMismatch):
        validation.validate_profile_counters("AB0000", counts, 3)


def test_missing_counter_rejected_instead_of_zero_default():
    counts = native_counters("AB0000")
    del counts["contact_fk_update_count"]
    with pytest.raises(validation.CounterMismatch, match="contact_fk_update_count"):
        validation.validate_profile_counters("AB0000", counts, 3)


@pytest.mark.parametrize("key", ["raw_doppler_update_count", "source_aware_evaluation_count",
    "source_aware_weight_changed_count", "go2_roll_pitch_update_count", "go2_horizontal_velocity_update_count"])
def test_full_requires_all_five_positive(key):
    counts = native_counters("AB1111")
    counts[key] = 0
    with pytest.raises(validation.CounterMismatch):
        validation.validate_profile_counters("AB1111", counts, 3)


def test_f02_receiver_gate_derived_from_frozen_features():
    counts = native_counters("basic_dual_yaw_EKF", receiver=0)
    assert validation.validate_profile_counters("basic_dual_yaw_EKF", counts, 3)
    counts["receiver_velocity_update_count"] = 3
    with pytest.raises(validation.CounterMismatch, match="receiver_velocity_update_count != 0"):
        validation.validate_profile_counters("basic_dual_yaw_EKF", counts, 3)
    counts["receiver_velocity_update_count"] = 0
    counts.update(yaw_NORMAL=2, yaw_DOWNWEIGHT=1)
    with pytest.raises(validation.CounterMismatch, match="F02 downweight"):
        validation.validate_profile_counters("basic_dual_yaw_EKF", counts, 3)


def test_dual_yaw_closures_and_duplicate_counter():
    counts = native_counters("AB0000")
    counts["dual_yaw_accepted_count"] = 2
    with pytest.raises(validation.CounterMismatch, match="accepted count"):
        validation.validate_profile_counters("AB0000", counts, 3)
    counts = native_counters("AB0000")
    counts["yaw_update_count"] = 2
    with pytest.raises(validation.CounterMismatch, match="duplicate counter"):
        validation.validate_profile_counters("AB0000", counts, 3)


def test_output_binding_changes_only_outputpath(tmp_path):
    original = yaml.safe_dump(synthetic_config())
    expected = rc.frozen_parameter_hash(original)
    bound, hashes = validation.bind_output_config(original, tmp_path, expected)
    validation.validate_outputpath_only(original, bound)
    assert yaml.safe_load(bound)["outputpath"] == str(tmp_path)
    assert hashes["frozen_parameter_hash"] == expected
    assert hashes["scientific_runtime_config_hash"] == rc.scientific_runtime_config_hash(original)
    with pytest.raises(rc.RuntimeConfigError):
        validation.bind_output_config(original, tmp_path, "0" * 64)


@pytest.mark.parametrize("change", ["gain: 0.2", "gain: true", "new_key: 1"])
def test_outputpath_other_key_changes_fail(change):
    before = "outputpath: /fixture/old\ngain: 0.1\n"
    after = "outputpath: /fixture/new\n" + change + "\n"
    with pytest.raises(rc.RuntimeConfigError):
        validation.validate_outputpath_only(before, after)


def test_outputpath_duplicate_key_rejected(tmp_path):
    text = "outputpath: /fixture/old\ngain: 0.1\ngain: 0.2\n"
    with pytest.raises(rc.RuntimeConfigError, match="duplicate"):
        validation.bind_output_config(text, tmp_path, rc.frozen_parameter_hash(text))


@pytest.mark.parametrize("profile", rc.METHODS.values())
def test_native_manifest_matches_frozen_flags_and_ledger(profile):
    config = synthetic_config(profile)
    manifest = native_manifest(config)
    contract = {"identity": {"dataset_id": "BY2H"}}
    assert validation.validate_clean5_manifest(manifest, config, contract)["passed"]
    manifest["trace_used_online"] = True
    with pytest.raises(validation.SolverValidationError, match="trace_used_online"):
        validation.validate_clean5_manifest(manifest, config, contract)


def test_native_manifest_no_extra_input_and_no_boolean_zero_coercion():
    config = synthetic_config()
    manifest = native_manifest(config)
    contract = {"identity": {"dataset_id": "BY2H"}}
    manifest["old_runtime_input_count"] = False
    with pytest.raises(validation.SolverValidationError):
        validation.validate_clean5_manifest(manifest, config, contract)
    manifest = native_manifest(config)
    manifest["actual_solver_input_paths"]["trace"] = "/fixture/trace.csv"
    with pytest.raises(validation.SolverValidationError, match="ledger"):
        validation.validate_clean5_manifest(manifest, config, contract)


def write_outputs(root, times=(1.25, 2.25)):
    root.mkdir(parents=True, exist_ok=True)
    (root / "KF_GINS_Navresult.nav").write_text("".join("0 " + str(time) + " 0" * 9 + "\n" for time in times))
    (root / "KF_GINS_STD.txt").write_text("".join(str(time) + " 0" * 9 + "\n" for time in times))
    (root / "RUN_MANIFEST.json").write_text("{}\n")
    (root / "CLEAN5_RUNTIME_CONFIG.yaml").write_text("fixture: synthetic\n")
    (root / "CLEAN5_FORMAL_RUN_MANIFEST.json").write_text('{"synthetic_fixture": true}\n')


def test_output_structure_checks_finite_monotonic_window_and_std(tmp_path):
    contract = {"window_contract": {"t_start": 1, "t_end": 3}}
    write_outputs(tmp_path)
    result = validation.validate_run_outputs(tmp_path, contract)
    assert (result["nav_rows"], result["nav_time_start"], result["nav_time_end"]) == (2, 1.25, 2.25)
    write_outputs(tmp_path, (1.25, 1.25))
    with pytest.raises(validation.AlgorithmFailure, match="strictly increasing"):
        validation.validate_run_outputs(tmp_path, contract)
    write_outputs(tmp_path, (0.5, 2.25))
    with pytest.raises(validation.AlgorithmFailure, match="outside"):
        validation.validate_run_outputs(tmp_path, contract)
    write_outputs(tmp_path)
    (tmp_path / "KF_GINS_STD.txt").write_text("1.25 " + "nan " * 9)
    with pytest.raises(validation.AlgorithmFailure, match="non-finite"):
        validation.validate_run_outputs(tmp_path, contract)


def test_wrong_executable_hash_refused_before_execution(tmp_path):
    executable = tmp_path / runner.EXECUTABLE_RELATIVE
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o755)
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        runner.verify_executable(executable, tmp_path)


def test_provider_hash_mismatch_rejected(tmp_path):
    artifacts = {}
    for role in set(rc.PATH_ROLES.values()) | {"source_quality_metadata"}:
        path = tmp_path / role
        path.write_text("synthetic fixture\n")
        artifacts[role] = {"path": str(path), "sha256": sha256_file(path)}
    bad = next(iter(artifacts.values()))
    Path(bad["path"]).write_text("mutated fixture\n")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        runner.verify_provider_files(tmp_path, {"artifacts": artifacts})


@pytest.fixture
def seal_fixture(tmp_path):
    records, audits = [], []
    for method, profile in rc.METHODS.items():
        run_id = f"BY2H_{method}_{profile}"
        root = tmp_path / "04_SOLVER_RUNS" / run_id
        write_outputs(root)
        records.append({"run_id": run_id, "run_dir": str(root), "method_id": method,
            "effective_profile": profile, "terminal_status": "COMPLETED", "config_hash": "a" * 64,
            "scientific_runtime_config_hash": "b" * 64, "frozen_parameter_hash": "c" * 64,
            "exit_code": 0, "runtime_seconds": 0.01, "nav_rows": 2, "nav_time_start": 1.25,
            "nav_time_end": 2.25, "counters": native_counters(profile)})
        audits.append({"run_id": run_id, **{key: 0 for key in seal.AUDIT_FIELDS}})
    metadata = {"dataset_id": "BY2H", "data_mode": "real_by2h_raw", "code_freeze_commit": "d" * 40,
        "execution_worktree": str(tmp_path / "synthetic_code"), "executable_sha256": "e" * 64,
        "provider_hashes": {"synthetic_provider": "f" * 64}}
    return tmp_path, records, metadata, audits


def test_seal_headers_aliases_and_missing_file_failure(seal_fixture):
    stage, records, metadata, audits = seal_fixture
    result = seal.seal_outputs(stage, records, metadata, audits)
    assert seal.validate_output_seal(result["output_seal_path"])["passed"]
    with Path(result["unique_registry_path"]).open(newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames[:len(seal.UNIQUE_FIELDS)]) == seal.UNIQUE_FIELDS
        assert len(list(reader)) == 5
    with Path(result["logical_registry_path"]).open(newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames[:len(seal.LOGICAL_FIELDS)]) == seal.LOGICAL_FIELDS
        rows = list(reader)
    assert len(rows) == 7 and {row["method_id"] for row in rows} == {"F01", "F02", "F03", "A04", "F04", "A01", "A02"}
    assert all(row["seed_index"] == "" and row["degradation_parameters_json"] == "{}" for row in rows)
    (Path(records[0]["run_dir"]) / "KF_GINS_Navresult.nav").unlink()
    with pytest.raises(seal.SealValidationError, match="missing"):
        seal.validate_output_seal(result["output_seal_path"])


def test_seal_refuses_missing_completed_output(seal_fixture):
    stage, records, metadata, audits = seal_fixture
    (Path(records[0]["run_dir"]) / "KF_GINS_STD.txt").unlink()
    with pytest.raises(seal.SealValidationError, match="missing"):
        seal.seal_outputs(stage, records, metadata, audits)


def test_partial_seal_preserves_failed_logs_and_unknown_audit(seal_fixture):
    stage, records, metadata, audits = seal_fixture
    failed = Path(records[0]["run_dir"])
    (failed / "KF_GINS_STD.txt").unlink()
    (failed / "stderr.log").write_text("synthetic technical failure\n")
    records[0]["terminal_status"] = "technical_failure"
    audits[0]["trace_open_count"] = None
    result = seal.seal_outputs(stage, records, metadata, audits)
    payload = json.loads(Path(result["output_seal_path"]).read_text())
    assert payload["audits_passed"] is False and payload["trace_reads_before_seal"] is None
    assert any(row["relative_path"].endswith("stderr.log") for row in payload["files"])


def test_seal_detects_modified_file(seal_fixture):
    result = seal.seal_outputs(*seal_fixture)
    root = Path(seal_fixture[1][0]["run_dir"])
    (root / "KF_GINS_STD.txt").write_text("changed\n")
    with pytest.raises(seal.SealValidationError, match="changed"):
        seal.validate_output_seal(result["output_seal_path"])


def test_occlusion_values_copied_from_hash_locked_record(tmp_path):
    payload = {"main_window": {"t0": 3369.943066596985, "t1": 3411.951585292816},
               "secondary_runs": [{"t0": 3495.939144849777, "t1": 3508.9415624141693}]}
    path = tmp_path / "OCCLUSION_WINDOW.json"
    path.write_text(json.dumps(payload))
    metadata = {"dataset_id": "BY2O", "occlusion_window_path": str(path),
                "occlusion_window_sha256": sha256_file(path)}
    params, _ = seal._degradation(metadata)
    assert params == {"start_s": payload["main_window"]["t0"], "end_s": payload["main_window"]["t1"],
        "source": "pre_registered_input_side_gnss2_fix_type", "secondary_runs": [[3495.939144849777, 3508.9415624141693]]}
    path.write_text(json.dumps({"main_window": {"t0": 0, "t1": 1}, "secondary_runs": []}))
    with pytest.raises(seal.SealValidationError, match="SHA256"):
        seal._degradation(metadata)


def test_failure_run_continues_all_five_with_fake_executable(tmp_path, monkeypatch):
    fixture_manifests = {}
    configs = {}
    gnss_provider = tmp_path / "synthetic_gnss15.txt"
    gnss_provider.write_text("".join(str(time) + " 0" * 14 + "\n" for time in (1.1, 2.0, 2.9)))
    imu_provider = tmp_path / "synthetic_imu7.txt"
    imu_provider.write_text("".join(str(time) + " 0" * 6 + "\n" for time in (0.5, 1.0, 1.25, 2.25, 3.5)))
    timeline = {"first_imu_time": 0.5, "last_imu_time": 3.5, "imu_row_count": 5,
        "first_gnss_time": 1.1, "last_gnss_time": 2.9, "gnss_row_count": 3,
        "config_starttime": 1.0, "config_endtime": 3.0,
        "effective_starttime": 1.0, "effective_endtime": 2.9,
        "overlap_start": 1.0, "overlap_end": 2.9,
        "gnss_rows_in_overlap": 3, "gnss_rows_after_start_before_end": 3,
        "trace_solver_input": False, "final_v23_output_solver_input": False, "paper_performance_claim": False}
    for method, profile in rc.METHODS.items():
        config = synthetic_config(profile)
        config["gnsspath"] = str(gnss_provider)
        config["imupath"] = str(imu_provider)
        config["run_id"] = "synthetic_native_" + method
        text = "\n".join(key + ": " + json.dumps(value, ensure_ascii=False) for key, value in config.items()) + "\n"
        fixture_manifests[profile] = {**native_manifest(config), **native_counters(profile)}
        configs[method] = {"text": text, "profile": {"frozen_parameter_hash": rc.frozen_parameter_hash(text)},
            "identity": {"path": str(tmp_path / (method + ".yaml")), "sha256": "a" * 64}}
    executable = tmp_path / "synthetic_solver.py"
    executable.write_text(
        "import json,sys,pathlib,yaml\n"
        "config=yaml.safe_load(pathlib.Path(sys.argv[sys.argv.index('--config')+1]).read_text())\n"
        "root=pathlib.Path(config['outputpath'])\n"
        "profile=config['algorithm_id']\n"
        "print('synthetic fixture only')\n"
        "if profile=='single_antenna_EKF':\n"
        " print('fixture failure',file=sys.stderr)\n"
        " sys.exit(7)\n"
        "(root/'KF_GINS_Navresult.nav').write_text('0 1.25'+' 0'*9+'\\n0 2.25'+' 0'*9+'\\n')\n"
        "(root/'KF_GINS_STD.txt').write_text('1.25'+' 0'*9+'\\n2.25'+' 0'*9+'\\n')\n"
        "manifests=" + repr(fixture_manifests) + "\n"
        "(root/'RUN_MANIFEST.json').write_text(json.dumps(manifests[profile]))\n"
        "timeline=" + repr(timeline) + "\n"
        "(root/'PORT_INPUT_TIMELINE_SNAPSHOT.json').write_text(json.dumps(timeline))\n")
    state = {"code_freeze_commit": "b" * 40, "execution_worktree": str(tmp_path)}
    monkeypatch.setattr(runner, "execution_state", lambda *args: state)
    monkeypatch.setattr(runner, "EXPECTED_GNSS_ROWS", {"BY2H": 3})
    launched = []
    def fake_tracer(command, **kwargs):
        # Run the real runner's fake solver process. Only strace is replaced with
        # a declared synthetic openat transcript; validators remain unmocked.
        start = command.index(str(executable))
        config_path = command[command.index("--config") + 1]
        launched.append(config_path)
        result = run_process_group([sys.executable, *command[start:]], **kwargs)
        log = Path(command[command.index("-o") + 1])
        log.write_text('openat(AT_FDCWD, ' + json.dumps(config_path) + ', O_RDONLY) = 3\n')
        return result
    monkeypatch.setattr(runner, "run_process_group", fake_tracer)
    (tmp_path / "04_SOLVER_RUNS").mkdir()
    prepared = {"stage": tmp_path, "configurations": configs,
        "provider_checks": {"synthetic_provider": {"sha256": "c" * 64}},
        "frozen_metadata_checks": {"02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json": {"sha256": "c" * 64}},
        "provider_manifest": {"raw_source_hashes": {}},
        "contract": {"identity": {"dataset_id": "BY2H"}, "window_contract": {"t_start": 1, "t_end": 3}}}
    records = runner.run_profiles(registry=SimpleNamespace(code_root=tmp_path, clean_root=tmp_path, raw_root=tmp_path / "unused_raw"),
        sequence=SimpleNamespace(dataset_id="BY2H", stage_id="SYNTHETIC_ONLY", data_mode="synthetic"),
        prepared=prepared, executable={"path": str(executable), "sha256": sha256_file(executable)}, state=state)
    assert len(launched) == 5
    assert [row["method_id"] for row in records] == list(rc.METHODS)
    assert [row["exit_code"] for row in records] == [7, 0, 0, 0, 0]
    assert [row["terminal_status"] for row in records] == ["technical_failure", *(["COMPLETED"] * 4)]
    assert "fixture failure" in records[0]["stderr_tail"]
    assert all((Path(row["run_dir"]) / "CLEAN5_FORMAL_RUN_MANIFEST.json").is_file() for row in records)


def test_v2_seal_namespace_preserves_v1_and_detects_missing_output(seal_fixture):
    stage, records, metadata, audits = seal_fixture
    (stage / "04_SOLVER_RUNS").rename(stage / "04_SOLVER_RUNS_V2")
    for record in records:
        record["run_dir"] = str(stage / "04_SOLVER_RUNS_V2" / record["run_id"])
    v1 = stage / "04_SOLVER_RUNS"
    v1.mkdir()
    sentinel = v1 / "SYNTHETIC_V1_SENTINEL.txt"
    sentinel.write_bytes(b"synthetic v1 preserved exactly\n")
    sentinel_hash = sha256_file(sentinel)
    old_seal = stage / "05_OUTPUT_SEAL"
    old_seal.mkdir()
    old_seal_sentinel = old_seal / "SYNTHETIC_V1_SENTINEL.txt"
    old_seal_sentinel.write_bytes(b"synthetic v1 seal preserved exactly\n")
    old_seal_hash = sha256_file(old_seal_sentinel)
    metadata.update(runs_subdir="04_SOLVER_RUNS_V2", seal_subdir="05_OUTPUT_SEAL_V2", contract_version=2)
    result = seal.seal_outputs(stage, records, metadata, audits)
    assert Path(result["output_seal_path"]).parent == stage / "05_OUTPUT_SEAL_V2"
    assert seal.validate_output_seal(result["output_seal_path"])["passed"]
    payload = json.loads(Path(result["output_seal_path"]).read_text())
    assert payload["contract_version"] == 2
    assert payload["runs_subdir"] == "04_SOLVER_RUNS_V2"
    assert sha256_file(sentinel) == sentinel_hash
    assert sha256_file(old_seal_sentinel) == old_seal_hash
    (Path(records[0]["run_dir"]) / "KF_GINS_Navresult.nav").unlink()
    with pytest.raises(seal.SealValidationError, match="missing"):
        seal.validate_output_seal(result["output_seal_path"])
    assert sha256_file(sentinel) == sentinel_hash
    assert sha256_file(old_seal_sentinel) == old_seal_hash
