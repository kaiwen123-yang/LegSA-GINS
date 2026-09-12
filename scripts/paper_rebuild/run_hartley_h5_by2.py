#!/usr/bin/env python3
"""Thin two-step H5 launcher with one immutable provider for all four runs."""

from __future__ import annotations

import argparse
import csv
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

REPOSITORY = Path(__file__).resolve().parents[2]


def _load_h5_isolated():
    """Load only the two Hartley modules required by H5.

    The public horizontal_literature package exports EXT01 and therefore its
    ``__init__`` has method-loading side effects.  A private package namespace
    preserves hartley_h5's relative import while never executing that package
    initializer or importing any unrelated literature implementation.
    """
    package_name = "_legsa_hartley_h5_isolated"
    package_path = (
        REPOSITORY / "src/legsa_gins/paper_rebuild/horizontal_literature"
    )
    package = types.ModuleType(package_name)
    package.__package__ = package_name
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package
    for basename in ("hartley_h0_h2", "hartley_h5"):
        qualified = f"{package_name}.{basename}"
        spec = importlib.util.spec_from_file_location(
            qualified, package_path / f"{basename}.py"
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot construct isolated H5 module spec: {basename}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
        setattr(package, basename, module)
    return sys.modules[f"{package_name}.hartley_h5"]


h5 = _load_h5_isolated()

PROVIDER_DIRECTORY = "00_PROVIDER"
RUNS_DIRECTORY = "01_RUNS"
PROVIDER_MANIFEST = "H5_INPUT_CACHE_MANIFEST.json"
TASK_START_HEAD = "b1b3b0ec5e5d811c1658541a98b660f326500ac3"
SCOPED_SOURCE_PATHS = (
    "scripts/paper_rebuild/run_hartley_h5_by2.py",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_h5.py",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/tools/run_h5.cpp",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/src/backend.cpp",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/include/hartley_inekf/backend.hpp",
    "src/legsa_gins/paper_rebuild/horizontal_literature/hartley_inekf/CMakeLists.txt",
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare-provider")
    prepare.add_argument("--paths-config", type=Path, required=True)
    prepare.add_argument("--attempt-root", type=Path, required=True)
    run = commands.add_parser("run")
    run.add_argument("--attempt-root", type=Path, required=True)
    run.add_argument("--native-executable", type=Path, required=True)
    run.add_argument("--run-id", choices=h5.H5_RUN_IDS, required=True)
    verify = commands.add_parser("verify-primary-gate")
    verify.add_argument("--attempt-root", type=Path, required=True)
    return parser.parse_args()


def _provider_paths(attempt: Path) -> tuple[Path, Path, Path]:
    provider = attempt / PROVIDER_DIRECTORY
    return provider / "H5_INPUT_CACHE.bin", provider / "H5_INPUT_CONTACT_EVENT_LEDGER.jsonl", provider / PROVIDER_MANIFEST


def _scoped_source_manifest() -> dict[str, object]:
    files = {}
    for relative in SCOPED_SOURCE_PATHS:
        path = REPOSITORY / relative
        files[relative] = {"size": path.stat().st_size, "sha256": h5.sha256_file(path)}
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    dirty = bool(subprocess.run(
        ["git", "status", "--porcelain", "--", *SCOPED_SOURCE_PATHS],
        cwd=REPOSITORY, check=True, capture_output=True, text=True,
    ).stdout.strip())
    return {
        "task_start_head": TASK_START_HEAD,
        "task_start_dirty_or_precommit": dirty,
        "later_final_commit_mapping": None,
        "files": files,
        "manifest_sha256": hashlib.sha256(canonical).hexdigest(),
    }


def _prepare(paths_config: Path, attempt: Path) -> dict[str, object]:
    if attempt.exists():
        raise h5.HartleyH5Error("H5 attempt root already exists")
    provider = attempt / PROVIDER_DIRECTORY
    runs = attempt / RUNS_DIRECTORY
    provider.mkdir(parents=True)
    runs.mkdir()
    source = h5.resolve_h5_source(paths_config)
    identity = h5.verify_source_identity(source)
    cache, ledger, manifest_path = _provider_paths(attempt)
    manifest = h5.build_immutable_cache(identity, cache, ledger)
    after = h5.verify_source_identity(source)
    manifest["raw_identity_before_cache"] = {
        "size": identity.raw_size, "sha256": identity.raw_sha256,
        "prefix_end_exclusive": identity.prefix_end_exclusive,
        "prefix_sha256": identity.prefix_sha256,
    }
    manifest["raw_identity_after_cache"] = {
        "size": after.raw_size, "sha256": after.raw_sha256,
        "prefix_end_exclusive": after.prefix_end_exclusive,
        "prefix_sha256": after.prefix_sha256,
    }
    manifest["raw_identity_before_after_cache_equal"] = (
        manifest["raw_identity_before_cache"] == manifest["raw_identity_after_cache"]
    )
    manifest["scoped_source_manifest"] = _scoped_source_manifest()
    h5.exclusive_write_bytes(
        manifest_path,
        [(json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode()],
    )
    return {"status": "PASS_H5_PROVIDER_PREPARED_ONCE", **manifest}


def _verify_provider(attempt: Path) -> tuple[Path, dict[str, object]]:
    cache, ledger, manifest_path = _provider_paths(attempt)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not cache.is_file() or not ledger.is_file():
        raise h5.HartleyH5Error("immutable H5 provider payload is incomplete")
    if h5.sha256_file(cache) != manifest.get("cache_sha256"):
        raise h5.HartleyH5Error("immutable H5 cache hash mismatch")
    if h5.sha256_file(ledger) != manifest.get("event_ledger_sha256"):
        raise h5.HartleyH5Error("immutable H5 event-ledger hash mismatch")
    if cache.stat().st_size != h5.CACHE_HEADER_SIZE + h5.H5_RECORD_COUNT * h5.CACHE_RECORD_SIZE:
        raise h5.HartleyH5Error("immutable H5 cache size mismatch")
    counters = manifest.get("semantic_read_counters", {})
    if counters.get("forbidden_or_audit_values_decoded") != 0:
        raise h5.HartleyH5Error("provider manifest reports forbidden-value decoding")
    if manifest.get("record_count") != h5.H5_RECORD_COUNT:
        raise h5.HartleyH5Error("provider manifest row count mismatch")
    if manifest.get("cache_size_bytes") != cache.stat().st_size:
        raise h5.HartleyH5Error("provider cache recorded size mismatch")
    if manifest.get("raw_identity_before_after_cache_equal") is not True:
        raise h5.HartleyH5Error("raw identity did not remain equal across cache generation")
    scoped = manifest.get("scoped_source_manifest")
    if not isinstance(scoped, dict) or scoped.get("manifest_sha256") != _scoped_source_manifest()["manifest_sha256"]:
        raise h5.HartleyH5Error("scoped H5 source manifest mismatch")
    header = h5.CACHE_HEADER_STRUCT.unpack(cache.read_bytes()[: h5.CACHE_HEADER_SIZE])
    if (header[0] != h5.CACHE_MAGIC or header[1:5] !=
            (1, h5.CACHE_HEADER_SIZE, h5.CACHE_RECORD_SIZE, manifest["record_count"])):
        raise h5.HartleyH5Error("provider cache header/schema mismatch")
    if (header[6], header[7]) != (manifest["first_timestamp_ns"], manifest["last_timestamp_ns"]):
        raise h5.HartleyH5Error("provider cache timestamp header mismatch")
    if header[8].hex() != manifest["raw_sha256"] or header[9].hex() != manifest["prefix_sha256"] or header[10].hex() != manifest["event_ledger_sha256"]:
        raise h5.HartleyH5Error("provider cache hash header mismatch")
    if manifest["record_count"] == h5.PRODUCTION_H5_RECORD_COUNT:
        production = (
            manifest["first_timestamp_ns"] == h5.PRODUCTION_BY2_FIRST_COMPLETE_TIMESTAMP_NS,
            manifest["last_timestamp_ns"] == h5.PRODUCTION_BY2_LAST_COMPLETE_TIMESTAMP_NS,
            manifest["frozen_transition_event_count_excluding_initial_add"] == h5.H5_FROZEN_TRANSITION_EVENT_COUNT,
        )
        if not all(production):
            raise h5.HartleyH5Error("post-run production provider count/timestamp/event gate failed")
    return cache, manifest


def _verify_frozen_files(run_directory: Path) -> dict[str, object]:
    freeze = json.loads((run_directory / "NATIVE_FREEZE.json").read_text(encoding="utf-8"))
    files = freeze.get("files")
    if not isinstance(files, dict):
        raise h5.HartleyH5Error("primary native freeze manifest is malformed")
    for name, identity in files.items():
        path = run_directory / name
        if (not path.is_file() or path.stat().st_size != identity.get("size") or
                h5.sha256_file(path) != identity.get("sha256")):
            raise h5.HartleyH5Error("primary native freeze file identity mismatch")
    return files


def _csv_rows(path: Path, expected_columns: tuple[str, ...]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != expected_columns:
            raise h5.HartleyH5Error(f"native CSV schema mismatch: {path.name}")
        rows = list(reader)
    if any(None in row for row in rows):
        raise h5.HartleyH5Error(f"native CSV malformed row: {path.name}")
    return rows


def _validate_native_outputs(run_directory: Path, expected_records: int) -> dict[str, object]:
    parsed = {name: _csv_rows(run_directory / name, columns)
              for name, columns in h5.OUTPUT_SCHEMAS.items()}
    nav = parsed["NAV.csv"]
    ledger = parsed["EXECUTION_LEDGER.csv"]
    covariance_rows = parsed["COVARIANCE_DIAGONALS.csv"]
    nis = parsed["NIS_DIAGNOSTICS.csv"]
    if not (len(nav) == len(ledger) == len(covariance_rows) == len(nis) == expected_records):
        raise h5.HartleyH5Error("native per-state output row-count mismatch")
    timestamps = [int(row["timestamp_ns"]) for row in nav]
    if any(b <= a for a, b in zip(timestamps, timestamps[1:])):
        raise h5.HartleyH5Error("native NAV chronology is not strict")
    contact_rows = parsed["CONTACT_STATE.csv"]
    if len(contact_rows) != 4 * expected_records:
        raise h5.HartleyH5Error("native contact-state row-count mismatch")
    contacts_by_row: dict[int, list[int]] = {}
    for index in range(expected_records):
        epoch = contact_rows[4 * index:4 * (index + 1)]
        if [int(row["leg_id"]) for row in epoch] != list(range(4)):
            raise h5.HartleyH5Error("native contact-state leg ordering mismatch")
        active_ids: list[int] = []
        for leg_id, row in enumerate(epoch):
            if int(row["row_index"]) != index or int(row["timestamp_ns"]) != timestamps[index]:
                raise h5.HartleyH5Error("native contact-state row/timestamp mismatch")
            if row["leg"] != ("FL", "FR", "RL", "RR")[leg_id] or row["active"] not in ("0", "1"):
                raise h5.HartleyH5Error("native contact-state identity/active mismatch")
            values = (row["contact_x"], row["contact_y"], row["contact_z"])
            if row["active"] == "1":
                if any(value == "" or not np.isfinite(float(value)) for value in values):
                    raise h5.HartleyH5Error("active contact state is blank or nonfinite")
                active_ids.append(leg_id)
            elif any(value != "" for value in values):
                raise h5.HartleyH5Error("inactive contact state fields must be blank")
        contacts_by_row[index] = active_ids

    base_columns = (
        "theta_x", "theta_y", "theta_z", "velocity_x", "velocity_y", "velocity_z",
        "position_x", "position_y", "position_z",
    )
    contact_columns = tuple(
        tuple(f"contact_{leg}_{axis}" for axis in "xyz") for leg in ("FL", "FR", "RL", "RR")
    )
    bias_columns = (
        "gyro_bias_x", "gyro_bias_y", "gyro_bias_z",
        "accel_bias_x", "accel_bias_y", "accel_bias_z",
    )
    gauge_columns = (
        "gauge_yaw_variance", "gauge_translation_x_variance",
        "gauge_translation_y_variance", "gauge_translation_z_variance",
    )
    for index, (nav_row, ledger_row, covariance_row) in enumerate(zip(nav, ledger, covariance_rows)):
        if int(nav_row["row_index"]) != index or int(ledger_row["input_row"]) != index or int(ledger_row["output_row"]) != index:
            raise h5.HartleyH5Error("native row-index conservation failed")
        if int(ledger_row["timestamp_ns"]) != timestamps[index]:
            raise h5.HartleyH5Error("native ledger/NAV timestamp mismatch")
        active = int(nav_row["active_contact_count"])
        dimension = int(nav_row["state_dimension"])
        if dimension != 15 + 3 * active or int(ledger_row["state_dimension"]) != dimension or int(covariance_row["dimension"]) != dimension:
            raise h5.HartleyH5Error("native active-contact/state-dimension mismatch")
        active_ids = contacts_by_row[index]
        expected_topology = "+".join(("FL", "FR", "RL", "RR")[leg] for leg in active_ids) or "NONE"
        if active != len(active_ids) or covariance_row["topology"] != expected_topology:
            raise h5.HartleyH5Error("native contact topology mismatch")
        if (int(covariance_row["row_index"]) != index or
                int(covariance_row["timestamp_ns"]) != timestamps[index]):
            raise h5.HartleyH5Error("native covariance-diagonal row/timestamp mismatch")
        nav_values = [float(nav_row[column]) for column in h5.OUTPUT_SCHEMAS["NAV.csv"][5:]]
        if not np.all(np.isfinite(nav_values)):
            raise h5.HartleyH5Error("native NAV state contains nonfinite values")
        populated = [*base_columns, *bias_columns, *gauge_columns]
        for leg_id, columns in enumerate(contact_columns):
            if leg_id in active_ids:
                populated.extend(columns)
            elif any(covariance_row[column] != "" for column in columns):
                raise h5.HartleyH5Error("inactive contact covariance fields must be blank")
        diagonal_values = np.asarray([float(covariance_row[column]) for column in populated])
        if (not np.all(np.isfinite(diagonal_values)) or
                np.min(diagonal_values) < -1.0e-12 * max(1.0, float(np.max(np.abs(diagonal_values))))):
            raise h5.HartleyH5Error("native covariance diagonal is nonfinite or negative")
        dt = float(ledger_row["dt_seconds"])
        if (index == 0 and dt != 0.0) or (index > 0 and not dt > 0.0):
            raise h5.HartleyH5Error("native execution-ledger dt contract failed")
    lifecycle_rows = [index for index, row in enumerate(ledger)
                      if int(row["add_mask"]) or int(row["remove_mask"])]
    expected_reasons = h5.checkpoint_reason_map(timestamps, lifecycle_rows)
    checkpoint_rows = parsed["COVARIANCE_CHECKPOINT_INDEX.csv"]
    if len(checkpoint_rows) != len(expected_reasons):
        raise h5.HartleyH5Error("checkpoint union count mismatch")
    expected_keys: list[str] = []
    dimensions: dict[str, int] = {}
    source_rows: dict[str, int] = {}
    for checkpoint_index, row in enumerate(checkpoint_rows):
        source_row = int(row["row_index"])
        key = row["npz_key"]
        if int(row["checkpoint_index"]) != checkpoint_index or key != f"covariance_{checkpoint_index}":
            raise h5.HartleyH5Error("checkpoint index/key sequence mismatch")
        if source_row not in expected_reasons or tuple(row["reason"].split(";")) != expected_reasons[source_row]:
            raise h5.HartleyH5Error("checkpoint reason union mismatch")
        if int(row["timestamp_ns"]) != timestamps[source_row]:
            raise h5.HartleyH5Error("checkpoint timestamp mismatch")
        expected_topology = covariance_rows[source_row]["topology"]
        if row["topology"] != expected_topology or int(row["dimension"]) != int(nav[source_row]["state_dimension"]):
            raise h5.HartleyH5Error("checkpoint topology/dimension mismatch")
        expected_keys.append(key)
        dimensions[key] = int(row["dimension"])
        source_rows[key] = source_row
    if (run_directory / "COVARIANCE_CHECKPOINTS.bin").exists():
        raise h5.HartleyH5Error("covariance intermediate survived conversion")
    with np.load(run_directory / "COVARIANCE_CHECKPOINTS.npz", allow_pickle=False) as archive:
        if archive.files != expected_keys:
            raise h5.HartleyH5Error("checkpoint NPZ key parity mismatch")
        for key in expected_keys:
            covariance = archive[key]
            dimension = dimensions[key]
            if covariance.shape != (dimension, dimension) or not np.all(np.isfinite(covariance)):
                raise h5.HartleyH5Error("checkpoint NPZ dimension/finiteness mismatch")
            scale = max(1.0, float(np.linalg.norm(covariance)))
            if float(np.linalg.norm(covariance - covariance.T)) / scale > 1.0e-12:
                raise h5.HartleyH5Error("checkpoint NPZ symmetry mismatch")
            eigenvalues = np.linalg.eigvalsh(0.5 * (covariance + covariance.T))
            if float(eigenvalues[0]) < -1.0e-12 * max(1.0, float(eigenvalues[-1])):
                raise h5.HartleyH5Error("checkpoint NPZ PSD mismatch")
            source_row = source_rows[key]
            row = covariance_rows[source_row]
            active_ids = contacts_by_row[source_row]
            expected_diagonal: dict[str, float] = {
                column: float(covariance[index, index])
                for index, column in enumerate(base_columns)
            }
            for contact_index, leg_id in enumerate(active_ids):
                for axis, column in enumerate(contact_columns[leg_id]):
                    offset = 9 + 3 * contact_index + axis
                    expected_diagonal[column] = float(covariance[offset, offset])
            bias_start = dimension - 6
            expected_diagonal.update({
                column: float(covariance[bias_start + index, bias_start + index])
                for index, column in enumerate(bias_columns)
            })
            projection, _ = h5.gauge_projection(dimension, active_ids)
            projected = np.diag(projection.T @ covariance @ projection)
            if any(float(row[column]) != value for column, value in expected_diagonal.items()):
                raise h5.HartleyH5Error("checkpoint NPZ/covariance-diagonal mapping mismatch")
            for column, value in zip(gauge_columns, map(float, projected)):
                serialized = float(row[column])
                ulp = max(abs(float(np.spacing(serialized))), abs(float(np.spacing(value))))
                if not np.isfinite(serialized) or abs(serialized - value) > 64.0 * ulp:
                    raise h5.HartleyH5Error("checkpoint NPZ/gauge-projection mapping mismatch")
    summary = json.loads((run_directory / "NATIVE_SUMMARY.json").read_text(encoding="utf-8"))
    if summary.get("covariance_checkpoint_count") != len(expected_keys):
        raise h5.HartleyH5Error("summary/checkpoint exact count mismatch")
    return {"summary": summary, "checkpoint_count": len(expected_keys)}


def _verify_primary(attempt: Path, provider_manifest: dict[str, object] | None = None) -> dict[str, object]:
    if provider_manifest is None:
        _, provider_manifest = _verify_provider(attempt)
    run_directory = attempt / RUNS_DIRECTORY / h5.H5_PRIMARY_RUN_ID
    _verify_frozen_files(run_directory)
    summary = _validate_native_outputs(run_directory, h5.H5_RECORD_COUNT)["summary"]
    exact = {
        "run_id": h5.H5_PRIMARY_RUN_ID,
        "backend_id": h5.H5_BACKEND_ID,
        "process_policy": "GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61",
        "sigma_fk_m": 0.010,
        "data_mode": "real_by2_raw",
        "state_rows": h5.H5_RECORD_COUNT,
        "propagation_calls": h5.H5_PROPAGATION_COUNT,
        "eq61_calls": h5.H5_PROPAGATION_COUNT,
        "eq52_calls": 0,
        "joint_encoder_adapter_call_count": 0,
        "dropped_input_rows": 0,
        "nonfinite_output_count": 0,
        "rotation_gate_failure_count": 0,
        "covariance_checkpoint_failure_count": 0,
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "reference_opened": False,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
    }
    mismatches = {key: (summary.get(key), value) for key, value in exact.items()
                  if summary.get(key) != value}
    if mismatches or summary.get("cache_sha256") != provider_manifest.get("cache_sha256"):
        raise h5.HartleyH5Error(f"primary native gate mismatch: {mismatches}")
    scoped = provider_manifest["scoped_source_manifest"]
    config_path = run_directory / "NATIVE_CONFIG.cfg"
    config_lines = config_path.read_text(encoding="utf-8").splitlines(keepends=True)
    config_values = dict(line.rstrip("\n").split("=", 1) for line in config_lines)
    recomputed = hashlib.sha256("".join(line for line in config_lines if not line.startswith("config_hash=")).encode()).hexdigest()
    bindings = {
        "config_hash": recomputed,
        "scoped_source_manifest_sha256": scoped["manifest_sha256"],
        "native_executable_sha256": config_values["native_executable_sha256"],
        "task_start_head": scoped["task_start_head"],
    }
    if any(summary.get(key) != value or config_values.get(key) != value for key, value in bindings.items()):
        raise h5.HartleyH5Error("primary source/binary/config provenance binding mismatch")
    return {"status": "PASS_H5_PRIMARY_NATIVE_GATE", "summary": summary}


def _sigma(run_id: str) -> float:
    return {"H5_FK05MM_SENSITIVITY": 0.005,
            "H5_FK20MM_SENSITIVITY": 0.020}.get(run_id, 0.010)


def _policy(run_id: str) -> str:
    return ("PAPER_TABLE1_FIVE_PROCESS_EQ61" if run_id ==
            "H5_PAPER_TABLE1_PROCESS_REGRESSION_WITH_GO2_FK_PROXY" else
            "GO2_CONTINUOUS_IMU_PAPER_NATIVE_CONTACT_EQ61")


def _convert_covariance(path: Path, destination: Path) -> None:
    arrays: dict[str, np.ndarray] = {}
    with path.open("rb") as handle:
        index = 0
        while (header := handle.read(4)):
            if len(header) != 4:
                raise h5.HartleyH5Error("truncated covariance intermediate header")
            dimension = struct.unpack("<I", header)[0]
            payload = handle.read(dimension * dimension * 8)
            if len(payload) != dimension * dimension * 8:
                raise h5.HartleyH5Error("truncated covariance intermediate matrix")
            arrays[f"covariance_{index}"] = np.frombuffer(payload, dtype="<f8").reshape(
                (dimension, dimension), order="F").copy()
            index += 1
    if not arrays:
        raise h5.HartleyH5Error("covariance intermediate is empty")
    for covariance in arrays.values():
        if not np.all(np.isfinite(covariance)):
            raise h5.HartleyH5Error("nonfinite covariance intermediate")
        scale = max(1.0, float(np.linalg.norm(covariance)))
        if float(np.linalg.norm(covariance - covariance.T)) / scale > 1.0e-12:
            raise h5.HartleyH5Error("asymmetric covariance intermediate")
        eigenvalues = np.linalg.eigvalsh(0.5 * (covariance + covariance.T))
        if float(eigenvalues[0]) < -1.0e-12 * max(1.0, float(eigenvalues[-1])):
            raise h5.HartleyH5Error("non-PSD covariance intermediate")
    np.savez(destination, **arrays)
    with np.load(destination, allow_pickle=False) as frozen:
        if set(frozen.files) != set(arrays) or any(
            not np.array_equal(frozen[name], arrays[name]) for name in arrays
        ):
            raise h5.HartleyH5Error("NPZ covariance conversion verification failed")
    path.unlink()


def _run(attempt: Path, executable: Path, run_id: str) -> dict[str, object]:
    cache, provider_manifest = _verify_provider(attempt)
    runs = attempt / RUNS_DIRECTORY
    if not runs.is_dir():
        raise h5.HartleyH5Error("H5 attempt runs directory is absent")
    if run_id not in h5.H5_RUN_IDS:
        raise h5.HartleyH5Error("unknown H5 run identity")
    entries = list(runs.iterdir())
    if any(not path.is_dir() for path in entries):
        raise h5.HartleyH5Error("unexpected preexisting entry in H5 runs directory")
    existing = {path.name for path in entries}
    if len(existing) != len(entries) or not existing.issubset(set(h5.H5_RUN_IDS)):
        raise h5.HartleyH5Error("unknown or duplicate preexisting H5 run directory")
    expected_prefix = set(h5.H5_RUN_IDS[:len(existing)])
    if existing != expected_prefix or len(existing) >= len(h5.H5_RUN_IDS):
        raise h5.HartleyH5Error("preexisting H5 runs do not form the exact preregistered prefix")
    expected_run = h5.H5_RUN_IDS[len(existing)]
    if run_id != expected_run:
        raise h5.HartleyH5Error(f"out-of-order H5 run: expected {expected_run}")
    for prior_run in h5.H5_RUN_IDS[:len(existing)]:
        _verify_frozen_files(runs / prior_run)
    if run_id != h5.H5_PRIMARY_RUN_ID:
        _verify_primary(attempt, provider_manifest)
    run_directory = runs / run_id
    run_directory.mkdir(exist_ok=False)
    config_path = run_directory / "NATIVE_CONFIG.cfg"
    code_commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPOSITORY,
                                 check=True, capture_output=True, text=True).stdout.strip()
    scoped = provider_manifest["scoped_source_manifest"]
    native_executable_sha256 = h5.sha256_file(executable.resolve(strict=True))
    later_mapping = (code_commit if code_commit != scoped["task_start_head"] and
                     not _scoped_source_manifest()["task_start_dirty_or_precommit"]
                     else "NOT_AVAILABLE_PRECOMMIT")
    config_base = (
        f"run_id={run_id}\nbackend_id={h5.H5_BACKEND_ID}\n"
        f"process_policy={_policy(run_id)}\nsigma_fk_m={_sigma(run_id):.3f}\n"
        f"expected_records={h5.H5_RECORD_COUNT}\n"
        f"cache_sha256={provider_manifest['cache_sha256']}\ncode_commit={code_commit}\n"
        f"task_start_head={scoped['task_start_head']}\n"
        f"task_start_dirty_or_precommit={str(scoped['task_start_dirty_or_precommit']).lower()}\n"
        f"scoped_source_manifest_sha256={scoped['manifest_sha256']}\n"
        f"native_executable_sha256={native_executable_sha256}\n"
        f"later_final_commit_mapping={later_mapping}\n"
    )
    config_text = config_base + f"config_hash={hashlib.sha256(config_base.encode()).hexdigest()}\n"
    h5.exclusive_write_bytes(config_path, [config_text.encode()])
    environment = dict(os.environ)
    for key in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        environment[key] = "1"
    h5.verify_single_thread_environment(environment)
    subprocess.run([str(executable.resolve(strict=True)), str(cache), str(config_path),
                    str(run_directory)], check=True, env=environment)
    if h5.sha256_file(executable.resolve(strict=True)) != native_executable_sha256:
        raise h5.HartleyH5Error("native executable changed across launch interval")
    _convert_covariance(run_directory / "COVARIANCE_CHECKPOINTS.bin",
                        run_directory / "COVARIANCE_CHECKPOINTS.npz")
    _validate_native_outputs(run_directory, h5.H5_RECORD_COUNT)
    h5.freeze_native_outputs(run_directory)
    return {"status": "PASS_H5_NATIVE_ONLY", "run_id": run_id,
            "cache_sha256": provider_manifest["cache_sha256"]}


def main() -> int:
    args = _arguments()
    if args.command == "prepare-provider":
        result = _prepare(args.paths_config, args.attempt_root)
    elif args.command == "run":
        result = _run(args.attempt_root, args.native_executable, args.run_id)
    else:
        result = _verify_primary(args.attempt_root)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
