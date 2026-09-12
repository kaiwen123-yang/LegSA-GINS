from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

from legsa_gins.paper_rebuild.horizontal_literature import hartley_h0_h2 as h0
from legsa_gins.paper_rebuild.horizontal_literature import hartley_h5 as h5


REPO = Path(__file__).resolve().parents[2]
CONTRACTS = REPO / "configs/paper_rebuild/horizontal_literature/hartley/stage_payload/04_METHOD_CONTRACTS"
IMPLEMENTATION = REPO / "docs/paper_rebuild/horizontal_literature/hartley/stage_payload/06_IMPLEMENTATION"


def _record(index: int, *, forces: tuple[float, ...] = (40, 41, 42, 43), poison: bool = True) -> str:
    sec = 100 + index
    bad = "" if not poison else """
position: [THIS IS NOT A NUMBER AND NEVER CLOSES
velocity:
  - !!malformed [
yaw_speed: .NaN_POISON
gait_type: {{broken
mode: [broken
"""
    return f"""stamp:
  sec: {sec}
  nanosec: {index}
imu_state:
  quaternion: [POISON, NOT, DECODED]
  gyroscope: [0.0, 0.0, 0.0]
  rpy: [POISON
  accelerometer: [0.0, 0.0, 9.81]
foot_force: [{','.join(map(str, forces))}]
foot_position_body: [1,2,3,4,5,6,7,8,9,10,11,12]
{bad}---
"""


def _source(tmp_path: Path, count: int = 7) -> tuple[Path, h5.H5SourceIdentity]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "by2.txt"
    source.write_bytes(("header: poison\n" + "".join(_record(i) for i in range(count))).encode())
    raw = hashlib.sha256(source.read_bytes()).hexdigest()
    identity = h5.verify_source_identity(
        source, expected_raw_size=source.stat().st_size, expected_raw_sha256=raw,
        prefix_end_exclusive=source.stat().st_size, expected_prefix_sha256=raw,
    )
    return source, identity


def _source_forces(tmp_path: Path, forces: list[tuple[float, ...]]) -> tuple[Path, h5.H5SourceIdentity]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    source = tmp_path / "by2.txt"
    source.write_bytes(("header: poison\n" + "".join(
        _record(index, forces=value) for index, value in enumerate(forces)
    )).encode())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    return source, h5.verify_source_identity(
        source, expected_raw_size=source.stat().st_size, expected_raw_sha256=digest,
        prefix_end_exclusive=source.stat().st_size, expected_prefix_sha256=digest,
    )


def _native_config(cache: Path, *, run_id: str = h5.H5_PRIMARY_RUN_ID,
                   policy: str = "GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61",
                   sigma: float = 0.010, records: int = 7) -> str:
    base = (
        f"run_id={run_id}\nbackend_id={h5.H5_BACKEND_ID}\n"
        f"process_policy={policy}\nsigma_fk_m={sigma:.3f}\n"
        f"expected_records={records}\ncache_sha256={h5.sha256_file(cache)}\n"
        "code_commit=fixture\ntask_start_head=fixture\n"
        "task_start_dirty_or_precommit=true\n"
        "scoped_source_manifest_sha256=fixture\n"
        "native_executable_sha256=fixture\n"
        "later_final_commit_mapping=NOT_AVAILABLE_PRECOMMIT\n"
    )
    return base + f"config_hash={hashlib.sha256(base.encode()).hexdigest()}\n"


