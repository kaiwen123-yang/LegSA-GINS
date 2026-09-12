"""Preparation-only support for the canonical BY2 541-case matrix.

This module deliberately stops at exact input binding and queue construction.
It cannot launch the solver, evaluator, or trace reader.  Formal execution is
guarded by a separate, future human-approved execution freeze.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import yaml

from .ablation_registry import (
    ABLATION_METHODS,
    validate_canonical_ablation_config,
    validate_tracked_ablation_contract,
)
from .execution_plan import (
    ExecutionPlanError,
    PROFILE_BY_METHOD,
    _profile_representatives,
    _provider_protocol_paths,
    normalize_case_row,
    read_csv,
    validate_code_freeze_gate,
    write_csv_atomic,
)
from .full_method_registry import (
    FEATURE_FIELDS,
    FULL_METHODS,
    MethodProfile,
    validate_canonical_full_config,
    validate_tracked_method_contract,
)
from .provider_generator import (
    ProviderBundle,
    ProviderTable,
    _read_csv,
    compose_solver_gnss18,
    sha256_file,
)
from .run_registry import build_logical_queues, resolve_execution_aliases
from .runner import (
    build_runtime_config, canonical_data_mode, runtime_profile_id,
    scientific_runtime_config_hash, actual_rendered_runtime_config_sha256,
)
from .authorization import CONTRACT as AUTHORIZATION_CONFIG, load_execution_authorization, validate_attempt_root
from ..manifest import git_code_state


STAGE_ID = "CLEAN3R4_BY2_CANONICAL_541_REPAIRED_MATRIX"
METHOD_BOUND_TOTAL = 541 * 11
FULL_QUEUE_TOTAL = 541 * 4
ABLATION_QUEUE_TOTAL = 541 * 9
ALL_LOGICAL_TOTAL = FULL_QUEUE_TOTAL + ABLATION_QUEUE_TOTAL
KNOWN_RECOVERY_UNIQUE_COUNT = 3981
KNOWN_RECOVERY_ALIAS_COUNT = 3052
KNOWN_RECOVERY_ANNOTATED_COUNT = 3981
KNOWN_RECOVERY_UNTOUCHED_COUNT = 1970
KNOWN_RECOVERY_CONFIG_COUNT = 3981
KNOWN_RECOVERY_CASE_COUNT = 541
KNOWN_RECOVERY_PROFILES_PER_CASE = 11
KNOWN_RECOVERY_COMMIT = "64c81965b17ef1bf8ae2ce3e4dd7b1ae35110b00"
KNOWN_RECOVERY_HASHES = {
    "EXECUTION_PLAN.json": "197fe18ab5e6855fbd3615ec2fc9bf492a31342e5cc04363329e0ecd494083f1",
    "CANONICAL541_UNIQUE_RUN_REGISTRY.csv": "f80f0c438cf309fd88d1346fb2278e6586a64700aebebf5db4a2a37f42c5038a",
    "FULL_ALGORITHM_QUEUE.csv": "7090889d51ebcebed332898e4310c1c1efda36c93b0c33cad7f8c73623f8102d",
    "INTERNAL_ABLATION_QUEUE.csv": "fd5435ce385812ff3f89b47cf00f629c0f34b3850cf04346a7b81b67aec5a006",
    "PREPARATION_STATUS.json": "282eb1e5f9bfcad8f208c83a0cb56d711d86acd27530d795773de979b72eaa36",
}
KNOWN_RECOVERY_SESSION_HASHES = {
    "RUN_SESSION.json": "3ad5e4b831e397d15c8e4a6ffbf1a83a40f9cadc44b93f98085611775cb437a0",
    "CANONICAL541_STATUS.json": "c4ba0b98032d8d9fad7dfce65712a0b3b0fe88343e5ef39b6446264559bbce66",
    "pipeline.stdout.log": "23cf06be5fa0d4500797655d45bc2b8be73a68d1bd562f3bb5272dba6ee4fdd2",
    "pipeline.stderr.log": "5731e7e2bbda2f26c496f526246300692d08a8e0b80cced95abb5a609c43e59e",
}
KNOWN_RECOVERY_PIDS = frozenset((403582, 403631))
SOURCE_NAMES = (
    "gnss_position",
    "receiver_velocity",
    "dual_yaw",
    "raw_doppler",
    "go2_rp",
    "go2_hv",
    "source_quality_metadata",
)
GNSS_SOURCE_NAMES = ("gnss_position", "receiver_velocity", "dual_yaw")
SHARED_GNSS_RE = re.compile(r"(?P<sha>[0-9a-f]{64})\.gnss\Z")


class PreparationError(RuntimeError):
    """Fail-closed preparation contract violation."""


class PreparationAuthorizationError(PreparationError):
    """Tracked repaired-execution authorization or ordering is invalid."""


def scientific_method_runtime_hash(
    profile: MethodProfile, case_id: str, runtime_contract_hash: str,
) -> str:
    """Hash the scientific runtime contract without paths, run IDs, or manifest self-reference."""

    payload = {
        "stage_id": STAGE_ID,
        "protocol_id": "CANONICAL541_BY2_CONTROLLED_DEGRADATION",
        "data_mode": canonical_data_mode(case_id),
        "algorithm_id": runtime_profile_id(profile),
        "effective_flags": dict(profile.flags),
        "tracked_runtime_contract_sha256": runtime_contract_hash,
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, payload: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp_{os.getpid()}")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return path


def _atomic_text(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp_{os.getpid()}")
    with temporary.open("x", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    directory_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    return path


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _regular_file_inventory(root: Path) -> dict[str, str]:
    """Inventory only regular non-symlink files and reject tmp/unknown links."""

    if not root.exists():
        return {}
    if root.is_symlink() or not root.is_dir():
        raise PreparationError(f"protected inventory root is not a regular directory: {root}")
    output: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise PreparationError(f"symlink in protected recovery inventory: {path}")
        if path.is_dir():
            if ".tmp_" in path.name:
                raise PreparationError(f"temporary directory in protected recovery inventory: {path}")
            continue
        if not path.is_file() or ".tmp_" in path.name:
            raise PreparationError(f"non-regular or temporary protected recovery item: {path}")
        relative = path.relative_to(root).as_posix()
        output[relative] = sha256_file(path)
    return output


PROTECTED_LIVE_ROOTS = (
    ("compact_readiness", "01_COMPACT_READINESS_RUN"),
    ("git_freeze", "01_GIT_FREEZE"),
    ("matrix_spec", "02_MATRIX_SPEC_LOCK"),
    ("seeds_anchors", "03_SEEDS_AND_ANCHORS"),
    ("effect_rules", "04_EFFECT_RULES"),
    ("provider_ready", "06_PROVIDER_READY"),
    ("shared_gnss", "07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/SHARED_GNSS_BY_HASH"),
    ("audits", "16_AUDITS"),
)
PROTECTED_LIVE_FILES = (
    "RUN_SESSION.json", "CANONICAL541_STATUS.json",
    "00_PIPELINE_LOGS/pipeline.stdout.log", "00_PIPELINE_LOGS/pipeline.stderr.log",
)
PROTECTED_LIVE_EXCLUSIONS = (
    "16_AUDITS/CANONICAL541_EXECUTION_INPUT_COMPLETENESS_AUDIT.json",
    "16_AUDITS/CANONICAL541_PREPARATION_REPORT.json",
    "16_AUDITS/CANONICAL541_PREPARATION_REPORT.md",
    "16_AUDITS/CANONICAL541_PREPARATION_REVIEW_PACKET.json",
)


def scan_protected_live_set(stage_root: str | Path) -> dict[str, Any]:
    """Scan the frozen live preparation/output roots with explicit exclusions."""

    stage = Path(stage_root).resolve(strict=True)
    rows: list[dict[str, str]] = []
    role_counts: dict[str, int] = {}
    for role, relative_root in PROTECTED_LIVE_ROOTS:
        root = stage / relative_root
        if not root.is_dir() or root.is_symlink():
            raise PreparationError(f"protected live root is omitted or nonregular: {relative_root}")
        inventory = _regular_file_inventory(root)
        included = {
            relative: digest for relative, digest in inventory.items()
            if (Path(relative_root) / relative).as_posix() not in PROTECTED_LIVE_EXCLUSIONS
        }
        if not included:
            raise PreparationError(f"protected live root is empty after exclusions: {relative_root}")
        role_counts[role] = len(included)
        for relative, digest in included.items():
            rows.append({
                "role": role, "relative_path": relative,
                "absolute_path": str(root / relative), "sha256": digest,
            })
    for relative in PROTECTED_LIVE_FILES:
        path = stage / relative
        if not path.is_file() or path.is_symlink():
            raise PreparationError(f"protected live session file is omitted or nonregular: {relative}")
        rows.append({"role": "session_file", "relative_path": relative,
                     "absolute_path": str(path), "sha256": sha256_file(path)})
    role_counts["session_file"] = len(PROTECTED_LIVE_FILES)
    if not rows or role_counts.get("session_file") != 4:
        raise PreparationError("protected live scan is empty or omitted")
    canonical = [f"{row['role']}\0{row['relative_path']}\0{row['sha256']}" for row in rows]
    return {
        "roots": [{"role": role, "relative_root": root} for role, root in PROTECTED_LIVE_ROOTS],
        "files": list(PROTECTED_LIVE_FILES),
        "exclusions": list(PROTECTED_LIVE_EXCLUSIONS),
        "rows": rows, "role_counts": role_counts, "file_count": len(rows),
        "set_sha256": hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest(),
    }


def _validate_protected_scan_record(record: Mapping[str, Any]) -> None:
    expected_roots = [{"role": role, "relative_root": root} for role, root in PROTECTED_LIVE_ROOTS]
    rows = record.get("rows")
    if (
        record.get("roots") != expected_roots
        or record.get("files") != list(PROTECTED_LIVE_FILES)
        or record.get("exclusions") != list(PROTECTED_LIVE_EXCLUSIONS)
        or not isinstance(rows, list) or not rows
        or record.get("file_count") != len(rows)
        or sum(int(value) for value in record.get("role_counts", {}).values()) != len(rows)
    ):
        raise PreparationError("protected live scan roots/exclusions/counts are omitted or unexpected")
    canonical = [f"{row['role']}\0{row['relative_path']}\0{row['sha256']}" for row in rows]
    if hashlib.sha256("\n".join(canonical).encode("utf-8")).hexdigest() != record.get("set_sha256"):
        raise PreparationError("protected live scan set hash mismatch")


def _canonical_sidecar_bytes(artifact: Path) -> bytes:
    return f"{sha256_file(artifact)}  {artifact.name}\n".encode("ascii")


def _write_or_validate_recovery_sidecar(artifact: Path, sidecar: Path) -> None:
    expected = _canonical_sidecar_bytes(artifact)
    if sidecar.exists():
        if sidecar.is_symlink() or not sidecar.is_file() or sidecar.read_bytes() != expected:
            raise PreparationError(f"noncanonical recovery sidecar: {sidecar.name}")
    else:
        _atomic_text(sidecar, expected.decode("ascii"))


def _is_false(value: Any) -> bool:
    return value is False


def load_preparation_authorization(repo_root: str | Path) -> dict[str, Any]:
    return load_execution_authorization(repo_root)


def assert_tracked_execution_authorized(
    *, repo_root: str | Path, requested_operation: str,
) -> dict[str, Any]:
    """Fail before any runner/evaluator side effect under the current contract."""

    contract = load_preparation_authorization(repo_root)
    allowed_field = {
        "full_algorithm": "full_algorithm_execution_allowed",
        "internal_ablation": "internal_ablation_execution_allowed",
        "evaluator": "evaluator_allowed_after_output_seal",
    }.get(requested_operation)
    if allowed_field is None:
        raise PreparationAuthorizationError(f"unknown formal operation: {requested_operation}")
    # 中文说明：这里是入口级硬门禁；不能先 prepare、跑 smoke 或打开 trace 再检查授权。
    if (
        contract.get("execution_authorized") is not True
        or contract.get("solver_allowed_after_readiness_freeze") is not True
        or contract.get(allowed_field) is not True
        or contract.get("human_approval_required") is not False
    ):
        raise PreparationAuthorizationError(
            "repaired Canonical-541 tracked execution authorization is incomplete"
        )
    return contract


def require_human_execution_freeze(
    *, repo_root: str | Path, stage_root: str | Path, requested_operation: str,
    executable_sha256: str, plan_sha256: str,
) -> dict[str, Any]:
    """Bind the tracked human authorization to the frozen executable and plan."""

    contract = assert_tracked_execution_authorized(
        repo_root=repo_root, requested_operation=requested_operation,
    )
    stage = validate_attempt_root(stage_root)
    plan_path = stage / "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json"
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    if (
        payload.get("execution_authorized") is not True
        or payload.get("executable_sha256") != executable_sha256
        or sha256_file(plan_path) != plan_sha256
    ):
        raise PreparationAuthorizationError("authorized repaired execution plan identity mismatch")
    return payload


def assert_execution_plan_authorized(
    *, stage_root: str | Path, requested_operation: str,
    tracked_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Second fail-closed gate on the stage-local plan and human freeze."""

    stage = validate_attempt_root(stage_root)
    plan_path = stage / "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    operation_field = {
        "full_algorithm": "full_algorithm_execution_allowed",
        "internal_ablation": "internal_ablation_execution_allowed",
        "evaluator": "evaluator_allowed_after_output_seal",
    }.get(requested_operation)
    if operation_field is None:
        raise PreparationAuthorizationError(f"unknown formal operation: {requested_operation}")
    if (
        plan.get("execution_authorized") is not True
        or plan.get("solver_allowed_after_readiness_freeze") is not True
        or plan.get(operation_field) is not True
        or plan.get("human_approval_required") is not False
    ):
        raise PreparationAuthorizationError("stage execution plan is not authorized")
    return plan


