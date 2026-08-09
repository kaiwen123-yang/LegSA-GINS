"""Hard-locked trusted-direct Canonical-541 preparation and one-shot execution.

The mode trusts hashes already recorded in the 5,951 method-bound manifests.
It requires every referenced input path to exist, but never reads or hashes the
IMU/GNSS/Raw-Doppler/Go2 payload bytes.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..clean2r2a_runner import build_runtime_config_from_trusted_metadata
from ..manifest import sha256_file
from .ablation_registry import ABLATION_METHODS
from .authorization import STAGE_ID, validate_attempt_root
from .execution_plan import normalize_case_row, read_csv
from .full_method_registry import FEATURE_FIELDS, FULL_METHODS, MethodProfile
from .run_registry import (
    build_logical_queues, effective_flag_hash, execution_key,
    validate_execution_registry,
)
from .runner import (
    TERMINAL_STATUSES, actual_rendered_runtime_config_sha256,
    build_runtime_config, run_unique_execution, scientific_runtime_config_hash,
    seal_unique_outputs, validate_terminal_output,
)


TRUSTED_ATTEMPT_NAME = ".attempt_20260808T200855P0800"
SCIENTIFIC_FREEZE = "64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00"
PREPARATION_BASELINE = "92ff47b2b0087e08bfb4eeb9737387426a74df8c"
SESSION_NAME = "canonical541_trusted_direct_20260808T200855P0800"
METHOD_BOUND_COUNT = 5951
LOGICAL_COUNT = 7033
JOBS = 12
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class TrustedDirectError(RuntimeError):
    pass


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp_{os.getpid()}")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n")
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise TrustedDirectError(f"refusing empty registry: {path.name}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp_{os.getpid()}")
    with temporary.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), extrasaction="ignore", lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
        handle.flush(); os.fsync(handle.fileno())
    os.replace(temporary, path)


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def validate_trusted_identity(stage_root: str | Path, scientific_freeze: str) -> Path:
    stage = validate_attempt_root(stage_root)
    if stage.name != TRUSTED_ATTEMPT_NAME:
        raise TrustedDirectError("trusted-direct mode is locked to the authorized attempt")
    if scientific_freeze != SCIENTIFIC_FREEZE:
        raise TrustedDirectError("trusted-direct scientific freeze mismatch")
    return stage


def _representatives() -> tuple[MethodProfile, ...]:
    result: list[MethodProfile] = []
    signatures: set[tuple[bool, ...]] = set()
    for profile in (*FULL_METHODS, *ABLATION_METHODS):
        if profile.signature not in signatures:
            signatures.add(profile.signature); result.append(profile)
    if len(result) != 11:
        raise TrustedDirectError("frozen method map does not contain eleven profiles")
    return tuple(result)


def _current_preparation_freeze(repo: Path) -> str:
    status = subprocess.run(("git", "status", "--porcelain"), cwd=repo,
                            capture_output=True, text=True, check=True)
    if status.stdout:
        raise TrustedDirectError("trusted-direct preparation requires a clean implementation HEAD")
    head = subprocess.run(("git", "rev-parse", "HEAD"), cwd=repo,
                          capture_output=True, text=True, check=True).stdout.strip()
    ancestor = subprocess.run(("git", "merge-base", "--is-ancestor", PREPARATION_BASELINE, head),
                              cwd=repo, capture_output=True, text=True, check=False)
    if ancestor.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40}", head):
        raise TrustedDirectError("implementation HEAD does not descend from trusted preparation baseline")
    return head


def _case_manifest(stage: Path) -> Path:
    candidates = (
        stage / "02_MATRIX_SPEC_LOCK/CANONICAL541_CASE_MANIFEST.csv",
        stage / "02_MATRIX_SPEC_LOCK/CANONICAL_BY2_DEGRADATION_CASE_MANIFEST.csv",
    )
    found = [path for path in candidates if path.is_file()]
    if len(found) != 1:
        raise TrustedDirectError("exactly one small Canonical-541 case manifest is required")
    return found[0].resolve(strict=True)


def _load_method_manifests(
    stage: Path, *, expected_executable_hash: str | None = None,
) -> dict[tuple[str, tuple[bool, ...]], tuple[Path, dict[str, Any]]]:
    root = stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/METHOD_BOUND"
    paths = sorted(root.glob("*/*/METHOD_BOUND_INPUT_MANIFEST.json"))
    if len(paths) != METHOD_BOUND_COUNT:
        raise TrustedDirectError(f"trusted method-bound count is {len(paths)}, expected 5951")
    bindings: dict[tuple[str, tuple[bool, ...]], tuple[Path, dict[str, Any]]] = {}
    profiles_by_signature = {profile.signature: profile for profile in _representatives()}
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise TrustedDirectError(f"method-bound manifest is not a regular file: {path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        case_id = str(payload.get("case_id", ""))
        flags = payload.get("effective_flags")
        actual = payload.get("actual_solver_inputs")
        hashes = payload.get("actual_solver_input_hashes")
        if not isinstance(flags, Mapping) or not isinstance(actual, Mapping) or not isinstance(hashes, Mapping):
            raise TrustedDirectError(f"method-bound metadata incomplete: {path}")
        def strict_bool(value: Any) -> bool:
            if isinstance(value, bool):
                return value
            if str(value).strip().lower() in {"true", "1"}:
                return True
            if str(value).strip().lower() in {"false", "0"}:
                return False
            raise TrustedDirectError(f"invalid method-bound boolean in {path}")
        signature = tuple(strict_bool(flags.get(field)) for field in FEATURE_FIELDS)
        profile = profiles_by_signature.get(signature)
        if (profile is None or case_id != path.parents[1].name
                or payload.get("method_id") != profile.method_id
                or payload.get("method_name") != profile.name
                or payload.get("effective_profile") != profile.effective_profile
                or {field: strict_bool(flags.get(field)) for field in FEATURE_FIELDS} != dict(profile.flags)
                or payload.get("stage_id") != STAGE_ID
                or payload.get("attempt_root") != str(stage)
                or payload.get("solver_code_freeze_commit") != SCIENTIFIC_FREEZE
                or (expected_executable_hash is not None
                    and payload.get("executable_sha256") != expected_executable_hash)):
            raise TrustedDirectError(f"method-bound recorded execution identity drift: {path}")
        if set(actual) != set(hashes) or any(not _SHA256.fullmatch(str(value)) for value in hashes.values()):
            raise TrustedDirectError(f"method-bound recorded input hash metadata invalid: {path}")
        for role, value in actual.items():
            source = Path(str(value)).resolve(strict=True)
            if not source.is_file():
                raise TrustedDirectError(f"required trusted input is not a file: {case_id}/{role}")
        bundle_hash = str(payload.get("method_bound_bundle_sha256", ""))
        if not _SHA256.fullmatch(bundle_hash):
            raise TrustedDirectError(f"method-bound bundle hash metadata invalid: {path}")
        key = (case_id, signature)
        if key in bindings:
            raise TrustedDirectError(f"duplicate case/profile method binding: {case_id}")
        bindings[key] = (path.resolve(strict=True), payload)
    return bindings


def prepare_trusted_direct(
    *, repo_root: str | Path, stage_root: str | Path, base_provider_root: str | Path,
    executable: str | Path, scientific_freeze: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    """Render exactly 11 configs per case, then construct all registries once."""

    repo = Path(repo_root).resolve(strict=True)
    stage = validate_trusted_identity(stage_root, scientific_freeze)
    preparation_freeze = _current_preparation_freeze(repo)
    binary = Path(executable).resolve(strict=True)
    executable_hash = sha256_file(binary)
    cases = [normalize_case_row(row) for row in read_csv(_case_manifest(stage))]
    if len(cases) != 541 or len({str(row["case_id"]) for row in cases}) != 541:
        raise TrustedDirectError("case manifest is not the exact 541-case set")
    bindings = _load_method_manifests(stage, expected_executable_hash=executable_hash)
    representatives = _representatives()
    expected_keys = {(str(case["case_id"]), profile.signature) for case in cases for profile in representatives}
    if set(bindings) != expected_keys:
        raise TrustedDirectError("method-bound case/profile set differs from exact 541 x 11")

    base_root = Path(base_provider_root).resolve(strict=True)
    auxiliary = base_root / "FRESH_AUXILIARIES_CLEAN2R2A/CLEAN1R2R1_AUXILIARY_MANIFEST.json"
    protocol = repo / "configs/paper_rebuild/clean1_by2_clean_protocol.yaml"
    templates = {
        profile.signature: build_runtime_config_from_trusted_metadata(
            method_id=(profile.effective_profile if profile.effective_profile in {
                "single_antenna_EKF", "basic_dual_yaw_EKF"
            } else profile.effective_profile),
            auxiliary_manifest=auxiliary, provider_protocol=protocol,
            output_dir=stage / "TRUSTED_TEMPLATE_PLACEHOLDER",
        ) for profile in representatives
    }

    full_rows, ablation_rows = build_logical_queues(cases)
    logical_source = [*full_rows, *ablation_rows]
    logical_lookup = {(str(row["case_id"]), str(row["method_id"])): row for row in logical_source}
    signature_owner: dict[tuple[str, tuple[bool, ...]], dict[str, Any]] = {}
    unique: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["case_id"])
        case_directories: set[Path] = set()
        for profile in representatives:
            manifest_path, manifest = bindings[(case_id, profile.signature)]
            run_id = f"RUN_{len(unique) + 1:05d}"
            owner = logical_lookup[(case_id, profile.method_id)]
            matrix = str(owner["matrix"])
            output_root = stage / (
                "08_FULL_ALGORITHM_RUNS" if matrix == "full_algorithm" else "10_INTERNAL_ABLATION_RUNS"
            ) / run_id
            output_root.mkdir(parents=True, exist_ok=True)
            if any(output_root.iterdir()):
                config_path = output_root / "CANONICAL541_RUNTIME_CONFIG.yaml"
                proof_path = output_root / "CANONICAL541_EXECUTION_PROOF.json"
                if not config_path.is_file() or (set(output_root.iterdir()) != {config_path} and not proof_path.is_file()):
                    raise TrustedDirectError(f"unexpected pre-run output state: {run_id}")
            config_text = build_runtime_config(
                profile=profile, clean_input_manifest="trusted-direct://not-read",
                auxiliary_manifest="trusted-direct://not-read", provider_protocol="trusted-direct://not-read",
                method_bound_manifest=manifest, output_dir=output_root,
                case_id=case_id, run_id=run_id,
                trusted_base_template=templates[profile.signature],
            )
            config_path = output_root / "CANONICAL541_RUNTIME_CONFIG.yaml"
            if config_path.exists():
                if config_path.read_text(encoding="utf-8") != config_text:
                    raise TrustedDirectError(f"trusted runtime config drift: {run_id}")
            else:
                with config_path.open("x", encoding="utf-8") as handle:
                    handle.write(config_text); handle.flush(); os.fsync(handle.fileno())
            case_directories.add(output_root)
            config_file_hash = sha256_file(config_path)
            scientific_hash = scientific_runtime_config_hash(config_text)
            provider_hash = str(manifest["method_bound_bundle_sha256"])
            key = execution_key(row=owner, method_bound_provider_hash=provider_hash,
                                runtime_config_hash=scientific_hash, executable_hash=executable_hash)
            record = {
                "run_id": run_id, "run_order": len(unique) + 1, "execution_key": key,
                "canonical_logical_id": owner["logical_id"], "logical_alias_count": 0,
                "case_id": case_id, "method_id": profile.method_id, "matrix": matrix,
                "effective_profile": profile.effective_profile,
                "case_family": owner.get("case_family", ""),
                "degradation_type_id": owner.get("degradation_type_id", ""),
                "seed_index": owner.get("seed_index", ""),
                "method_bound_provider_hash": provider_hash,
                "runtime_config_hash": scientific_hash,
                "executable_hash": executable_hash, "formal": True,
                "output_root": str(output_root), "repo_root": str(repo),
                "runtime_config_template_path": str(config_path),
                "runtime_config_template_hash": config_file_hash,
                "runtime_config_file_hash": config_file_hash,
                "runtime_config_path": str(config_path),
                "actual_rendered_runtime_config_sha256": actual_rendered_runtime_config_sha256(config_text),
                "method_bound_manifest_path": str(manifest_path),
                "method_bound_manifest_hash": sha256_file(manifest_path),
                "scientific_code_freeze_commit": SCIENTIFIC_FREEZE,
                "preparation_code_commit": preparation_freeze,
                "terminal_status": "PREPARED_AUTHORIZED_NOT_STARTED",
                **{field: bool(profile.flags[field]) for field in FEATURE_FIELDS},
            }
            unique.append(record); signature_owner[(case_id, profile.signature)] = record
        for directory in case_directories:
            _fsync_directory(directory)
        for parent in {directory.parent for directory in case_directories}:
            _fsync_directory(parent)

    method_profiles = {profile.method_id: profile for profile in (*FULL_METHODS, *ABLATION_METHODS)}
    logical: list[dict[str, Any]] = []
    for order, source in enumerate(logical_source, 1):
        row = dict(source); profile = method_profiles[str(row["method_id"])]
        owner = signature_owner[(str(row["case_id"]), profile.signature)]
        alias = str(row["logical_id"]) != str(owner["canonical_logical_id"])
        owner["logical_alias_count"] += 1
        row.update(
            logical_order=order, run_id=owner["run_id"], execution_key=owner["execution_key"],
            execution_alias=alias, alias_of=(owner["canonical_logical_id"] if alias else ""),
            method_bound_provider_hash=owner["method_bound_provider_hash"],
            runtime_config_hash=owner["runtime_config_hash"], executable_hash=executable_hash,
            provider_ready=True, formal=True, output_root=owner["output_root"],
            method_bound_manifest_hash=owner["method_bound_manifest_hash"],
            terminal_status="PREPARED_AUTHORIZED_NOT_STARTED",
        )
        logical.append(row)
    validate_execution_registry(logical, unique)
    registry = stage / "07_FULL_ALGORITHM_REGISTRY"
    unique_path = registry / "CANONICAL541_UNIQUE_RUN_REGISTRY.csv"
    logical_path = registry / "CANONICAL541_LOGICAL_ALIAS_REGISTRY.csv"
    full_path = registry / "FULL_ALGORITHM_QUEUE.csv"
    ablation_path = stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv"
    _write_csv(unique_path, unique); _write_csv(logical_path, logical)
    _write_csv(full_path, [row for row in logical if row["matrix"] == "full_algorithm"])
    _write_csv(ablation_path, [row for row in logical if row["matrix"] == "internal_ablation"])
    hash_rows: list[dict[str, Any]] = []
    representative_by_id = {profile.method_id: profile for profile in representatives}
    for row in unique:
        profile = representative_by_id[str(row["method_id"])]
        manifest_path, payload = bindings[(str(row["case_id"]), profile.signature)]
        hash_rows.append({
            "case_id": row["case_id"], "representative_method_id": row["method_id"],
            "effective_profile": row["effective_profile"],
            "method_bound_manifest_path": str(manifest_path),
            "method_bound_manifest_sha256": row["method_bound_manifest_hash"],
            "method_bound_provider_hash": row["method_bound_provider_hash"],
            "actual_solver_input_hashes_json": json.dumps(
                payload["actual_solver_input_hashes"], sort_keys=True, separators=(",", ":")
            ),
            "runtime_config_hash": row["runtime_config_hash"],
            "runtime_config_file_hash": row["runtime_config_file_hash"],
            "executable_sha256": executable_hash, "execution_key": row["execution_key"],
            "run_id": row["run_id"],
        })
    hash_registry_path = registry / "PROVIDER_CONFIG_EXECUTABLE_HASH_REGISTRY.csv"
    _write_csv(hash_registry_path, hash_rows)
    plan = {
        "schema_version": "paper_rebuild.canonical541_trusted_direct_plan.v1",
        "stage_id": STAGE_ID, "attempt_root": str(stage),
        "scientific_code_freeze_commit": SCIENTIFIC_FREEZE,
        "preparation_code_commit": preparation_freeze,
        "executable_path": str(binary), "executable_sha256": executable_hash,
        "method_bound_count": len(bindings), "runtime_config_count": len(unique),
        "unique_run_count": len(unique), "logical_row_count": len(logical),
        "full_logical_row_count": sum(row["matrix"] == "full_algorithm" for row in logical),
        "ablation_logical_row_count": sum(row["matrix"] == "internal_ablation" for row in logical),
        "alias_row_count": sum(bool(row["execution_alias"]) for row in logical),
        "trusted_manifest_recorded_payload_hashes": True,
        "payload_hash_reads_during_preparation": 0,
        "formal_execution_started": False, "solver_runs": 0,
        "jobs": JOBS, "metric_driven_rerun": False, "passed": True,
        "unique_registry_sha256": sha256_file(unique_path),
        "logical_alias_registry_sha256": sha256_file(logical_path),
        "full_queue_sha256": sha256_file(full_path),
        "ablation_queue_sha256": sha256_file(ablation_path),
        "provider_config_executable_hash_registry_sha256": sha256_file(hash_registry_path),
    }
    if (len(unique), len(logical), plan["alias_row_count"]) != (5951, 7033, 1082):
        raise TrustedDirectError("trusted-direct registry count closure failed")
    _atomic_json(registry / "EXECUTION_PLAN.json", plan)
    preparation_status = {
        "schema_version": "paper_rebuild.canonical541_trusted_direct_preparation_status.v1",
        "stage_id": STAGE_ID, "method_bound_completed": METHOD_BOUND_COUNT,
        "runtime_configs_written": METHOD_BOUND_COUNT,
        "runtime_configs_completed": METHOD_BOUND_COUNT,
        "unique_runs_planned": METHOD_BOUND_COUNT,
        "logical_rows_planned": LOGICAL_COUNT,
        "execution_plan_created": True, "formal_execution_started": False,
        "payload_hash_reads": 0, "passed": True,
    }
    _atomic_json(registry / "PREPARATION_STATUS.json", preparation_status)
    observable = {
        "session_name": SESSION_NAME, "pid": os.getpid(), "process_pid": os.getpid(),
        "phase": "TRUSTED_DIRECT_PREPARED", "formal_execution_started": False,
        "runtime_configs_written": METHOD_BOUND_COUNT, "execution_plan_created": True,
        "running_solver_count": 0, "jobs": JOBS, "heartbeat_time": _now(),
    }
    _atomic_json(stage / "RUN_SESSION.json", observable)
    _atomic_json(stage / "CANONICAL541_STATUS.json", observable)
    return plan, unique, logical


def _profile_map() -> dict[str, MethodProfile]:
    return {profile.method_id: profile for profile in (*FULL_METHODS, *ABLATION_METHODS)}


def execute_trusted_direct(
    *, repo_root: str | Path, stage_root: str | Path, executable: str | Path,
    scientific_freeze: str, raw_root: str | Path, clean_root: str | Path,
    unique_rows: Sequence[Mapping[str, Any]], logical_rows: Sequence[Mapping[str, Any]],
    timeout_seconds: int = 1800,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Submit all 5,951 physical runs once to one 12-worker executor."""

    stage = validate_trusted_identity(stage_root, scientific_freeze)
    binary = Path(executable).resolve(strict=True)
    if len(unique_rows) != METHOD_BOUND_COUNT or len(logical_rows) != LOGICAL_COUNT:
        raise TrustedDirectError("trusted-direct execution requires exact prepared registries")
    expected_executable_hash = str(unique_rows[0]["executable_hash"])
    if sha256_file(binary) != expected_executable_hash:
        raise TrustedDirectError("trusted-direct executable changed before submission")
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        os.environ[name] = "1"
    plan_path = stage / "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan.update(formal_execution_started=True, formal_execution_started_at=_now())
    _atomic_json(plan_path, plan)
    status_path = stage / "CANONICAL541_STATUS.json"
    _atomic_json(status_path, {
        "session_name": SESSION_NAME, "pid": os.getpid(), "process_pid": os.getpid(),
        "phase": "TRUSTED_DIRECT_SUBMITTING_5951", "formal_execution_started": True,
        "runtime_configs_written": METHOD_BOUND_COUNT, "execution_plan_created": True,
        "running_solver_count": 0, "jobs": JOBS, "heartbeat_time": _now(),
    })
    profiles = _profile_map(); by_run = {str(row["run_id"]): dict(row) for row in unique_rows}
    stop_event = threading.Event()

    def run_one(row: Mapping[str, Any]) -> dict[str, Any]:
        if stop_event.is_set():
            raise TrustedDirectError("trusted-direct submission cancelled after engineering failure")
        root = Path(str(row["output_root"]))
        config = root / "CANONICAL541_RUNTIME_CONFIG.yaml"
        proof_path = root / "CANONICAL541_EXECUTION_PROOF.json"
        updated = dict(row)
        if proof_path.is_file():
            updated["runtime_config_file_hash"] = sha256_file(config)
            updated["runtime_config_path"] = str(config.resolve(strict=True))
            proof = validate_terminal_output(updated)
            updated["terminal_status"] = proof["terminal_status"]
            return updated
        proof = run_unique_execution(
            executable=binary, runtime_config=config,
            method_bound_manifest=row["method_bound_manifest_path"], output_root=root,
            profile=profiles[str(row["method_id"])], case_id=str(row["case_id"]),
            run_id=str(row["run_id"]), raw_root=raw_root, clean_root=clean_root,
            repo_root=repo_root, expected_executable_hash=expected_executable_hash,
            expected_runtime_config_hash=str(row["runtime_config_file_hash"]),
            expected_scientific_config_hash=str(row["runtime_config_hash"]),
            expected_method_bound_manifest_hash=str(row["method_bound_manifest_hash"]),
            timeout_seconds=timeout_seconds, trusted_manifest_hashes=True,
        )
        updated["terminal_status"] = proof["terminal_status"]
        if proof["terminal_status"] not in TERMINAL_STATUSES:
            stop_event.set()
            raise TrustedDirectError(
                f"trusted-direct engineering failure: {row['run_id']}:{proof['terminal_status']}"
            )
        return updated

    failures: list[BaseException] = []; successful = 0; cancelled = 0; settled = 0
    with ThreadPoolExecutor(max_workers=JOBS) as pool:
        futures = {pool.submit(run_one, row): str(row["run_id"]) for row in unique_rows}
        _atomic_json(status_path, {
            "session_name": SESSION_NAME, "pid": os.getpid(), "process_pid": os.getpid(),
            "phase": "TRUSTED_DIRECT_RUNNING_5951", "formal_execution_started": True,
            "runtime_configs_written": METHOD_BOUND_COUNT, "execution_plan_created": True,
            "running_solver_count": JOBS, "jobs": JOBS, "heartbeat_time": _now(),
        })
        for future in as_completed(futures):
            run_id = futures[future]
            try:
                by_run[run_id] = future.result()
                successful += 1
            except BaseException as exc:
                if future.cancelled():
                    cancelled += 1
                if not failures:
                    failures.append(exc)
                stop_event.set()
                for pending in futures:
                    if not pending.done():
                        pending.cancel()
            settled += 1
            if settled % 25 == 0 or settled == METHOD_BOUND_COUNT:
                _atomic_json(status_path, {
                    "session_name": SESSION_NAME, "pid": os.getpid(), "process_pid": os.getpid(),
                    "phase": "TRUSTED_DIRECT_RUNNING_5951", "formal_execution_started": True,
                    "runtime_configs_written": METHOD_BOUND_COUNT, "execution_plan_created": True,
                    "completed_unique_runs": successful, "cancelled_unique_runs": cancelled,
                    "running_solver_count": min(JOBS, METHOD_BOUND_COUNT - settled),
                    "jobs": JOBS, "heartbeat_time": _now(),
                })
    unique = [by_run[str(row["run_id"])] for row in unique_rows]
    if failures:
        _atomic_json(status_path, {
            "session_name": SESSION_NAME, "pid": os.getpid(), "process_pid": os.getpid(),
            "phase": "TRUSTED_DIRECT_BLOCKED_ENGINEERING_FAILURE",
            "formal_execution_started": True, "running_solver_count": 0,
            "runtime_configs_written": METHOD_BOUND_COUNT, "execution_plan_created": True,
            "completed_unique_runs": successful, "cancelled_unique_runs": cancelled,
            "pending_or_not_started_unique_runs": METHOD_BOUND_COUNT - successful - cancelled,
            "jobs": JOBS,
            "failure": str(failures[0]), "heartbeat_time": _now(),
        })
        raise failures[0]
    unresolved = [row for row in unique if row.get("terminal_status") not in TERMINAL_STATUSES]
    if unresolved:
        raise TrustedDirectError(f"trusted-direct nonterminal rows: {len(unresolved)}")
    by_id = {str(row["run_id"]): row for row in unique}
    logical = [{**dict(row), "terminal_status": by_id[str(row["run_id"])]["terminal_status"]}
               for row in logical_rows]
    registry = stage / "07_FULL_ALGORITHM_REGISTRY"
    _write_csv(registry / "CANONICAL541_UNIQUE_RUN_REGISTRY.csv", unique)
    _write_csv(registry / "CANONICAL541_LOGICAL_ALIAS_REGISTRY.csv", logical)
    _write_csv(registry / "FULL_ALGORITHM_QUEUE.csv", [row for row in logical if row["matrix"] == "full_algorithm"])
    _write_csv(stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv",
               [row for row in logical if row["matrix"] == "internal_ablation"])
    attempts = [{
        "run_id": row["run_id"], "method_id": row["method_id"], "case_id": row["case_id"],
        "attempt": 1, "terminal_status": row["terminal_status"], "technical_retry": False,
        "retry_authorized": False, "metric_driven_rerun": False,
        "attempt_root": row["output_root"], "output_root": row["output_root"],
        "runtime_config_path": row["runtime_config_path"],
        "runtime_config_hash": row["runtime_config_file_hash"],
    } for row in unique]
    seal = seal_unique_outputs(
        unique, logical, stage / "11_OUTPUT_SEAL", raw_root=raw_root, attempt_rows=attempts,
    )
    plan.update(solver_runs=METHOD_BOUND_COUNT, terminal_unique_run_count=METHOD_BOUND_COUNT,
                output_sealed=True, output_seal_manifest_sha256=seal["manifest_sha256"])
    _atomic_json(plan_path, plan)
    _atomic_json(status_path, {
        "session_name": SESSION_NAME, "pid": os.getpid(), "process_pid": os.getpid(),
        "phase": "TRUSTED_DIRECT_OUTPUT_SEALED", "formal_execution_started": True,
        "runtime_configs_written": METHOD_BOUND_COUNT, "execution_plan_created": True,
        "completed_unique_runs": METHOD_BOUND_COUNT, "running_solver_count": 0,
        "jobs": JOBS, "heartbeat_time": _now(),
    })
    return unique, seal
