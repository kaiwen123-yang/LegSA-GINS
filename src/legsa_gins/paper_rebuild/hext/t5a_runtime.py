"""T5a bounded, no-retry native and offline evaluator execution.

The controller verifies the preregistration/code-freeze receipt and the per-sequence
frozen-table/raw checkpoints. This module owns immutable runtime inputs, a durable
launch reservation, native file-access audit, D8, and same-run NAV/STD evaluation.
All output is independent of the frozen v2.1 chain.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Mapping

import numpy as np
import yaml

from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_parity.evaluation import body_frame_bias, transform_nav, write_transformed_nav
from ..clean5_parity_p04.evaluation import metrics as window_metrics
from ..clean5_sequence.evaluation_process import EVALUATOR_SHA256, evaluate, write_json
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..clean5_sequence.solver_validation import CONFIG_FLAG_TO_MANIFEST
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group

BINARY_SHA256 = "96ae436d82ba8922c68382bd73fc42c8bf4bcb22d72a43a8bd05f506043a9c1c"
STAGE = "CLEAN7_T5A_HEADING_SENSITIVITY"
POLICY = "canonical_v2_wgs84_full_support"
STD_POLICY = "SAME_T5A_NATIVE_STD_UNMODIFIED"
SELECTED_COLUMNS = {name: name for name in ("time", "lat", "lon", "height", "roll", "pitch", "yaw")}
PROVIDER_KEYS = ("gnsspath", "imupath", "raw_doppler_factor_path", "go2_attitude_prior_path",
                 "go2_horizontal_velocity_prior_path")
FLAGS = {"synthetic_data_used": False, "semisynthetic_data_used": False, "trace_used_online": False,
         "receiver_imu_as_body_imu": False, "final_v23_output_solver_input": False,
         "LegSA_output_solver_input": False, "per_case_tuning": False, "output_only_correction": False,
         "epoch_deleted_for_metric": False, "old_runtime_input_count": 0}

def _write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _safe(path):
    path = Path(path)
    if ".." in path.parts or any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("T5a sensitivity path must not traverse symlinks")
    return path.absolute()


def _within(path, root):
    return path == root or root in path.parents


def _pinned(path, expected):
    path = _safe(path)
    if not path.is_file() or sha256_file(path) != expected:
        raise RuntimeError("HARD_STOP_SENSITIVITY_INPUT_IDENTITY: " + str(path))
    return {"path": str(path), "sha256": expected, "size_bytes": path.stat().st_size}


def native_argv(binary, config_path, output_root):
    return [str(binary), "--config", str(config_path), "--output-dir", str(output_root),
            "--debug-update-timeline", "--debug-output-dir", str(output_root), "--debug-max-rows", "1000000"]


def read_native_numeric(path, *, columns=None):
    rows, lines = [], []
    with _safe(path).open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip() or line.lstrip().startswith(("%", "#")):
                continue
            values = [float(token) for token in line.replace(",", " ").split()]
            if (columns is not None and len(values) != columns) or rows and len(values) != len(rows[0]):
                raise ValueError("native numeric output column count differs: " + str(path))
            rows.append(values)
            lines.append(number)
    return np.asarray(rows, dtype=float), lines


def fixed_first_ned(lla):
    """WGS84 LLA -> ECEF -> one NED frame fixed at the first output epoch."""
    from ..clean5_sequence.evaluator_identity import ELLIPSOID_A, ELLIPSOID_E2
    values = np.asarray(lla, float)
    lat, lon = np.deg2rad(values[:, 0]), np.deg2rad(values[:, 1])
    height = values[:, 2]
    sl, cl, so, co = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
    radius = ELLIPSOID_A / np.sqrt(1 - ELLIPSOID_E2 * sl * sl)
    xyz = np.column_stack(((radius + height) * cl * co, (radius + height) * cl * so,
                           (radius * (1 - ELLIPSOID_E2) + height) * sl))
    rotation = np.array([[-sl[0] * co[0], -sl[0] * so[0], cl[0]],
                         [-so[0], co[0], 0.0], [-cl[0] * co[0], -cl[0] * so[0], -sl[0]]])
    return (xyz - xyz[0]) @ rotation.T


def bounded_lla_native(nav_path, *, expected_sha256):
    _pinned(nav_path, expected_sha256)
    nav, lines = read_native_numeric(nav_path, columns=11)
    if not len(nav):
        raise ValueError("empty native NAV has no boundedness evidence")
    finite = np.isfinite(nav).all(axis=1)
    with np.errstate(invalid="ignore", over="ignore"):
        ned = fixed_first_ned(nav[:, 2:5])
        position = np.hypot.reduce(ned, axis=1)
        speed = np.hypot.reduce(nav[:, 5:8], axis=1)
        height = np.abs(nav[:, 4] - nav[0, 4])
    observed = {"position_displacement_m": position, "speed_mps": speed, "height_displacement_m": height}
    bounds = {"position_displacement_m": 1e4, "speed_mps": 50., "height_displacement_m": 1e3}
    valid_lla = (np.abs(nav[:, 2]) <= 90) & (np.abs(nav[:, 3]) <= 180)
    bad = ~finite | ~valid_lla
    maxima = {}
    for key, values in observed.items():
        bad |= ~np.isfinite(values) | (values > bounds[key])
        support = values[np.isfinite(values)]
        maxima[key] = float(np.max(support)) if len(support) else "NONFINITE"
    indices = np.flatnonzero(bad)
    first = None
    if len(indices):
        i = int(indices[0])
        reasons = ([] if finite[i] else ["NONFINITE_NUMERIC_NATIVE_ROW"]) + ([] if valid_lla[i] else ["INVALID_LLA_COORDINATES"])
        reasons += [key for key, values in observed.items() if not np.isfinite(values[i]) or values[i] > bounds[key]]
        first = {"data_row_one_based": i + 1, "file_line_one_based": lines[i],
                 "time_seconds": float(nav[i, 1]) if np.isfinite(nav[i, 1]) else "NONFINITE", "reasons": reasons,
                 **{key: float(values[i]) if np.isfinite(values[i]) else "NONFINITE" for key, values in observed.items()}}
    return {"passed": not len(indices), "failure_classification": "NONE" if not len(indices) else "ALGORITHM_FAILURE_DIVERGED",
            "row_count": len(nav), "all_numeric_rows_finite": bool(finite.all()), "bounds": bounds, "maxima": maxima,
            "first_violation": first, "source_nav_sha256": expected_sha256,
            "position_definition": "WGS84 LLA -> ECEF -> NED fixed at first native output epoch; Euclidean displacement",
            "height_definition": "absolute geodetic height minus first native geodetic height",
            "metric_epoch_deletion": False}


def _enabled_inputs(config):
    result = {"propagation_imu": ("imupath", "source_backed_propagation"),
              "gnss_position_receiver_velocity_dual_yaw": ("gnsspath", "validity_gated_measurements")}
    for flag, role, key, purpose in (
        ("enable_raw_doppler", "raw_doppler_velocity", "raw_doppler_factor_path", "source_backed_auxiliary_velocity"),
        ("enable_go2_roll_pitch_prior", "go2_roll_pitch_weak_prior", "go2_attitude_prior_path", "weak_prior_not_truth"),
        ("enable_go2_horizontal_velocity_prior", "go2_horizontal_velocity_weak_prior", "go2_horizontal_velocity_prior_path", "horizontal_weak_prior_not_truth")):
        if config[flag]:
            result[role] = (key, purpose)
    return result


def validate_native_identity(manifest, config):
    expected = {key: config[key] for key in ("run_id", "stage_id", "protocol_id", "case_id", "algorithm_id", "data_mode")}
    expected.update({native: config[key] for key, native in CONFIG_FLAG_TO_MANIFEST.items()})
    expected.update(FLAGS)
    expected.update(phase=config["stage_id"], port_role=config["runtime_role"])
    mismatches = [key for key, value in expected.items() if type(manifest.get(key)) is not type(value) or manifest[key] != value]
    inputs = _enabled_inputs(config)
    paths = {role: config[key] for role, (key, _purpose) in inputs.items()}
    roles = {role: purpose for role, (_key, purpose) in inputs.items()}
    if manifest.get("actual_solver_input_paths") != paths or manifest.get("actual_solver_input_roles") != roles:
        mismatches.append("actual_solver_input_paths_or_roles")
    if mismatches:
        raise RuntimeError("HARD_STOP_SENSITIVITY_NATIVE_IDENTITY: " + ",".join(mismatches))
    return {"passed": True, "retained_native_run_id": config["run_id"], "actual_solver_input_paths": paths}


def audit_native_access(log, sequence, output_root, config, binary, scratch_root=None):
    records = audited_open_records(log, sequence.code_root)
    expected = {str(_safe(config[key])) for key, _purpose in _enabled_inputs(config).values()}
    raw = [row for row in records if _within(Path(row["path"]), sequence.raw_root)]
    bag_fpl = [row for row in records if Path(row["path"]).suffix.lower() in (".bag", ".fpl")]
    protected_inputs = [sequence.clean_root] + ([Path(scratch_root)] if scratch_root is not None else [])
    unexpected = [row for row in records if any(_within(Path(row["path"]), root) for root in protected_inputs)
                  and row["path"] not in expected and not _within(Path(row["path"]), output_root)]
    opened = {row["path"] for row in records if row["return_code"] >= 0 and "O_RDONLY" in row["flags"]}
    scope = write_scope_audit(records, raw_root=sequence.raw_root, clean_root=sequence.clean_root, allowed_write_roots=[output_root])
    executions = [line for line in Path(log).read_text().splitlines() if "execve(" in line]
    evaluator = [line for line in executions if "evaluate_nav_trace" in line]
    native = [line for line in executions if str(binary) in line]
    violation = bool(raw or bag_fpl or unexpected or evaluator or not scope["pass"] or len(native) > 1)
    passed = not violation and expected <= opened and len(native) == 1
    return {"passed": passed, "violation_detected": violation,
            "raw_open_count": len(raw), "trace_open_count": sum(Path(row["path"]) == sequence.trace for row in raw),
            "bag_fpl_open_count": len(bag_fpl), "evaluator_invocation_count": len(evaluator), "native_exec_count": len(native),
            "missing_enabled_inputs": sorted(expected - opened), "unexpected_clean_input_opens": unexpected,
            "raw_open_records": raw, "write_scope": scope, "strace_sha256": sha256_file(log)}


class _UnavailableNative(Exception):
    """An ordinary native failure retained for row-level fail-soft reporting."""

    def __init__(self, classification, reason):
        self.classification = classification
        super().__init__(reason)


def _seal_summary(root, record, started):
    files = {path.name: sha256_file(_safe(path)) for path in sorted(root.iterdir()) if path.is_file()}
    nav, std = root / "KF_GINS_Navresult.nav", root / "KF_GINS_STD.txt"
    _write(root / "OUTPUT_SEAL.json", {"status": "SEALED", "files": files, "config_hash": record["config_hash"],
            "NAV": nav.name if nav.name in files else "UNAVAILABLE",
            "STD": std.name if std.name in files else "UNAVAILABLE", "same_native_invocation": True})
    record.update(file_hashes={**files, "OUTPUT_SEAL.json": sha256_file(root / "OUTPUT_SEAL.json")},
                  trace_open_count=record.get("access_audit", {}).get("trace_open_count", "UNAVAILABLE"),
                  runtime_seconds=time.monotonic() - started)
    for role, path in (("nav", nav), ("std", std)):
        if path.name in files:
            record[role + "_path"] = str(path)
            record[role + "_sha256"] = files[path.name]
    summary = root / "T5A_NATIVE_SUMMARY.json"
    _write(summary, record)
    return {**record, "native_summary": {"path": str(summary), "sha256": sha256_file(summary)}}


def _output_path(path, sequence, scratch_root):
    path, scratch = _safe(path), _safe(scratch_root)
    archive = _safe(sequence.clean_root) / "stages" / STAGE
    if any(_within(scratch, root) for root in (_safe(sequence.raw_root), _safe(sequence.clean_root))):
        raise ValueError("T5a scratch must be outside raw/archive roots")
    if not (scratch in path.parents or archive in path.parents):
        raise ValueError("T5a output must be below registered scratch or new archive root")
    return path


def _runtime_mapping(payload):
    class UniqueLoader(yaml.SafeLoader):
        pass
    def unique(loader, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in mapping:
                raise ValueError("duplicate runtime configuration key: " + str(key))
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique)
    value = yaml.load(payload, Loader=UniqueLoader)
    if not isinstance(value, dict) or "gnsspath" not in value:
        raise ValueError("runtime configuration must contain gnsspath")
    return value


def _field_hash(config):
    payload = json.dumps({key: value for key, value in config.items() if key != "gnsspath"},
                         sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def clone_runtime_config(frozen_bytes, *, expected_sha256, gnsspath):
    if hashlib.sha256(frozen_bytes).hexdigest() != expected_sha256:
        raise RuntimeError("HARD_STOP_T5A_FROZEN_CONFIG_IDENTITY")
    if not isinstance(gnsspath, str) or not gnsspath or "\n" in gnsspath or "\r" in gnsspath:
        raise ValueError("invalid replacement gnsspath")
    frozen = _runtime_mapping(frozen_bytes)
    changed = {**frozen, "gnsspath": gnsspath}
    payload = yaml.safe_dump(changed, allow_unicode=True, sort_keys=False).encode()
    copied = _runtime_mapping(payload)
    before, after = _field_hash(frozen), _field_hash(copied)
    if before != after:
        raise RuntimeError("HARD_STOP_T5A_NON_GNSS_CONFIG_HASH")
    return payload, {"passed": True, "non_gnsspath_sha256_before": before,
                     "non_gnsspath_sha256_after": after, "changed_fields": ["gnsspath"],
                     "frozen_config_sha256": expected_sha256,
                     "config_sha256": hashlib.sha256(payload).hexdigest(),
                     "enable_multi_state_qm": copied.get("enable_multi_state_qm"),
                     "enable_qa_fallback": copied.get("enable_qa_fallback")}


def reserve_slot(path, run_id, allowed_run_ids, *, kind):
    """Consume one fsynced no-retry slot before launch, even if launch fails."""
    budget = {"native": 16, "evaluator": 32}.get(kind)
    allowed = set(allowed_run_ids)
    if budget is None or not allowed or len(allowed) > budget or run_id not in allowed:
        raise PermissionError("unregistered T5a launch reservation or invalid budget")
    path = _safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        rows = [json.loads(line) for line in stream.read().splitlines()]
        if any(row.get("run_id") not in allowed or row.get("kind") != kind for row in rows):
            raise RuntimeError("HARD_STOP_T5A_RESERVATION_LEDGER_SCOPE")
        if len({row["run_id"] for row in rows}) != len(rows):
            raise RuntimeError("HARD_STOP_T5A_RESERVATION_DUPLICATE_HISTORY")
        if any(row["run_id"] == run_id for row in rows):
            raise RuntimeError("HARD_STOP_T5A_ALREADY_RESERVED_NO_RETRY")
        if len(rows) >= min(budget, len(allowed)):
            raise RuntimeError("HARD_STOP_T5A_BUDGET")
        entry = {"status": "RESERVED_BEFORE_LAUNCH", "kind": kind, "run_id": run_id,
                 "ordinal": len(rows) + 1, "budget": budget, "retry_count": 0}
        stream.write(json.dumps(entry) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return entry


def _non_yaw_gate(frozen, candidate):
    old, new = frozen.splitlines(keepends=True), candidate.splitlines(keepends=True)
    if len(old) != len(new):
        raise RuntimeError("HARD_STOP_T5A_D3_ROW_COUNT")
    for index, (left, right) in enumerate(zip(old, new)):
        if not left.strip() or left.lstrip().startswith((b"%", b"#")):
            if left != right:
                raise RuntimeError("HARD_STOP_T5A_D3_HEADER_BYTES")
            continue
        a, b = list(re.finditer(rb"\S+", left)), list(re.finditer(rb"\S+", right))
        if len(a) != 18 or len(b) != 18:
            raise RuntimeError("HARD_STOP_T5A_D3_GNSS18_WIDTH")
        def masked(line, spans):
            parts, cursor = [], 0
            for column in (13, 14, 17):
                span = spans[column]
                parts.extend((line[cursor:span.start()], b"<YAW>"))
                cursor = span.end()
            return b"".join(parts) + line[cursor:]
        if masked(left, a) != masked(right, b):
            raise RuntimeError("HARD_STOP_T5A_D3_NON_YAW_BYTE_DIFFERENCE_ROW_" + str(index + 1))
        if b[14].group() != b"2.933193" or b[17].group() not in (b"0", b"1"):
            raise RuntimeError("HARD_STOP_T5A_D3_STD_OR_VALIDITY")
        yaw = float(b[13].group())
        if not np.isfinite(yaw) or not 0 <= yaw < 360:
            raise RuntimeError("HARD_STOP_T5A_D3_NONFINITE_OR_UNWRAPPED_YAW")
    return {"passed": True, "rows_including_headers": len(old), "changed_columns": [13, 14, 17]}


def verify_native_inputs(sequence, *, contract, frozen_config_path, expected_config_sha256,
                         frozen_provider_hashes, prepared_gnss, scratch_root, slot_identity):
    cfg_id = slot_identity["configuration_id"]
    variant = slot_identity["variant"]
    if (slot_identity["sequence_id"] != sequence.sequence_id or cfg_id not in ("F02", "F04")
            or variant not in (("R1", "R5", "R1F", "R5F") if sequence.sequence_id == "BY2O" else ("R1", "R5"))
            or sequence.sequence_id not in ("BY2", "BY2H", "BY2O")):
        raise PermissionError("unregistered T5a matrix slot")
    frozen = contract["frozen"]
    declared = frozen["runtime_configs"][sequence.sequence_id + "_" + cfg_id]
    if declared["sha256"] != expected_config_sha256:
        raise RuntimeError("HARD_STOP_T5A_CONFIG_REGISTRATION")
    config_identity = _pinned(frozen_config_path, expected_config_sha256)
    original_bytes = Path(frozen_config_path).read_bytes()
    original = _runtime_mapping(original_bytes)
    if original["run_id"] != declared["run_id"]:
        raise RuntimeError("HARD_STOP_T5A_FROZEN_CONFIG_RUN_ID")
    if set(frozen_provider_hashes) != set(PROVIDER_KEYS):
        raise RuntimeError("HARD_STOP_T5A_PROVIDER_ROLE_SET")
    providers = {key: _pinned(original[key], frozen_provider_hashes[key]) for key in PROVIDER_KEYS}
    if frozen_provider_hashes["gnsspath"] != frozen["gnss18_sha256"][sequence.sequence_id]:
        raise RuntimeError("HARD_STOP_T5A_FROZEN_GNSS_IDENTITY")
    replacement = _output_path(prepared_gnss["path"], sequence, scratch_root)
    if prepared_gnss.get("byte_gate", {}).get("passed") is not True:
        raise RuntimeError("HARD_STOP_T5A_MISSING_PROVIDER_VALIDITY_GATE")
    prepared = _pinned(replacement, prepared_gnss["sha256"])
    byte_gate = _non_yaw_gate(Path(original["gnsspath"]).read_bytes(), replacement.read_bytes())
    binary = _safe(sequence.code_root) / "build/p13_v21_cpp/legsa_v23_port_core_demo"
    if frozen["executable"]["sha256"] != BINARY_SHA256:
        raise RuntimeError("HARD_STOP_T5A_BINARY_REGISTRATION")
    binary_identity = _pinned(binary, BINARY_SHA256)
    if not os.access(binary, os.X_OK):
        raise RuntimeError("HARD_STOP_T5A_BINARY_NOT_EXECUTABLE")
    cloned, config_gate = clone_runtime_config(original_bytes, expected_sha256=expected_config_sha256,
                                               gnsspath=str(replacement))
    identity = {"frozen_runtime_config": config_identity, "frozen_providers": providers,
                "prepared_gnss": prepared, "frozen_binary": binary_identity,
                "heading_byte_gate": byte_gate, "provider_validity_gate": prepared_gnss["byte_gate"],
                "config_gate": config_gate}
    return identity, cloned, _runtime_mapping(cloned)


def run_native(sequence, *, contract, frozen_config_path, expected_config_sha256,
               frozen_provider_hashes, prepared_gnss, output_root, scratch_root, code_commit,
               slot_identity, launch_ledger, allowed_run_ids, raw_source_hashes=None):
    """Launch one authorized native; parent owns code freeze and sequence checkpoints."""
    if not re.fullmatch(r"[0-9a-f]{40}", code_commit):
        raise ValueError("T5a execution requires a full code-freeze commit")
    specification = dict(slot_identity)
    if specification["run_id"] not in set(allowed_run_ids):
        raise PermissionError("unregistered T5a run identity")
    root = _output_path(output_root, sequence, scratch_root)
    expected = _safe(scratch_root) / "03_NATIVE" / sequence.sequence_id / specification["configuration_id"] / specification["variant"]
    if root != expected or root.exists():
        raise FileExistsError("T5a native output must be new exact scratch slot; no previous attempt")
    ledger = _output_path(launch_ledger, sequence, scratch_root)
    verify_kwargs = dict(contract=contract, frozen_config_path=frozen_config_path,
                         expected_config_sha256=expected_config_sha256,
                         frozen_provider_hashes=frozen_provider_hashes,
                         prepared_gnss=prepared_gnss, scratch_root=scratch_root,
                         slot_identity=specification)
    identities, config_bytes, config = verify_native_inputs(sequence, **verify_kwargs)
    root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    record = {**FLAGS, **specification, "data_mode": "real_raw_heading_sensitivity_outside_v21",
              "code_commit": code_commit, "contract_canonical_json_sha256": hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest(),
              "config_hash": identities["config_gate"]["config_sha256"], "input_identities": identities,
              "raw_source_hashes": dict(raw_source_hashes or {}),
              "provider_hashes": {**{key: value["sha256"] for key, value in identities["frozen_providers"].items()},
                                  "gnsspath": identities["prepared_gnss"]["sha256"]},
              "native_run_id_retained": config["run_id"], "frozen_outputpath_retained": config["outputpath"],
              "output_root": str(root), "native_invocation_count": 0, "evaluator_invocation_count": 0,
              "performance_table_admission": False, "retry_count": 0, "geometry_status": "NOT_APPLICABLE"}
    try:
        _write(root / "INPUT_IDENTITIES.json", identities)
        config_path = root / "T5A_RUNTIME_CONFIG.yaml"
        with config_path.open("xb") as stream:
            stream.write(config_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        _write(root / "LAUNCH_RESERVATION.json", reserve_slot(ledger, specification["run_id"], allowed_run_ids, kind="native"))
        record["native_invocation_count"] = 1
        log = root / "NATIVE_OPENAT.strace"
        binary = Path(identities["frozen_binary"]["path"])
        argv = native_argv(binary, config_path, root)
        command = ["env", "OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1", "MKL_NUM_THREADS=1", "NUMEXPR_NUM_THREADS=1",
                   "strace", "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat,execve", "-o", str(log), *argv]
        _write(root / "RUN_STARTED.json", {**record, "native_argv": argv, "status": "NATIVE_RESERVED"})
        completed, process_error = None, None
        try:
            completed = run_process_group(command, cwd=sequence.code_root, timeout_seconds=1800,
                timeout_message="T5a native timeout; no retry", launch_failure_message="T5a native launch failed")
        except (OSError, RuntimeError, TimeoutError) as exc:
            process_error = {"type": type(exc).__name__, "message": str(exc)}
        for filename, text in (("stdout.log", completed.stdout if completed is not None else ""),
                               ("stderr.log", completed.stderr if completed is not None else str(process_error))):
            with (root / filename).open("x", encoding="utf-8") as stream:
                stream.write(text)
        record["exit_code"] = completed.returncode if completed is not None else "UNAVAILABLE"
        record["process_error"] = process_error
        if _safe(log).is_file():
            try:
                record["access_audit"] = audit_native_access(log, sequence, root, config, binary, scratch_root)
            except (OSError, ValueError, SyntaxError) as exc:
                record["access_audit"] = {"passed": False, "status": "UNAVAILABLE_ACCESS_AUDIT",
                                          "reason": str(exc), "trace_open_count": "UNAVAILABLE"}
        else:
            record["access_audit"] = {"passed": False, "status": "UNAVAILABLE_ACCESS_AUDIT",
                                      "reason": "native access log missing", "trace_open_count": "UNAVAILABLE"}
        _write(root / "NATIVE_ACCESS_AUDIT.json", record["access_audit"])
        # Recheck inputs even if the native exits unsuccessfully; no old file is modified.
        post, post_config, _ = verify_native_inputs(sequence, **verify_kwargs)
        if post != identities or post_config != config_bytes or config_path.read_bytes() != config_bytes:
            raise RuntimeError("HARD_STOP_SENSITIVITY_INPUT_OR_CONFIG_DRIFT")
        if record["access_audit"].get("violation_detected"):
            raise RuntimeError("HARD_STOP_SENSITIVITY_NATIVE_ACCESS_VIOLATION")
        if record["access_audit"].get("passed") is not True:
            raise RuntimeError("HARD_STOP_T5A_NATIVE_ACCESS_AUDIT: native access evidence is missing, malformed, or incomplete")
        nav, std, manifest_path = root / "KF_GINS_Navresult.nav", root / "KF_GINS_STD.txt", root / "RUN_MANIFEST.json"
        # A native identity mismatch remains a hard stop even on nonzero exit.
        native = None
        if _safe(manifest_path).is_file():
            try:
                native = json.loads(manifest_path.read_text())
            except (ValueError, OSError):
                pass
            if isinstance(native, dict):
                record["native_identity_audit"] = validate_native_identity(native, config)
        if completed is None or completed.returncode:
            raise _UnavailableNative("UNAVAILABLE_NATIVE_PROCESS_FAILED", "native process failed: " + str(record["exit_code"]))
        for path in (nav, std, manifest_path):
            if not _safe(path).is_file():
                raise _UnavailableNative("UNAVAILABLE_NATIVE_OUTPUT_INVALID", "missing native output: " + path.name)
        if not isinstance(native, dict):
            raise _UnavailableNative("UNAVAILABLE_NATIVE_OUTPUT_INVALID", "native manifest is malformed or is not an object")
        try:
            gate = bounded_lla_native(nav, expected_sha256=sha256_file(nav))
        except (ValueError, OSError) as exc:
            raise _UnavailableNative("UNAVAILABLE_NATIVE_OUTPUT_INVALID", "invalid native NAV: " + str(exc)) from exc
        record["bounded_gate"] = gate
        _write(root / "BOUNDED_OUTPUT_GATE.json", gate)
        if gate["passed"]:
            try:
                nav_rows, _ = read_native_numeric(nav, columns=11)
                std_rows, _ = read_native_numeric(std)
            except (ValueError, OSError) as exc:
                raise _UnavailableNative("UNAVAILABLE_NATIVE_OUTPUT_INVALID", "invalid native STD: " + str(exc)) from exc
            if (len(std_rows) != len(nav_rows) or std_rows.ndim != 2 or std_rows.shape[1] < 10
                    or not np.isfinite(std_rows).all() or not np.array_equal(std_rows[:, 0], nav_rows[:, 1])):
                raise _UnavailableNative("UNAVAILABLE_NATIVE_OUTPUT_INVALID", "STD/NAV alignment or finite-value gate failed")
            if (np.any(np.diff(nav_rows[:, 1]) <= 0)
                    or nav_rows[0, 1] < sequence.window[0] or nav_rows[-1, 1] > sequence.window[1]):
                raise _UnavailableNative("UNAVAILABLE_NATIVE_OUTPUT_INVALID", "native time support is unusable")
            record["std_nav_alignment"] = {"status": "PASS", "rows": len(nav_rows)}
        else:
            record["std_nav_alignment"] = {"status": "NOT_ADMITTED_ALGORITHM_FAILURE",
                                            "original_STD_bytes_sealed_without_evaluation": True}
        record.update(status="COMPLETED" if gate["passed"] else "ALGORITHM_FAILURE_DIVERGED",
                      failure_classification=gate["failure_classification"],
                      evaluator_status="PENDING_SEPARATE_OFFLINE_EVALUATION" if gate["passed"] else "NOT_RUN_ALGORITHM_FAILURE")
        return _seal_summary(root, record, started)
    except _UnavailableNative as exc:
        record.update(status=exc.classification, failure_classification=exc.classification,
                      evaluator_status="NOT_RUN_NATIVE_UNAVAILABLE", unavailable_reason=str(exc))
        return _seal_summary(root, record, started)
    except Exception as exc:
        record.update(status="HARD_STOP", error_type=type(exc).__name__, error=str(exc),
                      failure_classification="HARD_STOP", evaluator_status="NOT_RUN_HARD_STOP")
        _write(root / "HARD_STOP.json", {**record, "runtime_seconds": time.monotonic() - started})
        if record.get("access_audit", {}).get("passed") is not True:
            # Unknown access never implies zero trace opens. Preserve the failed
            # invocation and its exact artifacts before propagating the hard stop.
            _seal_summary(root, record, started)
        raise

def _checked(path, expected, role):
    path = Path(path)
    if any(item.is_symlink() for item in (path, *path.parents)) or not path.is_file():
        raise RuntimeError("HARD_STOP_SENSITIVITY_INPUT_MISSING_OR_SYMLINK: " + role)
    if sha256_file(path) != expected:
        raise RuntimeError("HARD_STOP_SENSITIVITY_INPUT_IDENTITY: " + role)


def _support(nav, window):
    start, end = map(float, window)
    if not np.isfinite([start, end]).all() or start >= end:
        raise ValueError("Invalid frozen sensitivity evaluation window")
    if (nav.ndim != 2 or nav.shape[1] != 11 or not len(nav)
            or not np.isfinite(nav).all() or np.any(np.diff(nav[:, 1]) <= 0)):
        raise ValueError("Sensitivity NAV must be finite chronological 11-column native output")
    if np.any((nav[:, 1] < start) | (nav[:, 1] > end)):
        raise ValueError("Sensitivity native NAV outside the frozen sequence window")
    return start, end


def _capture(result, sequence):
    audit, capture = result.get("audit", {}), result.get("capture", {})
    if (audit.get("passed") is not True or audit.get("exit_code") != 0
            or audit.get("trace_open_count") != 1
            or audit.get("bag_open_count") != 0 or audit.get("fpl_open_count") != 0
            or audit.get("write_scope", {}).get("pass") is not True):
        raise RuntimeError("HARD_STOP_SENSITIVITY_EVALUATOR_PROCESS_OR_ACCESS_AUDIT")
    if (capture.get("trace_sha256") != sequence.trace_sha256
            or capture.get("trace_handle_hash_count") != 1
            or capture.get("selected_columns") != SELECTED_COLUMNS
            or type(capture.get("consistency", {}).get("passed")) is not bool):
        raise RuntimeError("HARD_STOP_SENSITIVITY_EVALUATOR_CAPTURE_IDENTITY")
    return audit, capture


def evaluate_native(sequence, evaluator, nav, std, outdir, version,
                         identity: Mapping[str, Any], *, expected_nav_sha256,
                         expected_std_sha256, baseline_median_m, bounded_gate,
                         scratch_root, launch_ledger, allowed_run_ids, nav_input_root=None):
    """Evaluate one reserved v3/v2 slot and persist an H03-shaped result payload.

    ``bounded_gate`` must bind its passed D8 result through
    ``source_nav_sha256``. NAV and STD must be sealed outputs of the same new
    native directory. The STD is passed unchanged in both versions. A false
    consistency result is reportable UNAVAILABLE only after all technical
    audits pass; every other exception propagates to the parent's hard stop.
    """
    if version not in ("v3", "v2"):
        raise ValueError("Only preregistered v3 and v2 evaluations are allowed")
    nav, std, evaluator = map(Path, (nav, std, evaluator))
    reservation_id = identity["run_id"] + "__" + version
    if reservation_id not in set(allowed_run_ids):
        raise PermissionError("unregistered T5a evaluator slot")
    if nav.absolute().parent != std.absolute().parent:
        raise ValueError("Sensitivity NAV and STD must belong to the same native output directory")
    if (not isinstance(bounded_gate, Mapping) or bounded_gate.get("passed") is not True
            or bounded_gate.get("source_nav_sha256") != expected_nav_sha256):
        raise ValueError("Sensitivity evaluation requires a passed identity-bound native D8 gate")
    pins = ((nav, expected_nav_sha256, "native NAV"),
            (std, expected_std_sha256, "same-run native STD"),
            (evaluator, EVALUATOR_SHA256, "frozen evaluator"))
    for path, digest, role in pins:
        _checked(path, digest, role)
    original = canonical._read_numeric_table(nav).to_numpy(float)
    window = _support(original, sequence.window)
    if not np.isfinite(float(sequence.base_time)):
        raise ValueError("Invalid frozen sequence base_time")
    if not np.isfinite(float(baseline_median_m)) or float(baseline_median_m) <= 0:
        raise ValueError("Invalid frozen sensitivity baseline length")
    outdir = _output_path(outdir, sequence, scratch_root)
    transform_root = _output_path(nav_input_root if nav_input_root is not None else outdir / "NAV_INPUTS", sequence, scratch_root)
    if outdir.exists() or (version == "v3" and transform_root.exists()):
        raise FileExistsError("Sensitivity evaluation output already exists; no overwrite or retry")
    outdir.mkdir(parents=True, exist_ok=False)
    ledger = _output_path(launch_ledger, sequence, scratch_root)
    actual = nav
    transform = {"evaluator_contract": "evaluator_contract_" + version,
                 "input_sha256": expected_nav_sha256, "output_sha256": expected_nav_sha256,
                 "STD": STD_POLICY, "std_sha256": expected_std_sha256,
                 "std_transformed": False, "fit_used": False, "further_correction_used": False}
    if version == "v3":
        transform_root.mkdir(parents=True, exist_ok=False)
        actual = transform_root / "EVAL_NAV_V3.nav"
        write_transformed_nav(nav, actual, transform_nav(original, float(baseline_median_m)))
        transform.update(output_sha256=sha256_file(actual), baseline_median_m=float(baseline_median_m),
                         lever_frd_m=[.03, .03-float(baseline_median_m)/2, -.30],
                         changed_columns_zero_based=[2, 3, 4],
                         uncertainty_status="UNTRANSPORTED_STD_DIAGNOSTIC_ONLY")
        write_json(transform_root / "TRANSFORM_MANIFEST.json", transform)
    else:
        transform.update(changed_columns_zero_based=[], uncertainty_status="DIAGONAL_ONLY_NOT_FULL_NEES")
    actual_hash = transform["output_sha256"]
    try:
        _write(outdir / "LAUNCH_RESERVATION.json", reserve_slot(ledger, reservation_id, allowed_run_ids, kind="evaluator"))
        result = evaluate(evaluator=evaluator, trace=sequence.trace, nav=actual, std=std,
            outdir=outdir / "FROZEN_EVALUATOR", base_time=sequence.base_time, window=window,
            trace_sha256=sequence.trace_sha256, code_root=sequence.code_root,
            raw_root=sequence.raw_root, clean_root=sequence.clean_root,
            instrument=True, consistency_policy=POLICY, measure_resources=True)
        audit, capture = _capture(result, sequence)
        # The shared evaluator's audit covers technical failures only. Preserve
        # that fact and expose the separate consistency outcome to H03 readers.
        audit = {**audit, "technical_passed": True, "technical_failures": [],
                 "consistency_passed": capture["consistency"]["passed"]}
        evaluation_identity = {**identity, "sequence_id": sequence.sequence_id,
            "dataset_id": sequence.sequence_id, "evaluator_contract": "evaluator_contract_" + version,
            "evaluator_sha256": EVALUATOR_SHA256, "source_nav_sha256": expected_nav_sha256,
            "native_nav_sha256": expected_nav_sha256, "evaluator_nav_sha256": actual_hash,
            "std_sha256": expected_std_sha256, "trace_sha256": sequence.trace_sha256,
            "base_time": sequence.base_time, "evaluation_invoked": True,
            "STD": STD_POLICY, "trace_used_online": False,
            "sensitivity_only": True, "main_table_admission": False,
            "uncertainty_status": transform["uncertainty_status"]}
        # Callers provide identity metadata, never inherited scientific values.
        # Scrub result-looking fields so an unavailable slot cannot retain a stale metric.
        for key in list(evaluation_identity):
            if key.startswith(("east_", "north_", "up_", "down_", "horizontal_", "position_3d_",
                               "roll_", "pitch_", "yaw_", "h_rmse", "finite_", "coverage_",
                               "matched_epoch_", "unmatched_epoch_", "output_epoch_", "reference_epoch_")):
                del evaluation_identity[key]
        if capture["consistency"]["passed"] is False:
            row = {**evaluation_identity, "status": "UNAVAILABLE_EVALUATION_FAILED",
                "evaluation_status": "UNAVAILABLE_EVALUATION_FAILED",
                "failure_classification": "UNAVAILABLE_EVALUATION_FAILED", "metrics_admitted": False,
                "reason": "D12: passed native D8; evaluator consistency failed; no retry"}
            bias = {**evaluation_identity, "status": "UNAVAILABLE_EVALUATION_FAILED"}
        else:
            errors = canonical._read_error_series(Path(result["outdir"]))
            times = np.asarray(errors["time"], float)
            if (not len(times) or not np.isfinite(times).all() or np.any(np.diff(times) <= 0)
                    or np.any((times < window[0]) | (times > window[1]))):
                raise RuntimeError("HARD_STOP_SENSITIVITY_ERROR_SUPPORT_OUTSIDE_WINDOW_OR_UNORDERED")
            row = window_metrics(errors, original, evaluation_identity, window, capture.get("reference_epoch_count"))
            row.update(status="COMPLETED", failure_classification="NONE", metrics_admitted=True)
            bias = {**evaluation_identity, **body_frame_bias(errors, original), "status": "AVAILABLE"}
        row.update(evaluation_runtime_seconds=result["runtime_seconds"], error_series_source=result["outdir"],
                   sequence_window_start_s=window[0], sequence_window_end_s=window[1], retry_count=0)
        payload = {"row": row, "audit": audit, "transform": transform, "body_frame_bias": bias}
    except Exception as exc:
        _write(outdir / "HARD_STOP.json", {"status": "HARD_STOP", "run_id": reservation_id, "error": str(exc), "retry_count": 0})
        raise
    finally:
        for path, digest, role in pins:
            _checked(path, digest, role + " after evaluation")
        _checked(actual, actual_hash, "evaluation NAV after evaluation")
    write_json(outdir / "EVALUATION_RESULT.json", payload)
    files = {str(path.relative_to(outdir)): sha256_file(_safe(path)) for path in sorted(outdir.rglob("*")) if path.is_file()}
    _write(outdir / "OUTPUT_SEAL.json", {"files": files, "status": "SEALED", "version": version})
    return payload
