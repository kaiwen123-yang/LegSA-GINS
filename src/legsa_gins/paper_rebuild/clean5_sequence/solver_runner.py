"""C-04 serial frozen-solver execution, isolated raw checkpoints, and sealing.

The solver never receives raw inputs or reference traces. Raw files are opened
only by independent, straced hash-checkpoint processes. Existing attempts cannot
be overwritten or retried. Native compatibility identity is preserved verbatim;
the outer manifests carry the actual CLEAN5 identity.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import yaml

from ..manifest import sha256_file, verify_raw_sources
from ..paths import guard_path, load_yaml_mapping
from ..subprocess_guard import run_process_group
from .generation_audit import (WRITE_FLAGS, audit_records, code_freeze_state,
                               open_records, selected_lock, validate_checkpoint,
                               write_json_exclusive)
from .registry import load_registry
from .runtime_config import (CONFIG_FILENAMES, METHODS, PATH_ROLES,
                             frozen_parameter_hash, scientific_runtime_config_hash)
from .solver_validation import (bind_output_config, expected_update_epochs, validate_nav_alignment, validate_clean5_manifest,
                                validate_profile_counters, validate_run_outputs)
from .solver_seal import seal_outputs, validate_output_seal

C02_COMMIT = "d9c2139fc80f392ea15b91d879475bfc5ae9abf7"
C03_COMMIT = "1441993e41a93eb5589be0ba31771b4b154eedc2"
FROZEN_EXECUTABLE_SHA256 = "9c00565c45b654453b2b378f3d5995e5dc21d1271323a9b683acdab75993235f"
EXECUTABLE_RELATIVE = Path("build/canonical541_cpp/legsa_v23_port_core_demo")
EXPECTED_GNSS_ROWS = {"BY2H": 272, "BY2O": 409}
# These C-03 counts identify the frozen provider metadata only. Runtime counter
# expectations use input-derived t_init and the frozen profile features.
SOLVER_TIMEOUT_SECONDS = 1800
RAW_CHECKPOINT_SCHEMA = "paper_rebuild.final_v23_external_raw_checkpoint.v1"
FORBIDDEN_FLAGS = ("trace_used_online", "synthetic_data_used", "semisynthetic_data_used",
                   "per_case_tuning", "output_only_correction", "epoch_deleted_for_metric",
                   "receiver_imu_as_body_imu", "final_v23_output_solver_input",
                   "LegSA_output_solver_input")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _git_bytes(root, revision, relative):
    return subprocess.check_output(["git", "show", f"{revision}:{relative}"], cwd=root,
                                   env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})


def _json(path):
    def reject(value):
        raise ValueError(f"Nonfinite JSON constant: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=reject)


def _hash_check(path, expected, *, root, role):
    path = guard_path(path, role=role, allowed_root=root, must_exist=True, regular_file=True)
    if not re.fullmatch(r"[0-9a-f]{64}", str(expected)) or sha256_file(path) != expected:
        raise RuntimeError(f"{role} SHA-256 mismatch: {path}")
    return {"path": str(path), "sha256": expected, "size_bytes": path.stat().st_size}


def verify_executable(executable, active_code_root):
    supplied = Path(executable)
    if not supplied.is_absolute() or supplied != active_code_root / EXECUTABLE_RELATIVE:
        raise RuntimeError("--executable must name the original active-worktree frozen binary by absolute path")
    identity = _hash_check(supplied, FROZEN_EXECUTABLE_SHA256, root=active_code_root,
                           role="Frozen executable (rebuilding forbidden)")
    if not os.access(supplied, os.X_OK):
        raise RuntimeError("Frozen binary is not executable")
    return identity


def execution_registry(registry, *, code_root, code_freeze_commit, executable, execution_script):
    requested = Path(code_root).resolve(strict=True)
    expected = registry.code_root.parent / ("clean5-run-" + code_freeze_commit[:12])
    if requested != expected or requested == registry.code_root:
        raise RuntimeError("--code-root differs from the authorized C-04 detached snapshot")
    if requested == registry.clean_root or requested in registry.clean_root.parents or registry.clean_root in requested.parents:
        raise RuntimeError("Execution snapshot and clean output root overlap")
    script = Path(execution_script).resolve(strict=True)
    if (Path(__file__).resolve().parents[4] != requested
            or script != requested / "scripts/paper_rebuild/clean5_run_sequence.py"):
        raise RuntimeError("Execution script and imported runner must come from --code-root")
    for name, module in tuple(sys.modules.items()):
        location = getattr(module, "__file__", None)
        if location and (name == "legsa_gins" or name.startswith("legsa_gins.")):
            if requested not in Path(location).resolve().parents:
                raise RuntimeError(f"Project module outside frozen snapshot: {name}")
    state = execution_state(requested, code_freeze_commit)
    identity = verify_executable(executable, registry.code_root)
    return replace(registry, code_root=requested), state, identity


def execution_state(root, commit):
    state = code_freeze_state(root, commit)
    state.pop("code_worktree_dirty_at_generation")
    state["code_worktree_dirty_at_execution"] = False
    return state


def _record_hashes(root):
    """Read the tracked C-03 record at its immutable publication commit."""
    record = _git_bytes(root, C03_COMMIT, "docs/paper_rebuild/CLEAN5_PROVIDER_FREEZE_RECORD.md")
    text = record.decode("utf-8")
    paths = dict(re.findall(r"\| `(<CLEAN_ROOT>/[^`]+)` \| `([0-9a-f]{64})` \|", text))
    profiles = {}
    for method, first, second, third in re.findall(
            r"\| (F01|F02|F03|A04|F04) \| `([0-9a-f]{64})` \| `([0-9a-f]{64})` \| `([0-9a-f]{64})` \| PASS \|", text):
        if first != second or second != third:
            raise RuntimeError("C-03 recorded cross-sequence frozen hashes disagree")
        profiles[method] = first
    if set(profiles) != set(METHODS):
        raise RuntimeError("C-03 record does not contain exactly five frozen profiles")
    return paths, profiles, sha256(record).hexdigest()


def verify_provider_files(provider_root, manifest):
    """Recheck every manifest-listed payload and retained backend file.

    Build scratch without a C-03 file hash is explicitly outside this check;
    it is never a solver input or included in the C-04 output seal.
    """
    required = set(PATH_ROLES.values()) | {"source_quality_metadata"}
    if set(manifest.get("artifacts", {})) != required:
        raise RuntimeError("Provider manifest must list exactly the six frozen runtime artifacts")
    checks = {}
    for role, entry in manifest["artifacts"].items():
        checks[role] = _hash_check(entry["path"], entry["sha256"], root=provider_root, role=f"Provider {role}")
    retained = manifest["raw_doppler_backend"]["retained_backend_artifacts"]
    required_backend = {"convbin_executable", "formal_raw_doppler_provider", "helper_executable",
                        "helper_source", "rebuilt_ubx", "rinex_nav", "rinex_obs"}
    if set(retained) != required_backend:
        raise RuntimeError("Retained backend artifact set differs from C-03")
    for role, entry in retained.items():
        checks["backend/" + role] = _hash_check(provider_root / entry["relative_path"], entry["sha256"],
                                                root=provider_root, role=f"Retained backend {role}")
    return checks


def preflight(registry, sequence, executable_identity, contract_version=1):
    if contract_version == 2:
        from .runtime_v2 import preflight_v2
        return preflight_v2(registry, sequence, executable_identity)
    stage = guard_path(registry.clean_root / "stages" / sequence.stage_id, role="C-04 stage",
                       allowed_root=registry.clean_root, must_exist=True)
    if (stage / "04_SOLVER_RUNS").exists() or (stage / "05_OUTPUT_SEAL").exists():
        raise FileExistsError("C-04 attempt already exists; overwrite and retry are forbidden")
    paths, hashes, record_sha = _record_hashes(registry.code_root)
    relative = f"configs/paper_rebuild/clean5/CLEAN5_{sequence.dataset_id}_SEQUENCE_CONTRACT.yaml"
    expected_contract = sha256(_git_bytes(registry.code_root, C02_COMMIT, relative)).hexdigest()
    contract_check = _hash_check(registry.code_root / relative, expected_contract,
                                 root=registry.code_root, role="C-02 contract")
    contract = load_yaml_mapping(contract_check["path"])
    expected_identity = {"dataset_id": sequence.dataset_id, "stage_id": sequence.stage_id,
                         "data_mode": sequence.data_mode}
    if any(contract["identity"].get(k) != v for k, v in expected_identity.items()):
        raise RuntimeError("Contract sequence identity mismatch")
    lock = selected_lock(registry, sequence)
    raw_hashes = {key: row["sha256"] for key, row in lock["rows"].items()}
    if raw_hashes != contract["identity"]["raw_files_sha256"]:
        raise RuntimeError("C-02 contract and raw-lock identities differ")
    frozen_paths = {}
    for relative_path in ("02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json", "03_RUNTIME_CONFIGS/RUNTIME_CONFIG_AUDIT.json"):
        alias = f"<CLEAN_ROOT>/stages/{sequence.stage_id}/{relative_path}"
        frozen_paths[relative_path] = _hash_check(stage / relative_path, paths[alias], root=stage, role="C-03 frozen metadata")
    manifest = _json(stage / "02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json")
    audit = _json(stage / "03_RUNTIME_CONFIGS/RUNTIME_CONFIG_AUDIT.json")
    for item in (manifest, audit):
        if any(item.get(k) != v for k, v in expected_identity.items()):
            raise RuntimeError("C-03 metadata sequence identity mismatch")
        if item.get("frozen_executable", {}).get("path") != executable_identity["path"] or item["frozen_executable"]["sha256"] != executable_identity["sha256"]:
            raise RuntimeError("C-03 executable lineage differs")
    if manifest["status"] != "PASS_PROVIDER_FREEZE" or audit["status"] != "PASS_PREPARED_NOT_EXECUTED":
        raise RuntimeError("C-03 provider/configuration gates must have passed")
    if manifest["raw_source_hashes"] != raw_hashes or manifest["contract_paths_sha256"][relative] != expected_contract:
        raise RuntimeError("C-03 contract/raw lineage differs")
    provider_checks = verify_provider_files(stage / "02_PROVIDER_FREEZE", manifest)
    # C-03 hash-referenced audit documents remain verifiable metadata, not raw opens.
    for relative_path, digest in manifest["audit_paths_sha256"].items():
        frozen_paths[relative_path] = _hash_check(stage / relative_path, digest, root=stage, role="C-03 audit")
    if manifest["artifacts"]["gnss_runtime_input"]["runtime_start_exclusive_in_window_count"] != EXPECTED_GNSS_ROWS[sequence.dataset_id]:
        raise RuntimeError("Frozen GNSS window row-count mismatch")
    profiles = {row["method_id"]: row for row in audit["profiles"]}
    if audit["method_order"] != list(METHODS) or len(audit["profiles"]) != 5 or set(profiles) != set(METHODS):
        raise RuntimeError("C-03 profile identity/order mismatch")
    configurations = {}
    for method, effective in METHODS.items():
        profile = profiles[method]
        path = stage / "03_RUNTIME_CONFIGS" / CONFIG_FILENAMES[method]
        alias = f"<CLEAN_ROOT>/stages/{sequence.stage_id}/03_RUNTIME_CONFIGS/{path.name}"
        check = _hash_check(path, paths[alias], root=stage, role=f"Rendered {method} config")
        frozen_paths[f"03_RUNTIME_CONFIGS/{path.name}"] = check
        text = path.read_text(encoding="utf-8")
        values = yaml.safe_load(text)
        if (profile["effective_configuration_id"] != effective or values["algorithm_id"] != effective
                or profile["runtime_config_sha256"] != check["sha256"]
                or frozen_parameter_hash(text) != hashes[method]
                or profile["frozen_parameter_hash"] != hashes[method]
                or scientific_runtime_config_hash(text) != profile["scientific_runtime_config_hash"]):
            raise RuntimeError(f"C-03 frozen profile/configuration mismatch: {method}")
        for key, role in PATH_ROLES.items():
            if Path(values[key]) != Path(provider_checks[role]["path"]):
                raise RuntimeError(f"{method} config path is not the frozen provider: {key}")
        configurations[method] = {"text": text, "profile": profile, "identity": check}
    occlusion = None
    if sequence.dataset_id == "BY2O":
        entry = manifest["occlusion_window"]
        occlusion = _hash_check(stage / "01_SEQUENCE_CONTRACT/OCCLUSION_WINDOW.json", entry["sha256"], root=stage,
                                role="Preregistered occlusion window")
        if occlusion["sha256"] != "4ffabd12c71ef08ec3bb43bb5969fe97883b657c6d68aec2fc827f1fb56e349f":
            raise RuntimeError("C-03 recorded occlusion window SHA-256 differs")
    return {"stage": stage, "contract": contract, "provider_manifest": manifest,
            "configurations": configurations, "provider_checks": provider_checks,
            "frozen_metadata_checks": frozen_paths, "contract_check": contract_check,
            "c03_record_sha256": record_sha, "lock": lock, "occlusion": occlusion}


def raw_checkpoint_worker(registry, sequence, phase, audit_dir):
    if phase not in ("pre_run", "post_run"):
        raise RuntimeError("Unknown raw checkpoint phase")
    lock = selected_lock(registry, sequence)
    hashes = verify_raw_sources(registry.raw_root, sorted(lock["rows"]), lock["rows"])
    payload = {"schema_version": RAW_CHECKPOINT_SCHEMA, "audit_phase": phase,
               "dataset_id": sequence.dataset_id, "raw_hash_lock_sha256": lock["sha256"],
               "expected": 22, "verified": len(hashes), "missing": 0, "mismatch": 0,
               "symlink_escape": 0, "raw_mutation": 0, "passed": True,
               "trace_read_role": "outer_raw_integrity_hash_audit_only",
               "trace_provider_or_solver_input": False, "verified_hashes": hashes,
               "synthetic_data_used": False, "semisynthetic_data_used": False}
    validate_checkpoint(payload, phase=phase, lock=lock)
    write_json_exclusive(audit_dir / f"{phase}_CHECKPOINT.json", payload)
    return payload


def run_checkpoint(args, registry, sequence, phase, audit_dir):
    log = audit_dir / f"{phase}_OPENAT.strace"
    command = [shutil.which("strace") or "strace", "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat", "-o", str(log),
               sys.executable, "-B", str(registry.code_root / "scripts/paper_rebuild/clean5_run_sequence.py"),
               "--sequence", sequence.dataset_id, "--code-root", str(registry.code_root),
               "--code-freeze-commit", args.code_freeze_commit, "--executable", str(args.executable),
               "--paths-config", str(args.paths_config), "--registry", str(args.registry), "--_checkpoint", phase]
    command.extend(["--contract-version", str(getattr(args, "contract_version", 1))])
    completed = run_process_group(command, cwd=registry.code_root, timeout_seconds=1800,
                                  timeout_message="CLEAN5 raw hash checkpoint timeout",
                                  launch_failure_message="CLEAN5 raw checkpoint launch failed")
    _write_text(audit_dir / f"{phase}_stdout.log", completed.stdout)
    _write_text(audit_dir / f"{phase}_stderr.log", completed.stderr)
    expected = {registry.raw_root / relative for relative in selected_lock(registry, sequence)["rows"]}
    try:
        audit = audit_records(open_records(log, registry.code_root), registry.raw_root, expected, checkpoint_phase=True)
        audit["strace_sha256"] = sha256_file(log)
    except Exception as exc:
        audit = {"pass": False, "failures": [str(exc)], "raw_open_count": None}
    audit.update(audit_phase=phase, worker_exit_code=completed.returncode, session_count=1,
                 trace_read_role="outer_raw_integrity_hash_audit_only")
    audit["pass"] = audit["pass"] and completed.returncode == 0
    write_json_exclusive(audit_dir / f"{phase}_STRACE_AUDIT.json", audit)
    if not audit["pass"]:
        raise RuntimeError(f"{phase} raw checkpoint/strace failed: {completed.stderr[-4000:]}")
    checkpoint = _json(audit_dir / f"{phase}_CHECKPOINT.json")
    validate_checkpoint(checkpoint, phase=phase, lock=selected_lock(registry, sequence))
    print(f"{sequence.dataset_id}: {phase} 22/22 PASS (hash-only session)", flush=True)
    return checkpoint, audit


def audit_solver_openat(log, *, cwd, raw_root, run_dir, clean_root=None):
    from .io_audit import audited_open_records, write_scope_audit
    records = audited_open_records(log, cwd)
    def inside(path, root):
        return path == root or root in path.parents
    raw = [row for row in records if inside(Path(row["path"]), raw_root)
           or inside(Path(row.get("lexical_path", row["path"])), raw_root)]
    scope = write_scope_audit(records, raw_root=raw_root, allowed_write_roots=[run_dir], clean_root=clean_root)
    forbidden = {"trace": sum(Path(row["path"]).name.lower().startswith("trace_") for row in records),
                 "bag": sum(Path(row["path"]).suffix.lower() == ".bag" for row in records),
                 "fpl": sum(Path(row["path"]).suffix.lower() == ".fpl" for row in records)}
    failures = []
    if not records:
        failures.append("No parseable solver openat records")
    if raw:
        failures.append("Solver opened raw_root")
    if any(forbidden.values()):
        failures.append("Solver opened trace/bag/fpl")
    if not scope["pass"]:
        failures.append("Solver write-open outside this run directory")
    return {"pass": not failures, "failures": failures, "session_count": 1,
            "total_open_count": len(records), "raw_open_count": len(raw),
            "forbidden_open_counts": forbidden,
            "trace_open_count": forbidden["trace"], "bag_open_count": forbidden["bag"],
            "fpl_open_count": forbidden["fpl"],
            "strace_sha256": sha256_file(log), "raw_open_records": raw,
            **{key: value for key, value in scope.items() if key != "pass"}}


def _write_text(path, text):
    with Path(path).open("x", encoding="utf-8") as handle:
        handle.write(text or "")


def run_one(*, registry, sequence, prepared, method, executable, state):
    effective = METHODS[method]
    run_id = f"{sequence.dataset_id}_{method}_{effective}"
    run_dir = prepared["stage"] / prepared.get("runs_subdir", "04_SOLVER_RUNS") / run_id
    run_dir.mkdir(exist_ok=False)
    config = prepared["configurations"][method]
    record = {"run_id": run_id, "dataset_id": sequence.dataset_id, "stage_id": sequence.stage_id,
              "data_mode": sequence.data_mode, "case_id": f"CLEAN5_{sequence.dataset_id}_NATURAL",
              "case_family": "natural_sequence", "seed_index": "", "method_id": method,
              "effective_profile": effective, "effective_configuration_id": effective,
              "logical_aliases": {"F03": ["F03", "A02"], "F04": ["F04", "A01"]}.get(method, [method]),
              "run_dir": str(run_dir), "terminal_status": "technical_failure", "exit_code": None,
              "runtime_seconds": 0.0, "nav_rows": None, "nav_time_start": None, "nav_time_end": None,
              "config_hash": None, "scientific_runtime_config_hash": None, "frozen_parameter_hash": None,
              "rendered_config_path": config["identity"]["path"],
              "rendered_config_sha256": config["identity"]["sha256"],
              "counters": {}, "validation_errors": [], "stderr_tail": "", **state,
              "code_commit": state["code_freeze_commit"], "frozen_executable": executable,
              "executable_sha256": executable["sha256"], "provider_files_sha256": prepared["provider_checks"],
              "provider_manifest_sha256": prepared["frozen_metadata_checks"]["02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json"]["sha256"],
              "raw_source_hashes": prepared["provider_manifest"]["raw_source_hashes"],
              "old_runtime_input_count": 0, "retry_count": 0, "evaluator_execution_count": 0,
              "module_expectation_source": "final_v23_clean_parity.METHOD_FEATURES and canonical541 bit table",
              **{key: False for key in FORBIDDEN_FLAGS}}
    try:
        text, hashes = bind_output_config(config["text"], run_dir, config["profile"]["frozen_parameter_hash"])
        record.update(hashes)
        native_config = yaml.safe_load(text)
        record["native_identity"] = {key: native_config[key] for key in
                                     ("stage_id", "case_id", "protocol_id", "run_id", "algorithm_id", "data_mode")}
        record["native_config_run_id"] = native_config["run_id"]
        config_path = run_dir / "CLEAN5_RUNTIME_CONFIG.yaml"
        _write_text(config_path, text)
        log = run_dir / "SOLVER_OPENAT.strace"
        command = [shutil.which("strace") or "strace", "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=openat", "-o", str(log),
                   executable["path"], "--config", str(config_path), "--output-dir", str(run_dir),
                   "--debug-update-timeline", "--debug-output-dir", str(run_dir), "--debug-max-rows", "1000000"]
        record["command"] = command
        started = time.monotonic()
        completed = run_process_group(command, cwd=registry.code_root, timeout_seconds=SOLVER_TIMEOUT_SECONDS,
                                      timeout_message="CLEAN5 solver timeout; process group terminated",
                                      launch_failure_message="CLEAN5 solver launch failed")
        record.update(runtime_seconds=time.monotonic() - started, exit_code=completed.returncode,
                      stderr_tail="\n".join(completed.stderr.splitlines()[-30:]))
        _write_text(run_dir / "stdout.log", completed.stdout)
        _write_text(run_dir / "stderr.log", completed.stderr)
        record["terminal_status"] = "COMPLETED" if completed.returncode == 0 else "technical_failure"
        if completed.returncode:
            record["validation_errors"].append(f"Solver exit code {completed.returncode}")
        try:
            audit = audit_solver_openat(log, cwd=registry.code_root, raw_root=registry.raw_root, run_dir=run_dir,
                                       clean_root=registry.clean_root)
        except Exception as exc:
            audit = {"pass": False, "failures": [str(exc)], "raw_open_count": None,
                     "forbidden_open_counts": {"trace": None, "bag": None, "fpl": None},
                     "write_open_count": None, "outside_run_write_open_count": None, "raw_write_open_count": None}
        audit["run_id"] = run_id
        record["strace_audit"] = audit
        write_json_exclusive(run_dir / "SOLVER_STRACE_AUDIT.json", audit)
        if not audit["pass"]:
            record["terminal_status"] = "technical_failure"
            record["validation_errors"].extend(audit["failures"])
        try:
            record.update(validate_run_outputs(run_dir, prepared["contract"]))
        except Exception as exc:
            record["validation_errors"].append(f"Output validation: {exc}")
            if record["terminal_status"] == "COMPLETED":
                record["terminal_status"] = getattr(exc, "terminal_status", "technical_failure")
        try:
            manifest = _json(run_dir / "RUN_MANIFEST.json")
            record["native_manifest_sha256"] = sha256_file(run_dir / "RUN_MANIFEST.json")
            record["native_provenance_flags"] = {key: manifest.get(key) for key in FORBIDDEN_FLAGS}
            record["all_native_counters"] = {key: value for key, value in manifest.items()
                                              if "count" in key or key.startswith("yaw_")}
            eligibility = expected_update_epochs(native_config,
                _json(run_dir / "PORT_INPUT_TIMELINE_SNAPSHOT.json"), Path(native_config["gnsspath"]))
            record["epoch_eligibility"] = eligibility
            record["effective_starttime"] = eligibility["effective_starttime"]
            record["t_init"] = eligibility["t_init"]
            record["skipped_epochs"] = eligibility["skipped_epochs"]
            record["nav_alignment"] = validate_nav_alignment(record["nav_time_start"], eligibility)
            record["effective_starttime_source"] = "PORT_INPUT_TIMELINE_SNAPSHOT.json.effective_starttime"
            try:
                record["counters"] = validate_profile_counters(effective, manifest, eligibility["expected_update_count"])
            except Exception as exc:
                record["counters"] = getattr(exc, "counters", {})
                record["validation_errors"].append(f"Counter validation: {exc}")
                if record["terminal_status"] == "COMPLETED":
                    record["terminal_status"] = "counter_mismatch"
            validate_clean5_manifest(manifest, text, prepared["contract"])
        except Exception as exc:
            record["validation_errors"].append(f"Native manifest validation: {exc}")
            if record["terminal_status"] == "COMPLETED":
                record["terminal_status"] = "technical_failure"
        if execution_state(registry.code_root, state["code_freeze_commit"]) != state:
            raise RuntimeError("Execution snapshot changed during solver execution")
    except Exception as exc:
        record["terminal_status"] = "technical_failure"
        record["validation_errors"].append(f"{type(exc).__name__}: {exc}")
    record["finished_at"] = _now()
    write_json_exclusive(run_dir / "CLEAN5_FORMAL_RUN_MANIFEST.json", record)
    print(f"{run_id}: {record['terminal_status']} exit={record['exit_code']} seconds={record['runtime_seconds']:.6f}", flush=True)
    if record["terminal_status"] != "COMPLETED":
        print(f"{run_id} stderr tail:\n{record['stderr_tail']}", flush=True)
    return record


def run_profiles(*, registry, sequence, prepared, executable, state):
    records = []
    for method in METHODS:
        records.append(run_one(registry=registry, sequence=sequence, prepared=prepared,
                               method=method, executable=executable, state=state))
    return records


def supervise(args, registry, sequence, state, executable):
    if not shutil.which("strace"):
        raise RuntimeError("strace is required; no solver launch without an openat audit")
    version = getattr(args, "contract_version", 1)
    runs_subdir, seal_subdir = ("04_SOLVER_RUNS_V2", "05_OUTPUT_SEAL_V2") if version == 2 else ("04_SOLVER_RUNS", "05_OUTPUT_SEAL")
    if sequence.dataset_id == "BY2O":
        previous = registry.clean_root / "stages" / registry.sequences["BY2H"].stage_id / seal_subdir / "SEAL_GATE.json"
        gate = _json(previous)
        if gate.get("code_freeze_commit") != state["code_freeze_commit"] or gate.get("run_count") != 5:
            raise RuntimeError("BY2H must finish and seal all five terminals under this freeze before BY2O")
        if version == 2 and not gate.get("passed"):
            raise RuntimeError("BY2H V2 seal gate failed; stop before BY2O")
    prepared = preflight(registry, sequence, executable, version)
    prepared["runs_subdir"] = runs_subdir
    runs_root = prepared["stage"] / runs_subdir
    runs_root.mkdir(exist_ok=False)
    audit_dir = runs_root / "00_SEQUENCE_AUDIT"
    audit_dir.mkdir(exist_ok=False)
    metadata = {"dataset_id": sequence.dataset_id, "stage_id": sequence.stage_id, "data_mode": sequence.data_mode,
                "contract_version": version, "runs_subdir": runs_subdir, "seal_subdir": seal_subdir,
                "case_id": f"CLEAN5_{sequence.dataset_id}_NATURAL", "case_family": "natural_sequence", **state,
                "frozen_executable": executable, "executable_sha256": executable["sha256"],
                "c02_commit": C02_COMMIT, "c03_record_commit": C03_COMMIT,
                "scientific_code_freeze_commit": "64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00",
                "c03_record_sha256": prepared["c03_record_sha256"], "contract_check": prepared["contract_check"],
                "provider_files": prepared["provider_checks"], "provider_hashes": prepared["provider_checks"],
                "provider_manifest_path": str(prepared["stage"] / "02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json"),
                "provider_manifest_sha256": prepared["frozen_metadata_checks"]["02_PROVIDER_FREEZE/PROVIDER_MANIFEST.json"]["sha256"],
                "contract": prepared["contract"], "module_expectation_policy": "frozen_canonical_features",
                "frozen_metadata_checks": prepared["frozen_metadata_checks"],
                "synthetic_data_used": False, "semisynthetic_data_used": False,
                "trace_used_online": False, "evaluator_execution_count": 0, "plot_execution_count": 0,
                "unhashed_provider_build_scratch_is_frozen_evidence": False}
    if prepared["occlusion"]:
        metadata.update(occlusion_window_path=prepared["occlusion"]["path"],
                        occlusion_window_sha256=prepared["occlusion"]["sha256"])
    write_json_exclusive(audit_dir / "PREFLIGHT.json", {"passed": True, **metadata})
    pre, pre_audit = run_checkpoint(args, registry, sequence, "pre_run", audit_dir)
    records = run_profiles(registry=registry, sequence=sequence, prepared=prepared, executable=executable, state=state)
    summaries = [row.get("strace_audit", {"pass": False, "run_id": row["run_id"]}) for row in records]
    failures = []
    seal = None
    try:
        seal = seal_outputs(prepared["stage"], records, metadata, summaries)
        validate_output_seal(seal["output_seal_path"])
    except Exception as exc:
        failures.append(f"Output seal failed: {exc}")
    post = post_audit = None
    try:
        post, post_audit = run_checkpoint(args, registry, sequence, "post_run", audit_dir)
        if pre["verified_hashes"] != post["verified_hashes"]:
            failures.append("Raw files changed between pre_run and post_run")
    except Exception as exc:
        failures.append(str(exc))
    provider_post = None
    try:
        provider_post = verify_provider_files(prepared["stage"] / "02_PROVIDER_FREEZE", prepared["provider_manifest"])
        if provider_post != prepared["provider_checks"]:
            failures.append("Provider identities changed after solver execution")
        for check in prepared["frozen_metadata_checks"].values():
            _hash_check(check["path"], check["sha256"], root=prepared["stage"], role="Post-run frozen metadata")
        if execution_state(registry.code_root, state["code_freeze_commit"]) != state:
            failures.append("Execution snapshot changed")
        if sha256_file(executable["path"]) != executable["sha256"]:
            failures.append("Frozen executable changed")
    except Exception as exc:
        failures.append(f"Post-run provider/code verification: {exc}")
    failed_runs = [row["run_id"] for row in records if row["terminal_status"] != "COMPLETED"]
    audit_pass = all(row.get("pass") is True for row in summaries)
    passed = not failures and not failed_runs and audit_pass and post is not None and seal is not None
    gate = {"status": "PASS" if passed else "PARTIAL", "passed": passed, "run_count": len(records),
            "completed_run_count": len(records) - len(failed_runs), "failed_runs": failed_runs,
            "failures": failures, "solver_strace_audits_passed": audit_pass, "output_seal": seal,
            "pre_run": pre, "post_run": post, "pre_run_strace": pre_audit, "post_run_strace": post_audit,
            "provider_post_run": provider_post, "sealed_at": _now(), **metadata}
    seal_root = prepared["stage"] / seal_subdir
    seal_root.mkdir(exist_ok=True)
    write_json_exclusive(seal_root / "SEAL_GATE.json", gate)
    print(json.dumps({"dataset_id": sequence.dataset_id, "seal_gate": gate["status"],
                      "failed_runs": failed_runs, "seal": seal, "failures": failures}, ensure_ascii=False), flush=True)
    return 0 if passed else 3


def main(argv=None, *, execution_script=None):
    supplied = list(sys.argv[1:] if argv is None else argv)
    if "--phase" in supplied:
        if supplied[supplied.index("--phase")+1] in ("render-v2", "amend-contracts-v2"):
            from .runtime_v2 import main as v2_main
            return v2_main(supplied, execution_script=execution_script)
        from .revalidation import main as revalidate_main
        return revalidate_main(supplied)
    root = Path(__file__).resolve().parents[4]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sequence", choices=("BY2H", "BY2O"), required=True)
    parser.add_argument("--code-root", type=Path, required=True)
    parser.add_argument("--code-freeze-commit", required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--paths-config", type=Path, required=True)
    parser.add_argument("--contract-version", type=int, choices=(1, 2), default=1)
    parser.add_argument("--registry", type=Path, default=root / "configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml")
    parser.add_argument("--_checkpoint", choices=("pre_run", "post_run"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    sys.dont_write_bytecode = True
    os.environ.update(PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0")
    try:
        registry = load_registry(args.registry, args.paths_config)
        registry, state, executable = execution_registry(registry, code_root=args.code_root,
            code_freeze_commit=args.code_freeze_commit, executable=args.executable,
            execution_script=execution_script if execution_script is not None else sys.argv[0])
        args.registry = args.registry.resolve(strict=True)
        args.paths_config = args.paths_config.resolve(strict=True)
        if registry.code_root not in args.registry.parents:
            raise RuntimeError("Sequence registry must come from the code freeze")
        sequence = registry.sequences[args.sequence]
        if args._checkpoint:
            folder = "04_SOLVER_RUNS_V2" if args.contract_version == 2 else "04_SOLVER_RUNS"
            audit_dir = registry.clean_root / "stages" / sequence.stage_id / folder / "00_SEQUENCE_AUDIT"
            raw_checkpoint_worker(registry, sequence, args._checkpoint, audit_dir)
            return 0
        return supervise(args, registry, sequence, state, executable)
    except Exception as exc:
        print(f"FAIL {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return 2