class UniqueFileHashCache:
    """Hash each physical file once and fail if it mutates during preparation."""

    def __init__(self, hasher: Callable[[Path], str] = sha256_file):
        self._hasher = hasher
        self._entries: dict[Path, tuple[tuple[int, int, int, int], str]] = {}
        self._json_entries: dict[Path, Any] = {}
        self.physical_reads = 0

    @staticmethod
    def _identity(path: Path) -> tuple[int, int, int, int]:
        stat = path.stat()
        return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)

    def sha256(self, path: str | Path) -> str:
        resolved = Path(path).resolve(strict=True)
        identity = self._identity(resolved)
        cached = self._entries.get(resolved)
        if cached is not None:
            if cached[0] != identity:
                raise PreparationError(f"prepared input mutated during hash cache lifetime: {resolved}")
            return cached[1]
        digest = self._hasher(resolved)
        if self._identity(resolved) != identity:
            raise PreparationError(f"prepared input mutated while hashing: {resolved}")
        self._entries[resolved] = (identity, digest)
        self.physical_reads += 1
        return digest

    def read_json(self, path: str | Path) -> Any:
        """Read, hash, and parse one JSON artifact in one physical read."""

        resolved = Path(path).resolve(strict=True)
        identity = self._identity(resolved)
        if resolved in self._json_entries:
            cached = self._entries[resolved]
            if cached[0] != identity:
                raise PreparationError(f"JSON artifact mutated during cache lifetime: {resolved}")
            return self._json_entries[resolved]
        raw = resolved.read_bytes()
        if self._identity(resolved) != identity:
            raise PreparationError(f"JSON artifact mutated while reading: {resolved}")
        payload = json.loads(raw.decode("utf-8"))
        self._entries[resolved] = (identity, hashlib.sha256(raw).hexdigest())
        self._json_entries[resolved] = payload
        self.physical_reads += 1
        return payload

    @property
    def unique_file_count(self) -> int:
        return len(self._entries)


class ProviderTableCache:
    """Parse every resolved provider table no more than once."""

    def __init__(self):
        self._entries: dict[Path, tuple[tuple[int, int, int, int], ProviderTable]] = {}
        self.physical_parses = 0

    def get(self, path: str | Path, *, expected_semantic_sha256: str) -> ProviderTable:
        resolved = Path(path).resolve(strict=True)
        stat = resolved.stat(); identity = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)
        cached = self._entries.get(resolved)
        if cached is not None:
            if cached[0] != identity:
                raise PreparationError(f"provider table mutated during parse cache lifetime: {resolved}")
            return cached[1]
        fields, rows = _read_csv(resolved)
        table = ProviderTable(fields, rows)
        if table.sha256() != expected_semantic_sha256:
            raise PreparationError(f"provider semantic hash mismatch: {resolved}")
        self._entries[resolved] = (identity, table)
        self.physical_parses += 1
        return table


@dataclass(frozen=True)
class ProviderRegistryRow:
    case_id: str
    source: str
    byte_sha256: str
    size_bytes: int
    semantic_sha256: str
    storage_mode: str
    resolved_path: Path


@dataclass(frozen=True)
class ExpectedBinding:
    ordinal: int
    case_id: str
    profile: MethodProfile
    destination: Path


class PreparationStatusWriter:
    """Write a small status atomically, at most once per requested interval."""

    def __init__(self, path: str | Path, *, interval_seconds: float = 60.0,
                 clock: Callable[[], float] = time.monotonic,
                 authorization: Mapping[str, Any] | None = None):
        if interval_seconds <= 0:
            raise PreparationError("status interval must be positive")
        self.path = Path(path)
        self.interval_seconds = float(interval_seconds)
        self.clock = clock
        self.last_write: float | None = None
        self.authorization = dict(authorization or {
            "execution_authorized": True,
            "solver_allowed_after_readiness_freeze": True,
            "evaluator_allowed_after_output_seal": True,
            "human_approval_required": False,
        })

    def write(self, *, phase: str, method_bound_completed: int,
              cases_completed: int, full_queue_rows: int = 0,
              ablation_queue_rows: int = 0, unique_runs_planned: int = 0,
              force: bool = False) -> bool:
        now = self.clock()
        if not force and self.last_write is not None and now - self.last_write < self.interval_seconds:
            return False
        payload = {
            "schema_version": "paper_rebuild.canonical541_preparation_status.v1",
            "stage_id": STAGE_ID,
            "scope": "AUTHORIZED_PREPARATION",
            "phase": phase,
            "method_bound_completed": int(method_bound_completed),
            "method_bound_total": METHOD_BOUND_TOTAL,
            "cases_completed": int(cases_completed),
            "cases_total": 541,
            "full_queue_rows": int(full_queue_rows),
            "ablation_queue_rows": int(ablation_queue_rows),
            "unique_runs_planned": int(unique_runs_planned),
            "solver_runs": 0,
            "evaluator_runs": 0,
            "trace_reads": 0,
            "execution_authorized": self.authorization["execution_authorized"],
            "solver_allowed_after_readiness_freeze": self.authorization["solver_allowed_after_readiness_freeze"],
            "evaluator_allowed_after_output_seal": self.authorization["evaluator_allowed_after_output_seal"],
            "human_approval_required": self.authorization["human_approval_required"],
            "formal_execution_started": False,
            "updated_at_utc": _utc_now(),
        }
        _atomic_json(self.path, payload)
        self.last_write = now
        return True


def validate_safe_cli_mode(*, prepare_only: bool, resume_preparation: bool,
                           stop_before_execution: bool) -> None:
    if not prepare_only or not stop_before_execution:
        raise PreparationAuthorizationError(
            "both --prepare-only and --stop-before-execution are mandatory"
        )
    if not isinstance(resume_preparation, bool):
        raise PreparationAuthorizationError("resume-preparation flag is not boolean")


def _read_provider_registry(
    *, stage: Path, provider_root: Path, case_ids: Sequence[str],
) -> tuple[dict[tuple[str, str], ProviderRegistryRow], dict[str, Any]]:
    """Trust the sealed aggregate registry, without re-running effect validation."""

    ready_root = stage / "06_PROVIDER_READY"
    gate_path = ready_root / "PROVIDER_GATE.json"
    ready_path = ready_root / "CANONICAL541_PROVIDER_READY_MANIFEST.csv"
    effect_path = ready_root / "CANONICAL541_EFFECT_VALIDATION_RESULTS.csv"
    sha_path = ready_root / "PROVIDER_SHA256_MANIFEST.csv"
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    ready = read_csv(ready_path); effect = read_csv(effect_path); sha_rows = read_csv(sha_path)
    expected_ids = list(case_ids)
    if (
        gate.get("passed") is not True
        or gate.get("provider_generation") != 541
        or gate.get("effect_validation") != 541
        or gate.get("provider_ready") != 541
        or gate.get("provider_sha_rows") != 541 * 8
        or gate.get("provider_sha_closure") is not True
        or gate.get("raw_mutation") != 0
        or gate.get("trace_open_count") != 0
        or len(ready) != 541
        or len(effect) != 541
        or len(sha_rows) != 541 * 8
        or [row.get("case_id") for row in ready] != expected_ids
        or [row.get("case_id") for row in effect] != expected_ids
        or any(str(row.get("provider_ready", "")).lower() != "true" for row in ready)
        or any(str(row.get("passed", "")).lower() != "true" for row in effect)
        or gate.get("ready_manifest_sha256") != sha256_file(ready_path)
        or gate.get("effect_result_sha256") != sha256_file(effect_path)
    ):
        raise PreparationError("sealed provider/effect-validation aggregate gate failed")
    finalized = (provider_root / "FINALIZED").resolve(strict=True)
    output: dict[tuple[str, str], ProviderRegistryRow] = {}
    for raw in sha_rows:
        case_id = str(raw.get("case_id", "")); source = str(raw.get("source", ""))
        if case_id not in expected_ids or source not in (*SOURCE_NAMES, "combined_gnss"):
            raise PreparationError("provider SHA registry contains unknown case/source")
        path = Path(str(raw.get("resolved_path", ""))).resolve(strict=True)
        key = (case_id, source)
        if key in output:
            raise PreparationError(f"duplicate provider SHA row: {case_id}/{source}")
        output[key] = ProviderRegistryRow(
            case_id=case_id,
            source=source,
            byte_sha256=str(raw["sha256"]),
            size_bytes=int(raw["size_bytes"]),
            semantic_sha256=str(raw["semantic_sha256"]),
            storage_mode=str(raw["storage_mode"]),
            resolved_path=path,
        )
        if path.stat().st_size != int(raw["size_bytes"]):
            raise PreparationError(f"provider registered size drift: {case_id}/{source}")
    expected_keys = {(case_id, source) for case_id in expected_ids for source in (*SOURCE_NAMES, "combined_gnss")}
    if set(output) != expected_keys:
        raise PreparationError("provider SHA registry key closure failed")
    gate_summary = {
        "provider_generation": 541,
        "effect_validation": 541,
        "provider_ready": 541,
        "provider_sha_rows": len(output),
        "provider_gate_sha256": sha256_file(gate_path),
        "ready_manifest_sha256": sha256_file(ready_path),
        "effect_manifest_sha256": sha256_file(effect_path),
        "provider_sha_manifest_sha256": sha256_file(sha_path),
        "finalized_provider_root": str(finalized),
        "provider_or_effect_regeneration_count": 0,
        "raw_mutation": 0,
        "trace_reads": 0,
        "passed": True,
    }
    return output, gate_summary


def _case_semantic_hashes(
    registry: Mapping[tuple[str, str], ProviderRegistryRow], case_id: str,
) -> dict[str, str]:
    return {source: registry[(case_id, source)].semantic_sha256 for source in SOURCE_NAMES}


def _bound_source_hashes(
    *, case_hashes: Mapping[str, str], base_hashes: Mapping[str, str], profile: MethodProfile,
) -> dict[str, str]:
    consumed = {
        "gnss_position": True,
        "receiver_velocity": profile.flags["receiver_velocity"],
        "dual_yaw": profile.flags["dual_yaw"],
        "raw_doppler": profile.flags["raw_doppler"],
        "go2_rp": profile.flags["go2_rp"],
        "go2_hv": profile.flags["go2_hv"],
        # 当前 C++ 没有 source-quality-metadata loader；SA 不是多状态 QM。
        "source_quality_metadata": False,
    }
    return {
        source: str(case_hashes[source] if consumed[source] else base_hashes[source])
        for source in SOURCE_NAMES
    }


def _expected_binding_tasks(prepared_root: Path, cases: Sequence[Mapping[str, Any]]) -> list[ExpectedBinding]:
    tasks: list[ExpectedBinding] = []
    ordinal = 0
    for case in cases:
        case_id = str(case["case_id"])
        for profile in _profile_representatives():
            tasks.append(ExpectedBinding(
                ordinal=ordinal,
                case_id=case_id,
                profile=profile,
                destination=prepared_root / "METHOD_BOUND" / case_id / profile.effective_profile,
            ))
            ordinal += 1
    if len(tasks) != METHOD_BOUND_TOTAL:
        raise PreparationError("expected method-bound task count is not 5951")
    return tasks


def _expected_actual_inputs(
    *, case_id: str, profile: MethodProfile,
    registry: Mapping[tuple[str, str], ProviderRegistryRow],
    base: ProviderBundle, shared_gnss_root: Path,
    recorded_actual_hashes: Mapping[str, str] | None = None,
) -> dict[str, tuple[Path | None, str | None]]:
    base_semantic = _case_semantic_hashes(registry, "C00_clean_normal")
    case_semantic = _case_semantic_hashes(registry, case_id)
    bound = _bound_source_hashes(case_hashes=case_semantic, base_hashes=base_semantic, profile=profile)
    expected: dict[str, tuple[Path | None, str | None]] = {
        "imu": (base.imu_path.resolve(strict=True), base.base_provider_hashes["imu"]),
    }
    if all(bound[source] == base_semantic[source] for source in GNSS_SOURCE_NAMES):
        expected["gnss"] = (
            Path(base.original_provider_paths["combined_gnss"]).resolve(strict=True),
            base.base_provider_hashes["gnss"],
        )
    else:
        recorded = None if recorded_actual_hashes is None else str(recorded_actual_hashes.get("gnss", ""))
        expected["gnss"] = (
            shared_gnss_root / f"{recorded}.gnss" if recorded else None,
            recorded or None,
        )
    for source, flag, base_key in (
        ("raw_doppler", "raw_doppler", "raw_doppler"),
        ("go2_rp", "go2_rp", "go2_rp"),
        ("go2_hv", "go2_hv", "go2_hv"),
    ):
        if not profile.flags[flag]:
            continue
        if case_semantic[source] == base_semantic[source]:
            expected[source] = (
                Path(base.original_provider_paths[source]).resolve(strict=True),
                base.base_provider_hashes[base_key],
            )
        else:
            row = registry[(case_id, source)]
            expected[source] = (row.resolved_path, row.byte_sha256)
    return expected


