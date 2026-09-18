"""Bounded T5bc launch wrappers, closed while the contract is a draft.

The controller resolves contract aliases in memory and registers exact run specs.
No calibration, case selection, retry, provider generation, or identity evaluator
is implemented here. Importing this module performs no input/output or execution.
"""
from __future__ import annotations

import csv
from copy import deepcopy
import fcntl
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import time

import numpy as np

from . import t5bc_provider as provider
from .t5bc_config_fidelity import clone_config, compare_effective_echo, derive_expected_echo_from_witness, B3_ROLE, B3_PURPOSE
from .t5a_config_fidelity import decode_echo
from .t5a_runtime import (BINARY_SHA256, PROVIDER_KEYS, SELECTED_COLUMNS, POLICY,
                         _runtime_mapping, _enabled_inputs, _support, _capture,
                         bounded_lla_native, read_native_numeric, native_argv)
from ..canonical541 import offline_eval_aggregate as canonical
from ..clean5_degradation.runtime import expected_counts
from ..clean6_canonical_v2.runtime import classify_all_yaw_rejected, csv_rows
from ..clean5_parity.evaluation import body_frame_bias, transform_nav, write_transformed_nav
from ..clean5_parity_p04.evaluation import metrics as window_metrics
from ..clean5_sequence.evaluation_process import EVALUATOR_SHA256, evaluate
from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group

STAGE = "CLEAN7_T5BC_V3_CANDIDATE_PILOT"
STD_POLICY = "SAME_T5BC_NATIVE_STD_UNMODIFIED"
IDENTITY_KEYS = ("run_id", "sequence_id", "configuration_id", "variant", "subset_case_id")
PROVENANCE_FLAGS = {"trace_used_online": False, "receiver_imu_as_body_imu": False,
    "final_v23_output_solver_input": False, "LegSA_output_solver_input": False,
    "per_case_tuning": False, "output_only_correction": False, "epoch_deleted_for_metric": False,
    "old_runtime_input_count": 0}


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _safe(path):
    value = Path(path)
    if not value.is_absolute() or ".." in value.parts or any(p.is_symlink() for p in (value, *value.parents)):
        raise ValueError("T5bc requires absolute paths without symlinks or parent traversal")
    return value


def _within(path, root):
    return path == root or root in path.parents


