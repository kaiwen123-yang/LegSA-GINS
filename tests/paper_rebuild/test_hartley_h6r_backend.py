from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pytest


REPO = Path(__file__).resolve().parents[2]
PACKAGE_PATH = REPO / "src/legsa_gins/paper_rebuild/horizontal_literature"
RUNNER_SOURCE = PACKAGE_PATH / "hartley_inekf/tools/run_h5.cpp"


def _isolated_h6r():
    package_name = "_test_hartley_h6r_backend_isolated"
    package = types.ModuleType(package_name)
    package.__package__ = package_name
    package.__path__ = [str(PACKAGE_PATH)]
    sys.modules[package_name] = package
    for basename in ("hartley_h0_h2", "hartley_h5", "hartley_h6", "hartley_h6r"):
        name = f"{package_name}.{basename}"
        spec = importlib.util.spec_from_file_location(name, PACKAGE_PATH / f"{basename}.py")
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        setattr(package, basename, module)
    return sys.modules[f"{package_name}.hartley_h6r"], sys.modules[f"{package_name}.hartley_h5"]


h6r, h5 = _isolated_h6r()


def _record(index: int) -> str:
    return f"""stamp:
  sec: {100 + index}
  nanosec: {index}
imu_state:
  gyroscope: [0.0, 0.0, 0.0]
  accelerometer: [0.0, -0.1712081071, 9.808505889]
foot_force: [40,41,42,43]
foot_position_body: [0.3,0.2,-0.4,0.3,-0.2,-0.4,-0.3,0.2,-0.4,-0.3,-0.2,-0.4]
---
"""


def _cache(tmp_path: Path, count: int = 7) -> Path:
    source = tmp_path / "by2.txt"
    source.write_text("header: fixture\n" + "".join(_record(index) for index in range(count)))
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    identity = h5.verify_source_identity(
        source, expected_raw_size=source.stat().st_size, expected_raw_sha256=digest,
        prefix_end_exclusive=source.stat().st_size, expected_prefix_sha256=digest,
    )
    cache = tmp_path / "cache.bin"
    h5.build_immutable_cache(identity, cache, tmp_path / "events.jsonl", expected_records=count)
    return cache


def _config(cache: Path, *, h6r_mode: bool) -> str:
    values = [
        ("run_id", "H6R_YAW_000" if h6r_mode else h5.H5_PRIMARY_RUN_ID),
        ("backend_id", h5.H5_BACKEND_ID),
        ("process_policy", "GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61"),
        ("sigma_fk_m", "0.010"), ("expected_records", "7"),
        ("cache_sha256", h5.sha256_file(cache)), ("code_commit", "fixture"),
        ("task_start_head", "fixture"), ("task_start_dirty_or_precommit", "true"),
        ("scoped_source_manifest_sha256", "fixture"),
        ("native_executable_sha256", "fixture"),
        ("later_final_commit_mapping", "NOT_AVAILABLE_PRECOMMIT"),
    ]
    if h6r_mode:
        values.extend((
            ("execution_phase", "H6R_FULL_PRECISION_CONTACT_RECOVERY"),
            ("initial_gauge_yaw_deg", "0.0"),
            ("evidence_serialization", "H6R_FULL_PRECISION_CONTACT_V1"),
        ))
    base = "".join(f"{key}={value}\n" for key, value in values)
    return base + f"config_hash={hashlib.sha256(base.encode()).hexdigest()}\n"


def _run(executable: Path, cache: Path, output: Path, *, h6r_mode: bool) -> None:
    output.mkdir()
    config = output / "NATIVE_CONFIG.cfg"
    config.write_text(_config(cache, h6r_mode=h6r_mode))
    environment = dict(os.environ)
    environment.update({key: "1" for key in h6r.THREAD_KEYS})
    subprocess.run(
        [str(executable), str(cache), str(config), str(output)],
        check=True, cwd=REPO, env=environment,
    )


def test_old_contact_serializer_statement_is_untouched_and_float64_is_conditional() -> None:
    source = RUNNER_SOURCE.read_text()
    old_statement = (
        "for(int leg=0; leg<4; ++leg) { auto found=state.contacts.find(leg); "
        "contact_state<<rows[index].timestamp_ns<<','<<index<<','<<leg<<','<<kLegs[leg]<<','"
        "<<(found!=state.contacts.end()); if(found==state.contacts.end()) "
        "contact_state<<\",,,\\n\"; else contact_state<<','<<found->second.x()<<','"
        "<<found->second.y()<<','<<found->second.z()<<'\\n'; }"
    )
    assert source.count(old_statement) == 1
    assert "contact_state << std::setprecision" not in source
    assert "contact_state << std::fixed" not in source
    assert "contact_state << std::scientific" not in source
    assert 'if (h6r_full_precision) {' in source
    assert 'full_precision_contact.open(output / "CONTACT_STATE_FLOAT64.raw"' in source
    assert source.index(old_statement) < source.index("H6RContactRecord record{}", source.index(old_statement))