def _validate_method_manifest(
    *, path: Path, task: ExpectedBinding,
    registry: Mapping[tuple[str, str], ProviderRegistryRow],
    base: ProviderBundle, shared_gnss_root: Path,
    hash_cache: UniqueFileHashCache,
    binding_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = hash_cache.read_json(path)
    if not isinstance(payload, dict):
        raise PreparationError("method-bound manifest is not an object")
    profile = task.profile
    case_hashes = _case_semantic_hashes(registry, task.case_id)
    base_hashes = _case_semantic_hashes(registry, "C00_clean_normal")
    expected_bound = _bound_source_hashes(
        case_hashes=case_hashes, base_hashes=base_hashes, profile=profile,
    )
    if (
        path.parent.resolve(strict=True) != task.destination.resolve(strict=True)
        or path.name != "METHOD_BOUND_INPUT_MANIFEST.json"
        or payload.get("method_id") != profile.method_id
        or payload.get("method_name") != profile.name
        or payload.get("effective_profile") != profile.effective_profile
        or payload.get("effective_flags") != dict(profile.flags)
        or payload.get("full_case_bundle_hashes") != case_hashes
        or payload.get("method_bound_source_hashes") != expected_bound
        or payload.get("source_quality_metadata_active_loader") is not False
        or ("case_id" in payload and payload.get("case_id") != task.case_id)
    ):
        raise PreparationError("method-bound manifest case/method/provider identity drift")
    if binding_contract is not None and any(payload.get(key) != value for key, value in binding_contract.items()):
        raise PreparationError("method-bound repaired freeze/attempt contract drift")
    expected_scientific_hash = scientific_method_runtime_hash(
        profile, task.case_id, str(payload.get("tracked_method_contract_sha256", "")),
    )
    if payload.get("scientific_runtime_contract_sha256") != expected_scientific_hash:
        raise PreparationError("method-bound scientific runtime contract hash drift")
    actual = payload.get("actual_solver_inputs")
    recorded_hashes = payload.get("actual_solver_input_hashes")
    if not isinstance(actual, dict) or not isinstance(recorded_hashes, dict) or set(actual) != set(recorded_hashes):
        raise PreparationError("method-bound actual input/hash keys are incomplete")
    expected_actual = _expected_actual_inputs(
        case_id=task.case_id, profile=profile, registry=registry, base=base,
        shared_gnss_root=shared_gnss_root, recorded_actual_hashes=recorded_hashes,
    )
    if set(actual) != set(expected_actual):
        raise PreparationError("method-bound actual input roles differ from effective profile")
    for role, (expected_path, expected_hash) in expected_actual.items():
        resolved = Path(str(actual[role])).resolve(strict=True)
        if expected_path is None or resolved != expected_path.resolve(strict=True):
            raise PreparationError(f"method-bound actual input path drift: {role}")
        digest = hash_cache.sha256(resolved)
        if digest != expected_hash or recorded_hashes.get(role) != digest:
            raise PreparationError(f"method-bound actual input hash drift: {role}")
        if role == "gnss" and resolved.parent == shared_gnss_root:
            match = SHARED_GNSS_RE.fullmatch(resolved.name)
            if match is None or match.group("sha") != digest:
                raise PreparationError("shared GNSS filename/content hash contract failed")
    bundle_hash = hashlib.sha256(
        json.dumps(recorded_hashes, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    if payload.get("method_bound_bundle_sha256") != bundle_hash:
        raise PreparationError("method-bound bundle hash drift")
    return payload


def _validate_shared_gnss_store(root: Path, cache: UniqueFileHashCache) -> int:
    root.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(root.iterdir()):
        if not path.is_file():
            raise PreparationError(f"unexpected non-file in shared GNSS store: {path.name}")
        match = SHARED_GNSS_RE.fullmatch(path.name)
        if match is None or cache.sha256(path) != match.group("sha"):
            raise PreparationError(f"shared GNSS content hash mismatch: {path.name}")
        count += 1
    return count


def _tail_recovery_allowed(
    *, invalid_ordinals: Sequence[int], artifact_ordinals: Sequence[int],
) -> int | None:
    if not invalid_ordinals:
        return None
    unique = sorted(set(int(value) for value in invalid_ordinals))
    if len(unique) != 1 or not artifact_ordinals or unique[0] != max(artifact_ordinals):
        raise PreparationError("only the last interrupted/invalid method-bound artifact may be rebuilt")
    return unique[0]


def _compose_method_bound_manifest(
    *, task: ExpectedBinding,
    registry: Mapping[tuple[str, str], ProviderRegistryRow],
    base: ProviderBundle, shared_gnss_root: Path,
    hash_cache: UniqueFileHashCache, table_cache: ProviderTableCache,
    binding_contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Create one exact method binding without cloning unused large providers."""

    profile = task.profile; case_id = task.case_id
    case_hashes = _case_semantic_hashes(registry, case_id)
    base_hashes = _case_semantic_hashes(registry, "C00_clean_normal")
    bound_hashes = _bound_source_hashes(
        case_hashes=case_hashes, base_hashes=base_hashes, profile=profile,
    )
    gnss_is_clean = all(bound_hashes[source] == base_hashes[source] for source in GNSS_SOURCE_NAMES)
    if gnss_is_clean:
        gnss_path = Path(base.original_provider_paths["combined_gnss"]).resolve(strict=True)
        gnss_hash = hash_cache.sha256(gnss_path)
        if gnss_hash != base.base_provider_hashes["gnss"]:
            raise PreparationError("clean method-bound GNSS differs from frozen fresh provider")
    else:
        tables: dict[str, ProviderTable] = {}
        for source in GNSS_SOURCE_NAMES:
            source_case = case_id if bound_hashes[source] == case_hashes[source] else "C00_clean_normal"
            row = registry[(source_case, source)]
            tables[source] = table_cache.get(
                row.resolved_path, expected_semantic_sha256=bound_hashes[source],
            )
        # compose_solver_gnss18 only consumes these three entries.  Avoid cloning
        # Raw Doppler/Go2 tables for every method binding.
        lean = ProviderBundle(
            imu_path=base.imu_path,
            tables=tables,
            raw_input_hashes={},
            base_provider_hashes={},
            dual_yaw_audit_rows=[],
            original_provider_paths={},
        )
        gnss_bytes = "".join(
            " ".join(row) + "\n" for row in compose_solver_gnss18(lean)
        ).encode("utf-8")
        gnss_hash = hashlib.sha256(gnss_bytes).hexdigest()
        gnss_path = shared_gnss_root / f"{gnss_hash}.gnss"
        if gnss_path.exists():
            if hash_cache.sha256(gnss_path) != gnss_hash:
                raise PreparationError("shared method-bound GNSS hash collision")
        else:
            # 中文说明：共享 GNSS 采用 content-addressed + atomic replace；
            # 中断只会留下命名临时文件，不会暴露半写入正式文件。
            temporary = shared_gnss_root / f".{gnss_hash}.gnss.tmp_{os.getpid()}"
            with temporary.open("xb") as handle:
                handle.write(gnss_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            if sha256_file(temporary) != gnss_hash:
                raise PreparationError("new shared GNSS bytes failed self-hash")
            if gnss_path.exists():
                temporary.unlink()
            else:
                os.replace(temporary, gnss_path)
                shared_fd = os.open(shared_gnss_root, os.O_RDONLY)
                try:
                    os.fsync(shared_fd)
                finally:
                    os.close(shared_fd)
            if hash_cache.sha256(gnss_path) != gnss_hash:
                raise PreparationError("promoted shared GNSS hash mismatch")
    actual_paths: dict[str, Path] = {
        "imu": base.imu_path.resolve(strict=True),
        "gnss": gnss_path.resolve(strict=True),
    }
    for source, flag, base_key in (
        ("raw_doppler", "raw_doppler", "raw_doppler"),
        ("go2_rp", "go2_rp", "go2_rp"),
        ("go2_hv", "go2_hv", "go2_hv"),
    ):
        if not profile.flags[flag]:
            continue
        if case_hashes[source] == base_hashes[source]:
            path = Path(base.original_provider_paths[source]).resolve(strict=True)
            if hash_cache.sha256(path) != base.base_provider_hashes[base_key]:
                raise PreparationError(f"clean auxiliary byte hash drift: {source}")
        else:
            row = registry[(case_id, source)]
            path = row.resolved_path
            if hash_cache.sha256(path) != row.byte_sha256:
                raise PreparationError(f"case auxiliary byte hash drift: {case_id}/{source}")
        actual_paths[source] = path
    actual_hashes = {role: hash_cache.sha256(path) for role, path in actual_paths.items()}
    payload = {
        **dict(binding_contract),
        "case_id": case_id,
        "method_id": profile.method_id,
        "method_name": profile.name,
        "effective_profile": profile.effective_profile,
        "effective_flags": dict(profile.flags),
        "actual_solver_inputs": {role: str(path) for role, path in actual_paths.items()},
        "actual_solver_input_hashes": actual_hashes,
        "full_case_bundle_hashes": case_hashes,
        "method_bound_source_hashes": bound_hashes,
        "source_quality_metadata_active_loader": False,
        "scientific_runtime_contract_sha256": scientific_method_runtime_hash(
            profile, case_id, str(binding_contract["tracked_method_contract_sha256"]),
        ),
        "shared_gnss_content_sha256": actual_hashes["gnss"],
        "trace_used_online": False,
        "old_runtime_input_count": 0,
        "legacy_provider_input_count": 0,
        "method_bound_bundle_sha256": hashlib.sha256(
            json.dumps(actual_hashes, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        ).hexdigest(),
    }
    return payload


def _write_method_bound_atomic(destination: Path, payload: Mapping[str, Any]) -> Path:
    if destination.exists():
        raise PreparationError(f"method-bound destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.tmp_{os.getpid()}")
    if temporary.exists():
        raise PreparationError(f"preparation-owned temporary already exists: {temporary}")
    temporary.mkdir(parents=False, exist_ok=False)
    manifest = temporary / "METHOD_BOUND_INPUT_MANIFEST.json"
    with manifest.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(payload), indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    temporary_fd = os.open(temporary, os.O_RDONLY)
    try:
        os.fsync(temporary_fd)
    finally:
        os.close(temporary_fd)
    os.replace(temporary, destination)
    parent_fd = os.open(destination.parent, os.O_RDONLY)
    try:
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
    return destination / "METHOD_BOUND_INPUT_MANIFEST.json"


def _quarantine_tail_artifact(
    *, task: ExpectedBinding, reason: str, prepared_root: Path,
    source_path: Path | None = None,
) -> Path:
    source = task.destination if source_path is None else source_path
    if not source.exists():
        raise PreparationError("tail recovery source disappeared")
    recovery = prepared_root / "PREPARATION_RECOVERY_QUARANTINE" / (
        f"{task.ordinal:04d}_{task.case_id}_{task.profile.effective_profile}_{os.getpid()}"
    )
    recovery.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, recovery)
    _atomic_json(recovery.parent / f"{recovery.name}_RECOVERY_REASON.json", {
        "ordinal": task.ordinal,
        "case_id": task.case_id,
        "effective_profile": task.profile.effective_profile,
        "reason": reason,
        "preserved": True,
        "rebuild_authorized": True,
        "timestamp_utc": _utc_now(),
    })
    return recovery


def _resume_method_bindings(
    *, tasks: Sequence[ExpectedBinding], registry: Mapping[tuple[str, str], ProviderRegistryRow],
    base: ProviderBundle, prepared_root: Path, hash_cache: UniqueFileHashCache,
    table_cache: ProviderTableCache, status: PreparationStatusWriter,
    binding_contract: Mapping[str, Any],
) -> tuple[dict[tuple[str, tuple[bool, ...]], tuple[Path, dict[str, Any]]], dict[str, Any]]:
    shared_gnss = prepared_root / "SHARED_GNSS_BY_HASH"
    shared_gnss.mkdir(parents=True, exist_ok=True)
    shared_before = _validate_shared_gnss_store(shared_gnss, hash_cache)
    by_key: dict[tuple[str, tuple[bool, ...]], tuple[Path, dict[str, Any]]] = {}
    invalid: list[tuple[ExpectedBinding, str, Path]] = []
    artifact_ordinals: list[int] = []
    valid_by_case: dict[str, int] = {}
    existing_artifact_count = 0
    existing_manifest_count = 0
    valid_existing_count = 0
    task_by_identity = {(task.case_id, task.profile.effective_profile): task for task in tasks}
    method_root = prepared_root / "METHOD_BOUND"
    if method_root.is_dir():
        for temporary in sorted(method_root.rglob(".*.tmp_*")):
            match = re.fullmatch(r"\.(?P<profile>.+)\.tmp_[0-9]+", temporary.name)
            task = task_by_identity.get((temporary.parent.name, match.group("profile") if match else ""))
            if task is None:
                raise PreparationError(f"unrecognized method-bound temporary: {temporary}")
            artifact_ordinals.append(task.ordinal)
            existing_artifact_count += 1
            invalid.append((task, "interrupted preparation temporary", temporary))
    for task in tasks:
        manifest = task.destination / "METHOD_BOUND_INPUT_MANIFEST.json"
        if task.destination.exists():
            artifact_ordinals.append(task.ordinal)
            existing_artifact_count += 1
            if not manifest.is_file():
                invalid.append((task, "method-bound directory lacks terminal manifest", task.destination))
                continue
            existing_manifest_count += 1
            try:
                payload = _validate_method_manifest(
                path=manifest, task=task, registry=registry, base=base,
                shared_gnss_root=shared_gnss, hash_cache=hash_cache,
                binding_contract=binding_contract,
                )
            except Exception as error:  # validation reason is preserved for the one authorized tail recovery
                invalid.append((task, f"{type(error).__name__}: {error}", task.destination))
                continue
            by_key[(task.case_id, task.profile.signature)] = (manifest, payload)
            valid_existing_count += 1
            valid_by_case[task.case_id] = valid_by_case.get(task.case_id, 0) + 1
            status.write(
                phase="VALIDATING_EXISTING_METHOD_BINDINGS",
                method_bound_completed=len(by_key),
                cases_completed=sum(value == 11 for value in valid_by_case.values()),
            )
    invalid_ordinal = _tail_recovery_allowed(
        invalid_ordinals=[task.ordinal for task, _, _ in invalid],
        artifact_ordinals=artifact_ordinals,
    )
    recovered = 0
    if invalid_ordinal is not None:
        matching_invalid = [item for item in invalid if item[0].ordinal == invalid_ordinal]
        if len(matching_invalid) != 1:
            raise PreparationError("tail ordinal contains multiple invalid artifacts")
        task, reason, source_path = matching_invalid[0]
        _quarantine_tail_artifact(
            task=task, reason=reason, prepared_root=prepared_root,
            source_path=source_path,
        )
        recovered = 1
    # Missing tasks are generated case-by-case.  Each physical provider table is
    # parsed once through table_cache, independent of logical-row multiplicity.
    generated_count = 0
    for task in tasks:
        key = (task.case_id, task.profile.signature)
        if key in by_key:
            continue
        payload = _compose_method_bound_manifest(
            task=task, registry=registry, base=base, shared_gnss_root=shared_gnss,
            hash_cache=hash_cache, table_cache=table_cache,
            binding_contract=binding_contract,
        )
        manifest = _write_method_bound_atomic(task.destination, payload)
        checked = _validate_method_manifest(
            path=manifest, task=task, registry=registry, base=base,
            shared_gnss_root=shared_gnss, hash_cache=hash_cache,
        )
        by_key[key] = (manifest, checked)
        generated_count += 1
        valid_by_case[task.case_id] = valid_by_case.get(task.case_id, 0) + 1
        status.write(
            phase="MATERIALIZING_MISSING_METHOD_BINDINGS",
            method_bound_completed=len(by_key),
            cases_completed=sum(value == 11 for value in valid_by_case.values()),
        )
    if len(by_key) != METHOD_BOUND_TOTAL or any(value != 11 for value in valid_by_case.values()) or len(valid_by_case) != 541:
        raise PreparationError("method-bound preparation did not close at 5951/5951")
    shared_after = _validate_shared_gnss_store(shared_gnss, hash_cache)
    return by_key, {
        "existing_artifact_count": existing_artifact_count,
        "existing_manifest_count": existing_manifest_count,
        "existing_valid_skipped": valid_existing_count,
        "tail_artifacts_recovered": recovered,
        "new_method_bound_manifests": generated_count,
        "method_bound_completed": len(by_key),
        "shared_gnss_files_before": shared_before,
        "shared_gnss_files_after": shared_after,
        "unique_file_hash_reads": hash_cache.physical_reads,
        "unique_provider_table_parses": table_cache.physical_parses,
    }


def _atomic_config(path: Path, text: str) -> Path:
    if path.is_file():
        if path.read_text(encoding="utf-8") != text:
            raise PreparationError(f"prepared runtime config changed across resume: {path.name}")
        return path
    if path.exists():
        raise PreparationError(f"runtime config destination is not a regular file: {path.name}")
    return _atomic_text(path, text)


def _build_plan_registries(
    *, repo: Path, stage: Path, executable: Path,
    scientific_code_freeze_commit: str, preparation_code_commit: str,
    cases: Sequence[Mapping[str, Any]],
    bindings: Mapping[tuple[str, tuple[bool, ...]], tuple[Path, Mapping[str, Any]]],
    base_provider_root: Path, hash_cache: UniqueFileHashCache,
    authorization: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    full_rows, ablation_rows = build_logical_queues(cases)
    logical_source = [*full_rows, *ablation_rows]
    for row in logical_source:
        row["provider_ready"] = True
    clean_manifest, auxiliary_manifest, provider_protocol = _provider_protocol_paths(
        repo, base_provider_root,
    )
    method_bound_hashes: dict[tuple[str, str], str] = {}
    runtime_hashes: dict[tuple[str, str], str] = {}
    for case in cases:
        case_id = str(case["case_id"])
        for candidate in (*FULL_METHODS, *ABLATION_METHODS):
            _, payload = bindings[(case_id, candidate.signature)]
            pair = (candidate.method_id, case_id)
            method_bound_hashes[pair] = str(payload["method_bound_bundle_sha256"])
            # 中文说明：data_mode 在 scientific config hash 中，C00 与 degraded
            # 不能共用一个预先假设的 hash。逐 case 从缓存 manifest 构造，完全
            # 避免把“看似 case-invariant”当作未经验证的前提。
            template = build_runtime_config(
                profile=candidate,
                clean_input_manifest=clean_manifest,
                auxiliary_manifest=auxiliary_manifest,
                provider_protocol=provider_protocol,
                method_bound_manifest=payload,
                output_dir=stage / "PLAN_PLACEHOLDER",
                case_id=case_id,
                run_id="PLAN_PLACEHOLDER",
            )
            runtime_hashes[pair] = scientific_runtime_config_hash(template)
    executable_hash = sha256_file(executable)
    logical, unique = resolve_execution_aliases(
        logical_source,
        method_bound_provider_hashes=method_bound_hashes,
        runtime_config_hashes=runtime_hashes,
        executable_hash=executable_hash,
    )
    logical_by_id = {str(row["logical_id"]): row for row in logical}
    prepared_root = stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS"
    configs_root = prepared_root / "RUNTIME_CONFIGS"
    configs_root.mkdir(parents=True, exist_ok=True)
    for record in unique:
        source = logical_by_id[str(record["canonical_logical_id"])]
        profile = PROFILE_BY_METHOD[str(source["method_id"])]
        matrix = str(source["matrix"]); case_id = str(source["case_id"])
        manifest_path, manifest_payload = bindings[(case_id, profile.signature)]
        output_root = stage / (
            "08_FULL_ALGORITHM_RUNS" if matrix == "full_algorithm" else "10_INTERNAL_ABLATION_RUNS"
        ) / str(record["run_id"])
        config_text = build_runtime_config(
            profile=profile,
            clean_input_manifest=clean_manifest,
            auxiliary_manifest=auxiliary_manifest,
            provider_protocol=provider_protocol,
            method_bound_manifest=manifest_payload,
            output_dir=output_root,
            case_id=case_id,
            run_id=str(record["run_id"]),
        )
        if scientific_runtime_config_hash(config_text) != record["runtime_config_hash"]:
            raise PreparationError("prepared runtime scientific config hash drift")
        rendered_hash = actual_rendered_runtime_config_sha256(config_text)
        _finalize_method_manifest_rendered_hash(
            path=manifest_path, payload=manifest_payload,
            rendered_hash=rendered_hash, hash_cache=hash_cache,
        )
        config_path = _atomic_config(configs_root / f"{record['run_id']}.yaml", config_text)
        record.update({
            "matrix": matrix,
            "effective_profile": profile.effective_profile,
            "case_family": source.get("case_family", ""),
            "degradation_type_id": source.get("degradation_type_id", ""),
            "seed_index": source.get("seed_index", ""),
            "output_root": str(output_root),
            "repo_root": str(repo),
            "runtime_config_template_path": str(config_path.resolve(strict=True)),
            "runtime_config_template_hash": sha256_file(config_path),
            "actual_rendered_runtime_config_sha256": rendered_hash,
            "runtime_config_file_hash": "",
            "runtime_config_path": "",
            "method_bound_manifest_path": str(manifest_path.resolve(strict=True)),
            "method_bound_manifest_hash": sha256_file(manifest_path),
            "scientific_code_freeze_commit": scientific_code_freeze_commit,
            "preparation_code_commit": preparation_code_commit,
            "terminal_status": "PREPARED_AUTHORIZED_NOT_STARTED",
            **{field: profile.flags[field] for field in FEATURE_FIELDS},
        })
    unique_by_run = {str(row["run_id"]): row for row in unique}
    for row in logical:
        owner = unique_by_run[str(row["run_id"])]
        row.update(
            provider_ready=True,
            output_root=owner["output_root"],
            method_bound_manifest_hash=owner["method_bound_manifest_hash"],
            terminal_status="PREPARED_AUTHORIZED_NOT_STARTED",
        )
    full_resolved = [row for row in logical if row["matrix"] == "full_algorithm"]
    ablation_resolved = [row for row in logical if row["matrix"] == "internal_ablation"]
    full_path = write_csv_atomic(
        stage / "07_FULL_ALGORITHM_REGISTRY/FULL_ALGORITHM_QUEUE.csv", full_resolved,
    )
    ablation_path = write_csv_atomic(
        stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv", ablation_resolved,
    )
    unique_path = write_csv_atomic(
        stage / "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_UNIQUE_RUN_REGISTRY.csv", unique,
    )
    plan = {
        "schema_version": "paper_rebuild.canonical541_execution_plan.v3_repaired",
        "stage_id": STAGE_ID,
        "scope": "REPAIRED_CANONICAL541_AUTOMATIC_COMPLETION",
        "scientific_code_freeze_commit": scientific_code_freeze_commit,
        "preparation_code_commit": preparation_code_commit,
        "executable_path": str(executable),
        "executable_sha256": executable_hash,
        "method_bound_count": METHOD_BOUND_TOTAL,
        "logical_row_count": len(logical),
        "full_logical_row_count": len(full_resolved),
        "ablation_logical_row_count": len(ablation_resolved),
        "unique_run_count": len(unique),
        "effective_profile_count": 11,
        "required_full_ablation_alias_rows": 541 * 2,
        "unique_registry_sha256": sha256_file(unique_path),
        "full_queue_sha256": sha256_file(full_path),
        "ablation_queue_sha256": sha256_file(ablation_path),
        "execution_authorized": authorization["execution_authorized"],
        "solver_allowed_after_readiness_freeze": authorization["solver_allowed_after_readiness_freeze"],
        "evaluator_allowed_after_output_seal": authorization["evaluator_allowed_after_output_seal"],
        "trace_allowed_online": authorization["trace_allowed_online"],
        "full_algorithm_execution_allowed": authorization["full_algorithm_execution_allowed"],
        "internal_ablation_execution_allowed": authorization["internal_ablation_execution_allowed"],
        "human_approval_required": authorization["human_approval_required"],
        "formal_execution_started": False,
        "solver_runs": 0,
        "evaluator_runs": 0,
        "trace_reads": 0,
        "metric_driven_rerun": False,
        "passed": True,
    }
    if (
        len(full_resolved) != FULL_QUEUE_TOTAL
        or len(ablation_resolved) != ABLATION_QUEUE_TOTAL
        or len(logical) != ALL_LOGICAL_TOTAL
        or len(unique) != METHOD_BOUND_TOTAL
        or len({str(row["case_id"]) for row in unique}) != 541
        or any(
            sum(str(row["case_id"]) == case_id for row in unique) != 11
            for case_id in {str(row["case_id"]) for row in logical}
        )
        or sum(bool(row["execution_alias"]) for row in logical if row["method_id"] in {"A01", "A02"}) != 1082
        or sum(bool(row["execution_alias"]) for row in logical) != 1082
    ):
        raise PreparationError("canonical queue/required-alias count closure failed")
    return plan, unique, full_resolved, ablation_resolved


def _finalize_method_manifest_rendered_hash(
    *, path: Path, payload: dict[str, Any], rendered_hash: str,
    hash_cache: UniqueFileHashCache,
) -> None:
    """Perform the sole authorized in-place semantic finalization atomically."""

    # Verify the attempt-owned manifest has not changed since resume parsing.
    hash_cache.sha256(path)
    prior = payload.get("actual_rendered_runtime_config_sha256")
    if prior not in (None, rendered_hash):
        raise PreparationError("method-bound actual rendered runtime config hash drift")
    if prior is None:
        finalized = dict(payload)
        finalized["actual_rendered_runtime_config_sha256"] = rendered_hash
        _atomic_json(path, finalized)
        payload["actual_rendered_runtime_config_sha256"] = rendered_hash


def _write_hash_registry(
    *, stage: Path, cases: Sequence[Mapping[str, Any]],
    bindings: Mapping[tuple[str, tuple[bool, ...]], tuple[Path, Mapping[str, Any]]],
    executable_sha256: str, logical_rows: Sequence[Mapping[str, Any]],
    hash_cache: UniqueFileHashCache,
) -> Path:
    logical_by_case_signature: dict[tuple[str, tuple[bool, ...]], Mapping[str, Any]] = {}
    for row in logical_rows:
        signature = tuple(bool(row[field]) for field in FEATURE_FIELDS)
        logical_by_case_signature.setdefault((str(row["case_id"]), signature), row)
    rows: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["case_id"])
        for profile in _profile_representatives():
            manifest, payload = bindings[(case_id, profile.signature)]
            candidate = next(
                row for row in (*FULL_METHODS, *ABLATION_METHODS)
                if row.signature == profile.signature
            )
            # Runtime config hashes are profile-scientific hashes; the logical
            # registry binds them to executable and method-bound provider hash.
            matching = logical_by_case_signature[(case_id, profile.signature)]
            rows.append({
                "case_id": case_id,
                "representative_method_id": candidate.method_id,
                "effective_profile": profile.effective_profile,
                "method_bound_manifest_path": str(manifest.resolve(strict=True)),
                "method_bound_manifest_sha256": hash_cache.sha256(manifest),
                "full_case_bundle_hashes_json": json.dumps(payload["full_case_bundle_hashes"], sort_keys=True, separators=(",", ":")),
                "method_bound_provider_hash": payload["method_bound_bundle_sha256"],
                "actual_solver_input_hashes_json": json.dumps(payload["actual_solver_input_hashes"], sort_keys=True, separators=(",", ":")),
                "runtime_config_hash": matching["runtime_config_hash"],
                "executable_sha256": executable_sha256,
                "execution_key": matching["execution_key"],
                "run_id": matching["run_id"],
            })
    if len(rows) != METHOD_BOUND_TOTAL:
        raise PreparationError("provider/config/executable hash registry count failed")
    return write_csv_atomic(
        stage / "07_FULL_ALGORITHM_REGISTRY/PROVIDER_CONFIG_EXECUTABLE_HASH_REGISTRY.csv", rows,
    )


def _affected_runtime_sources(case: Mapping[str, Any]) -> set[str]:
    raw = str(case.get("affected_sources", ""))
    tokens = {token.strip() for token in raw.split(";") if token.strip()}
    output: set[str] = set()
    for token in tokens:
        if token.startswith("gnss_position") or token.startswith("gnss_status"):
            output.add("gnss_position")
        elif token.startswith("receiver_velocity"):
            output.add("receiver_velocity")
        elif token.startswith("dual_yaw"):
            output.add("dual_yaw")
        elif token.startswith("raw_doppler"):
            output.add("raw_doppler")
        elif token.startswith("go2_roll_pitch"):
            output.add("go2_rp")
        elif token.startswith("go2_horizontal_velocity"):
            output.add("go2_hv")
        elif token.startswith("go2_source_metadata") or token.startswith("go2_contact") or token.startswith("go2_foot"):
            output.add("source_quality_metadata")
    return output


def _write_source_isolation_matrix(stage: Path, cases: Sequence[Mapping[str, Any]]) -> Path:
    representative_cases: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for case in cases:
        type_id = str(case["degradation_type_id"])
        if type_id not in seen:
            seen.add(type_id); representative_cases.append(case)
    if len(representative_cases) != 61:
        raise PreparationError("source-isolation matrix requires CLEAN plus 60 types")
    rows: list[dict[str, Any]] = []
    for case in representative_cases:
        affected = _affected_runtime_sources(case)
        for profile in _profile_representatives():
            consumed = {"gnss_position"}
            for source, flag in (
                ("receiver_velocity", "receiver_velocity"),
                ("dual_yaw", "dual_yaw"),
                ("raw_doppler", "raw_doppler"),
                ("go2_rp", "go2_rp"),
                ("go2_hv", "go2_hv"),
            ):
                if profile.flags[flag]:
                    consumed.add(source)
            active = sorted(affected & consumed)
            rows.append({
                "degradation_type_id": case["degradation_type_id"],
                "case_family": case["case_family"],
                "representative_case_id": case["case_id"],
                "effective_profile": profile.effective_profile,
                "affected_runtime_sources": ";".join(sorted(affected)),
                "consumed_runtime_sources": ";".join(sorted(consumed)),
                "active_affected_sources": ";".join(active),
                "expected_output_invariant": not bool(active),
                "source_quality_metadata_active_loader": False,
                "frozen_before_execution": True,
            })
    if len(rows) != 61 * 11:
        raise PreparationError("source-isolation expected matrix count failed")
    return write_csv_atomic(
        stage / "04_EFFECT_RULES/CANONICAL541_EXPECTED_SOURCE_ISOLATION_MATRIX.csv", rows,
    )


def _count_named_files(root: Path, names: set[str]) -> int:
    if not root.is_dir():
        return 0
    return sum(path.is_file() and path.name in names for path in root.rglob("*"))


def _resource_estimate(stage: Path, unique_run_count: int) -> dict[str, Any]:
    source_path = stage / "16_AUDITS/CANONICAL541_STORAGE_AND_PARALLELISM_PROJECTION.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if source.get("passed") is not True:
        raise PreparationError("frozen storage/parallelism projection did not pass")
    meminfo: dict[str, int] = {}
    for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
        key, value = line.split(":", 1)
        meminfo[key] = int(value.strip().split()[0]) * 1024
    disk = shutil.disk_usage(stage)
    contract = source.get("parallelism_contract", {})
    report = {
        "schema_version": "paper_rebuild.canonical541_preparation_resource_estimate.v1",
        "scope": "AUTHORIZED_PREPARATION_RESOURCE_CHECK",
        "source_projection_path": str(source_path),
        "source_projection_sha256": sha256_file(source_path),
        "unique_runs_planned": unique_run_count,
        "current_memory_total_bytes": meminfo.get("MemTotal", 0),
        "current_memory_available_bytes": meminfo.get("MemAvailable", 0),
        "current_swap_free_bytes": meminfo.get("SwapFree", 0),
        "current_stage_filesystem_free_bytes": disk.free,
        "projected_runtime_plus_evaluation_bytes": source.get("conservative_projection", {}).get("runtime_plus_evaluation_bytes"),
        "solver_initial_jobs": int(contract.get("solver_initial_jobs", 12)),
        "jobs_12_requires_future_measured_gate": True,
        "jobs_16_requires_future_measured_gate": True,
        "blas_threads_required": 1,
        "solver_launch_count": 0,
        "evaluator_launch_count": 0,
        "passed": True,
    }
    _atomic_json(stage / "16_AUDITS/CANONICAL541_PREPARATION_RESOURCE_ESTIMATE.json", report)
    return report


def _raw_post_provider_gate(stage: Path) -> dict[str, Any]:
    path = stage / "16_AUDITS/CANONICAL541_RAW_22_POST_PROVIDER.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        payload.get("passed") is not True
        or payload.get("verified") != 22
        or payload.get("expected") != 22
        or payload.get("missing") != 0
        or payload.get("mismatch") != 0
        or payload.get("raw_mutation") != 0
        or payload.get("old_provider_solver_input") is not False
        or payload.get("trace_open_count_online") != 0
    ):
        raise PreparationError("POST_PROVIDER raw 22/22 gate failed")
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "verified": 22,
        "raw_mutation": 0,
        "old_provider_solver_input": False,
        "trace_reads": 0,
        "passed": True,
    }


def _preparation_completeness_audit(
    *, repo: Path, stage: Path, plan: Mapping[str, Any],
    provider_gate: Mapping[str, Any], resume: Mapping[str, Any],
    hash_registry_path: Path, source_matrix_path: Path,
    resource_estimate: Mapping[str, Any], authorization: Mapping[str, Any],
) -> dict[str, Any]:
    run_roots = (stage / "08_FULL_ALGORITHM_RUNS", stage / "10_INTERNAL_ABLATION_RUNS")
    solver_proofs = sum(
        _count_named_files(root, {"RUN_PROOF.json", "CANONICAL541_EXECUTION_PROOF.json"})
        for root in run_roots
    )
    solver_outputs = sum(
        _count_named_files(root, {"KF_GINS_Navresult.nav", "KF_GINS_STD.txt"})
        for root in run_roots
    )
    evaluator_outputs = _count_named_files(
        stage / "12_OFFLINE_EVALUATION",
        {"summary.json", "error_series.csv.gz", "evaluator_manifest.json"},
    )
    commit, dirty = git_code_state(repo)
    raw = _raw_post_provider_gate(stage)
    full_path = stage / "07_FULL_ALGORITHM_REGISTRY/FULL_ALGORITHM_QUEUE.csv"
    ablation_path = stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv"
    unique_path = stage / "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_UNIQUE_RUN_REGISTRY.csv"
    audit = {
        "schema_version": "paper_rebuild.canonical541_preparation_completeness.v1",
        "stage_id": STAGE_ID,
        "scope": "AUTHORIZED_METHOD_BOUND_PREPARATION",
        "case_manifest_rows": 541,
        "provider_ready": provider_gate["provider_ready"],
        "effect_validation": provider_gate["effect_validation"],
        "method_bound_completed": resume["method_bound_completed"],
        "method_bound_total": METHOD_BOUND_TOTAL,
        "full_queue_rows": len(read_csv(full_path)),
        "ablation_queue_rows": len(read_csv(ablation_path)),
        "unique_runs_planned": plan["unique_run_count"],
        "provider_config_executable_hash_rows": len(read_csv(hash_registry_path)),
        "source_isolation_rows": len(read_csv(source_matrix_path)),
        "full_queue_sha256": sha256_file(full_path),
        "ablation_queue_sha256": sha256_file(ablation_path),
        "unique_registry_sha256": sha256_file(unique_path),
        "hash_registry_sha256": sha256_file(hash_registry_path),
        "source_isolation_sha256": sha256_file(source_matrix_path),
        "raw_post_provider": raw,
        "storage_and_parallelism_estimate": dict(resource_estimate),
        "solver_runs": solver_proofs,
        "solver_output_files": solver_outputs,
        "evaluator_runs": evaluator_outputs,
        "run_proof_count": solver_proofs,
        "trace_reads": 0,
        "execution_authorized": authorization["execution_authorized"],
        "solver_allowed_after_readiness_freeze": authorization["solver_allowed_after_readiness_freeze"],
        "evaluator_allowed_after_output_seal": authorization["evaluator_allowed_after_output_seal"],
        "human_approval_required": authorization["human_approval_required"],
        "formal_execution_started": False,
        "preparation_code_commit": commit,
        "worktree_clean": not dirty,
    }
    audit["passed"] = (
        audit["case_manifest_rows"] == 541
        and audit["provider_ready"] == 541
        and audit["effect_validation"] == 541
        and audit["method_bound_completed"] == METHOD_BOUND_TOTAL
        and audit["full_queue_rows"] == FULL_QUEUE_TOTAL
        and audit["ablation_queue_rows"] == ABLATION_QUEUE_TOTAL
        and audit["unique_runs_planned"] == METHOD_BOUND_TOTAL
        and audit["provider_config_executable_hash_rows"] == METHOD_BOUND_TOTAL
        and audit["source_isolation_rows"] == 61 * 11
        and solver_proofs == solver_outputs == evaluator_outputs == 0
        and audit["worktree_clean"] is True
    )
    _atomic_json(stage / "16_AUDITS/CANONICAL541_EXECUTION_INPUT_COMPLETENESS_AUDIT.json", audit)
    return audit


def _write_preparation_report(
    *, stage: Path, plan: Mapping[str, Any], provider_gate: Mapping[str, Any],
    resume: Mapping[str, Any], audit: Mapping[str, Any], authorization: Mapping[str, Any],
) -> tuple[Path, Path]:
    passed = bool(audit.get("passed"))
    terminal = (
        "PASS_CANONICAL541_AUTHORIZED_PREPARATION_READY_FOR_AUTOMATIC_EXECUTION"
        if passed else "BLOCKED_CANONICAL541_EXECUTION_PREPARATION_INCOMPLETE"
    )
    payload = {
        "schema_version": "paper_rebuild.canonical541_preparation_report.v1",
        "stage_id": STAGE_ID,
        "terminal_status": terminal,
        "provider_gate": dict(provider_gate),
        "resume": dict(resume),
        "execution_plan": dict(plan),
        "completeness_audit": dict(audit),
        "authorization": dict(authorization),
        "solver_runs": 0,
        "evaluator_runs": 0,
        "trace_reads": 0,
        "performance_metrics_generated": False,
        "figures_generated": False,
        "passed": passed,
    }
    json_path = stage / "16_AUDITS/CANONICAL541_PREPARATION_REPORT.json"
    md_path = stage / "16_AUDITS/CANONICAL541_PREPARATION_REPORT.md"
    _atomic_json(json_path, payload)
    markdown = f"""# Canonical541 authorized preparation report

Terminal status: `{terminal}`

- Canonical cases: 541
- Provider-ready/effect-validated: {provider_gate['provider_ready']}/{provider_gate['effect_validation']}
- Method-bound inputs: {resume['method_bound_completed']}/{METHOD_BOUND_TOTAL}
- Full-method logical queue: {plan['full_logical_row_count']}
- Internal-ablation logical queue: {plan['ablation_logical_row_count']}
- Planned unique executions: {plan['unique_run_count']}
- Solver runs: 0
- Evaluator runs: 0
- Trace reads: 0
- Execution authorized: {str(authorization['execution_authorized']).lower()}
- Human approval required: {str(authorization['human_approval_required']).lower()}

This package contains no performance results. The tracked authorization permits
automatic solver execution after the compact readiness/freeze gates and permits
the exact evaluator only after terminal outputs are sealed.
"""
    _atomic_text(md_path, markdown)
    packet_path = stage / "16_AUDITS/CANONICAL541_PREPARATION_REVIEW_PACKET.json"
    review_inputs = {
        "execution_plan": stage / "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json",
        "preparation_status": stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_STATUS.json",
        "full_queue": stage / "07_FULL_ALGORITHM_REGISTRY/FULL_ALGORITHM_QUEUE.csv",
        "ablation_queue": stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv",
        "unique_registry": stage / "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_UNIQUE_RUN_REGISTRY.csv",
        "input_completeness_audit": stage / "16_AUDITS/CANONICAL541_EXECUTION_INPUT_COMPLETENESS_AUDIT.json",
        "preparation_report_json": json_path,
        "preparation_report_md": md_path,
    }
    _atomic_json(packet_path, {
        "schema_version": "paper_rebuild.canonical541_preparation_review_packet.v1",
        "stage_id": STAGE_ID,
        "scope": "READ_ONLY_REVIEW_OF_AUTHORIZED_PREPARATION_ARTIFACTS",
        "review_inputs": {
            role: {"path": str(path), "sha256": sha256_file(path)}
            for role, path in review_inputs.items()
        },
        "solver_runs": 0,
        "evaluator_runs": 0,
        "trace_reads": 0,
        "performance_review_requested": False,
        "execution_authorized": authorization["execution_authorized"],
        "human_approval_required": authorization["human_approval_required"],
    })
    return md_path, json_path


def recover_known_3981_preparation(
    stage_root: str | Path, *, explicitly_authorized: bool = False,
) -> dict[str, Any] | None:
    """Recover only the known case-deduplicated, zero-execution attempt shape.

    Every superseded byte is preserved before the sole semantic reset: removal
    of the derived rendered-runtime hash from each attempt-owned method manifest.
    """

    if not explicitly_authorized:
        raise PreparationError("known-3981 recovery requires explicit invocation authorization")
    stage = validate_attempt_root(stage_root)
    registry = stage / "07_FULL_ALGORITHM_REGISTRY"
    recovery_root = registry / "PREPARATION_RECOVERY_KNOWN_3981"
    complete_path = recovery_root / "RECOVERY_COMPLETE.json"
    if complete_path.is_file():
        for artifact_name in ("RECOVERY_BOOTSTRAP.json", "PREINVENTORY.json", "RECOVERY_COMPLETE.json"):
            artifact = recovery_root / artifact_name
            sidecar = recovery_root / f"{artifact_name}.sha256"
            if not sidecar.is_file():
                raise PreparationError("completed known-3981 recovery sidecar is missing")
            _write_or_validate_recovery_sidecar(artifact, sidecar)
        payload = json.loads(complete_path.read_text(encoding="utf-8"))
        preinventory = json.loads((recovery_root / "PREINVENTORY.json").read_text(encoding="utf-8"))
        reset = json.loads((recovery_root / "RESET_LEDGER.json").read_text(encoding="utf-8"))
        post = json.loads((recovery_root / "POSTINVENTORY.json").read_text(encoding="utf-8"))
        phases = json.loads((recovery_root / "RECOVERY_PHASES.json").read_text(encoding="utf-8"))
        bootstrap_path = recovery_root / "RECOVERY_BOOTSTRAP.json"
        bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
        if (
            payload.get("passed") is not True
            or payload.get("reset_manifest_count") != KNOWN_RECOVERY_ANNOTATED_COUNT
            or payload.get("untouched_manifest_count") != KNOWN_RECOVERY_UNTOUCHED_COUNT
            or reset.get("reset_manifest_count") != KNOWN_RECOVERY_ANNOTATED_COUNT
            or post.get("passed") is not True
            or phases.get("phases", [])[-1:] != ["RECOVERY_COMPLETE"]
            or sha256_file(recovery_root / "RESET_LEDGER.json") != payload.get("reset_ledger_sha256")
            or sha256_file(recovery_root / "POSTINVENTORY.json") != payload.get("postinventory_sha256")
            or sha256_file(recovery_root / "RECOVERY_PHASES.json") != payload.get("phase_ledger_sha256")
            or sha256_file(bootstrap_path) != payload.get("bootstrap_sha256")
            or sha256_file(recovery_root / "PREINVENTORY.json") != payload.get("preinventory_sha256")
        ):
            raise PreparationError("known-3981 recovery completion ledger is invalid")
        method_root = registry / "PREPARED_EXECUTION_INPUTS/METHOD_BOUND"
        protected_complete = scan_protected_live_set(stage)
        recorded_post_scan = post.get("protected_live_post")
        if isinstance(recorded_post_scan, dict):
            _validate_protected_scan_record(recorded_post_scan)
        if (
            not isinstance(recorded_post_scan, dict)
            or protected_complete != recorded_post_scan
            or protected_complete != preinventory.get("protected_live_pre")
            or protected_complete.get("set_sha256") != recorded_post_scan.get("set_sha256")
        ):
            raise PreparationError("completed known-3981 protected COMPLETE rescan differs from POST")
        live_methods = _regular_file_inventory(method_root)
        manifest_rows = list(preinventory.get("manifest_rows", []))
        normalized_manifest_paths = [
            str(Path(row["path"]).resolve(strict=True)) for row in manifest_rows
        ]
        independent_manifest_paths = {
            str((method_root / relative).resolve(strict=True)) for relative in live_methods
        }
        case_profiles = {tuple(Path(relative).parts[:2]) for relative in live_methods}
        cases = {case for case, _ in case_profiles}
        if (
            len(manifest_rows) != METHOD_BOUND_TOTAL
            or len(set(normalized_manifest_paths)) != METHOD_BOUND_TOTAL
            or set(normalized_manifest_paths) != independent_manifest_paths
            or len(cases) != KNOWN_RECOVERY_CASE_COUNT
            or any(sum(case_id == case for case_id, _ in case_profiles) != KNOWN_RECOVERY_PROFILES_PER_CASE for case in cases)
            or set(live_methods) != set(preinventory["protected_method_inventory"])
            or len(live_methods) != METHOD_BOUND_TOTAL
        ):
            raise PreparationError("completed known-3981 live method set drift")
        annotated_rows = [row for row in preinventory["manifest_rows"] if row["annotated"]]
        untouched_rows = [row for row in preinventory["manifest_rows"] if not row["annotated"]]
        originals_root = recovery_root / "ORIGINAL_METHOD_MANIFESTS"
        originals_inventory = _regular_file_inventory(originals_root)
        expected_originals = {
            Path(row["path"]).relative_to(method_root).as_posix(): row["original_sha256"]
            for row in annotated_rows
        }
        if originals_inventory != expected_originals or len(annotated_rows) != KNOWN_RECOVERY_ANNOTATED_COUNT or len(untouched_rows) != KNOWN_RECOVERY_UNTOUCHED_COUNT:
            raise PreparationError("completed known-3981 original/untouched set closure failed")
        reset_by_path = {str(row["path"]): row for row in reset["reset_rows"]}
        if set(reset_by_path) != {str(row["path"]) for row in annotated_rows}:
            raise PreparationError("completed known-3981 reset ledger set differs from annotated manifests")
        for row in preinventory["manifest_rows"]:
            preserved = Path(row["preserved_path"]); current = Path(row["path"])
            if row["annotated"]:
                if not preserved.is_file() or preserved.is_symlink() or sha256_file(preserved) != row["original_sha256"]:
                    raise PreparationError("completed known-3981 preserved original no longer validates")
                expected = json.loads(preserved.read_text(encoding="utf-8"))
                expected.pop("actual_rendered_runtime_config_sha256")
            else:
                expected = json.loads(current.read_text(encoding="utf-8"))
                if preserved.exists() or sha256_file(current) != row["original_sha256"]:
                    raise PreparationError("completed known-3981 untouched manifest no longer validates")
            if current.is_symlink() or json.loads(current.read_text(encoding="utf-8")) != expected:
                raise PreparationError("completed known-3981 recovery no longer validates")
            if row["annotated"] and (
                reset_by_path[str(current)]["original_sha256"] != row["original_sha256"]
                or reset_by_path[str(current)]["reset_sha256"] != sha256_file(current)
            ):
                raise PreparationError("completed known-3981 reset ledger hash differs from disk")
        quarantine = recovery_root / "SUPERSEDED_PREPARATION_ARTIFACTS"
        for row in preinventory["superseded_rows"]:
            destination = quarantine / Path(row["path"]).relative_to(stage)
            if Path(row["path"]).exists() or not destination.is_file() or sha256_file(destination) != row["sha256"]:
                raise PreparationError("completed known-3981 quarantine no longer validates")
        config_root = registry / "PREPARED_EXECUTION_INPUTS/RUNTIME_CONFIGS"
        if _regular_file_inventory(config_root):
            raise PreparationError("completed known-3981 live stale runtime configs remain")
        config_destination = quarantine / config_root.relative_to(stage)
        for row in preinventory["runtime_config_rows"]:
            destination = config_destination / Path(row["path"]).relative_to(config_root)
            if not destination.is_file() or sha256_file(destination) != row["sha256"]:
                raise PreparationError("completed known-3981 config quarantine no longer validates")
        expected_quarantine = {
            Path(row["path"]).relative_to(stage).as_posix(): row["sha256"]
            for row in preinventory["superseded_rows"]
        }
        expected_quarantine.update({
            (config_root.relative_to(stage) / Path(row["path"]).relative_to(config_root)).as_posix(): row["sha256"]
            for row in preinventory["runtime_config_rows"]
        })
        if _regular_file_inventory(quarantine) != expected_quarantine or len(preinventory["runtime_config_rows"]) != KNOWN_RECOVERY_CONFIG_COUNT:
            raise PreparationError("completed known-3981 quarantine union contains missing/extra bytes")
        if (
            {str(row["path"]): str(row["sha256"]) for row in post["protected_manifest_rows"]}
            != {str(method_root / relative): digest for relative, digest in live_methods.items()}
            or {str(row["preserved_path"]): str(row["sha256"]) for row in post["protected_quarantine_rows"]}
            != {str(quarantine / Path(row["path"]).relative_to(stage)): str(row["sha256"]) for row in preinventory["superseded_rows"]}
            or {str(row["path"]): str(row["sha256"]) for row in post["protected_runtime_config_rows"]}
            != {str(config_destination / Path(row["path"]).relative_to(config_root)): str(row["sha256"]) for row in preinventory["runtime_config_rows"]}
        ):
            raise PreparationError("completed known-3981 postinventory differs from independent disk rescan")
        for row in bootstrap["session_evidence"]:
            if sha256_file(Path(row["path"])) != row["sha256"]:
                raise PreparationError("completed known-3981 session evidence mutated")
        for row in bootstrap["pid_dead_proof"]:
            try:
                os.kill(int(row["pid"]), 0); alive = True
            except (ProcessLookupError, ValueError):
                alive = False
            except PermissionError:
                alive = True
            if alive:
                raise PreparationError("completed known-3981 PID is unexpectedly live")
        if (
            len(bootstrap["session_evidence"]) != 4 or len(bootstrap["pid_dead_proof"]) != 2
            or frozenset(row.get("pid") for row in bootstrap["pid_dead_proof"]) != KNOWN_RECOVERY_PIDS
            or any(type(row.get("pid")) is not int for row in bootstrap["pid_dead_proof"])
            or {Path(row["path"]).name: row["sha256"] for row in bootstrap["session_evidence"]}
               != KNOWN_RECOVERY_SESSION_HASHES
        ):
            raise PreparationError("completed known-3981 session/PID set count drift")
        metadata_names = {
            "RECOVERY_BOOTSTRAP.json", "RECOVERY_BOOTSTRAP.json.sha256",
            "PREINVENTORY.json", "PREINVENTORY.json.sha256", "RECOVERY_PHASES.json",
            "RESET_LEDGER.json", "POSTINVENTORY.json", "RECOVERY_COMPLETE.json",
            "RECOVERY_COMPLETE.json.sha256",
        }
        expected_recovery_inventory = {
            name: sha256_file(recovery_root / name) for name in metadata_names
        }
        expected_recovery_inventory.update({
            f"ORIGINAL_METHOD_MANIFESTS/{relative}": digest
            for relative, digest in originals_inventory.items()
        })
        expected_recovery_inventory.update({
            f"SUPERSEDED_PREPARATION_ARTIFACTS/{relative}": digest
            for relative, digest in expected_quarantine.items()
        })
        if _regular_file_inventory(recovery_root) != expected_recovery_inventory:
            raise PreparationError("completed known-3981 recovery tree contains unknown/missing/tmp bytes")
        activity_roots = (stage / "08_FULL_ALGORITHM_RUNS", stage / "10_INTERNAL_ABLATION_RUNS",
                          stage / "11_OUTPUT_SEAL", stage / "12_OFFLINE_EVALUATION")
        if any(_regular_file_inventory(root) for root in activity_roots):
            raise PreparationError("completed known-3981 output/evaluator set is nonzero")
        trace_names = {"TRACE_ACCESS_LEDGER.json", "REFERENCE_TRACE_READ_LEDGER.json"}
        if any(path.is_file() and path.name in trace_names for path in stage.rglob("*") if recovery_root not in path.parents):
            raise PreparationError("completed known-3981 trace ledger is nonzero")
        return payload
    preinventory_path = recovery_root / "PREINVENTORY.json"
    unique_path = registry / "CANONICAL541_UNIQUE_RUN_REGISTRY.csv"
    plan_path = registry / "EXECUTION_PLAN.json"
    full_path = registry / "FULL_ALGORITHM_QUEUE.csv"
    ablation_path = stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv"
    quarantine = recovery_root / "SUPERSEDED_PREPARATION_ARTIFACTS"
    if not preinventory_path.is_file():
        if not plan_path.is_file() or not unique_path.is_file():
            return None
        unique = read_csv(unique_path); full = read_csv(full_path); ablation = read_csv(ablation_path)
        aliases = sum(str(row.get("execution_alias", "")).lower() == "true" for row in (*full, *ablation))
        if (len(unique) != KNOWN_RECOVERY_UNIQUE_COUNT or len(full) != FULL_QUEUE_TOTAL
                or len(ablation) != ABLATION_QUEUE_TOTAL or aliases != KNOWN_RECOVERY_ALIAS_COUNT):
            return None
        plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
        fixed_paths = (plan_path, unique_path, full_path, ablation_path, registry / "PREPARATION_STATUS.json")
        if (
            plan_payload.get("schema_version") != "paper_rebuild.canonical541_execution_plan.v3_repaired"
            or plan_payload.get("scientific_code_freeze_commit") != KNOWN_RECOVERY_COMMIT
            or plan_payload.get("preparation_code_commit") != KNOWN_RECOVERY_COMMIT
            or any(KNOWN_RECOVERY_HASHES.get(path.name) != sha256_file(path) for path in fixed_paths)
            or (registry / "PROVIDER_CONFIG_EXECUTABLE_HASH_REGISTRY.csv").exists()
        ):
            raise PreparationError("known-3981 fixed attempt signature/hash mismatch")
        session_paths = (
            stage / "RUN_SESSION.json", stage / "CANONICAL541_STATUS.json",
            stage / "00_PIPELINE_LOGS/pipeline.stdout.log",
            stage / "00_PIPELINE_LOGS/pipeline.stderr.log",
        )
        if any(not path.is_file() or path.is_symlink() or KNOWN_RECOVERY_SESSION_HASHES.get(path.name) != sha256_file(path) for path in session_paths):
            raise PreparationError("known-3981 session/status/log hash signature mismatch")
        session = json.loads(session_paths[0].read_text(encoding="utf-8"))
        pipeline_status = json.loads(session_paths[1].read_text(encoding="utf-8"))
        raw_pids = (session.get("pid"), pipeline_status.get("process_pid"))
        if any(type(pid) is not int for pid in raw_pids) or frozenset(raw_pids) != KNOWN_RECOVERY_PIDS:
            raise PreparationError("known-3981 session PID identity/type mismatch")
        pids = tuple(raw_pids)
        pid_proof: list[dict[str, Any]] = []
        for pid in pids:
            try:
                os.kill(pid, 0); alive = True
            except (ProcessLookupError, ValueError):
                alive = False
            except PermissionError:
                alive = True
            pid_proof.append({"pid": pid, "alive": alive})
        if (
            session.get("attempt_root") != str(stage)
            or session.get("code_freeze_commit") != KNOWN_RECOVERY_COMMIT
            or pipeline_status.get("phase") != "PIPELINE_STEP_2_OF_6"
            or pipeline_status.get("trace_reads_before_seal") != 0
            or any(row["alive"] for row in pid_proof)
            or "prepared input mutated during hash cache lifetime" not in session_paths[3].read_text(encoding="utf-8")
        ):
            raise PreparationError("known-3981 session/PID/failure evidence mismatch")
        lock = stage / "runner.lock"
        if lock.exists():
            lock_payload = json.loads(lock.read_text(encoding="utf-8"))
            pid = int(lock_payload.get("pid", -1))
            try:
                os.kill(pid, 0); alive = True
            except (ProcessLookupError, ValueError):
                alive = False
            except PermissionError:
                alive = True
            if (
                alive
                or str(lock_payload.get("stage_root", "")) != str(stage)
                or lock_payload.get("code_freeze_commit") != KNOWN_RECOVERY_COMMIT
            ):
                raise PreparationError("known-3981 recovery rejects live or foreign runner lock")
        activity_roots = (stage / "08_FULL_ALGORITHM_RUNS", stage / "10_INTERNAL_ABLATION_RUNS",
                          stage / "11_OUTPUT_SEAL", stage / "12_OFFLINE_EVALUATION")
        trace_names = {"TRACE_ACCESS_LEDGER.json", "REFERENCE_TRACE_READ_LEDGER.json"}
        if (
            any(path.is_file() for root in activity_roots if root.exists() for path in root.rglob("*"))
            or any(path.is_file() and path.name in trace_names for path in stage.rglob("*"))
        ):
            raise PreparationError("known-3981 recovery requires zero formal/evaluator/trace activity")
        protected_pre = scan_protected_live_set(stage)
        _validate_protected_scan_record(protected_pre)
        method_root = registry / "PREPARED_EXECUTION_INPUTS/METHOD_BOUND"
        method_inventory = _regular_file_inventory(method_root)
        if len(method_inventory) != METHOD_BOUND_TOTAL or any(
            not relative.endswith("/METHOD_BOUND_INPUT_MANIFEST.json") for relative in method_inventory
        ):
            raise PreparationError("known-3981 recovery requires exactly 5951 method manifests")
        manifests = [method_root / relative for relative in sorted(method_inventory)]
        recovery_root.mkdir(parents=True, exist_ok=True)
        phase_path = recovery_root / "RECOVERY_PHASES.json"
        bootstrap = {
            "schema_version": "paper_rebuild.canonical541_recovery_bootstrap.v1",
            "explicitly_authorized": True, "attempt_root": str(stage),
            "fixed_artifact_hashes": dict(KNOWN_RECOVERY_HASHES),
            "session_evidence": [{"path": str(path), "sha256": sha256_file(path)} for path in session_paths],
            "pid_dead_proof": pid_proof, "scientific_code_freeze_commit": KNOWN_RECOVERY_COMMIT,
        }
        bootstrap_path = recovery_root / "RECOVERY_BOOTSTRAP.json"
        if bootstrap_path.exists():
            if json.loads(bootstrap_path.read_text(encoding="utf-8")) != bootstrap:
                raise PreparationError("known-3981 recovery bootstrap drift")
        else:
            _atomic_json(bootstrap_path, bootstrap)
        bootstrap_sidecar = recovery_root / "RECOVERY_BOOTSTRAP.json.sha256"
        _write_or_validate_recovery_sidecar(bootstrap_path, bootstrap_sidecar)
        _atomic_json(phase_path, {"schema_version": "paper_rebuild.canonical541_recovery_phases.v1",
                                  "phases": ["BOOTSTRAP_DURABLE"]})
        originals = recovery_root / "ORIGINAL_METHOD_MANIFESTS"
        manifest_rows: list[dict[str, str]] = []
        for manifest in manifests:
            relative = manifest.relative_to(registry / "PREPARED_EXECUTION_INPUTS/METHOD_BOUND")
            preserved = originals / relative
            digest = sha256_file(manifest)
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            rendered = payload.get("actual_rendered_runtime_config_sha256")
            if rendered is not None and (not isinstance(rendered, str) or len(rendered) != 64):
                raise PreparationError("known-3981 manifest rendered-hash field is malformed")
            manifest_rows.append({"path": str(manifest), "preserved_path": str(preserved),
                                  "original_sha256": digest, "removed_value": rendered,
                                  "annotated": rendered is not None})
        annotated = sum(bool(row["annotated"]) for row in manifest_rows)
        untouched = len(manifest_rows) - annotated
        scanned_manifest_paths = {
            str((method_root / relative).resolve(strict=True)) for relative in method_inventory
        }
        recorded_manifest_paths = {
            str(Path(row["path"]).resolve(strict=True)) for row in manifest_rows
        }
        case_profiles = {
            tuple(Path(relative).parts[:2]) for relative in method_inventory
        }
        cases = {case for case, _ in case_profiles}
        if (
            recorded_manifest_paths != scanned_manifest_paths
            or len(recorded_manifest_paths) != METHOD_BOUND_TOTAL
            or len(cases) != KNOWN_RECOVERY_CASE_COUNT
            or any(sum(case_id == case for case_id, _ in case_profiles) != KNOWN_RECOVERY_PROFILES_PER_CASE for case in cases)
        ):
            raise PreparationError("known-3981 manifest rows do not equal independent 541x11 live scan")
        configs = registry / "PREPARED_EXECUTION_INPUTS/RUNTIME_CONFIGS"
        config_inventory = _regular_file_inventory(configs)
        config_rows = [
            {"path": str(configs / relative), "sha256": digest}
            for relative, digest in sorted(config_inventory.items())
        ]
        if (annotated, untouched, len(config_rows)) != (
            KNOWN_RECOVERY_ANNOTATED_COUNT, KNOWN_RECOVERY_UNTOUCHED_COUNT, KNOWN_RECOVERY_CONFIG_COUNT,
        ):
            raise PreparationError("known-3981 annotated/untouched/config signature mismatch")
        superseded = tuple(path for path in (
            full_path, ablation_path, unique_path,
            registry / "PROVIDER_CONFIG_EXECUTABLE_HASH_REGISTRY.csv",
            stage / "16_AUDITS/CANONICAL541_EXECUTION_INPUT_COMPLETENESS_AUDIT.json",
            registry / "PREPARATION_STATUS.json", plan_path,
            stage / "16_AUDITS/CANONICAL541_PREPARATION_REPORT.json",
            stage / "16_AUDITS/CANONICAL541_PREPARATION_REPORT.md",
            stage / "16_AUDITS/CANONICAL541_PREPARATION_REVIEW_PACKET.json",
            stage / "runner.lock",
        ) if path.is_file())
        preinventory = {
            "schema_version": "paper_rebuild.canonical541_known_3981_preinventory.v1",
            "known_unique_count": KNOWN_RECOVERY_UNIQUE_COUNT,
            "known_alias_count": KNOWN_RECOVERY_ALIAS_COUNT,
            "formal_runs": 0, "evaluator_runs": 0, "trace_reads": 0,
            "manifest_rows": manifest_rows,
            "superseded_rows": [{"path": str(path), "sha256": sha256_file(path)} for path in superseded],
            "runtime_config_rows": config_rows,
            "protected_method_inventory": method_inventory,
            "protected_runtime_config_inventory": config_inventory,
            "annotated_manifest_count": annotated, "untouched_manifest_count": untouched,
            "protected_live_pre": protected_pre,
        }
        _atomic_json(preinventory_path, preinventory)
        _write_or_validate_recovery_sidecar(
            preinventory_path, recovery_root / "PREINVENTORY.json.sha256",
        )
        _atomic_json(phase_path, {"schema_version": "paper_rebuild.canonical541_recovery_phases.v1",
                                  "phases": ["BOOTSTRAP_DURABLE", "PREINVENTORY_DURABLE"]})
    else:
        preinventory = json.loads(preinventory_path.read_text(encoding="utf-8"))
        if (preinventory.get("known_unique_count"), preinventory.get("known_alias_count")) != (
            KNOWN_RECOVERY_UNIQUE_COUNT, KNOWN_RECOVERY_ALIAS_COUNT,
        ):
            raise PreparationError("known-3981 preinventory signature drift")
        preinventory_sidecar = recovery_root / "PREINVENTORY.json.sha256"
        _write_or_validate_recovery_sidecar(preinventory_path, preinventory_sidecar)
    manifest_rows = list(preinventory["manifest_rows"])
    _validate_protected_scan_record(preinventory.get("protected_live_pre", {}))
    current_method_inventory = _regular_file_inventory(
        registry / "PREPARED_EXECUTION_INPUTS/METHOD_BOUND",
    )
    current_manifest_paths = {
        str((registry / "PREPARED_EXECUTION_INPUTS/METHOD_BOUND" / relative).resolve(strict=True))
        for relative in current_method_inventory
    }
    normalized_recorded_paths = {
        str(Path(row["path"]).resolve(strict=True)) for row in manifest_rows
    }
    current_case_profiles = {
        tuple(Path(relative).parts[:2]) for relative in current_method_inventory
    }
    current_cases = {case for case, _ in current_case_profiles}
    if (
        normalized_recorded_paths != current_manifest_paths
        or len(normalized_recorded_paths) != METHOD_BOUND_TOTAL
        or len(current_cases) != KNOWN_RECOVERY_CASE_COUNT
        or any(sum(case_id == case for case_id, _ in current_case_profiles) != KNOWN_RECOVERY_PROFILES_PER_CASE for case in current_cases)
    ):
        raise PreparationError("known-3981 manifest rows differ from current independent live scan")
    for row in manifest_rows:
        if not row["annotated"]:
            continue
        source = Path(row["path"]); preserved = Path(row["preserved_path"])
        if preserved.exists():
            if sha256_file(preserved) != row["original_sha256"]:
                raise PreparationError("known-3981 preserved manifest mutated")
            continue
        if sha256_file(source) != row["original_sha256"]:
            raise PreparationError("known-3981 manifest mutated before preservation")
        preserved.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(source, preserved)
        if sha256_file(preserved) != row["original_sha256"]:
            raise PreparationError("known-3981 quarantine byte preservation failed")
    _atomic_json(recovery_root / "RECOVERY_PHASES.json", {
        "schema_version": "paper_rebuild.canonical541_recovery_phases.v1",
        "phases": ["BOOTSTRAP_DURABLE", "PREINVENTORY_DURABLE", "ORIGINALS_PRESERVED"],
    })
    reset_rows: list[dict[str, str]] = []
    for row in manifest_rows:
        manifest = Path(row["path"]); preserved = Path(row["preserved_path"])
        if row["annotated"]:
            if sha256_file(preserved) != row["original_sha256"]:
                raise PreparationError("known-3981 preserved manifest mutated")
            expected = json.loads(preserved.read_text(encoding="utf-8"))
            rendered = expected.pop("actual_rendered_runtime_config_sha256")
            if sha256_file(manifest) == row["original_sha256"]:
                _atomic_json(manifest, expected)
            elif json.loads(manifest.read_text(encoding="utf-8")) != expected:
                raise PreparationError("known-3981 reset manifest contains non-rendered-field mutation")
        else:
            if sha256_file(manifest) != row["original_sha256"]:
                raise PreparationError("known-3981 untouched manifest mutated")
            continue
        reset_rows.append({
            "path": str(manifest), "preserved_path": str(preserved),
            "original_sha256": row["original_sha256"], "reset_sha256": sha256_file(manifest),
            "removed_field": "actual_rendered_runtime_config_sha256",
            "removed_value": rendered,
        })
    _atomic_json(recovery_root / "RECOVERY_PHASES.json", {
        "schema_version": "paper_rebuild.canonical541_recovery_phases.v1",
        "phases": ["BOOTSTRAP_DURABLE", "PREINVENTORY_DURABLE", "ORIGINALS_PRESERVED",
                   "RENDERED_FIELDS_RESET"],
    })
    quarantined: list[dict[str, str]] = []
    for row in preinventory["superseded_rows"]:
        source = Path(row["path"])
        destination = quarantine / source.relative_to(stage)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            if sha256_file(source) != row["sha256"]:
                raise PreparationError("known-3981 source mutated after preinventory")
            os.replace(source, destination)
            _fsync_directory(source.parent); _fsync_directory(destination.parent)
        if not destination.is_file() or sha256_file(destination) != row["sha256"]:
            raise PreparationError("known-3981 superseded artifact preservation failed")
        quarantined.append({"path": str(source), "preserved_path": str(destination), "sha256": row["sha256"]})
    configs = registry / "PREPARED_EXECUTION_INPUTS/RUNTIME_CONFIGS"
    config_destination = quarantine / configs.relative_to(stage)
    if configs.exists():
        config_destination.parent.mkdir(parents=True, exist_ok=True); os.replace(configs, config_destination)
        _fsync_directory(configs.parent); _fsync_directory(config_destination.parent)
    for row in preinventory["runtime_config_rows"]:
        destination = config_destination / Path(row["path"]).relative_to(configs)
        if not destination.is_file() or sha256_file(destination) != row["sha256"]:
            raise PreparationError("known-3981 runtime config preservation failed")
    protected_post = scan_protected_live_set(stage)
    _validate_protected_scan_record(protected_post)
    if protected_post != preinventory["protected_live_pre"]:
        raise PreparationError("known-3981 protected immutable live set changed PRE to POST")
    _atomic_json(recovery_root / "RECOVERY_PHASES.json", {
        "schema_version": "paper_rebuild.canonical541_recovery_phases.v1",
        "phases": ["BOOTSTRAP_DURABLE", "PREINVENTORY_DURABLE", "ORIGINALS_PRESERVED",
                   "RENDERED_FIELDS_RESET", "PROTECTED_ARTIFACTS_QUARANTINED"],
    })
    post_manifest_rows = [
        {"path": row["path"], "sha256": sha256_file(Path(row["path"])),
         "annotated_before_recovery": row["annotated"]}
        for row in manifest_rows
    ]
    post_config_rows = [
        {"path": str(config_destination / Path(row["path"]).relative_to(configs)),
         "sha256": row["sha256"]}
        for row in preinventory["runtime_config_rows"]
    ]
    _atomic_json(recovery_root / "RESET_LEDGER.json", {
        "schema_version": "paper_rebuild.canonical541_known_3981_reset.v1",
        "known_unique_count": KNOWN_RECOVERY_UNIQUE_COUNT,
        "known_alias_count": KNOWN_RECOVERY_ALIAS_COUNT,
        "reset_manifest_count": len(reset_rows), "reset_rows": reset_rows,
        "untouched_manifest_count": preinventory["untouched_manifest_count"],
        "quarantined_artifacts": quarantined, "byte_preservation_required": True,
    })
    post = {
        "schema_version": "paper_rebuild.canonical541_known_3981_postinventory.v1",
        "reset_manifest_count": len(reset_rows),
        "untouched_manifest_count": preinventory["untouched_manifest_count"],
        "quarantined_artifact_count": len(quarantined),
        "quarantined_runtime_config_count": len(preinventory["runtime_config_rows"]),
        "authoritative_superseded_paths_absent": all(not Path(row["path"]).exists() for row in preinventory["superseded_rows"]),
        "protected_manifest_rows": post_manifest_rows,
        "protected_quarantine_rows": quarantined,
        "protected_runtime_config_rows": post_config_rows,
        "protected_live_post": protected_post,
        "passed": (
            len(reset_rows) == KNOWN_RECOVERY_ANNOTATED_COUNT
            and preinventory["untouched_manifest_count"] == KNOWN_RECOVERY_UNTOUCHED_COUNT
            and len(preinventory["runtime_config_rows"]) == KNOWN_RECOVERY_CONFIG_COUNT
            and all(not Path(row["path"]).exists() for row in preinventory["superseded_rows"])
        ),
    }
    _atomic_json(recovery_root / "POSTINVENTORY.json", post)
    phases = ["BOOTSTRAP_DURABLE", "PREINVENTORY_DURABLE", "ORIGINALS_PRESERVED",
              "RENDERED_FIELDS_RESET", "PROTECTED_ARTIFACTS_QUARANTINED",
              "POSTINVENTORY_VALIDATED"]
    _atomic_json(recovery_root / "RECOVERY_PHASES.json", {
        "schema_version": "paper_rebuild.canonical541_recovery_phases.v1", "phases": phases,
    })
    complete = {
        "schema_version": "paper_rebuild.canonical541_known_3981_recovery_complete.v1",
        "terminal_status": "RECOVERY_COMPLETE", "passed": True,
        "known_unique_count": KNOWN_RECOVERY_UNIQUE_COUNT,
        "known_alias_count": KNOWN_RECOVERY_ALIAS_COUNT,
        "reset_manifest_count": len(reset_rows), "formal_runs": 0,
        "untouched_manifest_count": preinventory["untouched_manifest_count"],
        "evaluator_runs": 0, "trace_reads": 0,
        "reset_ledger_sha256": sha256_file(recovery_root / "RESET_LEDGER.json"),
        "postinventory_sha256": sha256_file(recovery_root / "POSTINVENTORY.json"),
        "bootstrap_sha256": sha256_file(recovery_root / "RECOVERY_BOOTSTRAP.json"),
        "preinventory_sha256": sha256_file(recovery_root / "PREINVENTORY.json"),
    }
    _atomic_json(recovery_root / "RECOVERY_PHASES.json", {
        "schema_version": "paper_rebuild.canonical541_recovery_phases.v1",
        "phases": [*phases, "RECOVERY_COMPLETE"],
    })
    complete["phase_ledger_sha256"] = sha256_file(recovery_root / "RECOVERY_PHASES.json")
    _atomic_json(complete_path, complete)  # marker excludes its own hash; sidecar binds it
    _write_or_validate_recovery_sidecar(
        complete_path, recovery_root / "RECOVERY_COMPLETE.json.sha256",
    )
    return recover_known_3981_preparation(stage, explicitly_authorized=True)


def prepare_only_execution_plan(
    *, repo_root: str | Path, stage_root: str | Path, provider_root: str | Path,
    base_provider_root: str | Path, base: ProviderBundle, executable: str | Path,
    code_freeze_commit: str, resume_preparation: bool = True,
    status_interval_seconds: float = 60.0,
    local_config_sha256: str = "",
) -> dict[str, Any]:
    """Finish all preparation artifacts, then stop before formal execution."""

    repo = Path(repo_root).resolve(strict=True)
    stage = validate_attempt_root(stage_root)
    provider = Path(provider_root).resolve(strict=True)
    executable_path = Path(executable).resolve(strict=True)
    authorization = load_preparation_authorization(repo)
    preparation_code_commit, preparation_dirty = git_code_state(repo)
    # 双 freeze：057c... 继续冻结科学/solver/provider 语义；当前干净 HEAD
    # 只冻结 preparation implementation。必须在第一次 stage 写入前检查。
    if preparation_dirty:
        raise PreparationError("preparation requires a clean preparation-code commit before stage writes")
    validate_code_freeze_gate(
        stage_root=stage, executable=executable_path,
        code_freeze_commit=code_freeze_commit,
    )
    validate_tracked_method_contract(repo / "configs/paper_rebuild/methods.yaml")
    validate_tracked_ablation_contract(repo / "configs/paper_rebuild/clean2r2a_ablation_2pow4.yaml")
    validate_canonical_full_config(repo / "configs/paper_rebuild/canonical_by2_full_method_modes.yaml")
    validate_canonical_ablation_config(repo / "configs/paper_rebuild/canonical_by2_internal_ablation_modes.yaml")
    case_manifest_path = stage / "02_MATRIX_SPEC_LOCK/CANONICAL541_CASE_MANIFEST.csv"
    cases = [normalize_case_row(row) for row in read_csv(case_manifest_path)]
    if len(cases) != 541 or len({str(row["case_id"]) for row in cases}) != 541:
        raise PreparationError("canonical case manifest is not 541 unique rows")
    registry_root = stage / "07_FULL_ALGORITHM_REGISTRY"
    prepared_root = registry_root / "PREPARED_EXECUTION_INPUTS"
    prepared_root.mkdir(parents=True, exist_ok=True)
    status = PreparationStatusWriter(
        registry_root / "PREPARATION_STATUS.json",
        interval_seconds=status_interval_seconds,
        authorization=authorization,
    )
    status.write(phase="STARTING", method_bound_completed=0, cases_completed=0, force=True)
    provider_registry, provider_gate = _read_provider_registry(
        stage=stage, provider_root=provider,
        case_ids=[str(row["case_id"]) for row in cases],
    )
    tasks = _expected_binding_tasks(prepared_root, cases)
    existing_artifacts = sum(task.destination.exists() for task in tasks)
    if existing_artifacts and not resume_preparation:
        raise PreparationError("existing preparation requires --resume-preparation")
    hash_cache = UniqueFileHashCache(); table_cache = ProviderTableCache()
    runtime_contract_paths = (
        repo / "configs/paper_rebuild/methods.yaml",
        repo / "configs/paper_rebuild/clean2r2a_ablation_2pow4.yaml",
        repo / "configs/paper_rebuild/canonical_by2_full_method_modes.yaml",
        repo / "configs/paper_rebuild/canonical_by2_internal_ablation_modes.yaml",
    )
    runtime_contract_hash = hashlib.sha256(
        "".join(sha256_file(path) for path in runtime_contract_paths).encode("ascii")
    ).hexdigest()
    binding_contract = {
        "stage_id": STAGE_ID,
        "attempt_root": str(stage),
        "solver_code_freeze_commit": code_freeze_commit,
        "executable_sha256": sha256_file(executable_path),
        "tracked_method_contract_sha256": runtime_contract_hash,
        "local_path_config_sha256": local_config_sha256,
    }
    bindings, resume = _resume_method_bindings(
        tasks=tasks, registry=provider_registry, base=base,
        prepared_root=prepared_root, hash_cache=hash_cache,
        table_cache=table_cache, status=status,
        binding_contract=binding_contract,
    )
    status.write(
        phase="BUILDING_QUEUES_AND_DEDUP_REGISTRY",
        method_bound_completed=METHOD_BOUND_TOTAL, cases_completed=541, force=True,
    )
    plan, unique, full_rows, ablation_rows = _build_plan_registries(
        repo=repo, stage=stage, executable=executable_path,
        scientific_code_freeze_commit=code_freeze_commit,
        preparation_code_commit=preparation_code_commit,
        cases=cases,
        bindings=bindings, base_provider_root=Path(base_provider_root).resolve(strict=True),
        hash_cache=hash_cache, authorization=authorization,
    )
    logical_rows = [*full_rows, *ablation_rows]
    # _build_plan_registries may perform the narrowly authorized, atomic
    # attempt-owned manifest finalization above.  Start a fresh cache boundary
    # afterward so the final registry hashes the finalized bytes, while its
    # own stat-before/stat-after checks continue to reject external mutation.
    finalized_hash_cache = UniqueFileHashCache()
    hash_registry = _write_hash_registry(
        stage=stage, cases=cases, bindings=bindings,
        executable_sha256=plan["executable_sha256"], logical_rows=logical_rows,
        hash_cache=finalized_hash_cache,
    )
    source_matrix = _write_source_isolation_matrix(stage, cases)
    freeze_root = stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_REGISTRY_FREEZE"
    prepared_registry_sources = {
        "full_queue": stage / "07_FULL_ALGORITHM_REGISTRY/FULL_ALGORITHM_QUEUE.csv",
        "ablation_queue": stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv",
        "unique_registry": stage / "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_UNIQUE_RUN_REGISTRY.csv",
    }
    prepared_registry_freeze: dict[str, Path] = {}
    for role, source in prepared_registry_sources.items():
        destination = freeze_root / source.name
        _atomic_text(destination, source.read_text(encoding="utf-8"))
        if sha256_file(destination) != sha256_file(source):
            raise PreparationError("immutable prepared registry freeze hash mismatch")
        prepared_registry_freeze[role] = destination
    resources = _resource_estimate(stage, int(plan["unique_run_count"]))
    status.write(
        phase="AUDITING_PREPARATION",
        method_bound_completed=METHOD_BOUND_TOTAL,
        cases_completed=541,
        full_queue_rows=FULL_QUEUE_TOTAL,
        ablation_queue_rows=ABLATION_QUEUE_TOTAL,
        unique_runs_planned=int(plan["unique_run_count"]),
        force=True,
    )
    audit = _preparation_completeness_audit(
        repo=repo, stage=stage, plan=plan, provider_gate=provider_gate,
        resume=resume, hash_registry_path=hash_registry,
        source_matrix_path=source_matrix, resource_estimate=resources,
        authorization=authorization,
    )
    if not audit["passed"]:
        status.write(
            phase="BLOCKED", method_bound_completed=METHOD_BOUND_TOTAL,
            cases_completed=541, full_queue_rows=FULL_QUEUE_TOTAL,
            ablation_queue_rows=ABLATION_QUEUE_TOTAL,
            unique_runs_planned=int(plan["unique_run_count"]), force=True,
        )
        raise PreparationError("preparation completeness audit did not pass")
    status.write(
        phase="READY_FOR_AUTOMATIC_EXECUTION",
        method_bound_completed=METHOD_BOUND_TOTAL,
        cases_completed=541,
        full_queue_rows=FULL_QUEUE_TOTAL,
        ablation_queue_rows=ABLATION_QUEUE_TOTAL,
        unique_runs_planned=int(plan["unique_run_count"]),
        force=True,
    )
    prepared_artifacts = {
        **prepared_registry_freeze,
        "hash_registry": hash_registry,
        "source_isolation": source_matrix,
        "completeness_audit": stage / "16_AUDITS/CANONICAL541_EXECUTION_INPUT_COMPLETENESS_AUDIT.json",
        "preparation_status": stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_STATUS.json",
    }
    plan["prepared_artifact_sha256"] = {
        role: sha256_file(path) for role, path in prepared_artifacts.items()
    }
    plan["current_status_registry_sha256"] = {
        role: sha256_file(path) for role, path in prepared_registry_sources.items()
    }
    # The plan is the authoritative commit marker and is written last among
    # all execution-gating preparation artifacts.
    _atomic_json(stage / "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json", plan)
    report_md, report_json = _write_preparation_report(
        stage=stage, plan=plan, provider_gate=provider_gate,
        resume=resume, audit=audit, authorization=authorization,
    )
    return {
        "terminal_status": "PASS_CANONICAL541_AUTHORIZED_PREPARATION_READY_FOR_AUTOMATIC_EXECUTION",
        "plan": plan,
        "provider_gate": provider_gate,
        "resume": resume,
        "audit": audit,
        "report_md": str(report_md),
        "report_json": str(report_json),
        "solver_runs": 0,
        "evaluator_runs": 0,
        "trace_reads": 0,
    }


def verify_preparation_only(
    *, repo_root: str | Path, stage_root: str | Path,
) -> dict[str, Any]:
    """Read-only terminal verification; never opens providers, trace, or outputs."""

    repo = Path(repo_root).resolve(strict=True); stage = validate_attempt_root(stage_root)
    authorization = load_preparation_authorization(repo)
    plan_path = stage / "07_FULL_ALGORITHM_REGISTRY/EXECUTION_PLAN.json"
    status_path = stage / "07_FULL_ALGORITHM_REGISTRY/PREPARATION_STATUS.json"
    audit_path = stage / "16_AUDITS/CANONICAL541_EXECUTION_INPUT_COMPLETENESS_AUDIT.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    status = json.loads(status_path.read_text(encoding="utf-8"))
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    full_path = stage / "07_FULL_ALGORITHM_REGISTRY/FULL_ALGORITHM_QUEUE.csv"
    ablation_path = stage / "09_INTERNAL_ABLATION_REGISTRY/INTERNAL_ABLATION_QUEUE.csv"
    unique_path = stage / "07_FULL_ALGORITHM_REGISTRY/CANONICAL541_UNIQUE_RUN_REGISTRY.csv"
    hashes_path = stage / "07_FULL_ALGORITHM_REGISTRY/PROVIDER_CONFIG_EXECUTABLE_HASH_REGISTRY.csv"
    full = read_csv(full_path); ablation = read_csv(ablation_path); unique = read_csv(unique_path)
    hash_rows = read_csv(hashes_path)
    all_rows = [*full, *ablation]
    by_logical = {row["logical_id"]: row for row in all_rows}
    alias_ok = all(
        by_logical[f"ABLATION_{ablation_id}_{case_id}"]["run_id"]
        == by_logical[f"FULL_{full_id}_{case_id}"]["run_id"]
        and by_logical[f"ABLATION_{ablation_id}_{case_id}"]["execution_key"]
        == by_logical[f"FULL_{full_id}_{case_id}"]["execution_key"]
        for case_id in {row["case_id"] for row in full}
        for ablation_id, full_id in (("A01", "F04"), ("A02", "F03"))
    )
    method_bound_count = sum(
        1 for path in (stage / "07_FULL_ALGORITHM_REGISTRY/PREPARED_EXECUTION_INPUTS/METHOD_BOUND").rglob("METHOD_BOUND_INPUT_MANIFEST.json")
        if path.is_file()
    )
    run_proofs = sum(
        _count_named_files(root, {"RUN_PROOF.json", "CANONICAL541_EXECUTION_PROOF.json"})
        for root in (stage / "08_FULL_ALGORITHM_RUNS", stage / "10_INTERNAL_ABLATION_RUNS")
    )
    evaluator_runs = _count_named_files(
        stage / "12_OFFLINE_EVALUATION", {"summary.json", "evaluator_manifest.json"},
    )
    commit, dirty = git_code_state(repo)
    passed = (
        len(full) == FULL_QUEUE_TOTAL
        and len(ablation) == ABLATION_QUEUE_TOTAL
        and len(hash_rows) == METHOD_BOUND_TOTAL
        and method_bound_count == METHOD_BOUND_TOTAL
        and len(unique) == plan.get("unique_run_count") == METHOD_BOUND_TOTAL
        and len(by_logical) == ALL_LOGICAL_TOTAL
        and alias_ok
        and plan.get("scientific_code_freeze_commit") is not None
        and plan.get("preparation_code_commit") == commit
        and plan.get("execution_authorized") is True
        and plan.get("solver_allowed_after_readiness_freeze") is True
        and plan.get("evaluator_allowed_after_output_seal") is True
        and plan.get("trace_allowed_online") is False
        and plan.get("human_approval_required") is False
        and status.get("phase") == "READY_FOR_AUTOMATIC_EXECUTION"
        and status.get("solver_runs") == status.get("evaluator_runs") == status.get("trace_reads") == 0
        and audit.get("passed") is True
        and run_proofs == evaluator_runs == 0
        and dirty is False
    )
    return {
        "schema_version": "paper_rebuild.canonical541_preparation_verification.v1",
        "terminal_status": (
            "PASS_CANONICAL541_AUTHORIZED_PREPARATION_READY_FOR_AUTOMATIC_EXECUTION"
            if passed else "BLOCKED_CANONICAL541_EXECUTION_PREPARATION_INCOMPLETE"
        ),
        "case_manifest_rows": 541,
        "provider_ready": audit.get("provider_ready"),
        "effect_validation": audit.get("effect_validation"),
        "method_bound": method_bound_count,
        "full_queue_rows": len(full),
        "ablation_queue_rows": len(ablation),
        "unique_runs_planned": len(unique),
        "required_aliases_valid": alias_ok,
        "solver_runs": run_proofs,
        "evaluator_runs": evaluator_runs,
        "run_proof_count": run_proofs,
        "trace_reads": 0,
        "execution_authorized": True,
        "human_approval_required": authorization["human_approval_required"],
        "preparation_code_commit": commit,
        "worktree_clean": not dirty,
        "registry_hashes": {
            "execution_plan": sha256_file(plan_path),
            "full_queue": sha256_file(full_path),
            "ablation_queue": sha256_file(ablation_path),
            "unique_registry": sha256_file(unique_path),
            "provider_config_executable": sha256_file(hashes_path),
        },
        "passed": passed,
    }