def _write(path, value):
    path = _safe(path)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(_json(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def _pin(reference):
    if set(reference) != {"path", "sha256"} or not re.fullmatch(r"[0-9a-f]{64}", reference["sha256"]):
        raise ValueError("T5bc input references require exactly absolute path and full sha256")
    path = _safe(reference["path"])
    if not path.is_file() or sha256_file(path) != reference["sha256"]:
        raise RuntimeError("HARD_STOP_T5BC_INPUT_IDENTITY: " + str(path))
    return {**reference, "size_bytes": path.stat().st_size}


def _native_relative(spec):
    seq, cfg, variant, case = (spec[key] for key in ("sequence_id", "configuration_id", "variant", "subset_case_id"))
    if seq not in ("BY2", "BY2H", "BY2O") or cfg not in ("F02", "A04", "F04"):
        raise PermissionError("unregistered T5bc sequence/configuration")
    if variant == "IDENTITY":
        if seq != "BY2" or cfg not in ("F02", "F04") or case is not None:
            raise PermissionError("T5bc identity scope differs")
        return f"02_IDENTITY_GATE/{seq}/{cfg}"
    if variant not in ("R5", "R5W", "R5SIGMA", "B3") or (variant != "B3" and cfg != "F04"):
        raise PermissionError("T5bc variant/configuration scope differs")
    if case is not None:
        if seq != "BY2" or cfg != "F04" or not re.fullmatch(r"[A-Za-z0-9_-]+", case):
            raise PermissionError("T5bc subset case scope differs")
        return f"05_NATIVE_SUBSET61/{case}/{variant}"
    if variant == "R5":
        raise PermissionError("T5bc R5 rerun is subset-only")
    return f"04_NATIVE_C00_SEQ/{seq}/{cfg}/{variant}"


def validate_registration(contract, *, code_commit):
    """No file reads precede the ready/freeze and exact matrix checks."""
    if contract.get("execution_ready") is not True or contract.get("preregistered") is not True:
        raise PermissionError("T5BC_DRAFT_NOT_AUTHORIZED_FOR_EXECUTION")
    if (contract.get("task") != "T5bc" or contract.get("stage_id") != STAGE
            or not re.fullmatch(r"[0-9a-f]{40}", code_commit)
            or contract.get("code_freeze") != code_commit):
        raise PermissionError("T5BC_CODE_FREEZE_OR_STAGE_NOT_REGISTERED")
    budget = contract["budget"]
    names = ("subset_N", "matrix_native", "identity_native", "matrix_evaluator")
    if any(type(budget.get(key)) is not int or budget[key] < 0 for key in names):
        raise PermissionError("T5BC_EXPLICIT_INTEGER_BUDGET_REQUIRED")
    n = budget["subset_N"]
    if (n != 61 or budget["matrix_native"] != 259 or budget["identity_native"] != 2
            or budget["matrix_evaluator"] != 518 or budget.get("identity_evaluator") != 0):
        raise PermissionError("T5BC_BUDGET_FORMULA_MISMATCH")
    runs = contract["registered_runs"]
    identities, matrix, actual_slots, paths = [], [], set(), set()
    for run_id, spec in runs.items():
        if spec.get("run_id") != run_id or not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
            raise PermissionError("T5BC_RUN_ID_REGISTRATION")
        path = _native_relative(spec)
        if spec.get("output_relpath") != path or path in paths:
            raise PermissionError("T5BC_OUTPUT_SLOT_REGISTRATION")
        paths.add(path)
        actual_slots.add(tuple(spec[key] for key in IDENTITY_KEYS[1:]))
        (identities if spec["variant"] == "IDENTITY" else matrix).append(run_id)
    cases = contract["matrix"]["subset"]["case_ids"]
    exact_cases = ["C00_clean_normal"] + [f"D{i:02d}_seed_00" for i in range(1, 61)]
    if not isinstance(cases, list) or cases != exact_cases:
        raise PermissionError("T5BC_EXACT_SUBSET_NOT_REGISTERED")
    expected = {(seq, cfg, variant, None) for seq in ("BY2", "BY2H", "BY2O")
                for variant in ("R5W", "R5SIGMA", "B3")
                for cfg in (("F02", "A04", "F04") if variant == "B3" else ("F04",))}
    expected |= {("BY2", "F04", variant, case) for case in cases for variant in ("R5", "R5W", "R5SIGMA", "B3")}
    expected |= {("BY2", cfg, "IDENTITY", None) for cfg in ("F02", "F04")}
    if actual_slots != expected or len(matrix) != budget["matrix_native"] or len(identities) != 2:
        raise PermissionError("T5BC_EXACT_MATRIX_REGISTRATION_MISMATCH")
    evaluations = contract["registered_evaluator_ids"]
    wanted = {run_id + "__" + version for run_id in matrix for version in ("v3", "v2")}
    if len(evaluations) != budget["matrix_evaluator"] or set(evaluations) != wanted:
        raise PermissionError("T5BC_EXACT_EVALUATOR_REGISTRATION_MISMATCH")
    return {"matrix_native": matrix, "identity_native": identities, "evaluator": evaluations}, {
        "matrix_native": budget["matrix_native"], "identity_native": 2,
        "evaluator": budget["matrix_evaluator"]}


GENERATED_REFERENCE_KEYS = ("prepared_gnss", "sidecar", "prepared_raw_manifest")

def scientific_contract_sha256(contract):
    """Bind planned paths and science before provider payload hashes exist.

    Only new artifact digests are omitted; all frozen pins, model values,
    identities, evaluation settings, source provenance and paths stay bound.
    Each consumed slot separately binds its complete resolved run spec.
    """
    normalized = deepcopy(contract)
    for spec in normalized.get("registered_runs", {}).values():
        for key in GENERATED_REFERENCE_KEYS:
            if key in spec:
                spec[key]["sha256"] = None
    return hashlib.sha256(_json(normalized).encode()).hexdigest()


def expected_echo(run_spec, frozen_config_bytes):
    frozen = decode_echo(_safe(run_spec["frozen_echo"]["path"]).read_bytes())
    witness = run_spec.get("frozen_echo_witness")
    if witness is None:
        return frozen, {"status": "PINNED_FROZEN_RUN_ECHO"}
    if run_spec["subset_case_id"] != "D37_seed_00":
        raise RuntimeError("HARD_STOP_T5BC_ECHO_WITNESS_SCOPE")
    _pin(witness["config"])
    return derive_expected_echo_from_witness(frozen_config_bytes,
        _safe(witness["config"]["path"]).read_bytes(), frozen, changed_keys=witness["changed_keys"])


def _registered(sequence, contract, spec, scratch_root, code_commit):
    allowed, budgets = validate_registration(contract, code_commit=code_commit)
    if _json(contract["registered_runs"].get(spec["run_id"])) != _json(spec):
        raise PermissionError("T5BC_RUN_SPEC_DIFFERS_FROM_REGISTRATION")
    evaluation = spec["evaluation"]
    expected = {"window": list(sequence.window), "base_time": sequence.base_time,
                "trace": {"path": str(sequence.trace), "sha256": sequence.trace_sha256}}
    if _json(evaluation) != _json(expected) or sequence.sequence_id != spec["sequence_id"]:
        raise PermissionError("T5BC_SEQUENCE_EVALUATION_CONTEXT_DIFFERS")
    scratch = _safe(scratch_root)
    if any(_within(scratch, _safe(root)) for root in (sequence.raw_root, sequence.clean_root, sequence.code_root)):
        raise ValueError("T5bc scratch must be independent ext4 storage outside raw, archive and code roots")
    if Path(scratch).name != STAGE:
        raise ValueError("T5bc scratch stage identity differs")
    return allowed, budgets, scratch


def reserve_slot(path, run_id, allowed_run_ids, *, kind, budget, contract_sha256):
    """Separate durable ledgers; reservation consumes a slot even on launch error."""
    if (kind not in ("matrix_native", "identity_native", "evaluator") or type(budget) is not int
            or budget <= 0 or len(set(allowed_run_ids)) != budget or len(allowed_run_ids) != budget
            or run_id not in allowed_run_ids):
        raise PermissionError("T5BC_UNREGISTERED_RESERVATION_OR_BUDGET")
    path = _safe(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.seek(0)
        rows = [json.loads(line) for line in stream.read().splitlines()]
        if any(row.get("run_id") not in allowed_run_ids or row.get("kind") != kind
               or row.get("contract_sha256") != contract_sha256 or row.get("budget") != budget for row in rows):
            raise RuntimeError("HARD_STOP_T5BC_LEDGER_SCOPE_OR_FREEZE")
        if len({row["run_id"] for row in rows}) != len(rows):
            raise RuntimeError("HARD_STOP_T5BC_DUPLICATE_LEDGER_HISTORY")
        if any(row["run_id"] == run_id for row in rows):
            raise RuntimeError("HARD_STOP_T5BC_ALREADY_RESERVED_NO_RETRY")
        if len(rows) >= budget:
            raise RuntimeError("HARD_STOP_T5BC_BUDGET_EXHAUSTED")
        entry = {"run_id": run_id, "kind": kind, "budget": budget, "ordinal": len(rows)+1,
                 "contract_sha256": contract_sha256, "status": "RESERVED_BEFORE_LAUNCH", "retry_count": 0}
        stream.write(_json(entry) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    return entry


def _slot_path(output_root, scratch, relative):
    root = _safe(output_root)
    if root != scratch / relative or root.exists():
        raise FileExistsError("T5bc requires a new exact registered scratch slot; no overwrite or retry")
    return root


def _ledger_path(launch_ledger, scratch, kind):
    ledger = _safe(launch_ledger)
    if ledger != scratch / "LAUNCH_LEDGERS" / (kind + ".jsonl"):
        raise ValueError("T5bc ledger path or namespace differs")
    return ledger


def validate_scalar_table(frozen_bytes, candidate_bytes, reference_bytes=None, *, manifest=None, variant="R5W"):
    """Independent byte/numeric and exact-time source gate; D57 has no nearest join."""
    try:
        gate = provider.hp.validate_heading_byte_gate(frozen_bytes, candidate_bytes)
        rows, width = provider.hp._rows(candidate_bytes)
        frozen_rows, _ = provider.hp._rows(frozen_bytes)
        if manifest is None:
            gate.update(provider.validate_variant_byte_gate(frozen_bytes, candidate_bytes, r5_reference_bytes=reference_bytes))
        else:
            provenance = manifest["rows"]
            if manifest["source_sha256"] != hashlib.sha256(frozen_bytes).hexdigest() or len(provenance) != len(rows):
                raise RuntimeError("HARD_STOP_T5BC_RAW_MANIFEST_SOURCE_OR_ROWS")
            for row, original, source in zip(rows, frozen_rows, provenance):
                if row["tokens"][0].decode("ascii") != source["time_token"] or type(source["raw_valid"]) is not bool:
                    raise RuntimeError("HARD_STOP_T5BC_RAW_MANIFEST_TIME_OR_VALID")
                if row["tokens"][17] != (b"1" if source["raw_valid"] else b"0"):
                    raise RuntimeError("HARD_STOP_T5BC_RAW_MANIFEST_VALIDITY")
                if source["raw_valid"] and row["tokens"][13].decode("ascii") != source["raw_yaw_token"]:
                    raise RuntimeError("HARD_STOP_T5BC_RAW_MANIFEST_YAW")
                token = "2.933193" if variant == "R5" else source["std_"+variant+"_token"]
                expected = original["tokens"][14] if token is None else token.encode("ascii")
                if row["tokens"][14] != expected:
                    raise RuntimeError("HARD_STOP_T5BC_RAW_MANIFEST_STD")
            gate.update(exact_time_manifest=True, no_nearest_alignment=True)
    except provider.hp.HeadingProviderError as error:
        raise RuntimeError("HARD_STOP_T5BC_PROVIDER_BYTE_OR_NUMERIC_GATE: " + str(error)) from error
    if width != 18:
        raise RuntimeError("HARD_STOP_T5BC_GNSS18_WIDTH")
    for row in rows:
        yaw, std = map(float, (row["tokens"][13], row["tokens"][14]))
        if (not math.isfinite(yaw) or not 0 <= yaw < 360 or not math.isfinite(std) or std < 0
                or row["tokens"][17] not in (b"0", b"1")):
            raise RuntimeError("HARD_STOP_T5BC_PROVIDER_YAW_STD_VALIDITY")
    return {**gate, "std_finite_nonnegative": True, "std_clipping_used": False}


def validate_sidecar(gnss_bytes, payload, *, manifest=None):
    """Read only registered new sidecar bytes; no raw inputs or scalar-yaw values."""
    rows, width = provider.hp._rows(gnss_bytes)
    reader = csv.DictReader(io.StringIO(payload.decode("ascii")))
    columns = ["time", "b_n", "b_e", "b_d", "pAcc1", "pAcc2", "valid"]
    sidecar = list(reader)
    if width != 18 or reader.fieldnames != columns or len(sidecar) != len(rows):
        raise RuntimeError("HARD_STOP_T5BC_SIDECAR_ROW_OR_COLUMN_IDENTITY")
    zero_covariance, invalid = 0, 0
    for index, (gnss, row) in enumerate(zip(rows, sidecar)):
        if set(row) != set(columns) or row["time"].encode("ascii") != gnss["tokens"][0] or row["valid"] not in ("0", "1"):
            raise RuntimeError("HARD_STOP_T5BC_SIDECAR_TIME_OR_VALIDITY")
        values = []
        for key in columns[1:6]:
            token = row[key]
            value = None if token == "" else float(token)
            if ((value is None and row["valid"] == "1") or
                    (value is not None and (not math.isfinite(value) or (key.startswith("pAcc") and value < 0)))):
                raise RuntimeError("HARD_STOP_T5BC_SIDECAR_NUMERIC_VALUE")
            values.append(value)
        if manifest is not None:
            source = manifest["rows"][index]
            if source["time_token"] != row["time"] or source["raw_valid"] != (row["valid"] == "1"):
                raise RuntimeError("HARD_STOP_T5BC_SIDECAR_MANIFEST_TIME_OR_VALID")
            if values != [source[key] for key in columns[1:6]]:
                raise RuntimeError("HARD_STOP_T5BC_SIDECAR_MANIFEST_OBSERVATIONS")
        invalid += row["valid"] == "0"
        zero_covariance += row["valid"] == "1" and values[-2:] == [0., 0.]
    return {"passed": True, "exact_time_tokens": True, "row_count": len(rows),
            "invalid_count": invalid, "zero_covariance_rows_for_native_rejection": zero_covariance}


def verify_native_inputs(sequence, *, contract, run_spec, scratch_root):
    spec = run_spec
    expected_semisynthetic = spec["subset_case_id"] not in (None, "C00_clean_normal")
    expected_roles = {"data_mode": "semisynthetic" if expected_semisynthetic else "real_clean" if spec["subset_case_id"] == "C00_clean_normal" else "real_raw",
        "synthetic_data_used": False, "semisynthetic_data_used": expected_semisynthetic}
    if _json(spec.get("data_roles")) != _json(expected_roles):
        raise RuntimeError("HARD_STOP_T5BC_ACTUAL_DATA_ROLES_REQUIRED")
    raw_hashes = spec.get("raw_source_hashes")
    if not isinstance(raw_hashes, dict) or not raw_hashes:
        raise RuntimeError("HARD_STOP_T5BC_RAW_HASH_PROVENANCE_REQUIRED")
    for name, digest in raw_hashes.items():
        # Pure path/hash metadata validation: do not stat, open, or hash raw data.
        path = Path(name)
        if (not path.is_absolute() or ".." in path.parts or not _within(path, Path(sequence.raw_root))
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            raise RuntimeError("HARD_STOP_T5BC_RAW_HASH_PROVENANCE_VALUE")
    config_ref, echo_ref = spec["frozen_config"], spec["frozen_echo"]
    frozen_refs = [config_ref, echo_ref, *spec["frozen_providers"].values()]
    if "frozen_echo_witness" in spec:
        frozen_refs.append(spec["frozen_echo_witness"]["config"])
    if spec["variant"] != "IDENTITY":
        frozen_refs.append(spec["r5_reference"])
    if any(not _within(_safe(item["path"]), _safe(sequence.clean_root)) for item in frozen_refs):
        raise RuntimeError("HARD_STOP_T5BC_FROZEN_REFERENCE_OUTSIDE_CLEAN_ROOT")
    identities = {"frozen_config": _pin(config_ref), "frozen_echo": _pin(echo_ref)}
    original_bytes = _safe(config_ref["path"]).read_bytes()
    original = _runtime_mapping(original_bytes)
    for key, expected in PROVENANCE_FLAGS.items():
        if type(original.get(key)) is not type(expected) or original[key] != expected:
            raise RuntimeError("HARD_STOP_T5BC_FORBIDDEN_CONFIG_PROVENANCE: " + key)
    if spec["subset_case_id"] is not None and original.get("case_id") != spec["subset_case_id"]:
        raise RuntimeError("HARD_STOP_T5BC_FROZEN_SUBSET_CASE_ID")
    frozen_echo, identities["frozen_echo_basis"] = expected_echo(spec, original_bytes)
    compare_effective_echo(frozen_echo, frozen_echo)
    if set(spec["frozen_providers"]) != set(PROVIDER_KEYS):
        raise RuntimeError("HARD_STOP_T5BC_PROVIDER_ROLE_SET")
    identities["frozen_providers"] = {}
    for key, reference in spec["frozen_providers"].items():
        if original[key] != reference["path"]:
            raise RuntimeError("HARD_STOP_T5BC_CONFIG_PROVIDER_PATH: " + key)
        identities["frozen_providers"][key] = _pin(reference)
    variant = spec["variant"]
    clone_kwargs = {}
    generated_root = _safe(scratch_root) / "03_PROVIDER_TABLES"
    def new_provider(reference):
        if not _within(_safe(reference["path"]), generated_root):
            raise RuntimeError("HARD_STOP_T5BC_PREPARED_PROVIDER_PATH")
        return _pin(reference)
    manifest = None
    if variant != "IDENTITY":
        identities["prepared_raw_manifest"] = new_provider(spec["prepared_raw_manifest"])
        manifest = json.loads(_safe(spec["prepared_raw_manifest"]["path"]).read_text())
        if manifest["source_sha256"] != spec["frozen_providers"]["gnsspath"]["sha256"]:
            raise RuntimeError("HARD_STOP_T5BC_PREPARED_MANIFEST_SOURCE")
        if manifest["pinned_r5_source"] != spec["r5_reference"]:
            raise RuntimeError("HARD_STOP_T5BC_PREPARED_MANIFEST_R5_PIN")
        identities["r5_reference"] = _pin(spec["r5_reference"])
    if variant in ("R5", "R5W", "R5SIGMA"):
        identities["prepared_gnss"] = new_provider(spec["prepared_gnss"])
        identities["r5_reference"] = _pin(spec["r5_reference"])
        identities["provider_byte_gate"] = validate_scalar_table(
            _safe(original["gnsspath"]).read_bytes(), _safe(spec["prepared_gnss"]["path"]).read_bytes(),
            _safe(spec["r5_reference"]["path"]).read_bytes(), manifest=manifest, variant=variant)
        clone_kwargs["gnsspath"] = spec["prepared_gnss"]["path"]
        binary_ref = contract["frozen"]["executable"]
        if binary_ref["sha256"] != BINARY_SHA256:
            raise RuntimeError("HARD_STOP_T5BC_FROZEN_BINARY_REGISTRATION")
    else:
        binary_ref = {key: contract["candidate"][key] for key in ("path", "sha256")}
        if variant == "B3":
            if spec["baseline3d"]["baseline3d_path"] != spec["sidecar"]["path"]:
                raise RuntimeError("HARD_STOP_T5BC_SIDECAR_CONFIG_PATH")
            if spec["baseline3d"]["baseline3d_length_m"] != .35:
                raise RuntimeError("HARD_STOP_T5BC_FIXED_MEASUREMENT_BASELINE_LENGTH")
            identities["prepared_gnss"] = new_provider(spec["prepared_gnss"])
            prepared_bytes = _safe(spec["prepared_gnss"]["path"]).read_bytes()
            identities["provider_byte_gate"] = provider.hp.validate_heading_byte_gate(
                _safe(original["gnsspath"]).read_bytes(), prepared_bytes)
            rows, width = provider.hp._rows(prepared_bytes)
            if width != 18 or any(row["tokens"][17] != b"0" for row in rows):
                raise RuntimeError("HARD_STOP_T5BC_B3_SCALAR_YAW_VALID_NOT_ZERO")
            identities["sidecar"] = new_provider(spec["sidecar"])
            identities["sidecar_gate"] = validate_sidecar(prepared_bytes, _safe(spec["sidecar"]["path"]).read_bytes(), manifest=manifest)
            clone_kwargs.update(baseline3d=spec["baseline3d"], gnsspath=spec["prepared_gnss"]["path"])
    identities["binary"] = _pin(binary_ref)
    if not os.access(binary_ref["path"], os.X_OK):
        raise RuntimeError("HARD_STOP_T5BC_BINARY_NOT_EXECUTABLE")
    expected_binary = _safe(sequence.code_root) / "build" / (
        "p13_v21_cpp" if variant in ("R5", "R5W", "R5SIGMA") else "t5bc_v3_candidate_cpp") / "legsa_v23_port_core_demo"
    if _safe(binary_ref["path"]) != expected_binary:
        raise RuntimeError("HARD_STOP_T5BC_BINARY_PATH_REGISTRATION")
    cloned, config_gate = clone_config(original_bytes, expected_sha256=config_ref["sha256"], **clone_kwargs)
    identities["config_byte_gate"] = config_gate
    config = _runtime_mapping(cloned)
    for key in ("synthetic_data_used", "semisynthetic_data_used"):
        if type(config.get(key)) is not bool:
            raise RuntimeError("HARD_STOP_T5BC_DATA_ROLE_NOT_EXPLICIT")
    if config["synthetic_data_used"]:
        raise RuntimeError("HARD_STOP_T5BC_SYNTHETIC_SCIENTIFIC_SLOT")
    if spec["subset_case_id"] is None and config["semisynthetic_data_used"]:
        raise RuntimeError("HARD_STOP_T5BC_SEMISYNTHETIC_IN_REAL_SEQUENCE_SLOT")
    return identities, cloned, config, clone_kwargs


def audit_native_access(log, sequence, output_root, config, binary, scratch_root):
    records = audited_open_records(log, sequence.code_root)
    text = _safe(log).read_text()
    inputs = _enabled_inputs(config)
    if config.get("dual_antenna_measurement_model") == "baseline3d":
        inputs[B3_ROLE] = ("baseline3d_path", B3_PURPOSE)
    expected = {str(_safe(config[key])) for key, _ in inputs.values()}
    reads = {row["path"] for row in records if row["return_code"] >= 0 and "O_RDONLY" in row["flags"]}
    raw = [row for row in records if _within(Path(row["path"]), _safe(sequence.raw_root))]
    forbidden_suffix = [row for row in records if Path(row["path"]).suffix.lower() in (".bag", ".fpl")]
    system_roots = tuple(Path(path) for path in ("/usr/lib", "/usr/local/lib", "/lib", "/lib64", "/proc", "/sys", "/usr/share/locale"))
    system_files = {"/etc/ld.so.cache", "/etc/localtime", "/dev/null"}
    unexpected = [row for row in records if row["return_code"] >= 0 and "O_RDONLY" in row["flags"]
                  and row["path"] not in expected | system_files
                  and not _within(Path(row["path"]), output_root)
                  and not any(_within(Path(row["path"]), root) for root in system_roots)]
    scope = write_scope_audit(records, raw_root=sequence.raw_root, clean_root=sequence.clean_root,
                              allowed_write_roots=[output_root])
    executions = [line for line in text.splitlines() if "execve(" in line]
    native = [line for line in executions if ('execve("' + str(binary) + '"') in line]
    evaluators = [line for line in executions if "evaluate_nav_trace" in line]
    open_lines = [line for line in text.splitlines() if "openat(" in line]
    complete = bool(records) and len(native) == 1 and len(open_lines) == len(records) and "unfinished ..." not in text
    unexpected_exec = [line for line in executions if line not in native]
    violation = bool(raw or forbidden_suffix or unexpected or unexpected_exec or evaluators or not scope["pass"] or len(native) > 1)
    return {"passed": complete and not violation and expected <= reads, "evidence_complete": complete,
            "violation_detected": violation, "missing_enabled_inputs": sorted(expected - reads),
            "raw_open_count": len(raw), "trace_open_count": sum(Path(row["path"]) == sequence.trace for row in records),
            "bag_fpl_open_count": len(forbidden_suffix), "native_exec_count": len(native),
            "evaluator_invocation_count": len(evaluators), "unexpected_read_opens": unexpected,
            "unexpected_execve_records": unexpected_exec,
            "write_scope": scope, "strace_sha256": sha256_file(log)}


def _seal(root, record, *, filename):
    files = {str(path.relative_to(root)): sha256_file(_safe(path)) for path in sorted(root.rglob("*")) if path.is_file()}
    _write(root / "OUTPUT_SEAL.json", {"status": "SEALED", "files": files, "same_native_invocation": filename == "T5BC_NATIVE_SUMMARY.json"})
    record["file_hashes"] = {**files, "OUTPUT_SEAL.json": sha256_file(root / "OUTPUT_SEAL.json")}
    _write(root / filename, record)
    return {**record, "native_summary" if filename == "T5BC_NATIVE_SUMMARY.json" else "evaluation_summary":
            {"path": str(root / filename), "sha256": sha256_file(root / filename)}}


class _Unavailable(Exception):
    pass


def classify_heading_failure(root, config, *, variant):
    """Positive full-window counter evidence; never infer an algorithm class from exit alone."""
    report = {"passed": False, "classification": "UNAVAILABLE_NATIVE_PROCESS_FAILED"}
    if variant not in ("R5", "R5W", "R5SIGMA", "B3"):
        return report
    update, loop = root / "PORT_GNSS_UPDATE_TRACE.csv", root / "PORT_RUNTIME_LOOP_TRACE.csv"
    if not update.is_file() or not loop.is_file():
        return report
    try:
        imu = np.loadtxt(config["imupath"], ndmin=2)
        gnss = np.loadtxt(config["gnsspath"], ndmin=2)
        expected = expected_counts(config, gnss, imu)
        if variant != "B3" and expected["dual_yaw_attempt_count"] > 0:
            return classify_all_yaw_rejected(root, config, expected, imu)
        updates, loops = csv_rows(update), csv_rows(loop)
        initial = int(np.searchsorted(imu[:, 0], config["starttime"], side="left"))
        processed = imu[initial+1:]
        processed = processed[processed[:, 0] <= config["endtime"]]
        complete = (len(loops) == len(processed) > 0
            and all(int(row["loop_index"]) == i for i,row in enumerate(loops))
            and abs(float(loops[-1]["timestamp_after_process"])-expected["last_processed_imu_time"]) <= .00051)
        counts = {key: sum(int(row[field]) for row in updates) for key,field in (
            ("position_update_count", "position_update"), ("receiver_velocity_update_count", "velocity_update"),
            ("dual_yaw_attempt_count", "yaw_update"))}
        reason = "FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH: actual formal module activation counters mismatch"
        stderr = (root / "stderr.log").read_text().strip()
        sidecar_evidence = {}
        if variant == "B3":
            sidecar = csv_rows(config["baseline3d_path"])
            diagnostics = root/"BASELINE3D_DIAGNOSTICS.csv"
            no_heading = (bool(sidecar) and len(sidecar)==len(gnss) and all(row["valid"]=="0" for row in sidecar)
                and counts["dual_yaw_attempt_count"]==0)
            if diagnostics.is_file():
                no_heading = no_heading and all(row["attempt"]=="0" for row in csv_rows(diagnostics))
            sidecar_evidence = {"heading_input_role":"dual_antenna_baseline3d",
                "sidecar_valid_count":sum(row["valid"]=="1" for row in sidecar),
                "sidecar_sha256":sha256_file(config["baseline3d_path"]),
                "baseline3d_diagnostics_available":diagnostics.is_file(),
                "attempt_evidence":"PORT_GNSS_UPDATE_TRACE.yaw_update_FORMAL_A1_ALIAS",
                "scalar_yaw_valid_used_for_b3_classification":False}
        else:
            no_heading = bool(len(gnss)) and bool(np.all(gnss[:,17] == 0)) and counts["dual_yaw_attempt_count"] == 0
        passed = bool(complete and no_heading and stderr == reason
            and config.get("enable_dual_yaw") is True and all(counts[key] == expected[key] for key in counts))
        return {"passed": passed, "classification": "ALGORITHM_FAILURE_NO_VALID_HEADING_INPUT" if passed else report["classification"],
            **sidecar_evidence, "provider_yaw_valid_count": None if variant=="B3" else int(np.count_nonzero(gnss[:,17])), "counters": counts,
            "full_window_processed": complete, "exact_formal_counter_error": stderr == reason,
            "update_trace_sha256": sha256_file(update), "loop_trace_sha256": sha256_file(loop)}
    except (ValueError, KeyError, OSError, IndexError, TypeError) as error:
        return {**report, "evidence_unavailable": str(error)}


def run_native(sequence, *, contract, run_spec, output_root, scratch_root, code_commit, launch_ledger):
    allowed, budgets, scratch = _registered(sequence, contract, run_spec, scratch_root, code_commit)
    spec = run_spec
    kind = "identity_native" if spec["variant"] == "IDENTITY" else "matrix_native"
    root = _slot_path(output_root, scratch, _native_relative(spec))
    ledger = _ledger_path(launch_ledger, scratch, kind)
    identities, config_bytes, config, clone_kwargs = verify_native_inputs(
        sequence, contract=contract, run_spec=spec, scratch_root=scratch)
    root.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    record = {**{key: spec[key] for key in IDENTITY_KEYS}, "code_commit": code_commit,
              "contract_sha256": scientific_contract_sha256(contract),
              "resolved_contract_sha256": hashlib.sha256(_json(contract).encode()).hexdigest(),
              "run_spec_sha256": hashlib.sha256(_json(spec).encode()).hexdigest(),
              "config_hash": hashlib.sha256(config_bytes).hexdigest(), "input_identities": identities,
              **spec["data_roles"],
              "controlled_degradation_applied": spec["data_roles"]["semisynthetic_data_used"],
              "original_native_config_data_roles": {key: config[key] for key in spec["data_roles"]},
              "output_root": str(root),
              "native_run_id_retained": config["run_id"], "trace_used_online": False,
              "native_invocation_count": 0, "evaluator_invocation_count": 0, "retry_count": 0,
              "main_table_admission": False, "identity_comparison": "PENDING_CONTROLLER_THIN_NAV" if kind == "identity_native" else "NOT_APPLICABLE"}
    record.update(PROVENANCE_FLAGS)
    record["raw_source_hashes"] = dict(spec["raw_source_hashes"])
    record["provider_hashes"] = {key: value["sha256"] for key, value in spec["frozen_providers"].items()}
    if spec["variant"] != "IDENTITY":
        record["provider_hashes"]["gnsspath"] = spec["prepared_gnss"]["sha256"]
    if spec["variant"] == "B3":
        record["provider_hashes"]["baseline3d_path"] = spec["sidecar"]["sha256"]
    try:
        _write(root / "INPUT_IDENTITIES.json", identities)
        runtime_config = root / "T5BC_RUNTIME_CONFIG.yaml"
        with runtime_config.open("xb") as stream:
            stream.write(config_bytes); stream.flush(); os.fsync(stream.fileno())
        _write(root / "LAUNCH_RESERVATION.json", reserve_slot(ledger, spec["run_id"], allowed[kind],
               kind=kind, budget=budgets[kind], contract_sha256=record["contract_sha256"]))
        record["native_invocation_count"] = 1
        binary = Path(identities["binary"]["path"])
        log = root / "NATIVE_OPENAT.strace"
        argv = native_argv(binary, runtime_config, root)
        command = ["env", "OMP_NUM_THREADS=1", "OPENBLAS_NUM_THREADS=1", "MKL_NUM_THREADS=1", "NUMEXPR_NUM_THREADS=1",
                   "strace", "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat,execve", "-o", str(log), *argv]
        _write(root / "RUN_STARTED.json", {**record, "native_argv": argv})
        completed, process_error = None, None
        try:
            completed = run_process_group(command, cwd=sequence.code_root, timeout_seconds=1800,
                timeout_message="T5bc native timeout; no retry", launch_failure_message="T5bc native launch failed")
        except (OSError, RuntimeError, TimeoutError) as error:
            process_error = str(error)
        record.update(exit_code=completed.returncode if completed else "UNAVAILABLE", process_error=process_error)
        for name, value in (("stdout.log", completed.stdout if completed else ""),
                            ("stderr.log", completed.stderr if completed else str(process_error))):
            with (root / name).open("x", encoding="utf-8") as stream:
                stream.write(value)
        try:
            access = audit_native_access(log, sequence, root, config, binary, scratch)
        except (OSError, ValueError, SyntaxError) as error:
            access = {"passed": False, "evidence_complete": False, "reason": str(error), "trace_open_count": "UNAVAILABLE"}
        record["access_audit"] = access
        _write(root / "NATIVE_ACCESS_AUDIT.json", access)
        post = verify_native_inputs(sequence, contract=contract, run_spec=spec, scratch_root=scratch)
        if post != (identities, config_bytes, config, clone_kwargs) or runtime_config.read_bytes() != config_bytes:
            raise RuntimeError("HARD_STOP_T5BC_INPUT_OR_CONFIG_DRIFT")
        failed_before_inputs = (completed is not None and completed.returncode != 0 and
                               access.get("evidence_complete") is True and access.get("violation_detected") is False)
        if access.get("passed") is not True and not failed_before_inputs:
            raise RuntimeError("HARD_STOP_T5BC_NATIVE_ACCESS_AUDIT")
        if failed_before_inputs and access.get("missing_enabled_inputs"):
            record["missing_inputs_classification"] = "NATIVE_FAILED_COMPLETE_STRACE_NO_FORBIDDEN_OPENS"
        manifest_path = root / "RUN_MANIFEST.json"
        if manifest_path.exists():
            native = decode_echo(manifest_path.read_bytes())
            baseline, _ = expected_echo(spec, _safe(spec["frozen_config"]["path"]).read_bytes())
            record["effective_echo_gate"] = compare_effective_echo(native, baseline, **clone_kwargs)
            _write(root / "EFFECTIVE_CONFIG_ECHO_GATE.json", record["effective_echo_gate"])
        if completed is None or completed.returncode:
            failed_nav=root / "KF_GINS_Navresult.nav"
            if failed_nav.is_file():
                try:
                    failed_nav_sha=sha256_file(failed_nav)
                    failed_bound=bounded_lla_native(failed_nav,expected_sha256=failed_nav_sha)
                except (ValueError,OSError):
                    failed_bound=None
                if failed_bound is not None and failed_bound.get("failure_classification")=="ALGORITHM_FAILURE_DIVERGED":
                    record.update(bounded_gate=failed_bound,nav_path=str(failed_nav),nav_sha256=failed_nav_sha,
                                  std_nav_alignment="NOT_ADMITTED_ALGORITHM_FAILURE")
                    _write(root/"BOUNDED_OUTPUT_GATE.json",failed_bound)
                    raise _Unavailable("ALGORITHM_FAILURE_DIVERGED")
            classification = classify_heading_failure(root, config, variant=spec["variant"])
            record["heading_failure_evidence"] = classification
            if classification.get("passed"):
                raise _Unavailable(classification["classification"])
            raise RuntimeError("HARD_STOP_UNCLASSIFIABLE_NATIVE_FAILURE")
        if record.get("effective_echo_gate", {}).get("passed") is not True:
            raise RuntimeError("HARD_STOP_T5BC_EFFECTIVE_ECHO_MISSING")
        nav, std = root / "KF_GINS_Navresult.nav", root / "KF_GINS_STD.txt"
        if not nav.is_file() or not std.is_file():
            raise _Unavailable("UNAVAILABLE_NATIVE_OUTPUT_INVALID")
        nav_sha, std_sha = sha256_file(nav), sha256_file(std)
        try:
            gate = bounded_lla_native(nav, expected_sha256=nav_sha)
            if gate["passed"]:
                nav_rows, _ = read_native_numeric(nav, columns=11)
                std_rows, _ = read_native_numeric(std)
                _support(nav_rows, sequence.window)
                if (std_rows.ndim != 2 or std_rows.shape[1] < 10 or len(std_rows) != len(nav_rows)
                        or not np.isfinite(std_rows).all() or not np.array_equal(std_rows[:, 0], nav_rows[:, 1])):
                    raise ValueError("same-native STD/NAV alignment failed")
        except (ValueError, OSError) as error:
            raise _Unavailable("UNAVAILABLE_NATIVE_OUTPUT_INVALID: " + str(error)) from error
        _write(root / "BOUNDED_OUTPUT_GATE.json", gate)
        record.update(bounded_gate=gate, nav_path=str(nav), nav_sha256=nav_sha, std_path=str(std), std_sha256=std_sha,
                      status="COMPLETED" if gate["passed"] else "ALGORITHM_FAILURE_DIVERGED",
                      failure_classification=gate["failure_classification"],
                      std_nav_alignment="PASS" if gate["passed"] else "NOT_ADMITTED_ALGORITHM_FAILURE",
                      evaluator_status="NOT_APPLICABLE_IDENTITY" if kind == "identity_native" else
                          "PENDING" if gate["passed"] else "NOT_RUN_ALGORITHM_FAILURE")
    except _Unavailable as error:
        record.update(status=str(error).split(":")[0], failure_classification=str(error).split(":")[0],
                      unavailable_reason=str(error), evaluator_status="NOT_RUN_ALGORITHM_FAILURE"
                      if str(error).startswith("ALGORITHM_FAILURE_") else "NOT_RUN_NATIVE_UNAVAILABLE")
    except Exception as error:
        record.update(status="HARD_STOP", failure_classification="HARD_STOP", error=str(error), evaluator_status="NOT_RUN_HARD_STOP")
        record["trace_open_count"] = record.get("access_audit", {}).get("trace_open_count", "UNAVAILABLE")
        _write(root / "HARD_STOP.json", record)
        if record["native_invocation_count"]:
            record["runtime_seconds"] = time.monotonic() - started
            _seal(root, record, filename="T5BC_NATIVE_SUMMARY.json")
        raise
    record.update(runtime_seconds=time.monotonic() - started,
                  trace_open_count=record.get("access_audit", {}).get("trace_open_count", "UNAVAILABLE"))
    return _seal(root, record, filename="T5BC_NATIVE_SUMMARY.json")


def evaluate_native(sequence, evaluator, *, contract, run_spec, native_summary, version,
                    output_root, scratch_root, code_commit, launch_ledger):
    allowed, budgets, scratch = _registered(sequence, contract, run_spec, scratch_root, code_commit)
    if run_spec["variant"] == "IDENTITY" or version not in ("v3", "v2"):
        raise PermissionError("T5BC_IDENTITY_EVALUATION_FORBIDDEN_OR_VERSION_UNREGISTERED")
    reservation_id = run_spec["run_id"] + "__" + version
    root = _slot_path(output_root, scratch, "06_EVAL/" + version + "/" + run_spec["run_id"])
    ledger = _ledger_path(launch_ledger, scratch, "evaluator")
    summary_ref = native_summary["native_summary"]
    _pin(summary_ref)
    persisted = json.loads(_safe(summary_ref["path"]).read_text())
    if (persisted.get("contract_sha256") != scientific_contract_sha256(contract)
            or persisted.get("run_spec_sha256") != hashlib.sha256(_json(run_spec).encode()).hexdigest()):
        raise RuntimeError("HARD_STOP_T5BC_NATIVE_CONTRACT_BINDING")
    if _json(persisted) != _json({k: v for k, v in native_summary.items() if k != "native_summary"}):
        raise RuntimeError("HARD_STOP_T5BC_NATIVE_SUMMARY_BINDING")
    native_root = scratch / _native_relative(run_spec)
    if (_safe(summary_ref["path"]) != native_root / "T5BC_NATIVE_SUMMARY.json" or
            any(persisted[key] != run_spec[key] for key in IDENTITY_KEYS) or persisted["code_commit"] != code_commit
            or persisted["status"] != "COMPLETED" or persisted.get("std_nav_alignment") != "PASS"):
        raise RuntimeError("HARD_STOP_T5BC_NATIVE_EVALUATION_ADMISSION")
    pins = [{"path": persisted[key+"_path"], "sha256": persisted[key+"_sha256"]} for key in ("nav", "std")]
    if contract["frozen"]["evaluator_sha256"] != EVALUATOR_SHA256:
        raise RuntimeError("HARD_STOP_T5BC_EVALUATOR_REGISTRATION")
    pins.append({"path": str(evaluator), "sha256": EVALUATOR_SHA256})
    for ref in pins:
        _pin(ref)
    nav, std = (Path(pins[i]["path"]) for i in (0, 1))
    if (nav != native_root / "KF_GINS_Navresult.nav" or std != native_root / "KF_GINS_STD.txt"
            or persisted["bounded_gate"].get("passed") is not True
            or persisted["bounded_gate"].get("source_nav_sha256") != pins[0]["sha256"]):
        raise RuntimeError("HARD_STOP_T5BC_SAME_NATIVE_NAV_STD_OR_D8")
    seal = native_root / "OUTPUT_SEAL.json"
    _pin({"path": str(seal), "sha256": persisted["file_hashes"]["OUTPUT_SEAL.json"]})
    sealed = json.loads(seal.read_text())["files"]
    if any(sealed.get(Path(ref["path"]).name) != ref["sha256"] for ref in pins[:2]):
        raise RuntimeError("HARD_STOP_T5BC_NAV_STD_SEAL_BINDING")
    original = canonical._read_numeric_table(nav).to_numpy(float)
    window = _support(original, sequence.window)
    length = run_spec["baseline_median_m"]
    if type(length) not in (int, float) or not math.isfinite(length) or length <= 0:
        raise ValueError("T5bc baseline median must be explicitly registered positive finite")
    root.mkdir(parents=True, exist_ok=False)
    record = {"run_id": reservation_id, "code_commit": code_commit, "config_hash": persisted["config_hash"], "native_summary": summary_ref,
              "retry_count": 0, "evaluation_invoked": False}
    record.update({key: persisted[key] for key in (*PROVENANCE_FLAGS, "raw_source_hashes", "provider_hashes",
                                                  "data_mode", "synthetic_data_used", "semisynthetic_data_used",
                                                  "controlled_degradation_applied", "original_native_config_data_roles")})
    record["contract_sha256"] = scientific_contract_sha256(contract)
    actual, actual_hash = nav, pins[0]["sha256"]
    transform = {"version": version, "input_sha256": actual_hash, "output_sha256": actual_hash,
                 "STD": STD_POLICY, "std_sha256": pins[1]["sha256"], "std_transformed": False,
                 "fit_used": False, "changed_columns_zero_based": [], "uncertainty_status": "DIAGONAL_ONLY_NOT_FULL_NEES"}
    try:
        if version == "v3":
            actual = root / "EVAL_NAV_V3.nav"
            write_transformed_nav(nav, actual, transform_nav(original, length))
            actual_hash = sha256_file(actual)
            transform.update(output_sha256=actual_hash, baseline_median_m=length,
                             changed_columns_zero_based=[2, 3, 4],
                             uncertainty_status="UNTRANSPORTED_STD_DIAGNOSTIC_ONLY")
        _write(root / "TRANSFORM_MANIFEST.json", transform)
        contract_sha = scientific_contract_sha256(contract)
        _write(root / "LAUNCH_RESERVATION.json", reserve_slot(ledger, reservation_id, allowed["evaluator"],
               kind="evaluator", budget=budgets["evaluator"], contract_sha256=contract_sha))
        record["evaluation_invoked"] = True
        result = evaluate(evaluator=Path(evaluator), trace=sequence.trace, nav=actual, std=std,
            outdir=root / "FROZEN_EVALUATOR", base_time=sequence.base_time, window=window,
            trace_sha256=sequence.trace_sha256, code_root=sequence.code_root, raw_root=sequence.raw_root,
            clean_root=sequence.clean_root, instrument=True, consistency_policy=POLICY, measure_resources=True)
        audit, capture = _capture(result, sequence)
        identity = {**{key: run_spec[key] for key in IDENTITY_KEYS}, "dataset_id": sequence.sequence_id,
            "code_commit": code_commit, "config_hash": persisted["config_hash"],
            "method_id": run_spec["configuration_id"], "data_mode": persisted["data_mode"],
            "synthetic_data_used": persisted["synthetic_data_used"], "semisynthetic_data_used": persisted["semisynthetic_data_used"],
            "evaluator_contract": "evaluator_contract_"+version, "evaluator_sha256": EVALUATOR_SHA256,
            "native_nav_sha256": pins[0]["sha256"], "evaluator_nav_sha256": actual_hash, "std_sha256": pins[1]["sha256"],
            "trace_sha256": sequence.trace_sha256, "base_time": sequence.base_time, "evaluation_invoked": True,
            "trace_used_online": False, "sensitivity_only": True, "main_table_admission": False,
            "STD": STD_POLICY, "uncertainty_status": transform["uncertainty_status"]}
        identity.update({key: persisted[key] for key in (*PROVENANCE_FLAGS, "raw_source_hashes", "provider_hashes",
            "controlled_degradation_applied", "original_native_config_data_roles")})
        if capture["consistency"]["passed"] is False:
            row = {**identity, "status": "UNAVAILABLE_EVALUATION_FAILED", "evaluation_status": "UNAVAILABLE_EVALUATION_FAILED",
                   "failure_classification": "UNAVAILABLE_EVALUATION_FAILED", "metrics_admitted": False,
                   "reason": "D12 consistency failed after native D8; no retry"}
            bias = {"status": "UNAVAILABLE_EVALUATION_FAILED"}
        else:
            errors = canonical._read_error_series(Path(result["outdir"]))
            times = np.asarray(errors["time"], float)
            if (not len(times) or not np.isfinite(times).all() or np.any(np.diff(times) <= 0)
                    or np.any((times < window[0]) | (times > window[1]))):
                raise RuntimeError("HARD_STOP_T5BC_EVALUATION_ERROR_SUPPORT")
            row = window_metrics(errors, original, identity, window, capture.get("reference_epoch_count"))
            if run_spec["subset_case_id"] is not None:
                subset_metrics = canonical._compute_result(run_spec["source_registry_row"], run_spec["case_meta"],
                    native_root, Path(result["outdir"]), capture["reference_epoch_count"], result["runtime_seconds"], True)
                row.update(subset_metrics)
                row.update(identity)
                record["subset_metrics"] = subset_metrics
                record["source_registry_row"] = run_spec["source_registry_row"]
                record["case_meta"] = run_spec["case_meta"]
            row.update(status="COMPLETED", failure_classification="NONE", metrics_admitted=True)
            bias = {**body_frame_bias(errors, original), "status": "AVAILABLE"}
        row.update(evaluation_runtime_seconds=result["runtime_seconds"], error_series_source=result["outdir"],
                   sequence_window_start_s=window[0], sequence_window_end_s=window[1], retry_count=0)
        record.update(status=row["status"], row=row, body_frame_bias=bias, transform=transform,
                      audit={**audit, "technical_passed": True, "consistency_passed": capture["consistency"]["passed"]})
        for reference in pins:
            _pin(reference)
        _pin({"path": str(actual), "sha256": actual_hash})
    except Exception as error:
        record.update(status="HARD_STOP", error=str(error))
        try:
            for reference in pins:
                _pin(reference)
            _pin({"path": str(actual), "sha256": actual_hash})
        except Exception as identity_error:
            record["post_failure_identity_error"] = str(identity_error)
        _write(root / "HARD_STOP.json", record)
        _seal(root, record, filename="T5BC_EVALUATION_SUMMARY.json")
        raise
    _write(root / "EVALUATION_RESULT.json", {key: record[key] for key in ("row", "audit", "transform", "body_frame_bias")})
    return _seal(root, record, filename="T5BC_EVALUATION_SUMMARY.json")