def test_packed_float64_abi_and_lossless_npz_schema(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert h6r.RAW_HEADER.size == 64
    assert h6r.RAW_RECORD.size == 120
    monkeypatch.setattr(h6r, "STATE_ROWS", 3)
    raw = tmp_path / "CONTACT_STATE_FLOAT64.raw"
    header = h6r.RAW_HEADER.pack(h6r.RAW_MAGIC, 1, h6r.RAW_HEADER.size,
                                 h6r.RAW_RECORD.size, 3, 0, 1, 2, 3)
    records = []
    expected_active = np.asarray([
        [True, False, True, False], [True, True, False, False], [False, False, False, False],
    ])
    expected_xyz = np.full((3, 4, 3), np.nan, dtype=np.float64)
    expected_xyz[0, 0] = [100.00000000000001, -2.5, 0.125]
    expected_xyz[0, 2] = [99.99999999999999, 3.0, -0.4]
    expected_xyz[1, 0] = [1.0, 2.0, 3.0]
    expected_xyz[1, 1] = [-1.0, -2.0, -3.0]
    for index in range(3):
        records.append(h6r.RAW_RECORD.pack(
            1_000 + index, index, *expected_active[index].tolist(), *expected_xyz[index].reshape(-1),
        ))
    raw.write_bytes(header + b"".join(records))
    destination = tmp_path / "CONTACT_STATE_FLOAT64.npz"
    schema = h6r.convert_contact_raw(raw, destination)
    assert raw.exists()
    assert schema["authoritative_comparator"] is True
    assert schema["raw_binary_retained_until_member_parity_freeze"] is True
    assert schema["npz_reopen_validation_deferred_until_after_old_format_freeze"] is True
    with np.load(destination, allow_pickle=False) as archive:
        assert set(archive.files) == {
            "timestamp_ns", "row_index", "active_mask", "contact_xyz", "leg_ids", "leg_names",
        }
        assert archive["timestamp_ns"].dtype == np.int64
        assert archive["row_index"].dtype == np.int64
        assert archive["active_mask"].dtype == np.bool_
        assert archive["contact_xyz"].dtype == np.float64
        assert archive["leg_ids"].dtype == np.int32
        assert archive["timestamp_ns"].shape == archive["row_index"].shape == (3,)
        assert archive["active_mask"].shape == (3, 4)
        assert archive["contact_xyz"].shape == (3, 4, 3)
        assert np.array_equal(archive["active_mask"], expected_active)
        assert np.array_equal(archive["contact_xyz"][expected_active], expected_xyz[expected_active])
        assert np.all(np.isnan(archive["contact_xyz"][~expected_active]))
        assert archive["leg_ids"].tolist() == [0, 1, 2, 3]
        assert [value.decode() for value in archive["leg_names"]] == list(h6r.LEGS)


def test_native_tiny_zero_degree_old_format_byte_parity_and_conditional_binary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    executable = Path(os.environ.get("HARTLEY_H6R_RUNNER", "/tmp/hartley_h6_build/hartley_h5_runner"))
    if not executable.is_file():
        pytest.skip("H6R native fixture runner is not built")
    cache = _cache(tmp_path)
    h5_output, h6r_output = tmp_path / "h5", tmp_path / "h6r-zero"
    _run(executable, cache, h5_output, h6r_mode=False)
    _run(executable, cache, h6r_output, h6r_mode=True)
    assert (h6r_output / "CONTACT_STATE.csv").read_bytes() == (h5_output / "CONTACT_STATE.csv").read_bytes()
    assert not (h5_output / "CONTACT_STATE_FLOAT64.raw").exists()
    assert (h6r_output / "CONTACT_STATE_FLOAT64.raw").is_file()
    monkeypatch.setattr(h6r, "STATE_ROWS", 7)
    destination = tmp_path / "CONTACT_STATE_FLOAT64.npz"
    h6r.convert_contact_raw(h6r_output / "CONTACT_STATE_FLOAT64.raw", destination)
    assert (h6r_output / "CONTACT_STATE_FLOAT64.raw").is_file()
    timestamps, rows, active, xyz = h6r.read_contact_npz(destination)
    assert timestamps.shape == rows.shape == (7,)
    assert active.shape == (7, 4) and xyz.shape == (7, 4, 3)


def test_packed_schema_rejects_non_nan_inactive_coordinates(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(h6r, "STATE_ROWS", 1)
    raw = tmp_path / "bad.raw"
    header = h6r.RAW_HEADER.pack(h6r.RAW_MAGIC, 1, h6r.RAW_HEADER.size,
                                 h6r.RAW_RECORD.size, 1, 0, 1, 2, 3)
    record = h6r.RAW_RECORD.pack(1, 0, False, False, False, False, *([0.0] * 12))
    raw.write_bytes(header + record)
    with pytest.raises(h6r.HartleyH6RError, match="inactive H6R contacts must be NaN"):
        h6r.convert_contact_raw(raw, tmp_path / "bad.npz")
    assert raw.is_file()


def test_nonzero_execution_requires_zero_parity_marker(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    scratch = tmp_path / "scratch"
    admin = scratch / "00_ADMIN"
    admin.mkdir(parents=True)
    (admin / "H6R_PREPARE_PASS.json").write_text(json.dumps({"prepare_pass": True}))
    cache = tmp_path / "cache.bin"
    cache.write_bytes(b"fixture-cache")
    monkeypatch.setattr(h6r.h6, "CACHE_SHA256", h6r.sha256_file(cache))
    with pytest.raises(h6r.HartleyH6RError, match="zero-degree parity PASS marker absent"):
        h6r.execute_member(
            REPO, Path(__file__), scratch, tmp_path / "unreached-runner", cache,
            "H6R_YAW_M050",
        )
    assert not (scratch / "01_NATIVE_RAW_H6R").exists()


def test_raw_full_payload_is_preserved_when_zero_parity_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setattr(h6r, "STATE_ROWS", 1)
    scratch = tmp_path / "scratch"
    raw = scratch / "01_NATIVE_RAW_H6R/H6R_YAW_000"
    raw.mkdir(parents=True)
    header = h6r.RAW_HEADER.pack(
        h6r.RAW_MAGIC, 1, h6r.RAW_HEADER.size, h6r.RAW_RECORD.size, 1, 0, 1, 2, 3,
    )
    record = h6r.RAW_RECORD.pack(1, 0, True, False, False, False,
                                  1.0, 2.0, 3.0, *([float("nan")] * 9))
    (raw / "CONTACT_STATE_FLOAT64.raw").write_bytes(header + record)
    payloads = {
        "CONTACT_STATE.csv": b"new-contact\n", "NAV.csv": b"nav\n",
        "CONTACT_EVENT_LEDGER.csv": b"events\n", "KINEMATIC_INNOVATIONS.csv": b"innov\n",
        "NIS_DIAGNOSTICS.csv": b"nis\n", "COVARIANCE_CHECKPOINT_INDEX.csv": b"index\n",
        "EXECUTION_LEDGER.csv": b"ledger\n", "RUNTIME.csv": b"runtime\n",
        "NATIVE_CONFIG.cfg": b"config\n",
    }
    for name, content in payloads.items():
        (raw / name).write_bytes(content)
    (raw / "COVARIANCE_CHECKPOINTS.bin").write_bytes(struct.pack("<Id", 1, 2.0))
    provenance = {
        key: False for key in (
            "synthetic_data_used", "semisynthetic_data_used", "trace_used_online",
            "receiver_imu_as_body_imu", "final_v23_output_solver_input", "LegSA_output_solver_input",
            "per_case_tuning", "output_only_correction", "epoch_deleted_for_metric",
        )
    }
    provenance.update({
        "data_mode": "real_by2_raw", "raw_source_sha256": "a" * 64,
        "prefix_sha256": "b" * 64, "cache_sha256": "c" * 64,
        "old_runtime_input_count": 0, "code_commit": h6r.TASK_START_HEAD,
        "config_hash": "d" * 64, "propagation_calls": 0, "eq61_calls": 0,
        "eq52_calls": 0, "scoped_source_manifest_sha256": "e" * 64,
        "native_executable_sha256": "f" * 64, "reference_open_count": 0,
        "trace_open_count": 0, "forbidden_value_decode_count": 0,
    })
    (raw / "NATIVE_SUMMARY.json").write_text(json.dumps(provenance))
    anchor = tmp_path / "anchor"
    anchor.mkdir()
    for name, content in payloads.items():
        if name not in {"RUNTIME.csv", "NATIVE_CONFIG.cfg"}:
            (anchor / name).write_bytes(b"old-contact\n" if name == "CONTACT_STATE.csv" else content)
    np.savez(anchor / "COVARIANCE_CHECKPOINTS.npz", covariance_0=np.asarray([[2.0]]))
    with pytest.raises(h6r.HartleyH6RError, match=h6r.BLOCKERS["zero"]):
        h6r.compact_and_verify_member(
            scratch, tmp_path / "cache", anchor, tmp_path / "original",
            {"raw": raw, "run_id": "H6R_YAW_000"},
        )
    freeze = json.loads((h6r._member_root(scratch, "H6R_YAW_000") / "MEMBER_FREEZE.json").read_text())
    assert freeze["raw_full_payload_deletion_authorized"] is False
    assert freeze["raw_full_payload_retained_on_failure"] is True
    assert raw.is_dir() and (raw / "CONTACT_STATE_FLOAT64.raw").is_file()