def test_corrected_run_registry_and_eq52_boundary() -> None:
    contract = yaml.safe_load((CONTRACTS / "HARTLEY_FUTURE_H5_IMU_PROFILE_CONTRACT.yaml").read_text())
    assert tuple(contract["run_order"]) == h5.H5_RUN_IDS
    assert set(contract["run_identities"]) == set(h5.H5_RUN_IDS)
    assert "H5_PAPER_TABLE1_PARAMETER_REGRESSION" not in contract["run_identities"]
    assert contract["eq52_available_in_h5_runtime"] is False
    assert contract["real_BY2_EQ52_run"] is False
    paper = contract["run_identities"]["H5_PAPER_TABLE1_PROCESS_REGRESSION_WITH_GO2_FK_PROXY"]
    assert paper["process_cpp_type"] == "PaperTable1ProcessStd"
    assert paper["process_value_count"] == len(paper["process_values"]) == 5
    assert paper["paper_branch_label"] == "PAPER_PROCESS_PARAMETER_REGRESSION"
    assert paper["measurement_adapter_label"] == (
        "WITH_NONPAPER_GO2_FK_PROXY_MEASUREMENT_ADAPTER"
    )
    assert contract["joint_encoder_boundary"]["by2_applicability"] == (
        "NOT_APPLICABLE_TO_BY2_WITHOUT_RAW_JOINTS_AND_JACOBIAN"
    )
    execution = yaml.safe_load((CONTRACTS / "HARTLEY_H5_BY2_EXECUTION_CONTRACT.yaml").read_text())
    assert execution["chronology"]["state_rows"] == 63277
    assert execution["chronology"]["propagation_calls"] == 63276
    assert execution["chronology"]["initialization_interval_excludes_execution_rows"] is False
    assert execution["real_BY2_EQ52_run"] is False
    assert execution["paper_process_regression_classification"] == {
        "run_id": "H5_PAPER_TABLE1_PROCESS_REGRESSION_WITH_GO2_FK_PROXY",
        "paper_branch_label": "PAPER_PROCESS_PARAMETER_REGRESSION",
        "measurement_adapter_label": "WITH_NONPAPER_GO2_FK_PROXY_MEASUREMENT_ADAPTER",
    }
    registry = yaml.safe_load((IMPLEMENTATION / "HARTLEY_BACKEND_IDENTITY_REGISTRY.yaml").read_text())
    assert registry["execution_boundary"]["h5_runtime_eq52_available"] is False
    boundary = registry["execution_boundary"]
    assert boundary["historical_h3_h4_snapshot"]["real_BY2_navigation_executed"] is False
    assert boundary["historical_h3_h4_snapshot"]["external_stage_publication"] is True
    assert boundary["historical_h3_h4_snapshot"]["external_stage_hash_parity_verified"] is True
    assert boundary["h5_native_snapshot"]["real_BY2_navigation_execution_status"] == (
        "FOUR_NATIVE_RUNS_FROZEN_LOCAL_ONLY"
    )
    assert boundary["h5_native_snapshot"]["real_BY2_EQ52_run"] is False
    assert boundary["h5_native_snapshot"]["external_stage_publication"] is False


def test_h5_launcher_import_isolated_from_unrelated_method_modules(tmp_path: Path) -> None:
    strace = shutil.which("strace")
    assert strace is not None, "strace is required for the H5 import-open audit"
    launcher = REPO / "scripts/paper_rebuild/run_hartley_h5_by2.py"
    trace = tmp_path / "h5-import.strace"
    code = f"""
import importlib.util
import sys
spec = importlib.util.spec_from_file_location('h5_launcher_audit', {str(launcher)!r})
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
forbidden = (
    'ext01_', 'ext02_', 'ext03_', 'ext04_', 'ext05_', 'ext06_',
    'horizontal18', 'horizontal_18', 'canonical541',
)
loaded = [name for name in sys.modules if any(token in name.lower() for token in forbidden)]
assert not loaded, loaded
assert 'legsa_gins.paper_rebuild.horizontal_literature' not in sys.modules
sys.argv = [{str(launcher)!r}, '--help']
try:
    module.main()
except SystemExit as exc:
    assert exc.code == 0
"""
    completed = subprocess.run(
        [strace, "-f", "-qq", "-e", "trace=open,openat", "-o", str(trace),
         sys.executable, "-c", code],
        cwd=REPO, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stderr
    opened = trace.read_text(encoding="utf-8").lower()
    forbidden_paths = (
        "/horizontal_literature/ext01_", "/horizontal_literature/ext02_",
        "/horizontal_literature/ext03_", "/horizontal_literature/ext04_",
        "/horizontal_literature/ext05_", "/horizontal_literature/ext06_",
        "horizontal18", "horizontal_18", "/canonical541/",
        "/reference/", "/trace/", "/reference.py", "/trace.py",
    )
    assert not [token for token in forbidden_paths if token in opened]
    assert "hartley_h5" in opened and "hartley_h0_h2" in opened


def test_parser_never_decodes_poison_forbidden_fields_and_cache_abi(tmp_path: Path) -> None:
    source, identity = _source(tmp_path, 3)
    iterator, summary = h5.stream_h5_prefix(source, prefix_end_exclusive=source.stat().st_size,
                                             expected_records=3)
    rows = list(iterator)
    assert len(rows) == 3
    assert rows[0].gyro_body == (0.0, 0.0, 0.0)
    assert rows[0].foot_force_canonical == (41.0, 40.0, 43.0, 42.0)
    assert rows[0].foot_position_body_canonical == (
        (4.0, 5.0, 6.0), (1.0, 2.0, 3.0),
        (10.0, 11.0, 12.0), (7.0, 8.0, 9.0),
    )
    counters = summary["semantic_read_counters"]
    assert counters == {
        "timestamp_values": 6, "gyro_values": 9, "accel_values": 9,
        "foot_force_values": 12, "foot_position_values": 36,
        "forbidden_or_audit_values_decoded": 0,
        "lexically_skipped_lines": counters["lexically_skipped_lines"],
    }
    cache, ledger = tmp_path / "cache.bin", tmp_path / "events.jsonl"
    manifest = h5.build_immutable_cache(identity, cache, ledger, expected_records=3)
    assert cache.stat().st_size == h5.CACHE_HEADER_SIZE + 3 * h5.CACHE_RECORD_SIZE
    header = h5.CACHE_HEADER_STRUCT.unpack(cache.read_bytes()[: h5.CACHE_HEADER_SIZE])
    assert header[0] == h5.CACHE_MAGIC and header[4] == 3
    assert manifest["semantic_read_counters"]["forbidden_or_audit_values_decoded"] == 0
    assert manifest["initial_add_event_count"] == 4
    assert manifest["frozen_transition_event_count_excluding_initial_add"] == 0
    with pytest.raises(FileExistsError):
        h5.build_immutable_cache(identity, cache, tmp_path / "other-events.jsonl", expected_records=3)


def test_contact_hysteresis_exactly_matches_frozen_elapsed_time_policy() -> None:
    timestamps_ns = np.array([
        1_772_784_044_887_078_145,
        1_772_784_044_891_078_145,
        1_772_784_044_895_078_145,
        1_772_784_044_899_178_145,
        1_772_784_044_903_278_145,
        1_772_784_044_907_378_145,
    ], dtype=np.int64)
    times = timestamps_ns.astype(float) / 1.0e9
    forces = np.array([
        [30, 30, 30, 30], [40, 10, 40, 10], [40, 10, 40, 10],
        [40, 10, 40, 10], [40, 10, 40, 10], [40, 10, 40, 10],
    ], dtype=float)
    expected, _ = h0.force_hysteresis_contacts(
        times, forces,
        h0.ContactDetectorConfig(h0.FROZEN_CONTACT_ON_THRESHOLDS,
                                 h0.FROZEN_CONTACT_OFF_THRESHOLDS,
                                 h0.FROZEN_CONTACT_DWELL_SECONDS,
                                 h0.FROZEN_CONTACT_DWELL_SAMPLES),
    )
    detector = h5.ContactHysteresis()
    actual = []
    for timestamp_ns, force in zip(timestamps_ns, forces):
        mask, _, _ = detector.update(int(timestamp_ns), force)
        actual.append([(mask & (1 << leg)) != 0 for leg in range(4)])
    assert np.array_equal(np.asarray(actual), expected)
    frozen_audit = json.loads((
        REPO / "docs/paper_rebuild/horizontal_literature/hartley/stage_payload/03_BY2_INPUT_AUDIT/FK_PROXY_COVARIANCE_SUMMARY.json"
    ).read_text())
    assert frozen_audit["contact_policy"]["transition_event_count"] == 4706
    assert h5.H5_FROZEN_TRANSITION_EVENT_COUNT == 4706


def test_checkpoint_gauge_schema_and_non_circular_freeze(tmp_path: Path) -> None:
    assert h5.checkpoint_rows([0, 400_000_000, 1_600_000_000, 2_400_000_000], [2], [3]) == (0, 1, 2, 3)
    gauge, labels = h5.gauge_projection(21, [0, 3])
    assert tuple(gauge[:3, 0]) == (0.0, 0.0, -1.0)
    assert np.linalg.norm(gauge[:, 0]) == pytest.approx(1.0)
    assert np.allclose(np.linalg.norm(gauge[:, 1:], axis=0), 1.0)
    assert labels[0] == "yaw_about_unit_gravity"
    assert "gauge_yaw_variance" in h5.OUTPUT_SCHEMAS["COVARIANCE_DIAGONALS.csv"]
    for name, columns in h5.OUTPUT_SCHEMAS.items():
        (tmp_path / name).write_text(",".join(columns) + "\n", encoding="utf-8")
    (tmp_path / "NATIVE_SUMMARY.json").write_text("{}\n")
    (tmp_path / "NATIVE_CONFIG.cfg").write_text("fixture=true\n")
    np.savez(tmp_path / "COVARIANCE_CHECKPOINTS.npz", covariance_0=np.eye(15))
    manifest = h5.freeze_native_outputs(tmp_path)
    assert "NATIVE_FREEZE.json" not in manifest
    assert "COVARIANCE_CHECKPOINTS.bin" not in manifest
    frozen = json.loads((tmp_path / "NATIVE_FREEZE.json").read_text())
    assert frozen["files"] == manifest


def test_publish_exact_manifest_byte_parity_and_refusal(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "one.csv").write_bytes(b"a,b\n1,2\n")
    (source / "two.json").write_bytes(b'{"pass":true}\n')
    manifest = {
        path.name: {"size": path.stat().st_size, "sha256": h5.sha256_file(path)}
        for path in source.iterdir()
    }
    destination = tmp_path / "published"
    h5.publish_exact_manifest(source, destination, manifest)
    assert {path.name: path.read_bytes() for path in destination.iterdir()} == {
        path.name: path.read_bytes() for path in source.iterdir()
    }
    (source / "one.csv").write_bytes(b"changed\n")
    refused = tmp_path / "refused"
    with pytest.raises(h5.HartleyH5Error, match="differs"):
        h5.publish_exact_manifest(source, refused, manifest)
    assert not refused.exists()


def test_native_fixture_runner_schemas_and_chronology(tmp_path: Path) -> None:
    executable = Path(os.environ.get("HARTLEY_H5_RUNNER", "/tmp/hartley_h5_build/hartley_h5_runner"))
    if not executable.is_file():
        pytest.skip("H5 native fixture runner is not built")
    _, identity = _source(tmp_path, 7)
    cache = tmp_path / "cache.bin"
    h5.build_immutable_cache(identity, cache, tmp_path / "input-events.jsonl", expected_records=7)
    config = tmp_path / "fixture.cfg"
    config.write_text(_native_config(cache))
    environment = dict(os.environ)
    environment.update({key: "1" for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
    output = tmp_path / "native"
    output.mkdir()
    owned_config = output / "NATIVE_CONFIG.cfg"
    config.replace(owned_config)
    subprocess.run([str(executable), str(cache), str(owned_config), str(output)], check=True, env=environment)
    for name, columns in h5.OUTPUT_SCHEMAS.items():
        with (output / name).open(newline="") as handle:
            reader = csv.reader(handle)
            assert tuple(next(reader)) == columns
    runtime = list(csv.DictReader((output / "RUNTIME.csv").open()))[0]
    assert runtime["state_rows"] == "7"
    assert runtime["propagation_calls"] == runtime["eq61_calls"] == "6"
    assert runtime["eq52_calls"] == "0"
    summary = json.loads((output / "NATIVE_SUMMARY.json").read_text())
    assert summary["data_mode"] == "real_by2_raw"
    assert summary["synthetic_data_used"] is False
    assert summary["trace_used_online"] is False
    assert summary["old_runtime_input_count"] == 0
    assert summary["initialization_window_rows"] == 5
    assert summary["initialization_window_half_open"] is True
    assert summary["initial_rpy_rad"][2] == 0
    assert summary["initial_rpy_rad"][0] == pytest.approx(np.deg2rad(1.0), abs=1.0e-6)
    assert summary["initial_rpy_rad"][1] == pytest.approx(0.0, abs=1.0e-12)
    rotation = np.asarray(summary["initial_rotation_row_major"]).reshape(3, 3)
    assert np.allclose(rotation.T @ rotation, np.eye(3), atol=2.0e-6)
    assert np.linalg.det(rotation) == pytest.approx(1.0, abs=2.0e-6)
    assert np.allclose(summary["initial_gyro_mean"], summary["initial_gyro_bias"])
    assert np.linalg.norm(summary["initial_acceleration_residual_world"]) < 1.0e-12
    assert summary["initial_acceleration_residual_norm"] < 1.0e-12
    assert summary["dt_count"] == 6
    assert summary["forbidden_value_decode_count"] == 0
    assert summary["reference_open_count"] == summary["trace_open_count"] == 0
    nav = list(csv.DictReader((output / "NAV.csv").open()))
    assert len(nav) == 7 and nav[0]["state_role"] == "INITIALIZED"
    assert all(row["state_role"] == "FILTERED" for row in nav[1:])
    assert not (output / "COVARIANCE_CHECKPOINTS.csv").exists()


def test_switching_simultaneous_lifecycle_chronology_and_topology(tmp_path: Path) -> None:
    executable = Path(os.environ.get("HARTLEY_H5_RUNNER", "/tmp/hartley_h5_review_build/hartley_h5_runner"))
    if not executable.is_file():
        pytest.skip("H5 native fixture runner is not built")
    forces = [
        (40, 40, 40, 40),
        (0, 0, 40, 40),
        (0, 0, 40, 40),       # simultaneous remove canonical FL+FR
        (0, 40, 0, 40),
        (0, 40, 0, 40),       # simultaneous add FL/remove canonical RR
        (0, 40, 0, 40),
        (0, 40, 0, 40),
    ]
    _, identity = _source_forces(tmp_path / "source", forces)
    cache = tmp_path / "cache.bin"
    h5.build_immutable_cache(identity, cache, tmp_path / "events.jsonl", expected_records=7)
    output = tmp_path / "native"
    output.mkdir()
    config = output / "NATIVE_CONFIG.cfg"
    config.write_text(_native_config(cache))
    environment = dict(os.environ)
    environment.update({key: "1" for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
    subprocess.run([str(executable), str(cache), str(config), str(output)], check=True, env=environment)
    ledger = list(csv.DictReader((output / "EXECUTION_LEDGER.csv").open()))
    assert (ledger[2]["active_contacts_before"], ledger[2]["active_contacts_after"], ledger[2]["state_dimension"]) == ("4", "2", "21")
    assert int(ledger[2]["remove_mask"]).bit_count() == 2
    assert (ledger[4]["active_contacts_before"], ledger[4]["active_contacts_after"], ledger[4]["state_dimension"]) == ("2", "2", "21")
    assert int(ledger[4]["add_mask"]).bit_count() == int(ledger[4]["remove_mask"]).bit_count() == 1
    checkpoints = list(csv.DictReader((output / "COVARIANCE_CHECKPOINT_INDEX.csv").open()))
    by_row = {int(row["row_index"]): row for row in checkpoints}
    assert "contact_event_after_settled_lifecycle" in by_row[2]["reason"] and by_row[2]["dimension"] == "21"
    assert "contact_event_after_settled_lifecycle" in by_row[4]["reason"] and by_row[4]["dimension"] == "21"


@pytest.mark.parametrize("variable", [
    "HARTLEY_H5_INJECT_OUTPUT_FAILURE_AFTER_ROW",
    "HARTLEY_H5_INJECT_ROTATION_FAILURE_ROW",
    "HARTLEY_H5_INJECT_COVARIANCE_FAILURE_ROW",
    "HARTLEY_H5_INJECT_STATE_DIMENSION_FAILURE_ROW",
])
def test_native_failures_never_emit_pass_or_freeze(tmp_path: Path, variable: str) -> None:
    executable = Path(os.environ.get("HARTLEY_H5_RUNNER", "/tmp/hartley_h5_review_build/hartley_h5_runner"))
    if not executable.is_file():
        pytest.skip("H5 native fixture runner is not built")
    _, identity = _source(tmp_path / "source", 7)
    cache = tmp_path / "cache.bin"
    h5.build_immutable_cache(identity, cache, tmp_path / "events.jsonl", expected_records=7)
    output = tmp_path / "native"
    output.mkdir()
    config = output / "NATIVE_CONFIG.cfg"
    config.write_text(_native_config(cache))
    environment = dict(os.environ)
    environment.update({key: "1" for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
    environment[variable] = "0"
    completed = subprocess.run([str(executable), str(cache), str(config), str(output)],
                               env=environment, capture_output=True, text=True)
    assert completed.returncode != 0
    assert "PASS_HARTLEY_H5_NATIVE" not in completed.stdout
    assert not (output / "NATIVE_FREEZE.json").exists()
    assert not (output / "NATIVE_SUMMARY.json").exists()


def test_native_rejects_config_hash_and_policy_binding_tampering(tmp_path: Path) -> None:
    executable = Path(os.environ.get("HARTLEY_H5_RUNNER", "/tmp/hartley_h5_review_build/hartley_h5_runner"))
    if not executable.is_file():
        pytest.skip("H5 native fixture runner is not built")
    _, identity = _source(tmp_path / "source", 7)
    cache = tmp_path / "cache.bin"
    h5.build_immutable_cache(identity, cache, tmp_path / "events.jsonl", expected_records=7)
    environment = dict(os.environ)
    environment.update({key: "1" for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS")})
    for name, text in {
        "hash": _native_config(cache).replace("sigma_fk_m=0.010", "sigma_fk_m=0.020"),
        "binding": _native_config(cache, sigma=0.020),
    }.items():
        output = tmp_path / name
        output.mkdir()
        config = output / "NATIVE_CONFIG.cfg"
        config.write_text(text)
        completed = subprocess.run([str(executable), str(cache), str(config), str(output)],
                                   env=environment, capture_output=True, text=True)
        assert completed.returncode != 0
        assert "PASS_HARTLEY_H5_NATIVE" not in completed.stdout


def test_one_provider_cache_exact_four_run_sequence_and_output_tamper_gates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    executable = Path(os.environ.get("HARTLEY_H5_RUNNER", "/tmp/hartley_h5_build/hartley_h5_runner"))
    if not executable.is_file():
        pytest.skip("H5 native fixture runner is not built")
    spec = importlib.util.spec_from_file_location(
        "run_hartley_h5_by2_fixture",
        REPO / "scripts/paper_rebuild/run_hartley_h5_by2.py",
    )
    assert spec and spec.loader
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    finalizer_spec = importlib.util.spec_from_file_location(
        "finalize_hartley_h5_native_fixture",
        REPO / "scripts/paper_rebuild/finalize_hartley_h5_native.py",
    )
    assert finalizer_spec and finalizer_spec.loader
    finalizer = importlib.util.module_from_spec(finalizer_spec)
    finalizer_spec.loader.exec_module(finalizer)
    monkeypatch.setattr(h5, "H5_RECORD_COUNT", 7)
    monkeypatch.setattr(h5, "H5_PROPAGATION_COUNT", 6)
    monkeypatch.setattr(launcher.h5, "H5_RECORD_COUNT", 7)
    monkeypatch.setattr(launcher.h5, "H5_PROPAGATION_COUNT", 6)
    monkeypatch.setattr(finalizer.h5, "H5_RECORD_COUNT", 7)
    monkeypatch.setattr(finalizer.h5, "H5_PROPAGATION_COUNT", 6)
    _, identity = _source_forces(tmp_path / "source", [(0, 41, 42, 43)] * 7)
    attempt = tmp_path / "attempt"
    provider = attempt / launcher.PROVIDER_DIRECTORY
    (attempt / launcher.RUNS_DIRECTORY).mkdir(parents=True)
    provider.mkdir()
    cache, ledger, manifest_path = launcher._provider_paths(attempt)
    manifest = h5.build_immutable_cache(identity, cache, ledger, expected_records=7)
    raw_identity = {"size": identity.raw_size, "sha256": identity.raw_sha256,
                    "prefix_end_exclusive": identity.prefix_end_exclusive,
                    "prefix_sha256": identity.prefix_sha256}
    manifest["raw_identity_before_cache"] = raw_identity
    manifest["raw_identity_after_cache"] = dict(raw_identity)
    manifest["raw_identity_before_after_cache_equal"] = True
    manifest["scoped_source_manifest"] = launcher._scoped_source_manifest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    before = (cache.stat().st_ino, cache.stat().st_size, h5.sha256_file(cache))
    primary = launcher._run(attempt, executable, h5.H5_PRIMARY_RUN_ID)
    assert primary["cache_sha256"] == manifest["cache_sha256"]
    assert launcher._verify_primary(attempt)["status"] == "PASS_H5_PRIMARY_NATIVE_GATE"
    primary_directory = attempt / launcher.RUNS_DIRECTORY / h5.H5_PRIMARY_RUN_ID
    assert not (primary_directory / "COVARIANCE_CHECKPOINTS.bin").exists()
    assert (primary_directory / "COVARIANCE_CHECKPOINTS.npz").is_file()
    summary = json.loads((primary_directory / "NATIVE_SUMMARY.json").read_text())
    assert summary["process_policy"] == "GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61"
    assert summary["sigma_fk_m"] == 0.010
    assert summary["native_executable_sha256"] == h5.sha256_file(executable)
    assert summary["scoped_source_manifest_sha256"] == manifest["scoped_source_manifest"]["manifest_sha256"]
    def tampered_copy(name: str, filename: str, mutate) -> Path:
        destination = tmp_path / name
        shutil.copytree(primary_directory, destination)
        path = destination / filename
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = tuple(reader.fieldnames or ())
            rows = list(reader)
        mutate(rows)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return destination

    tampered = tampered_copy(
        "tampered-diagonal", "COVARIANCE_DIAGONALS.csv",
        lambda rows: rows[0].__setitem__(
            "theta_x", repr(float(rows[0]["theta_x"]) * (1.0 + 1.0e-5))
        ),
    )
    with pytest.raises(launcher.h5.HartleyH5Error, match="NPZ/covariance-diagonal"):
        launcher._validate_native_outputs(tampered, 7)
    tampered = tampered_copy("tampered-topology", "COVARIANCE_DIAGONALS.csv",
                             lambda rows: rows[0].__setitem__("topology", "FL+FR+RL+RR"))
    with pytest.raises(launcher.h5.HartleyH5Error, match="topology"):
        launcher._validate_native_outputs(tampered, 7)
    tampered = tampered_copy("tampered-inactive", "CONTACT_STATE.csv",
                             lambda rows: rows[1].__setitem__("contact_x", "1"))
    with pytest.raises(launcher.h5.HartleyH5Error, match="inactive contact state"):
        launcher._validate_native_outputs(tampered, 7)
    tampered = tampered_copy("tampered-gauge", "COVARIANCE_DIAGONALS.csv",
                             lambda rows: rows[0].__setitem__("gauge_yaw_variance", "999"))
    with pytest.raises(launcher.h5.HartleyH5Error, match="NPZ/gauge-projection"):
        launcher._validate_native_outputs(tampered, 7)

    with pytest.raises(launcher.h5.HartleyH5Error, match="out-of-order"):
        launcher._run(attempt, executable,
                      "H5_PAPER_TABLE1_PROCESS_REGRESSION_WITH_GO2_FK_PROXY")
    with pytest.raises(launcher.h5.HartleyH5Error, match="out-of-order"):
        launcher._run(attempt, executable, h5.H5_PRIMARY_RUN_ID)
    for run_id in h5.H5_RUN_IDS[1:]:
        companion = launcher._run(attempt, executable, run_id)
        assert companion["cache_sha256"] == primary["cache_sha256"]
    with pytest.raises(launcher.h5.HartleyH5Error, match="exact preregistered prefix"):
        launcher._run(attempt, executable, h5.H5_RUN_IDS[-1])
    with pytest.raises(launcher.h5.HartleyH5Error, match="unknown H5 run identity"):
        launcher._run(attempt, executable, "H5_UNKNOWN")
    after = (cache.stat().st_ino, cache.stat().st_size, h5.sha256_file(cache))
    assert before == after
    assert {path.name for path in (attempt / launcher.RUNS_DIRECTORY).iterdir()} == set(h5.H5_RUN_IDS)
    publication = attempt / "FINAL_PUBLICATION"
    health = attempt / "SUPERVISOR_STORAGE_HEALTH.json"
    health.write_text(json.dumps({
        "DriveLetter": "G", "FileSystemType": "exFAT", "HealthStatus": "Warning",
        "OperationalStatus": "Full Repair Needed",
        "query": "Get-Volume -DriveLetter G", "read_only": True,
        "repair_invoked": False, "selected_execution_storage": "LINUX_LOCAL_EXT4_SCRATCH",
    }) + "\n")
    access_audit = attempt / "SUPERVISOR_FILE_ACCESS_AUDIT.json"
    access_audit.write_text(json.dumps({"schema_version": "fixture", "logs_published": False}) + "\n")
    attempt_ledger = attempt / "SUPERVISOR_ATTEMPT_LEDGER.json"
    attempt_ledger.write_text(json.dumps({"schema_version": "fixture", "real_BY2_filter_run_count_total": 4}) + "\n")
    monkeypatch.setattr(finalizer, "SUPERVISOR_EVIDENCE_SHA256", {
        path.name: h5.sha256_file(path) for path in (health, access_audit, attempt_ledger)
    })
    finalized = finalizer._finalize_native(
        attempt, publication, health, access_audit, attempt_ledger
    )
    assert finalized["status"] == "PASS_LSE01_H5_BY2_NATIVE_FOUR_RUN_FINALIZED_LOCAL_ONLY"
    native_root = publication / "08_BY2_NATIVE"
    assert {path.name for path in native_root.iterdir()} == {
        "00_PROVIDER", *finalizer.FINAL_RUN_DIRECTORIES, "05_NATIVE_COMPARISON"
    }
    assert len(list(publication.rglob("H5_INPUT_CACHE.bin"))) == 1
    published_health = native_root / "00_PROVIDER/SUPERVISOR_STORAGE_HEALTH.json"
    assert published_health.read_bytes() == health.read_bytes()
    assert (native_root / "00_PROVIDER/SUPERVISOR_FILE_ACCESS_AUDIT.json").read_bytes() == access_audit.read_bytes()
    assert (native_root / "00_PROVIDER/SUPERVISOR_ATTEMPT_LEDGER.json").read_bytes() == attempt_ledger.read_bytes()
    for directory in finalizer.FINAL_RUN_DIRECTORIES:
        for required in (
            "NAV.csv", "COVARIANCE_DIAGONALS.csv", "CONTACT_STATE.csv",
            "KINEMATIC_INNOVATIONS.csv", "NIS_DIAGNOSTICS.csv", "EXECUTION_LEDGER.csv",
        ):
            assert (native_root / directory / required).is_file()
    comparison = list(csv.DictReader(
        (native_root / "05_NATIVE_COMPARISON/H5_VARIANT_NATIVE_COMPARISON.csv").open()
    ))
    assert [row["run_id"] for row in comparison] == list(h5.H5_RUN_IDS)
    assert all(row["comparison_scope"] == "NATIVE_ONLY_NO_REFERENCE_NO_RANKING"
               for row in comparison)
    difference_columns = {
        "state_component_rms_difference_from_primary",
        "rotation_matrix_rms_difference_from_primary",
        "velocity_rms_difference_from_primary_m_per_s",
        "position_rms_difference_from_primary_m",
        "gyro_bias_rms_difference_from_primary_rad_per_s",
        "accel_bias_rms_difference_from_primary_m_per_s2",
        "innovation_norm_quantile_l1_difference_from_primary",
        "nis_quantile_l1_difference_from_primary",
        "covariance_diagonal_rms_difference_from_primary",
    }
    assert difference_columns.issubset(comparison[0])
    assert all(float(comparison[0][column]) == 0.0 for column in difference_columns)
    status = json.loads((publication / "11_REPORT/LSE01_H5_STATUS.json").read_text())
    assert status["run_count"] == 4 and status["eq52_calls_total"] == 0
    assert status["real_BY2_EQ52_run"] is False
    assert status["paper_process_regression_classification"] == {
        "paper_branch_label": "PAPER_PROCESS_PARAMETER_REGRESSION",
        "measurement_adapter_label": "WITH_NONPAPER_GO2_FK_PROXY_MEASUREMENT_ADAPTER",
    }
    report_text = (publication / "11_REPORT/LSE01_H5_BY2_NATIVE_REPORT.md").read_text()
    assert "PAPER_PROCESS_PARAMETER_REGRESSION" in report_text
    assert "WITH_NONPAPER_GO2_FK_PROXY_MEASUREMENT_ADAPTER" in report_text
    assert status["h6_executed"] is status["h7_executed"] is False
    assert status["storage_health"]["HealthStatus"] == "Warning"
    assert status["storage_health"]["OperationalStatus"] == "Full Repair Needed"
    parity = json.loads((publication / "H5_SCRATCH_PUBLICATION_PARITY.json").read_text())
    assert parity["all_copied_bytes_equal"] is True
    manifest_path = publication / "H5_LOCAL_PUBLICATION_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text())
    for relative, identity in manifest["files"].items():
        path = publication / relative
        assert path.stat().st_size == identity["size"]
        assert h5.sha256_file(path) == identity["sha256"]
    manifest_hash = (publication / "H5_LOCAL_PUBLICATION_MANIFEST.sha256").read_text().split()[0]
    assert manifest_hash == h5.sha256_file(manifest_path)
    with pytest.raises(finalizer.h5.HartleyH5Error, match="already exists"):
        finalizer._finalize_native(attempt, publication, health, access_audit, attempt_ledger)
