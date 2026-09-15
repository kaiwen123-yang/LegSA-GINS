"""Isolated Phase-2 EXT02/C00 execution, freeze, and diagnostic pipeline.

The native path is deliberately trace-closed.  It reconstructs RAWX/SFRBX
once, with NAV-HPPOSECEF semantic decoding disabled, and places paired epochs
in a fingerprinted NumPy memory-map cache.  Parallel workers consume only that
cache plus the explicit RTKLIB broadcast-state bridge.  Post-native proxy and
trace diagnostics are a separate lifecycle entered only after every native
hash in ``EXT02_C00_NATIVE_FREEZE.json`` has been revalidated.

This module has no dependency on either Phase-1 runner or EXT01 code.
"""

from __future__ import annotations

import csv
import ctypes
import base64
import bisect
import errno
import hashlib
import io
import json
import math
import os
import platform
import resource
import re
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
import yaml

from .shared_raw_backend import (
    DoubleDifferenceStageError,
    RawBackendError,
    RawxEpoch,
    RawxMeasurement,
    RtklibBroadcastProvider,
    SignalIdentity,
    TrackingContinuity,
    build_gps_l1_double_difference_model,
    dd_matrix_condition_diagnostics,
    ecef_to_geodetic,
    gps_l1_code_spp,
    identity_text,
    pair_epochs,
    reconstruct_ubx_stream,
    tracking_epoch_summary,
    wavelength_m,
)


for _thread_variable in (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_variable] = "1"


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = (
    REPOSITORY_ROOT / "configs/paper_rebuild/horizontal_literature/"
    "PHASE2_EXT02_CWLS_CONTRACT_V1.yaml"
)
HEADING_SCHEMA_PATH = (
    REPOSITORY_ROOT / "configs/paper_rebuild/horizontal_literature/"
    "STANDARD_HEADING_STREAM_SCHEMA_V1.yaml"
)
CLI_PATH = REPOSITORY_ROOT / "scripts/paper_rebuild/run_horizontal_literature_phase2.py"

METHOD_ID = "EXT02_CWLS"
CASE_ID = "C00"
DATA_MODE = "real_by2_raw"
DEFAULT_WORKERS = 16
MAX_WORKERS = 20
EXPECTED_PAIR_COUNT = 1509
BASELINE_LENGTH_M = 0.350
ELEVATION_MASK_RAD = math.radians(10.0)
COMMON_BACKBONE_YAW_STD_DEG = 1.5
RESOURCE_RSS_AVAILABLE_FRACTION_LIMIT = 0.70
RESOURCE_PROJECTED_BYTES_PER_EPOCH = 1024 * 1024
RESOURCE_PROJECTED_FIXED_BYTES = 64 * 1024 * 1024
RESOURCE_DISK_SAFETY_RESERVE_BYTES = 1024 * 1024 * 1024
MAX20_TEMPERATURE_STABILITY_C = 5.0
CSV_FIELD_SIZE_LIMIT = 8 * 1024 * 1024
GPS_EPOCH_UNIX_SECONDS = 315964800.0
EXPECTED_GPS_UTC_LEAP_SECONDS = 18
POST_RECOVERY_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
PROXY_ASSOCIATION_POLICY = (
    "UNIQUE_NEAREST_ON_SORTED_COMMON_HPPOSECEF_ITOW_GRID_STRICTLY_WITHIN_"
    "HALF_LOCAL_CADENCE_MONOTONIC_ONE_TO_ONE"
)
TRACE_CSV_COLUMNS = (
    "time", "lat", "lon", "height", "processed_lat", "processed_lon",
    "processed_height", "yaw", "pitch", "roll",
)
PASS_READY = "PASS_PHASE2_EXT02_CWLS_C00_READY_FOR_NATIVE_COMPARISON"
PASS_VALIDATED = "PASS_PHASE2_EXT02_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT"
UNSUPPORTED = "UNSUPPORTED_EXT02_ON_BY2_DUE_TO_EXPLICIT_PAPER_ASSUMPTION_VIOLATION"
BLOCKED_PREFIX = "BLOCKED_PHASE2_EXT02_"
NATIVE_FILE_NAMES = {
    "heading_results": "EXT02_C00_NATIVE_HEADING_RESULTS.csv",
    "failure_ledger": "EXT02_C00_FAILURE_LEDGER.csv",
    "runtime": "EXT02_C00_RUNTIME.csv",
    "dd_diagnostics": "EXT02_C00_DD_DIAGNOSTICS.csv",
    "candidate_diagnostics": "EXT02_C00_CANDIDATE_DIAGNOSTICS.csv",
    "refinement_diagnostics": "EXT02_C00_REFINEMENT_DIAGNOSTICS.csv",
    "objective_oracle_diagnostics": "EXT02_C00_OBJECTIVE_ORACLE_DIAGNOSTICS.csv",
    "tracking_diagnostics": "EXT02_C00_TRACKING_DIAGNOSTICS.csv",
    "native_summary": "EXT02_C00_NATIVE_SUMMARY.json",
    "native_freeze": "EXT02_C00_NATIVE_FREEZE.json",
}
POST_NATIVE_FILE_NAMES = {
    "proxy_diagnostics": "EXT02_C00_PROXY_DIAGNOSTICS.csv",
    "objective_diagnostics": "EXT02_C00_POST_NATIVE_OBJECTIVE_DIAGNOSTICS.csv",
    "trace_diagnostics": "EXT02_C00_TRACE_DIAGNOSTICS.csv",
    "fractional_dd_diagnostics": "EXT02_C00_FRACTIONAL_DD_DIAGNOSTICS.csv",
    "post_native_manifest": "EXT02_C00_POST_NATIVE_DIAGNOSTICS_MANIFEST.json",
}
REPORT_FILE_NAME = "PHASE2_EXT02_C00_REPORT.md"
STATUS_FILE_NAME = "PHASE2_STATUS.json"
ALLOWED_MODES = frozenset({
    "preflight", "resource-determinism-probe", "native-only",
    "post-native-diagnostics", "full",
})


class Phase2RunnerError(RuntimeError):
    """Fail-closed Phase-2 contract or lifecycle violation."""


class ResourceAdmissionError(Phase2RunnerError):
    """Resource/determinism rejection carrying the evidence that caused it."""

    def __init__(self, evidence: Mapping[str, Any]):
        self.evidence = dict(evidence)
        reasons = self.evidence.get("rejection_reasons", [])
        super().__init__(f"resource admission rejected: {','.join(str(item) for item in reasons)}")


@dataclass(frozen=True)
class Phase2Paths:
    config_path: Path
    code_root: Path
    raw_root: Path
    by2_fix_root: Path
    clean_root: Path
    raw_hash_lock: Path
    gnss1_raw: Path
    gnss2_raw: Path
    trace: Path
    rtklib_root: Path
    convbin: Path
    rtklib_bridge: Path
    bridge_root: Path
    stage_root: Path
    native_root: Path
    report_root: Path
    final_report: Path
    final_status: Path

    @property
    def native_files(self) -> dict[str, Path]:
        return {name: self.native_root / filename for name, filename in NATIVE_FILE_NAMES.items()}

    @property
    def post_native_files(self) -> dict[str, Path]:
        return {
            name: self.native_root / filename
            for name, filename in POST_NATIVE_FILE_NAMES.items()
        }


@dataclass(frozen=True)
class PostNativeDestinations:
    recovery_id: str | None
    output_root: Path
    post_native_files: Mapping[str, Path]
    report: Path
    status: Path

    @property
    def is_recovery(self) -> bool:
        return self.recovery_id is not None


def _validated_post_recovery_id(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or POST_RECOVERY_ID_PATTERN.fullmatch(value) is None:
        raise Phase2RunnerError(
            "post recovery id must match [A-Za-z0-9][A-Za-z0-9_-]{0,63}"
        )
    return value


def _post_native_destinations(
    paths: Phase2Paths,
    post_recovery_id: str | None,
) -> PostNativeDestinations:
    recovery_id = _validated_post_recovery_id(post_recovery_id)
    if recovery_id is None:
        return PostNativeDestinations(
            recovery_id=None,
            output_root=paths.native_root,
            post_native_files=paths.post_native_files,
            report=paths.final_report,
            status=paths.final_status,
        )
    output_root = paths.native_root / f"POST_NATIVE_RECOVERY_{recovery_id}"
    return PostNativeDestinations(
        recovery_id=recovery_id,
        output_root=output_root,
        post_native_files={
            name: output_root / filename
            for name, filename in POST_NATIVE_FILE_NAMES.items()
        },
        report=paths.report_root / f"PHASE2_EXT02_C00_REPORT_{recovery_id}.md",
        status=paths.report_root / f"PHASE2_STATUS_{recovery_id}.json",
    )


@dataclass(frozen=True)
class PreflightResult:
    paths: Phase2Paths
    contract: dict[str, Any]
    config_hash: str
    contract_hash: str
    schema_hash: str
    code_commit: str
    raw_source_hashes: dict[str, str]
    provider_hashes: dict[str, str]
    source_fingerprint: str
    runtime_source_hashes: dict[str, str] = field(default_factory=dict)
    git_source_state: dict[str, Any] = field(default_factory=dict)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def terminal_json(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _load_mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise Phase2RunnerError(f"YAML document is not a mapping: {path}")
    return value


def _reject_symlink_components(path: Path) -> None:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise Phase2RunnerError(f"machine path must be absolute: {candidate}")
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise Phase2RunnerError(f"symlink path component is forbidden: {current}")
        if not current.exists():
            # Nonexistent descendants cannot contain a symlink yet; their
            # existing parent chain has already been checked.
            break


def _configured_absolute(values: Mapping[str, Any], name: str) -> Path:
    path = Path(str(values[name]))
    _reject_symlink_components(path)
    return path.resolve()


def _require_contained(path: Path, root: Path, label: str) -> None:
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise Phase2RunnerError(f"{label} lies outside its authorized root") from exc


def load_paths(config_path: Path) -> Phase2Paths:
    config = Path(config_path).resolve()
    document = _load_mapping(config)
    if document.get("schema_version") != "paper_rebuild.paths.v1":
        raise Phase2RunnerError("unsupported local paths schema")
    values = document.get("paths")
    if not isinstance(values, dict):
        raise Phase2RunnerError("local paths document lacks paths mapping")
    required = (
        "code_root", "raw_root", "by2_fix_root", "clean_root",
        "horizontal_literature_rtklib_root", "horizontal_literature_convbin",
        "horizontal_literature_rtklib_bridge", "horizontal_literature_bridge_root",
    )
    missing = [name for name in required if not isinstance(values.get(name), str)]
    if missing:
        raise Phase2RunnerError(f"local paths missing required entries: {missing}")
    code_root = _configured_absolute(values, "code_root")
    raw_root = _configured_absolute(values, "raw_root")
    by2 = _configured_absolute(values, "by2_fix_root")
    clean = _configured_absolute(values, "clean_root")
    stage = clean / "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
    trace_name = "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv"
    report_root = stage / "11_REPORT"
    return Phase2Paths(
        config_path=config,
        code_root=code_root,
        raw_root=raw_root,
        by2_fix_root=by2,
        clean_root=clean,
        raw_hash_lock=clean / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv",
        gnss1_raw=by2 / "gnss1-raw.csv",
        gnss2_raw=by2 / "gnss2-raw.csv",
        trace=by2 / trace_name,
        rtklib_root=_configured_absolute(values, "horizontal_literature_rtklib_root"),
        convbin=_configured_absolute(values, "horizontal_literature_convbin"),
        rtklib_bridge=_configured_absolute(values, "horizontal_literature_rtklib_bridge"),
        bridge_root=_configured_absolute(values, "horizontal_literature_bridge_root"),
        stage_root=stage,
        native_root=stage / "03_EXT02_CWLS/C00",
        report_root=report_root,
        final_report=report_root / REPORT_FILE_NAME,
        final_status=report_root / STATUS_FILE_NAME,
    )


def load_phase2_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = _load_mapping(path)
    if contract.get("schema_version") != "horizontal_literature.phase2_ext02_cwls.v1":
        raise Phase2RunnerError("unsupported Phase-2 contract schema")
    exact = {
        "method_id": METHOD_ID,
        "case_id": CASE_ID,
        "formal_reproduction_level": "FAITHFUL_ALGORITHM_REPRODUCTION",
    }
    for name, expected in exact.items():
        if contract.get(name) != expected:
            raise Phase2RunnerError(f"Phase-2 contract drift: {name}")
    algorithm = contract.get("algorithm", {})
    observation = contract.get("observation_contract", {})
    parallel = contract.get("parallel_execution", {})
    if (
        algorithm.get("K_policy") != "ALL_UNIQUE_CANDIDATES"
        or float(algorithm.get("delta_Delta", math.nan)) != 0.05
        or float(algorithm.get("baseline_length_m", math.nan)) != BASELINE_LENGTH_M
        or float(algorithm.get("sphere_refinement", {}).get("tolerance", math.nan)) != 1.0e-10
        or int(algorithm.get("sphere_refinement", {}).get("max_iterations", -1)) != 20
    ):
        raise Phase2RunnerError("Phase-2 mathematical constants drifted")
    if (
        observation.get("constellation") != "GPS"
        or observation.get("signal") != "L1_CA"
        or float(observation.get("pairing_tolerance_seconds", math.nan)) != 0.0
        or int(observation.get("required_paired_epoch_count", -1)) != EXPECTED_PAIR_COUNT
        or float(observation.get("elevation_mask_deg", math.nan)) != 10.0
        or observation.get("HPPOSECEF_solver_input") is not False
    ):
        raise Phase2RunnerError("Phase-2 raw observation contract drifted")
    if int(parallel.get("default_workers", -1)) != DEFAULT_WORKERS or int(
        parallel.get("maximum_workers", -1)
    ) != MAX_WORKERS:
        raise Phase2RunnerError("Phase-2 worker contract drifted")
    admission = parallel.get("resource_admission", {})
    projection = admission.get("deterministic_output_size_projection", {})
    if (
        float(admission.get("projected_RSS_exclusive_limit_fraction_of_available_RAM", -1.0))
        != RESOURCE_RSS_AVAILABLE_FRACTION_LIMIT
        or int(projection.get("paired_epoch_count", -1)) != EXPECTED_PAIR_COUNT
        or int(projection.get("bytes_per_epoch", -1)) != RESOURCE_PROJECTED_BYTES_PER_EPOCH
        or int(projection.get("fixed_bytes", -1)) != RESOURCE_PROJECTED_FIXED_BYTES
        or int(projection.get("disk_safety_reserve_bytes", -1))
        != RESOURCE_DISK_SAFETY_RESERVE_BYTES
    ):
        raise Phase2RunnerError("Phase-2 resource-admission contract drifted")
    required_shared_codes = {
        "INSUFFICIENT_PR_CP_VALID", "INSUFFICIENT_INTEGER_COMPATIBLE_PHASE",
        "INSUFFICIENT_ELEVATION_ELIGIBLE", "NORMAL_MATRIX_RANK_DEFICIENT",
    }
    if not required_shared_codes.issubset(contract.get("failure_codes", ())):
        raise Phase2RunnerError("Phase-2 shared-backend failure-code contract drifted")
    native_files = contract.get("runtime_topology", {}).get("native_files")
    if native_files != NATIVE_FILE_NAMES:
        raise Phase2RunnerError("Phase-2 native filename inventory drifted")
    csv_contract = contract.get("runtime_topology", {}).get("native_csv_field_contract", {})
    if int(csv_contract.get("python_csv_decoded_character_limit", -1)) != CSV_FIELD_SIZE_LIMIT:
        raise Phase2RunnerError("Phase-2 native CSV field-size contract drifted")
    post_evaluator = contract.get("post_native_evaluator", {})
    trace_csv_contract = post_evaluator.get("trace_csv_contract", {})
    leap_contract = post_evaluator.get("leap_seconds", {})
    if (
        int(trace_csv_contract.get("observed_column_count", -1)) != len(TRACE_CSV_COLUMNS)
        or trace_csv_contract.get("first_column") != "time"
        or trace_csv_contract.get("exact_columns") != list(TRACE_CSV_COLUMNS)
        or trace_csv_contract.get("timestamp_alias_accepted") is not False
    ):
        raise Phase2RunnerError("Phase-2 fixed trace CSV contract drifted")
    if (
        post_evaluator.get("gps_to_unix_seconds")
        != "315964800+gps_week*604800+gps_tow_seconds-leap_seconds"
        or int(leap_contract.get("expected_value", -1))
        != EXPECTED_GPS_UTC_LEAP_SECONDS
        or leap_contract.get("authority")
        != "COMPACT_CACHE_PAIRED_EPOCHS_R1_R2_LEAP_FIELDS"
        or leap_contract.get("require_identical_all_receiver_epochs") is not True
    ):
        raise Phase2RunnerError("Phase-2 fixed GPS-to-Unix trace contract drifted")
    if (
        post_evaluator.get("trace_unwrap_domain")
        != "FULL_VALIDATED_MONOTONIC_TRACE_BEFORE_NATIVE_WINDOW_GATE"
        or post_evaluator.get("native_epoch_match_gate_seconds") != [66.0, 340.0]
        or post_evaluator.get("matched_native_time_must_be_bracketed_by_trace") is not True
    ):
        raise Phase2RunnerError("Phase-2 trace unwrap/window contract drifted")
    invocation_contract = post_evaluator.get("invocation_accounting", {})
    if (
        invocation_contract.get("manifest_count_scope")
        != "SUCCESSFUL_POST_NATIVE_INVOCATION_ONLY"
        or invocation_contract.get("hpposecef_decode_pass_count_unit")
        != "GNSS_RECEIVER_STREAM"
        or int(invocation_contract.get(
            "successful_invocation_receiver_stream_decode_pass_count", -1
        )) != 2
        or invocation_contract.get(
            "prior_failed_post_native_attempts_not_in_successful_invocation_counts"
        ) is not True
    ):
        raise Phase2RunnerError("Phase-2 post-native invocation accounting drifted")
    proxy_association = post_evaluator.get("proxy_epoch_association", {})
    if (
        proxy_association.get("receiver_streams_duplicate_free") is not True
        or proxy_association.get("candidate_grid")
        != "SORTED_INTERSECTION_OF_GNSS1_AND_GNSS2_HPPOSECEF_ITOW"
        or proxy_association.get("nearest_requirement")
        != "UNIQUE_NEAREST_COMMON_EPOCH"
        or proxy_association.get("midpoint_tie") != "UNAVAILABLE"
        or proxy_association.get("assignment_requirement")
        != "STRICT_MONOTONIC_ONE_TO_ONE"
        or proxy_association.get("trace_or_accuracy_used") is not False
    ):
        raise Phase2RunnerError("Phase-2 proxy epoch-association contract drifted")
    recovery_contract = post_evaluator.get("recovery_outputs", {})
    if (
        recovery_contract.get("safe_slug_regex")
        != "[A-Za-z0-9][A-Za-z0-9_-]{0,63}"
        or recovery_contract.get("permitted_mode") != "post-native-diagnostics"
        or recovery_contract.get("collision_policy")
        != "REFUSE_IF_ANY_RECOVERY_TARGET_EXISTS"
        or recovery_contract.get("primary_post_role")
        != "HASHED_IMMUTABLE_INPUT_ONLY"
        or recovery_contract.get("supersedes_for_proxy_diagnostics_only") is not True
    ):
        raise Phase2RunnerError("Phase-2 post-native recovery-output contract drifted")
    schema = _load_mapping(HEADING_SCHEMA_PATH)
    fields = schema.get("fields", {})
    if METHOD_ID not in fields.get("method_id", {}).get("enum", ()):
        raise Phase2RunnerError("standard heading schema does not admit EXT02_CWLS")
    if "accepted_wrapped_solution" not in fields.get("solution_state", {}).get("enum", ()):
        raise Phase2RunnerError("standard heading schema lacks accepted_wrapped_solution")
    return contract


def _git_commit(root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise Phase2RunnerError(f"cannot resolve Git commit for {root}")
    value = completed.stdout.strip()
    if len(value) != 40:
        raise Phase2RunnerError(f"invalid Git commit identity for {root}")
    return value


def _runtime_source_hashes() -> dict[str, str]:
    sources = (
        CONTRACT_PATH,
        HEADING_SCHEMA_PATH,
        CLI_PATH,
        Path(__file__),
        Path(__file__).with_name("shared_raw_backend.py"),
        Path(__file__).with_name("ext02_cwls.py"),
    )
    return {
        source.relative_to(REPOSITORY_ROOT).as_posix(): _sha256_file(source)
        for source in sources
    }


def _git_runtime_source_state(runtime_source_hashes: Mapping[str, str]) -> dict[str, Any]:
    paths = sorted(runtime_source_hashes)
    completed = subprocess.run(
        [
            "git", "-C", str(REPOSITORY_ROOT), "status", "--short",
            "--untracked-files=all", "--", *paths,
        ],
        text=True, capture_output=True, check=False,
    )
    if completed.returncode != 0:
        raise Phase2RunnerError("cannot audit authorized runtime-source Git delta")
    entries = [line for line in completed.stdout.splitlines() if line.strip()]
    return {
        "code_commit_role": "BASE_HEAD_ONLY_NOT_COMPLETE_RUNTIME_SOURCE_IDENTITY",
        "runtime_source_identity_role": "SOURCE_HASHES_PLUS_SOURCE_FINGERPRINT",
        "authorized_dirty_runtime_delta_allowed": True,
        "authorized_dirty_runtime_delta_present": bool(entries),
        "authorized_dirty_runtime_delta_entries": entries,
        "runtime_source_paths": paths,
    }


def _raw_hash_lock_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise Phase2RunnerError(f"raw hash lock is unavailable: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"relative_path", "size_bytes", "sha256"}
        if not required.issubset(reader.fieldnames or ()):
            raise Phase2RunnerError("raw hash lock schema is invalid")
        rows = {row["relative_path"].replace("\\", "/"): row for row in reader}
    return rows


def _verify_locked_raw(paths: Phase2Paths) -> dict[str, str]:
    rows = _raw_hash_lock_rows(paths.raw_hash_lock)
    result: dict[str, str] = {}
    for name, source in (("gnss1_raw", paths.gnss1_raw), ("gnss2_raw", paths.gnss2_raw)):
        if not source.is_file():
            raise Phase2RunnerError(f"required raw source is unavailable: {source}")
        try:
            relative = source.relative_to(paths.raw_root).as_posix()
        except ValueError as exc:
            raise Phase2RunnerError("BY2 raw source lies outside configured raw_root") from exc
        locked = rows.get(relative)
        if locked is None:
            raise Phase2RunnerError(f"raw source absent from hash lock: {relative}")
        digest = _sha256_file(source)
        if digest != locked["sha256"] or source.stat().st_size != int(locked["size_bytes"]):
            raise Phase2RunnerError(f"raw hash-lock mismatch: {relative}")
        result[name] = digest
    result["raw_hash_lock"] = _sha256_file(paths.raw_hash_lock)
    return result


def _external_provider_audit(paths: Phase2Paths) -> dict[str, str]:
    for source in (paths.convbin, paths.rtklib_bridge):
        if not source.is_file():
            raise Phase2RunnerError(f"external provider file is unavailable: {source}")
    if not paths.rtklib_root.is_dir() or not paths.bridge_root.is_dir():
        raise Phase2RunnerError("external RTKLIB/bridge source root is unavailable")
    commit = _git_commit(paths.rtklib_root)
    expected = "180043ee24b6d2b168f98b64be15f69d50046b1a"
    if commit != expected:
        raise Phase2RunnerError("RTKLIB commit does not match the frozen dependency")
    remote = subprocess.run(
        ["git", "-C", str(paths.rtklib_root), "remote", "get-url", "origin"],
        text=True, capture_output=True, check=False,
    )
    if remote.returncode != 0 or remote.stdout.strip() != "https://github.com/tomojitakasu/RTKLIB.git":
        raise Phase2RunnerError("RTKLIB origin remote does not match the frozen dependency")
    tracked = subprocess.run(
        ["git", "-C", str(paths.rtklib_root), "status", "--porcelain", "--untracked-files=no"],
        text=True, capture_output=True, check=False,
    )
    if tracked.returncode != 0 or tracked.stdout.strip():
        raise Phase2RunnerError("RTKLIB tracked worktree is not clean")
    license_candidates = [
        path for name in ("LICENSE", "LICENSE.txt", "COPYING")
        if (path := paths.rtklib_root / name).is_file()
    ]
    if len(license_candidates) != 1:
        raise Phase2RunnerError("RTKLIB license file identity is ambiguous")
    license_path = license_candidates[0]
    license_text = license_path.read_text(encoding="utf-8", errors="strict")
    if "Redistribution and use in source and binary forms" not in license_text:
        raise Phase2RunnerError("RTKLIB license text is not the expected BSD form")
    bridge_sources = sorted(
        path for path in paths.bridge_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".c", ".cc", ".cpp", ".h", ".hpp"}
    )
    if not bridge_sources:
        raise Phase2RunnerError("RTKLIB bridge source inventory is empty")
    result = {
        "rtklib_commit": commit,
        "rtklib_remote": remote.stdout.strip(),
        "rtklib_license": "BSD-2-Clause",
        "rtklib_license_sha256": _sha256_file(license_path),
        "rtklib_tracked_worktree_clean": "true",
        "convbin_sha256": _sha256_file(paths.convbin),
        "rtklib_bridge_sha256": _sha256_file(paths.rtklib_bridge),
    }
    for source in bridge_sources:
        result[f"bridge_source_sha256::{source.relative_to(paths.bridge_root).as_posix()}"] = (
            _sha256_file(source)
        )
    return result


def _fingerprint(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def preflight_phase2(
    config_path: Path,
    *,
    mode: str = "full",
    workers: int = DEFAULT_WORKERS,
    method_id: str = METHOD_ID,
    case_id: str = CASE_ID,
    trace_mode: str = "disabled",
    post_recovery_id: str | None = None,
) -> PreflightResult:
    if mode not in ALLOWED_MODES:
        raise Phase2RunnerError(f"unsupported lifecycle mode: {mode}")
    if method_id != METHOD_ID or case_id != CASE_ID:
        raise Phase2RunnerError("Phase 2 enables exactly EXT02_CWLS/C00")
    if trace_mode != "disabled":
        raise Phase2RunnerError("native trace mode must be the literal disabled")
    recovery_id = _validated_post_recovery_id(post_recovery_id)
    if recovery_id is not None and mode != "post-native-diagnostics":
        raise Phase2RunnerError(
            "post recovery id is allowed only in post-native-diagnostics mode"
        )
    if not isinstance(workers, int) or isinstance(workers, bool) or not 1 <= workers <= MAX_WORKERS:
        raise Phase2RunnerError(f"workers must be in 1..{MAX_WORKERS}")
    paths = load_paths(config_path)
    if paths.code_root != REPOSITORY_ROOT.resolve():
        raise Phase2RunnerError("configured code_root is not this worktree")
    expected_by2_relative = Path(
        "BY2_BY3/2026-03-06/fixption数据/2026.3.6/by2/"
        "vrtk2_a87c6e_2026-03-06-08-00-54_minimal"
    )
    if paths.by2_fix_root != paths.raw_root / expected_by2_relative:
        raise Phase2RunnerError("configured BY2 source identity drifted")
    _require_contained(paths.by2_fix_root, paths.raw_root, "BY2 source")
    _require_contained(paths.stage_root, paths.clean_root, "CLEAN4 stage")
    for target, label in (
        (paths.native_root, "native root"), (paths.report_root, "report root"),
        (paths.final_report, "final report"), (paths.final_status, "final status"),
    ):
        _reject_symlink_components(target)
        _require_contained(target, paths.stage_root, label)
    destinations = _post_native_destinations(paths, recovery_id)
    if destinations.is_recovery:
        for target, root, label in (
            (destinations.output_root, paths.native_root, "post recovery output root"),
            (destinations.report, paths.report_root, "post recovery report"),
            (destinations.status, paths.report_root, "post recovery status"),
        ):
            _reject_symlink_components(target)
            _require_contained(target, root, label)
    if not paths.raw_root.is_dir() or not paths.by2_fix_root.is_dir() or not paths.clean_root.is_dir():
        raise Phase2RunnerError("configured raw/BY2/clean root is unavailable")
    contract = load_phase2_contract()
    raw_hashes = _verify_locked_raw(paths)
    provider_hashes = _external_provider_audit(paths)
    code_commit = _git_commit(REPOSITORY_ROOT)
    config_hash = _sha256_file(paths.config_path)
    contract_hash = _sha256_file(CONTRACT_PATH)
    schema_hash = _sha256_file(HEADING_SCHEMA_PATH)
    runtime_source_hashes = _runtime_source_hashes()
    git_source_state = _git_runtime_source_state(runtime_source_hashes)
    native_exists = paths.native_root.exists()
    terminal_exists = paths.final_status.exists() or paths.final_report.exists()
    if mode in {"preflight", "native-only", "full", "resource-determinism-probe"}:
        if native_exists:
            raise Phase2RunnerError("final native root already exists")
        if terminal_exists:
            raise Phase2RunnerError("final Phase-2 terminal output already exists")
    elif mode == "post-native-diagnostics":
        if not paths.native_root.is_dir():
            raise Phase2RunnerError("post-native diagnostics require the native root")
        if recovery_id is None and terminal_exists:
            raise Phase2RunnerError("final Phase-2 terminal output already exists")
        if recovery_id is not None:
            _validate_recovery_targets_absent(destinations)
            _primary_post_inventory(paths)
    source_payload = {
        "schema": "horizontal_literature.phase2.source_fingerprint.v1",
        "config_hash": config_hash,
        "contract_hash": contract_hash,
        "heading_schema_hash": schema_hash,
        "code_commit": code_commit,
        "code_commit_role": git_source_state["code_commit_role"],
        "runtime_source_hashes": runtime_source_hashes,
        "git_source_state": git_source_state,
        "raw_source_hashes": raw_hashes,
        "provider_hashes": provider_hashes,
        "python": platform.python_version(),
        "numpy": np.__version__,
    }
    return PreflightResult(
        paths=paths, contract=contract, config_hash=config_hash,
        contract_hash=contract_hash, schema_hash=schema_hash,
        code_commit=code_commit, raw_source_hashes=raw_hashes,
        provider_hashes=provider_hashes,
        source_fingerprint=_fingerprint(source_payload),
        runtime_source_hashes=runtime_source_hashes,
        git_source_state=git_source_state,
    )


def _path_lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _validate_recovery_targets_absent(destinations: PostNativeDestinations) -> None:
    if not destinations.is_recovery:
        return
    collisions = [
        str(path) for path in (
            destinations.output_root, destinations.report, destinations.status,
        )
        if _path_lexists(path)
    ]
    if collisions:
        raise Phase2RunnerError(
            f"post recovery target collision: {sorted(collisions)}"
        )


def _primary_post_inventory(paths: Phase2Paths) -> dict[str, Any]:
    sources: dict[str, Path] = {
        f"post_native::{name}": path
        for name, path in paths.post_native_files.items()
    }
    sources.update({
        "report::phase2_report": paths.final_report,
        "report::phase2_status": paths.final_status,
    })
    entries: dict[str, dict[str, Any]] = {}
    for logical, path in sorted(sources.items()):
        _reject_symlink_components(path)
        if not path.is_file():
            raise Phase2RunnerError(
                f"post recovery requires immutable primary evidence: {logical}"
            )
        entries[logical] = {
            "absolute_path": str(path),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
    identity = {
        "schema_version": "horizontal_literature.phase2.prior_post_inventory.v1",
        "role": "IMMUTABLE_PRIMARY_POST_EVIDENCE_INPUT_ONLY",
        "files": entries,
    }
    return {
        **identity,
        "inventory_sha256": _fingerprint(identity),
    }


def _revalidate_primary_post_inventory(
    paths: Phase2Paths,
    expected: Mapping[str, Any],
) -> None:
    if _primary_post_inventory(paths) != dict(expected):
        raise Phase2RunnerError("immutable primary post inventory changed during recovery")


def _prepare_recovery_output_root(destinations: PostNativeDestinations) -> None:
    if not destinations.is_recovery:
        return
    _validate_recovery_targets_absent(destinations)
    try:
        destinations.output_root.mkdir()
    except FileExistsError as exc:
        raise Phase2RunnerError(
            f"post recovery target collision: {destinations.output_root}"
        ) from exc


def _mountinfo_unescape(value: str) -> str:
    return (
        value.replace("\\040", " ").replace("\\011", "\t")
        .replace("\\012", "\n").replace("\\134", "\\")
    )


def _mount_identity(path: Path) -> dict[str, str]:
    absolute = Path(os.path.abspath(path))
    matches: list[tuple[int, dict[str, str]]] = []
    for line in Path("/proc/self/mountinfo").read_text(encoding="utf-8").splitlines():
        if " - " not in line:
            continue
        prefix, suffix = line.split(" - ", 1)
        left, right = prefix.split(), suffix.split()
        if len(left) < 6 or len(right) < 3:
            continue
        mount_point = Path(_mountinfo_unescape(left[4]))
        if absolute != mount_point and mount_point not in absolute.parents:
            continue
        matches.append((len(mount_point.parts), {
            "mount_point": str(mount_point),
            "filesystem_type": right[0],
            "source": _mountinfo_unescape(right[1]),
            "mount_options": left[5],
            "super_options": " ".join(right[2:]),
        }))
    if not matches:
        raise Phase2RunnerError(f"cannot identify filesystem mount for atomic target: {path}")
    return max(matches, key=lambda item: item[0])[1]


def _same_drvfs_mount(source: Path, target: Path) -> dict[str, str]:
    source_mount = _mount_identity(source)
    target_mount = _mount_identity(target.parent)
    if source_mount != target_mount:
        raise Phase2RunnerError("atomic Windows fallback requires the same filesystem mount")
    if (
        source_mount["filesystem_type"] != "9p"
        or "aname=drvfs" not in source_mount["super_options"]
    ):
        raise Phase2RunnerError("atomic Windows fallback is permitted only on 9p DrvFS")
    mount_parts = Path(source_mount["mount_point"]).parts
    if (
        len(mount_parts) != 3
        or mount_parts[:2] != ("/", "mnt")
        or len(mount_parts[2]) != 1
        or not mount_parts[2].isalpha()
    ):
        raise Phase2RunnerError("DrvFS atomic target is not under one /mnt/<drive> mount")
    return source_mount


def _wsl_windows_path(path: Path) -> str:
    converter = shutil.which("wslpath")
    if converter is None:
        raise Phase2RunnerError("wslpath is unavailable for DrvFS atomic move")
    completed = subprocess.run(
        [converter, "-w", os.fspath(path)], capture_output=True, check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise Phase2RunnerError(f"wslpath failed for DrvFS atomic move: {detail}")
    value = completed.stdout.decode("utf-8", errors="strict").strip()
    if not value:
        raise Phase2RunnerError("wslpath returned an empty DrvFS path")
    return value


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _windows_dotnet_move_noreplace(
    source: Path,
    target: Path,
    *,
    kind: str,
    label: str,
) -> str:
    if kind not in {"file", "directory"}:
        raise Phase2RunnerError(f"invalid atomic install kind: {kind}")
    _same_drvfs_mount(source, target)
    powershell = shutil.which("powershell.exe")
    if powershell is None:
        raise Phase2RunnerError("powershell.exe is unavailable for DrvFS atomic move")
    source_windows = _wsl_windows_path(source)
    target_windows = _wsl_windows_path(target)
    source_literal = "'" + source_windows.replace("'", "''") + "'"
    target_literal = "'" + target_windows.replace("'", "''") + "'"
    kind_literal = "'" + kind.replace("'", "''") + "'"
    script = f"""
$ErrorActionPreference = 'Stop'
$source = {source_literal}
$target = {target_literal}
$kind = {kind_literal}
if ($kind -eq 'directory') {{
    [System.IO.Directory]::Move($source, $target)
}} elseif ($kind -eq 'file') {{
    [System.IO.File]::Move($source, $target)
}} else {{
    throw "invalid atomic move kind"
}}
""".strip()
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    completed = subprocess.run(
        [
            powershell, "-NoLogo", "-NoProfile", "-NonInteractive",
            "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded,
        ],
        capture_output=True, check=False,
    )
    if completed.returncode != 0:
        if _path_lexists(target):
            raise Phase2RunnerError(f"{label} target collision: {target}")
        detail = (completed.stderr or completed.stdout).decode(
            "utf-8", errors="replace",
        ).strip()
        raise Phase2RunnerError(
            f"DrvFS Windows no-replace {kind} move failed ({completed.returncode}): {detail}"
        )
    if _path_lexists(source) or not _path_lexists(target):
        raise Phase2RunnerError("DrvFS Windows move returned without exact source/target transition")
    return f"WINDOWS_DOTNET_{kind.upper()}_MOVE_NOREPLACE"


def _atomic_install_noreplace(
    temporary: Path,
    target: Path,
    *,
    label: str,
    kind: str = "file",
) -> str:
    if _path_lexists(target):
        raise Phase2RunnerError(f"{label} target collision: {target}")
    if kind == "directory":
        _fsync_directory(temporary)
    library = ctypes.CDLL(None, use_errno=True)
    rename_noreplace = getattr(library, "renameat2", None)
    error = errno.ENOSYS
    if rename_noreplace is not None:
        rename_noreplace.argtypes = [
            ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint,
        ]
        rename_noreplace.restype = ctypes.c_int
        result = rename_noreplace(
            -100, os.fsencode(temporary), -100, os.fsencode(target), 1,
        )
        if result == 0:
            _fsync_directory(target.parent)
            return "LINUX_RENAMEAT2_NOREPLACE"
        error = ctypes.get_errno()
    if error in {errno.EEXIST, errno.ENOTEMPTY, errno.EISDIR}:
        raise Phase2RunnerError(f"{label} target collision: {target}")
    fallback_errors = {
        errno.EINVAL, errno.ENOSYS, errno.EPERM,
        getattr(errno, "ENOTSUP", errno.EINVAL),
        getattr(errno, "EOPNOTSUPP", errno.EINVAL),
    }
    if error in fallback_errors:
        mode = _windows_dotnet_move_noreplace(
            temporary, target, kind=kind, label=label,
        )
        _fsync_directory(target.parent)
        return mode
    raise OSError(error, os.strerror(error), str(target))


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if _path_lexists(path):
        raise Phase2RunnerError(f"atomic byte target collision: {path}")
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    if _path_lexists(temporary):
        raise Phase2RunnerError(f"atomic temporary path already exists: {temporary}")
    with temporary.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    _atomic_install_noreplace(temporary, path, label="atomic byte")


def _atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    _atomic_write_bytes(path, (json.dumps(_jsonable(value), indent=2, sort_keys=True,
                                                ensure_ascii=False) + "\n").encode("utf-8"))


def _atomic_write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if _path_lexists(path):
        raise Phase2RunnerError(f"atomic CSV target collision: {path}")
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    if _path_lexists(temporary):
        raise Phase2RunnerError(f"atomic temporary path already exists: {temporary}")
    with temporary.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: _csv_value(row.get(name)) for name in fields})
        stream.flush()
        os.fsync(stream.fileno())
    _atomic_install_noreplace(temporary, path, label="atomic CSV")


def _csv_value(value: Any) -> Any:
    value = _jsonable(value)
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return _canonical_json(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _max_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    # Linux reports KiB; macOS reports bytes.  This execution contract is
    # Linux/WSL, but retain the platform distinction for unit portability.
    return value * 1024 if platform.system() == "Linux" else value


MEASUREMENT_DTYPE = np.dtype([
    ("gnss_id", "u1"), ("sv_id", "u1"), ("sig_id", "u1"), ("freq_id", "u1"),
    ("pr_mes_m", "<f8"), ("cp_mes_cycles", "<f8"), ("do_mes_hz", "<f8"),
    ("locktime_ms", "<u2"), ("cno_dbhz", "u1"),
    ("pr_std_code", "u1"), ("cp_std_code", "u1"), ("do_std_code", "u1"),
    ("tracking_status", "u1"),
])
EPOCH_DTYPE = np.dtype([
    ("gps_week", "<i4"), ("gps_tow_seconds", "<f8"),
    ("r1_leap", "i1"), ("r1_status", "u1"), ("r1_version", "u1"),
    ("r1_offset", "<i8"), ("r1_count", "<i4"),
    ("r2_leap", "i1"), ("r2_status", "u1"), ("r2_version", "u1"),
    ("r2_offset", "<i8"), ("r2_count", "<i4"),
])


def _measurement_tuple(measurement: RawxMeasurement) -> tuple[Any, ...]:
    identity = measurement.identity
    return (
        identity.gnss_id, identity.sv_id, identity.sig_id, identity.freq_id,
        measurement.pr_mes_m, measurement.cp_mes_cycles, measurement.do_mes_hz,
        measurement.locktime_ms, measurement.cno_dbhz, measurement.pr_std_code,
        measurement.cp_std_code, measurement.do_std_code, measurement.tracking_status,
    )


def _pack_pairs(
    pairs: Sequence[tuple[RawxEpoch, RawxEpoch]],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    epochs = np.empty(len(pairs), dtype=EPOCH_DTYPE)
    receiver1: list[tuple[Any, ...]] = []
    receiver2: list[tuple[Any, ...]] = []
    for index, (left, right) in enumerate(pairs):
        if (left.gps_week, left.gps_tow_seconds) != (right.gps_week, right.gps_tow_seconds):
            raise Phase2RunnerError("compact cache received a non-exact epoch pair")
        offset1, offset2 = len(receiver1), len(receiver2)
        receiver1.extend(_measurement_tuple(item) for item in left.measurements)
        receiver2.extend(_measurement_tuple(item) for item in right.measurements)
        epochs[index] = (
            left.gps_week, left.gps_tow_seconds,
            left.leap_seconds, left.receiver_status, left.version, offset1, len(left.measurements),
            right.leap_seconds, right.receiver_status, right.version, offset2, len(right.measurements),
        )
    return (
        epochs,
        np.asarray(receiver1, dtype=MEASUREMENT_DTYPE),
        np.asarray(receiver2, dtype=MEASUREMENT_DTYPE),
    )


def _atomic_save_npy(path: Path, array: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if _path_lexists(path):
        raise Phase2RunnerError(f"cache target collision: {path}")
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    if _path_lexists(temporary):
        raise Phase2RunnerError(f"cache temporary already exists: {temporary}")
    with temporary.open("xb") as stream:
        np.save(stream, array, allow_pickle=False)
        stream.flush()
        os.fsync(stream.fileno())
    _atomic_install_noreplace(temporary, path, label="cache")


def write_compact_cache(
    cache_root: Path,
    pairs: Sequence[tuple[RawxEpoch, RawxEpoch]],
    *,
    source_fingerprint: str,
    extra_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cache = Path(cache_root)
    if cache.exists():
        raise Phase2RunnerError("compact cache root already exists")
    cache.mkdir(parents=True)
    epochs, receiver1, receiver2 = _pack_pairs(pairs)
    files = {
        "epochs": cache / "paired_epochs.npy",
        "receiver1_measurements": cache / "receiver1_measurements.npy",
        "receiver2_measurements": cache / "receiver2_measurements.npy",
    }
    _atomic_save_npy(files["epochs"], epochs)
    _atomic_save_npy(files["receiver1_measurements"], receiver1)
    _atomic_save_npy(files["receiver2_measurements"], receiver2)
    manifest: dict[str, Any] = {
        "schema_version": "horizontal_literature.phase2.compact_cache.v1",
        "source_fingerprint": source_fingerprint,
        "pair_count": len(pairs),
        "original_index_order": list(range(len(pairs))),
        "memory_map_format": "NUMPY_NPY_ALLOW_PICKLE_FALSE",
        "raw_csv_access_by_workers": False,
        "files": {
            name: {"filename": path.name, "sha256": _sha256_file(path),
                   "size_bytes": path.stat().st_size}
            for name, path in files.items()
        },
    }
    if extra_manifest:
        manifest.update(_jsonable(dict(extra_manifest)))
    _atomic_write_json(cache / "CACHE_MANIFEST.json", manifest)
    return manifest


def validate_compact_cache(
    cache_root: Path,
    *,
    source_fingerprint: str,
    expected_pair_count: int | None = None,
) -> dict[str, Any]:
    cache = Path(cache_root)
    manifest_path = cache / "CACHE_MANIFEST.json"
    if not manifest_path.is_file():
        raise Phase2RunnerError("compact cache manifest is absent")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "horizontal_literature.phase2.compact_cache.v1":
        raise Phase2RunnerError("compact cache schema drift")
    if manifest.get("source_fingerprint") != source_fingerprint:
        raise Phase2RunnerError("compact cache fingerprint mismatch")
    pair_count = int(manifest.get("pair_count", -1))
    if expected_pair_count is not None and pair_count != expected_pair_count:
        raise Phase2RunnerError("compact cache pair count mismatch")
    if manifest.get("original_index_order") != list(range(pair_count)):
        raise Phase2RunnerError("compact cache original-index order mismatch")
    for entry in manifest.get("files", {}).values():
        path = cache / entry["filename"]
        if (
            not path.is_file() or path.stat().st_size != int(entry["size_bytes"])
            or _sha256_file(path) != entry["sha256"]
        ):
            raise Phase2RunnerError(f"compact cache file hash mismatch: {path.name}")
    return manifest


class CompactCacheReader:
    """Read-only reconstruction of one paired epoch from NumPy memory maps."""

    def __init__(self, cache_root: Path):
        cache = Path(cache_root)
        self.epochs = np.load(cache / "paired_epochs.npy", mmap_mode="r", allow_pickle=False)
        self.receiver1 = np.load(
            cache / "receiver1_measurements.npy", mmap_mode="r", allow_pickle=False,
        )
        self.receiver2 = np.load(
            cache / "receiver2_measurements.npy", mmap_mode="r", allow_pickle=False,
        )

    def __len__(self) -> int:
        return int(len(self.epochs))

    @staticmethod
    def _measurements(array: np.ndarray, offset: int, count: int) -> tuple[RawxMeasurement, ...]:
        rows = array[offset:offset + count]
        return tuple(
            RawxMeasurement(
                SignalIdentity(int(row["gnss_id"]), int(row["sv_id"]),
                               int(row["sig_id"]), int(row["freq_id"])),
                float(row["pr_mes_m"]), float(row["cp_mes_cycles"]),
                float(row["do_mes_hz"]), int(row["locktime_ms"]),
                int(row["cno_dbhz"]), int(row["pr_std_code"]),
                int(row["cp_std_code"]), int(row["do_std_code"]),
                int(row["tracking_status"]),
            )
            for row in rows
        )

    def pair(self, index: int) -> tuple[RawxEpoch, RawxEpoch]:
        if not 0 <= index < len(self):
            raise IndexError(index)
        row = self.epochs[index]
        week, tow = int(row["gps_week"]), float(row["gps_tow_seconds"])
        left = RawxEpoch(
            tow, week, int(row["r1_leap"]), int(row["r1_status"]), int(row["r1_version"]),
            self._measurements(self.receiver1, int(row["r1_offset"]), int(row["r1_count"])),
        )
        right = RawxEpoch(
            tow, week, int(row["r2_leap"]), int(row["r2_status"]), int(row["r2_version"]),
            self._measurements(self.receiver2, int(row["r2_offset"]), int(row["r2_count"])),
        )
        return left, right


def deterministic_shards(count: int, workers: int) -> tuple[tuple[int, int, int], ...]:
    if count < 0 or not 1 <= workers <= MAX_WORKERS:
        raise Phase2RunnerError("invalid deterministic shard request")
    shard_count = min(count, workers)
    if shard_count == 0:
        return ()
    quotient, remainder = divmod(count, shard_count)
    result = []
    start = 0
    for shard_id in range(shard_count):
        stop = start + quotient + (1 if shard_id < remainder else 0)
        result.append((shard_id, start, stop))
        start = stop
    if start != count:
        raise AssertionError("deterministic shard conservation failure")
    return tuple(result)


def _attempt_root(preflight: PreflightResult) -> Path:
    return preflight.paths.native_root.parent / (
        f".C00.attempt_{preflight.source_fingerprint[:20]}"
    )


def _open_attempt(preflight: PreflightResult, *, resume: bool) -> Path:
    final = preflight.paths.native_root
    if _path_lexists(final):
        raise Phase2RunnerError("final native root exists; overwrite is forbidden")
    attempt = _attempt_root(preflight)
    _reject_symlink_components(attempt)
    _require_contained(attempt, preflight.paths.native_root.parent, "Phase-2 attempt")
    _require_contained(attempt, preflight.paths.stage_root, "Phase-2 attempt")
    identity = {
        "schema_version": "horizontal_literature.phase2.attempt_identity.v1",
        "source_fingerprint": preflight.source_fingerprint,
        "code_commit": preflight.code_commit,
        "code_commit_role": "BASE_HEAD_ONLY_NOT_COMPLETE_RUNTIME_SOURCE_IDENTITY",
        "runtime_source_hashes": dict(sorted(preflight.runtime_source_hashes.items())),
        "git_source_state": dict(preflight.git_source_state),
        "method_id": METHOD_ID,
        "case_id": CASE_ID,
        "final_native_root": str(final),
    }
    if attempt.exists():
        if not resume:
            raise Phase2RunnerError("fingerprinted attempt exists; --resume is required")
        identity_path = attempt / "ATTEMPT_IDENTITY.json"
        if not identity_path.is_file():
            raise Phase2RunnerError("resume attempt lacks immutable identity")
        observed = json.loads(identity_path.read_text(encoding="utf-8"))
        if observed != identity:
            raise Phase2RunnerError("resume attempt identity mismatch")
        if (attempt / "ATTEMPT_TERMINAL.json").exists():
            raise Phase2RunnerError("terminalized failed attempt is immutable")
        return attempt
    if resume:
        raise Phase2RunnerError("--resume requested but fingerprinted attempt is absent")
    attempt.parent.mkdir(parents=True, exist_ok=True)
    attempt.mkdir()
    _atomic_write_json(attempt / "ATTEMPT_IDENTITY.json", identity)
    return attempt


def _run_convbin(executable: Path, source: Path, observation: Path, navigation: Path) -> list[str]:
    command = [
        str(executable), "-r", "ubx", "-o", str(observation),
        "-n", str(navigation), str(source),
    ]
    completed = subprocess.run(
        command, text=True, capture_output=True, check=False, timeout=600,
    )
    if completed.returncode != 0:
        raise Phase2RunnerError(
            f"convbin failed with {completed.returncode}: {completed.stderr.strip()}"
        )
    if not observation.is_file() or not navigation.is_file():
        raise Phase2RunnerError("convbin did not create the required OBS/NAV files")
    return command


def _prepare_or_resume_cache(
    preflight: PreflightResult,
    attempt: Path,
    *,
    resume: bool,
) -> tuple[Path, tuple[Path, Path], dict[str, Any], dict[str, str]]:
    source_root = attempt / "SOURCE_BACKEND"
    cache_root = attempt / "COMPACT_CACHE"
    _require_contained(source_root, attempt, "source backend cache")
    _require_contained(cache_root, attempt, "compact memory-map cache")
    manifest_path = cache_root / "CACHE_MANIFEST.json"
    if manifest_path.exists():
        if not resume:
            raise Phase2RunnerError("cache exists outside resume mode")
        manifest = validate_compact_cache(
            cache_root, source_fingerprint=preflight.source_fingerprint,
            expected_pair_count=EXPECTED_PAIR_COUNT,
        )
        derived = manifest.get("derived_provider_files", {})
        for entry in derived.values():
            path = attempt / entry["relative_path"]
            if not path.is_file() or _sha256_file(path) != entry["sha256"]:
                raise Phase2RunnerError("resume derived-provider hash mismatch")
        nav_paths = (
            source_root / "gnss1_reconstructed.nav",
            source_root / "gnss2_reconstructed.nav",
        )
        provider_hashes = {
            name: entry["sha256"] for name, entry in derived.items()
        }
        return cache_root, nav_paths, manifest, provider_hashes
    if resume and (cache_root.exists() or source_root.exists()):
        raise Phase2RunnerError("partial unmanifested cache cannot be resumed")
    source_root.mkdir(parents=True)
    ubx1 = source_root / "gnss1_reconstructed.ubx"
    ubx2 = source_root / "gnss2_reconstructed.ubx"
    observation1 = source_root / "gnss1_reconstructed.obs"
    observation2 = source_root / "gnss2_reconstructed.obs"
    navigation1 = source_root / "gnss1_reconstructed.nav"
    navigation2 = source_root / "gnss2_reconstructed.nav"
    reconstruction1 = reconstruct_ubx_stream(
        preflight.paths.gnss1_raw, ubx1,
        decode_nav_hpposecef_semantics=False,
    )
    reconstruction2 = reconstruct_ubx_stream(
        preflight.paths.gnss2_raw, ubx2,
        decode_nav_hpposecef_semantics=False,
    )
    if (
        reconstruction1.nav_hpposecef_semantic_decode_enabled
        or reconstruction2.nav_hpposecef_semantic_decode_enabled
        or reconstruction1.nav_hpposecef_epochs
        or reconstruction2.nav_hpposecef_epochs
    ):
        raise Phase2RunnerError("native cache semantically decoded NAV-HPPOSECEF")
    pairs, pairing_failures = pair_epochs(
        reconstruction1.rawx_epochs, reconstruction2.rawx_epochs,
        tolerance_seconds=0.0,
    )
    if pairing_failures or len(pairs) != EXPECTED_PAIR_COUNT:
        raise Phase2RunnerError(
            f"exact pairing gate failed: pairs={len(pairs)} failures={len(pairing_failures)}"
        )
    command1 = _run_convbin(preflight.paths.convbin, ubx1, observation1, navigation1)
    command2 = _run_convbin(preflight.paths.convbin, ubx2, observation2, navigation2)
    derived_paths = {
        "gnss1_reconstructed_ubx": ubx1,
        "gnss2_reconstructed_ubx": ubx2,
        "gnss1_reconstructed_obs": observation1,
        "gnss2_reconstructed_obs": observation2,
        "gnss1_reconstructed_nav": navigation1,
        "gnss2_reconstructed_nav": navigation2,
    }
    derived = {
        name: {
            "relative_path": str(path.relative_to(attempt)),
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for name, path in derived_paths.items()
    }
    manifest = write_compact_cache(
        cache_root, pairs, source_fingerprint=preflight.source_fingerprint,
        extra_manifest={
            "exact_pairing_tolerance_seconds": 0.0,
            "pairing_failure_count": 0,
            "raw_csv_parent_read_count": 2,
            "raw_csv_worker_read_count": 0,
            "trace_open_count_before_native_freeze": 0,
            "HPPOSECEF_semantic_decode_count_before_native_freeze": 0,
            "HPPOSECEF_solver_input": False,
            "reconstruction": {
                "gnss1": {
                    "message_counts": reconstruction1.message_counts,
                    "input_cell_count": reconstruction1.input_cell_count,
                    "discarded_byte_count": reconstruction1.discarded_byte_count,
                    "checksum_failure_count": reconstruction1.checksum_failure_count,
                },
                "gnss2": {
                    "message_counts": reconstruction2.message_counts,
                    "input_cell_count": reconstruction2.input_cell_count,
                    "discarded_byte_count": reconstruction2.discarded_byte_count,
                    "checksum_failure_count": reconstruction2.checksum_failure_count,
                },
            },
            "convbin_commands": [command1, command2],
            "derived_provider_files": derived,
        },
    )
    return (
        cache_root, (navigation1, navigation2), manifest,
        {name: entry["sha256"] for name, entry in derived.items()},
    )


def _wrap360(value: float) -> float:
    wrapped = value % 360.0
    return 0.0 if wrapped == 360.0 else wrapped


def _wrap180(value: float) -> float:
    return (value + 180.0) % 360.0 - 180.0


def _numeric_statistics(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return {"count": 0, "mean": None, "median": None, "rms": None,
                "p95": None, "min": None, "max": None}
    return {
        "count": int(array.size), "mean": float(np.mean(array)),
        "median": float(np.median(array)),
        "rms": float(np.sqrt(np.mean(array**2))),
        "p95": float(np.quantile(array, 0.95)),
        "min": float(np.min(array)), "max": float(np.max(array)),
    }


def _relationship(left: Sequence[float], right: Sequence[float]) -> dict[str, Any]:
    x, y = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    correlation = None
    if x.size >= 2 and float(np.std(x)) > 0.0 and float(np.std(y)) > 0.0:
        correlation = float(np.corrcoef(x, y)[0, 1])
    return {"paired_count": int(x.size), "pearson_correlation": correlation,
            "role": "DESCRIPTIVE_ONLY_NOT_SELECTION_OR_TUNING"}


def _circular_statistics_deg(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray(list(values), dtype=float)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return {"count": 0, "circular_mean_deg": None, "resultant_length": None,
                "wrapsafe_rms_about_mean_deg": None,
                "wrapsafe_max_abs_about_mean_deg": None}
    radians = np.radians(array)
    mean_sine, mean_cosine = float(np.mean(np.sin(radians))), float(np.mean(np.cos(radians)))
    mean = _wrap360(math.degrees(math.atan2(mean_sine, mean_cosine)))
    residual = np.asarray([_wrap180(float(value) - mean) for value in array])
    return {
        "count": int(array.size), "circular_mean_deg": mean,
        "resultant_length": math.hypot(mean_sine, mean_cosine),
        "wrapsafe_rms_about_mean_deg": float(np.sqrt(np.mean(residual**2))),
        "wrapsafe_max_abs_about_mean_deg": float(np.max(np.abs(residual))),
    }


def _continuity_metrics(indices: Sequence[int], tow_seconds: Sequence[float]) -> dict[str, Any]:
    if len(indices) != len(tow_seconds):
        raise Phase2RunnerError("continuity metric input lengths disagree")
    if not indices:
        return {"valid_count": 0, "segment_count": 0, "longest_segment_epochs": 0,
                "maximum_gap_seconds": None, "continuity_definition": (
                    "segments split when accepted original epoch indices are nonconsecutive"
                )}
    if list(indices) != sorted(indices) or len(set(indices)) != len(indices):
        raise Phase2RunnerError("continuity indices must be strictly increasing")
    lengths: list[int] = []
    length = 1
    for previous, current in zip(indices, indices[1:]):
        if current == previous + 1:
            length += 1
        else:
            lengths.append(length)
            length = 1
    lengths.append(length)
    gaps = np.diff(np.asarray(tow_seconds, dtype=float))
    return {
        "valid_count": len(indices), "segment_count": len(lengths),
        "longest_segment_epochs": max(lengths),
        "maximum_gap_seconds": float(np.max(gaps)) if gaps.size else 0.0,
        "continuity_definition": (
            "segments split when accepted original epoch indices are nonconsecutive"
        ),
    }


def _wrapsafe_error_metrics(
    errors_deg: Sequence[float],
    indices: Sequence[int],
    tow_seconds: Sequence[float],
    *,
    valid_denominator: int,
) -> dict[str, Any]:
    errors = np.asarray(errors_deg, dtype=float)
    if errors.size != len(indices) or errors.size != len(tow_seconds):
        raise Phase2RunnerError("wrap-safe metric input lengths disagree")
    if np.any(~np.isfinite(errors)):
        raise Phase2RunnerError("wrap-safe metric received nonfinite errors")
    continuity = _continuity_metrics(indices, tow_seconds)
    if errors.size == 0:
        return {
            "matched_count": 0, "valid_denominator": valid_denominator,
            "valid_coverage": 0.0 if valid_denominator else None,
            "wrapsafe_bias_deg": None, "circular_wrapsafe_bias_deg": None,
            "rmse_deg": None, "mae_deg": None,
            "median_absolute_deg": None, "p90_absolute_deg": None,
            "p95_absolute_deg": None, "p99_absolute_deg": None,
            "max_absolute_deg": None, **continuity,
        }
    absolute = np.abs(errors)
    circular = _circular_statistics_deg(errors)
    return {
        "matched_count": int(errors.size), "valid_denominator": valid_denominator,
        "valid_coverage": errors.size / valid_denominator if valid_denominator else None,
        "wrapsafe_bias_deg": float(np.mean(errors)),
        "circular_wrapsafe_bias_deg": _wrap180(float(circular["circular_mean_deg"])),
        "rmse_deg": float(np.sqrt(np.mean(errors**2))),
        "mae_deg": float(np.mean(absolute)),
        "median_absolute_deg": float(np.median(absolute)),
        "p90_absolute_deg": float(np.quantile(absolute, 0.90)),
        "p95_absolute_deg": float(np.quantile(absolute, 0.95)),
        "p99_absolute_deg": float(np.quantile(absolute, 0.99)),
        "max_absolute_deg": float(np.max(absolute)),
        **continuity,
    }


def _baseline_angles(vector_ned_m: Sequence[float]) -> tuple[float, float, float]:
    vector = np.asarray(vector_ned_m, dtype=float)
    if vector.shape != (3,) or np.any(~np.isfinite(vector)):
        raise Phase2RunnerError("baseline vector is not a finite NED three-vector")
    north, east, down = (float(item) for item in vector)
    horizontal = math.hypot(north, east)
    heading = _wrap360(math.degrees(math.atan2(east, north)))
    elevation = math.degrees(math.atan2(-down, horizontal))
    body_yaw = _wrap360(heading + 90.0)
    return heading, elevation, body_yaw


def _ecef_vector_to_ned(
    vector_ecef_m: Sequence[float], receiver_ecef_m: Sequence[float],
) -> np.ndarray:
    latitude, longitude, _height = ecef_to_geodetic(receiver_ecef_m)
    sin_lat, cos_lat = math.sin(latitude), math.cos(latitude)
    sin_lon, cos_lon = math.sin(longitude), math.cos(longitude)
    rotation = np.array([
        [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
        [-sin_lon, cos_lon, 0.0],
        [-cos_lat * cos_lon, -cos_lat * sin_lon, -sin_lat],
    ])
    vector = np.asarray(vector_ecef_m, dtype=float)
    if vector.shape != (3,) or np.any(~np.isfinite(vector)):
        raise Phase2RunnerError("ECEF baseline vector is invalid")
    return rotation @ vector


ORACLE_INDICES = frozenset(range(0, EXPECTED_PAIR_COUNT, 150))
ORACLE_GRID_COUNT = 4096


def _oracle_round_half_down(values: Any) -> np.ndarray:
    """Oracle-local Eq. (75) integer rule; independent of production rounding."""
    return np.ceil(np.asarray(values, dtype=float) - 0.5).astype(np.int64)


def _independent_wrapped_objectives(model: Any, directions: np.ndarray) -> np.ndarray:
    """Independent dense-oracle objective using its own wrap/Cholesky path."""
    directions = np.asarray(directions, dtype=float)
    prediction = model.baseline_length_m * directions @ model.design_cycles_per_m.T
    raw_phase = model.phase_cycles[None, :] - prediction
    phase_residual = raw_phase - np.ceil(raw_phase - 0.5)
    code_residual = model.code_cycles[None, :] - prediction
    residual = np.concatenate((phase_residual, code_residual), axis=1)
    cholesky = np.linalg.cholesky(model.covariance_phase_code_cycles2)
    whitened = np.linalg.solve(cholesky, residual.T).T
    return np.einsum("ij,ij->i", whitened, whitened)


def _fibonacci_sphere(count: int = ORACLE_GRID_COUNT) -> np.ndarray:
    indices = np.arange(count, dtype=float) + 0.5
    z = 1.0 - 2.0 * indices / count
    radius = np.sqrt(np.maximum(0.0, 1.0 - z * z))
    angle = math.pi * (3.0 - math.sqrt(5.0)) * indices
    directions = np.column_stack((radius * np.cos(angle), radius * np.sin(angle), z))
    return directions


def _oracle_refine(model: Any, seed: np.ndarray) -> tuple[np.ndarray, float, tuple[int, ...], int]:
    from .ext02_cwls import solve_unit_sphere_quadratic

    current = np.asarray(seed, dtype=float)
    design = model.baseline_length_m * np.vstack(
        (model.design_cycles_per_m, model.design_cycles_per_m)
    )
    precision = np.linalg.solve(
        model.covariance_phase_code_cycles2,
        np.eye(2 * model.observation_count, dtype=float),
    )
    quadratic = design.T @ precision @ design
    previous_key: tuple[int, ...] | None = None
    for iteration in range(1, 21):
        prediction = model.baseline_length_m * model.design_cycles_per_m @ current
        corrections = _oracle_round_half_down(prediction - model.phase_cycles)
        key = tuple(int(item) for item in corrections)
        observations = np.concatenate((model.phase_cycles + corrections, model.code_cycles))
        linear = design.T @ precision @ observations
        sphere = solve_unit_sphere_quadratic(quadratic, linear)
        updated = np.asarray(sphere.direction, dtype=float)
        if key == previous_key and float(np.linalg.norm(updated - current)) <= 1.0e-10:
            current = updated
            break
        current, previous_key = updated, key
    objective = float(_independent_wrapped_objectives(model, current[None, :])[0])
    prediction = model.baseline_length_m * model.design_cycles_per_m @ current
    final_corrections = tuple(
        int(item) for item in _oracle_round_half_down(prediction - model.phase_cycles)
    )
    return current, objective, final_corrections, iteration


def _objective_oracle(index: int, model: Any, formal_solution: Any) -> dict[str, Any]:
    base = {
        "epoch_index": index,
        "oracle_subset_selection": "INPUT_INDEX_ONLY",
        "formal_objective": float(formal_solution.objective),
        "grid_direction_count": ORACLE_GRID_COUNT,
        "objective_path": "INDEPENDENT_RESIDUAL_CHOLESKY",
        "algorithm1_candidates_used": False,
    }
    if index not in ORACLE_INDICES:
        return {
            **base, "oracle_status": "NOT_SELECTED_INPUT_ONLY", "oracle_objective": None,
            "oracle_minus_formal": None, "comparison_tolerance": None,
            "comparison_pass": "NOT_EVALUATED",
        }
    grid = _fibonacci_sphere()
    objectives = _independent_wrapped_objectives(model, grid)
    seed_indices = np.argsort(objectives, kind="stable")[:64]
    refined: dict[tuple[int, ...], tuple[np.ndarray, float, int]] = {}
    for seed_index in seed_indices:
        direction, objective, corrections, iterations = _oracle_refine(model, grid[seed_index])
        prior = refined.get(corrections)
        if prior is None or objective < prior[1]:
            refined[corrections] = (direction, objective, iterations)
    direction, objective, iterations = min(
        refined.values(), key=lambda item: (item[1], *[float(x) for x in item[0]]),
    )
    formal = float(formal_solution.objective)
    tolerance = max(1.0e-9, 1.0e-9 * max(1.0, abs(formal), abs(objective)))
    return {
        **base,
        "oracle_status": "EVALUATED_DENSE_FULL_SPHERE",
        "oracle_objective": objective,
        "oracle_minus_formal": objective - formal,
        "comparison_tolerance": tolerance,
        "comparison_pass": bool(formal <= objective + tolerance),
        "oracle_direction_ecef": direction.tolist(),
        "oracle_refined_integer_region_count": len(refined),
        "oracle_selected_iterations": iterations,
    }


def _failure_code(exc: BaseException) -> str:
    explicit = getattr(exc, "code", None)
    if isinstance(explicit, str) and explicit:
        return explicit
    if isinstance(exc, DoubleDifferenceStageError):
        return exc.code
    text = str(exc).lower()
    if "empty ambiguity interval" in text or "eq. (58)" in text:
        return "NO_VALID_INTEGER_INTERVAL"
    if "no finite direction candidates" in text or "algorithm 1" in text:
        return "NO_CIRCLE_PAIR_CANDIDATE"
    if "sphere" in text or "global certificate" in text:
        return "SPHERE_SOLVER_FAILURE"
    if "non-finite" in text or "finite" in text and "must" in text:
        return "NONFINITE_OBJECTIVE"
    if "spp" in text or "satellite state" in text or "broadcast state" in text:
        return "INSUFFICIENT_SATELLITE_STATES"
    return "NUMERICAL_FAILURE"


def _candidate_search_complete(solution: Any) -> bool:
    raw_diagnostics = getattr(solution, "diagnostics", None)
    diagnostics = () if raw_diagnostics is None else tuple(raw_diagnostics)
    candidate_count = int(getattr(solution, "candidate_count", -1))
    return (
        candidate_count > 0
        and len(diagnostics) == candidate_count
        and all(
            item.converged is True
            and item.failure_code is None
            and item.objective is not None
            and math.isfinite(float(item.objective))
            for item in diagnostics
        )
    )


def _optional_vector(value: Any) -> list[float] | None:
    if value is None:
        return None
    vector = np.asarray(value, dtype=float)
    return vector.tolist()


def _tuple_or_empty(value: Any) -> tuple[Any, ...]:
    return () if value is None else tuple(value)


def _rejected_candidate_evidence(
    index: int,
    left: RawxEpoch,
    exc: BaseException,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    diagnostics = _tuple_or_empty(getattr(exc, "candidate_diagnostics", None))
    pool = getattr(exc, "candidate_pool", None)
    if not diagnostics:
        return [], [], {
            "raw_candidate_count": 0, "unique_candidate_count": 0,
            "refined_candidate_count": 0,
        }
    pool_directions = _tuple_or_empty(getattr(pool, "directions", None))
    aggregate = {
        "phase_row_count": int(getattr(pool, "phase_row_count", 0)),
        "integer_option_count_per_row": list(
            _tuple_or_empty(getattr(pool, "integer_option_count_per_row", None))
        ),
        "circle_count": len(_tuple_or_empty(getattr(pool, "circles", None))),
        "circle_pair_count": int(getattr(pool, "pair_count", 0)),
        "intersecting_pair_count": int(getattr(pool, "intersecting_pair_count", 0)),
        "near_tangent_candidate_count": int(
            getattr(pool, "near_tangent_candidate_count", 0)
        ),
        "degenerate_pair_count": int(getattr(pool, "degenerate_pair_count", 0)),
        "raw_candidate_count": int(getattr(pool, "raw_candidate_count", len(diagnostics))),
        "unique_candidate_count": len(pool_directions) if pool_directions else len(diagnostics),
        "exact_objective_tie_count": None,
    }
    candidates: list[dict[str, Any]] = []
    refinements: list[dict[str, Any]] = []
    for item in diagnostics:
        candidates.append({
            "epoch_index": index, "gps_week": left.gps_week,
            "gps_tow_seconds": left.gps_tow_seconds,
            "coarse_index": item.coarse_index, "selected": False,
            "coarse_direction": _optional_vector(item.coarse_direction),
            "coarse_objective": item.coarse_objective,
            "refined_direction": _optional_vector(item.refined_direction),
            "objective": item.objective, "converged": item.converged,
            "integer_ambiguities": list(_tuple_or_empty(item.integer_ambiguities)),
            "wrapped_phase_rms_cycles": item.wrapped_phase_rms_cycles,
            "wrapped_phase_max_abs_cycles": item.wrapped_phase_max_abs_cycles,
            "refined_unwrapped_objective": item.refined_unwrapped_objective,
            "iteration_count": item.iteration_count,
            "integer_vector_stable": item.integer_vector_stable,
            "unit_norm_error": item.unit_norm_error,
            "convergence_state": item.convergence_state,
            "failure_code": item.failure_code,
            **aggregate,
            "K_policy": "ALL_UNIQUE_CANDIDATES",
        })
        for iteration in _tuple_or_empty(item.iterations):
            sphere = iteration.sphere_solution
            refinements.append({
                "epoch_index": index, "gps_week": left.gps_week,
                "gps_tow_seconds": left.gps_tow_seconds,
                "coarse_index": item.coarse_index,
                "iteration": iteration.iteration,
                "integer_corrections": list(iteration.integer_corrections),
                "direction_change": iteration.direction_change,
                "integer_stable": iteration.integer_stable,
                "sphere_objective": sphere.objective,
                "lagrange_multiplier": sphere.lagrange_multiplier,
                "unit_norm_residual": sphere.unit_norm_residual,
                "stationarity_residual": sphere.stationarity_residual,
                "duality_gap": sphere.duality_gap,
                "global_certified": sphere.global_certified,
            })
    return candidates, refinements, {
        "raw_candidate_count": aggregate["raw_candidate_count"],
        "unique_candidate_count": aggregate["unique_candidate_count"],
        "refined_candidate_count": sum(
            item.converged is True and item.failure_code is None
            and item.objective is not None and math.isfinite(float(item.objective))
            for item in diagnostics
        ),
    }


def _invalid_record(
    index: int,
    left: RawxEpoch,
    failure_code: str,
    detail: str,
    runtime_seconds: float,
    accounting: Any | None = None,
    candidate_rows: Sequence[Mapping[str, Any]] = (),
    refinement_rows: Sequence[Mapping[str, Any]] = (),
    candidate_counts: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    counts = accounting.as_counts() if accounting is not None else {}
    rejected_counts = dict(candidate_counts or {})
    heading = {
        "epoch_index": index, "gps_week": left.gps_week,
        "gps_tow_seconds": left.gps_tow_seconds, "method_id": METHOD_ID,
        "case_id": CASE_ID, "status": "FAILURE", "solution_type": "invalid",
        "solution_state": "invalid", "method_native_accepted": False,
        "ambiguity_correctness_known": False,
        "common_backbone_yaw_std_deg": COMMON_BACKBONE_YAW_STD_DEG,
        "failure_code": failure_code, "baseline_ned_m": None,
        "baseline_length_m": BASELINE_LENGTH_M, "baseline_heading_deg": None,
        "baseline_elevation_deg": None, "body_yaw_deg": None,
        "pivot_identity": None, "pivot_switched": False,
        "ambiguity_candidate": None,
        "recovered_integer_vector_present": False,
        "recovered_integer_vector": None,
        "ambiguity_satellite_identities": None,
        "constrained_objective": None,
        "second_objective": None, "final_second_objective": None,
        "wrapped_phase_rms_cycles": None, "wrapped_phase_p95_cycles": None,
        "wrapped_phase_max_abs_cycles": None,
        "pseudorange_residual_rms_m": None, "refinement_iterations": None,
        "candidate_threshold_delta": 0.05, "K_policy": "ALL_UNIQUE_CANDIDATES",
        "raw_candidate_count": int(rejected_counts.get("raw_candidate_count", 0)),
        "unique_candidate_count": int(rejected_counts.get("unique_candidate_count", 0)),
        "refined_candidate_count": int(rejected_counts.get("refined_candidate_count", 0)),
        "ratio": None, "ratio_valid": False,
        "search_complete": False, "search_nodes": 0,
        "constraint_error_m": None, "residual_norm": None,
        "runtime_seconds": runtime_seconds, "pseudorange_valid": False,
        "carrier_valid": False, "lock_reset": False,
        "half_cycle_valid": False, "half_cycle_subtracted": False,
        "receiver_clock_reset": bool(left.receiver_status & 0x02),
        "cycle_slip": False, "arc_reset": False,
    }
    return {
        "epoch_index": index,
        "heading": heading,
        "failure": {
            "epoch_index": index, "gps_week": left.gps_week,
            "gps_tow_seconds": left.gps_tow_seconds, "method_id": METHOD_ID,
            "case_id": CASE_ID, "failure_code": failure_code,
            "failure_detail": detail,
        },
        "runtime": {
            "epoch_index": index, "gps_week": left.gps_week,
            "gps_tow_seconds": left.gps_tow_seconds,
            "runtime_seconds": runtime_seconds, "worker_pid": os.getpid(),
            "worker_max_rss_bytes": _max_rss_bytes(),
        },
        "dd": {
            "epoch_index": index, "gps_week": left.gps_week,
            "gps_tow_seconds": left.gps_tow_seconds, "failure_code": failure_code,
            **counts,
        },
        "candidates": [dict(row) for row in candidate_rows],
        "refinements": [dict(row) for row in refinement_rows],
        "objective_oracle": {
            "epoch_index": index, "oracle_status": "NATIVE_SOLUTION_UNAVAILABLE",
            "formal_objective": None, "oracle_objective": None,
            "comparison_pass": "NOT_EVALUATED",
        },
    }


def _solve_native_epoch(
    index: int,
    left: RawxEpoch,
    right: RawxEpoch,
    provider: RtklibBroadcastProvider,
) -> dict[str, Any]:
    from .ext02_cwls import (
        CWLSError,
        adapt_metric_double_differences,
        solve_single_baseline_cwls,
        wrapped_objective,
    )

    started = time.perf_counter()
    model = None
    try:
        spp = gps_l1_code_spp(left, provider)
        model = build_gps_l1_double_difference_model(
            left, right, provider, spp.position_ecef_m,
            minimum_elevation_rad=ELEVATION_MASK_RAD,
            previous_pivot=None,
        )
        count = len(model.satellites)
        if count < 2:
            raise DoubleDifferenceStageError(
                "INSUFFICIENT_DD_DIMENSION", "C-WLS needs at least two DD rows",
                model.accounting,
            )
        gps_l1_wavelength = wavelength_m(model.satellites[0])
        cwls_model = adapt_metric_double_differences(
            code_m=model.observation_m[:count],
            phase_m=model.observation_m[count:],
            design_m_per_m=model.baseline_design[:count],
            covariance_code_phase_m2=model.covariance_m2,
            wavelength_m=gps_l1_wavelength,
            baseline_length_m=BASELINE_LENGTH_M,
        )
        solution = solve_single_baseline_cwls(cwls_model)
        search_complete = _candidate_search_complete(solution)
        if not search_complete:
            raise Phase2RunnerError(
                "C-WLS solver returned an incomplete all-unique-candidate search"
            )
        vector_ecef = np.asarray(solution.baseline_vector_m, dtype=float)
        norm = float(np.linalg.norm(vector_ecef))
        if np.any(~np.isfinite(vector_ecef)) or abs(norm - BASELINE_LENGTH_M) > 1.0e-9:
            raise CWLSError("baseline hard constraint failed")
        if not math.isfinite(float(solution.objective)):
            raise CWLSError("NONFINITE_OBJECTIVE")
        oracle_objective = float(wrapped_objective(cwls_model, solution.direction))
        if abs(oracle_objective - float(solution.objective)) > max(
            1.0e-10, 1.0e-10 * max(1.0, abs(oracle_objective), abs(float(solution.objective)))
        ):
            raise CWLSError("production wrapped-objective identity mismatch")
        vector_ned = _ecef_vector_to_ned(vector_ecef, spp.position_ecef_m)
        heading_deg, elevation_deg, body_yaw_deg = _baseline_angles(vector_ned)
        elapsed = time.perf_counter() - started
        selected = solution.diagnostics[solution.selected_candidate_index]
        converged_objectives = sorted(
            float(item.objective) for item in solution.diagnostics
            if item.converged and item.objective is not None
        )
        second_objective = converged_objectives[1] if len(converged_objectives) > 1 else None
        wrapped_absolute = np.abs(np.asarray(selected.wrapped_phase_residual_cycles, dtype=float))
        prediction_cycles = BASELINE_LENGTH_M * (
            cwls_model.design_cycles_per_m @ np.asarray(solution.direction, dtype=float)
        )
        pseudorange_residual_m = (
            cwls_model.code_cycles - prediction_cycles
        ) * gps_l1_wavelength
        condition = dd_matrix_condition_diagnostics(model)
        heading = {
            "epoch_index": index, "gps_week": left.gps_week,
            "gps_tow_seconds": left.gps_tow_seconds, "method_id": METHOD_ID,
            "case_id": CASE_ID, "status": "SUCCESS",
            "solution_type": "accepted_wrapped_solution",
            "solution_state": "accepted_wrapped_solution",
            "method_native_accepted": True, "ambiguity_correctness_known": False,
            "common_backbone_yaw_std_deg": COMMON_BACKBONE_YAW_STD_DEG,
            "failure_code": None, "baseline_ned_m": vector_ned.tolist(),
            "baseline_length_m": BASELINE_LENGTH_M,
            "baseline_heading_deg": heading_deg,
            "baseline_elevation_deg": elevation_deg,
            "body_yaw_deg": body_yaw_deg,
            "pivot_identity": model.pivot_identity, "pivot_switched": False,
            "ambiguity_candidate": list(solution.integer_ambiguities),
            "recovered_integer_vector_present": True,
            "recovered_integer_vector": list(solution.integer_ambiguities),
            "ambiguity_satellite_identities": list(model.ambiguity_signal_identities),
            "constrained_objective": float(solution.objective),
            "second_objective": second_objective,
            "final_second_objective": second_objective,
            "wrapped_phase_rms_cycles": selected.wrapped_phase_rms_cycles,
            "wrapped_phase_p95_cycles": float(np.quantile(wrapped_absolute, 0.95)),
            "wrapped_phase_max_abs_cycles": selected.wrapped_phase_max_abs_cycles,
            "pseudorange_residual_rms_m": float(np.sqrt(np.mean(pseudorange_residual_m**2))),
            "refinement_iterations": selected.iteration_count,
            "candidate_threshold_delta": 0.05,
            "K_policy": "ALL_UNIQUE_CANDIDATES",
            "raw_candidate_count": solution.raw_candidate_count,
            "unique_candidate_count": solution.candidate_count,
            "refined_candidate_count": sum(item.converged for item in solution.diagnostics),
            "ratio": None, "ratio_valid": False,
            "search_complete": search_complete, "search_nodes": solution.candidate_count,
            "constraint_error_m": abs(norm - BASELINE_LENGTH_M),
            "residual_norm": selected.wrapped_phase_rms_cycles,
            "runtime_seconds": elapsed,
            "pseudorange_valid": True, "carrier_valid": True,
            "lock_reset": False, "half_cycle_valid": True,
            "half_cycle_subtracted": False,
            "receiver_clock_reset": bool(
                left.receiver_status & 0x02 or right.receiver_status & 0x02
            ),
            "cycle_slip": False, "arc_reset": False,
        }
        dd = {
            "epoch_index": index, "gps_week": left.gps_week,
            "gps_tow_seconds": left.gps_tow_seconds, "failure_code": None,
            **model.accounting.as_counts(),
            "receiver_ecef_m_raw_code_spp": spp.position_ecef_m.tolist(),
            "baseline_ecef_m": vector_ecef.tolist(),
            "baseline_direction_ecef": np.asarray(solution.direction, dtype=float).tolist(),
            "receiver_spp_residual_rms_m": spp.residual_rms_m,
            "pivot_identity": model.pivot_identity,
            "ambiguity_signal_identities": list(model.ambiguity_signal_identities),
            "dd_dimension": count,
            "backend_order": "code_m_then_phase_m",
            "code_dd_m": model.observation_m[:count].tolist(),
            "phase_dd_m": model.observation_m[count:].tolist(),
            "design_m_per_m": model.baseline_design[:count].tolist(),
            "covariance_code_phase_m2": model.covariance_m2.tolist(),
            "gps_l1_wavelength_m": gps_l1_wavelength,
            "covariance_condition": condition.covariance_condition,
            "whitened_design_rank": condition.whitened_design_rank,
            "whitened_design_condition": condition.whitened_design_condition,
        }
        candidates = []
        refinements = []
        for item in solution.diagnostics:
            candidates.append({
                "epoch_index": index, "gps_week": left.gps_week,
                "gps_tow_seconds": left.gps_tow_seconds,
                "coarse_index": item.coarse_index,
                "selected": item.coarse_index == solution.selected_candidate_index,
                "coarse_direction": item.coarse_direction.tolist(),
                "coarse_objective": item.coarse_objective,
                "refined_direction": item.refined_direction.tolist(),
                "objective": item.objective, "converged": item.converged,
                "integer_ambiguities": list(item.integer_ambiguities),
                "wrapped_phase_rms_cycles": item.wrapped_phase_rms_cycles,
                "wrapped_phase_max_abs_cycles": item.wrapped_phase_max_abs_cycles,
                "refined_unwrapped_objective": item.refined_unwrapped_objective,
                "iteration_count": item.iteration_count,
                "integer_vector_stable": item.integer_vector_stable,
                "unit_norm_error": item.unit_norm_error,
                "convergence_state": item.convergence_state,
                "failure_code": item.failure_code,
                "circle_count": solution.circle_count,
                "circle_pair_count": solution.circle_pair_count,
                "phase_row_count": solution.phase_row_count,
                "integer_option_count_per_row": list(solution.integer_option_count_per_row),
                "intersecting_pair_count": solution.intersecting_pair_count,
                "near_tangent_candidate_count": solution.near_tangent_candidate_count,
                "degenerate_pair_count": solution.degenerate_pair_count,
                "raw_candidate_count": solution.raw_candidate_count,
                "unique_candidate_count": solution.candidate_count,
                "exact_objective_tie_count": solution.exact_objective_tie_count,
                "K_policy": "ALL_UNIQUE_CANDIDATES",
            })
            for iteration in item.iterations:
                refinements.append({
                    "epoch_index": index, "gps_week": left.gps_week,
                    "gps_tow_seconds": left.gps_tow_seconds,
                    "coarse_index": item.coarse_index,
                    "iteration": iteration.iteration,
                    "integer_corrections": list(iteration.integer_corrections),
                    "direction_change": iteration.direction_change,
                    "integer_stable": iteration.integer_stable,
                    "sphere_objective": iteration.sphere_solution.objective,
                    "lagrange_multiplier": iteration.sphere_solution.lagrange_multiplier,
                    "unit_norm_residual": iteration.sphere_solution.unit_norm_residual,
                    "stationarity_residual": iteration.sphere_solution.stationarity_residual,
                    "duality_gap": iteration.sphere_solution.duality_gap,
                    "global_certified": iteration.sphere_solution.global_certified,
                })
        return {
            "epoch_index": index, "heading": heading, "failure": None,
            "runtime": {
                "epoch_index": index, "gps_week": left.gps_week,
                "gps_tow_seconds": left.gps_tow_seconds,
                "runtime_seconds": elapsed, "worker_pid": os.getpid(),
                "worker_max_rss_bytes": _max_rss_bytes(),
            },
            "dd": dd, "candidates": candidates, "refinements": refinements,
            "objective_oracle": _objective_oracle(index, cwls_model, solution),
        }
    except (RawBackendError, CWLSError, np.linalg.LinAlgError, ValueError) as exc:
        elapsed = time.perf_counter() - started
        accounting = getattr(exc, "accounting", None)
        if accounting is None and model is not None:
            accounting = model.accounting
        code = "ALL_REFINEMENTS_FAILED" if "ALL_REFINEMENTS_FAILED" in str(exc) else _failure_code(exc)
        candidates, refinements, candidate_counts = _rejected_candidate_evidence(
            index, left, exc,
        )
        return _invalid_record(
            index, left, code, str(exc), elapsed, accounting,
            candidate_rows=candidates, refinement_rows=refinements,
            candidate_counts=candidate_counts,
        )


def _scientific_part(value: Any) -> Any:
    """Remove only process/runtime metadata for semantic determinism checks."""
    excluded = {"runtime_seconds", "worker_pid", "worker_max_rss_bytes", "shard_id"}
    if isinstance(value, Mapping):
        return {
            str(key): _scientific_part(item)
            for key, item in value.items()
            if key not in excluded
        }
    if isinstance(value, list):
        return [_scientific_part(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_scientific_part(item) for item in value)
    return _jsonable(value)


def _part_paths(part_root: Path, shard_id: int, start: int, stop: int) -> tuple[Path, Path]:
    stem = f"part_{shard_id:04d}_{start:04d}_{stop:04d}"
    return part_root / f"{stem}.jsonl", part_root / f"{stem}.manifest.json"


def _write_part_atomic(
    data_path: Path,
    manifest_path: Path,
    records: Sequence[Mapping[str, Any]],
    *,
    source_fingerprint: str,
    shard_id: int,
    start: int,
    stop: int,
) -> dict[str, Any]:
    if _path_lexists(data_path) or _path_lexists(manifest_path):
        raise Phase2RunnerError("part target collision")
    payload = b"".join(
        (_canonical_json(_jsonable(record)) + "\n").encode("utf-8")
        for record in records
    )
    _atomic_write_bytes(data_path, payload)
    manifest = {
        "schema_version": "horizontal_literature.phase2.part.v1",
        "source_fingerprint": source_fingerprint,
        "shard_id": shard_id,
        "start_index": start,
        "stop_index_exclusive": stop,
        "record_count": len(records),
        "original_indices": [int(record["epoch_index"]) for record in records],
        "data_file": data_path.name,
        "data_sha256": _sha256_file(data_path),
        "data_size_bytes": data_path.stat().st_size,
        "atomic_part_complete": True,
    }
    _atomic_write_json(manifest_path, manifest)
    return manifest


def validate_part(
    data_path: Path,
    manifest_path: Path,
    *,
    source_fingerprint: str,
    shard_id: int,
    start: int,
    stop: int,
) -> list[dict[str, Any]]:
    if not data_path.is_file() or not manifest_path.is_file():
        raise Phase2RunnerError("resume part is incomplete")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_indices = list(range(start, stop))
    exact = {
        "schema_version": "horizontal_literature.phase2.part.v1",
        "source_fingerprint": source_fingerprint,
        "shard_id": shard_id,
        "start_index": start,
        "stop_index_exclusive": stop,
        "record_count": stop - start,
        "original_indices": expected_indices,
        "data_file": data_path.name,
        "atomic_part_complete": True,
    }
    if any(manifest.get(name) != value for name, value in exact.items()):
        raise Phase2RunnerError(f"resume part manifest mismatch: {manifest_path.name}")
    if (
        data_path.stat().st_size != int(manifest.get("data_size_bytes", -1))
        or _sha256_file(data_path) != manifest.get("data_sha256")
    ):
        raise Phase2RunnerError(f"resume part payload hash mismatch: {data_path.name}")
    records: list[dict[str, Any]] = []
    with data_path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise Phase2RunnerError(
                    f"invalid part JSON at {data_path.name}:{line_number}"
                ) from exc
            if not isinstance(value, dict):
                raise Phase2RunnerError("part record is not an object")
            records.append(value)
    if [int(record.get("epoch_index", -1)) for record in records] != expected_indices:
        raise Phase2RunnerError(f"resume part original-index order mismatch: {data_path.name}")
    return records


def _process_shard(
    cache_root_text: str,
    bridge_path_text: str,
    navigation_path_texts: Sequence[str],
    part_root_text: str,
    source_fingerprint: str,
    shard_id: int,
    start: int,
    stop: int,
) -> dict[str, Any]:
    cache = CompactCacheReader(Path(cache_root_text))
    records: list[dict[str, Any]] = []
    with RtklibBroadcastProvider(
        Path(bridge_path_text), tuple(Path(item) for item in navigation_path_texts),
    ) as provider:
        for index in range(start, stop):
            left, right = cache.pair(index)
            record = _solve_native_epoch(index, left, right, provider)
            record["runtime"]["shard_id"] = shard_id
            records.append(record)
    part_root = Path(part_root_text)
    data_path, manifest_path = _part_paths(part_root, shard_id, start, stop)
    return _write_part_atomic(
        data_path, manifest_path, records,
        source_fingerprint=source_fingerprint, shard_id=shard_id,
        start=start, stop=stop,
    )


def _probe_epoch(
    cache_root_text: str,
    bridge_path_text: str,
    navigation_path_texts: Sequence[str],
    index: int,
) -> dict[str, Any]:
    cache = CompactCacheReader(Path(cache_root_text))
    with RtklibBroadcastProvider(
        Path(bridge_path_text), tuple(Path(item) for item in navigation_path_texts),
    ) as provider:
        left, right = cache.pair(index)
        return _solve_native_epoch(index, left, right, provider)


def _probe_epoch_with_resources(
    cache_root_text: str,
    bridge_path_text: str,
    navigation_path_texts: Sequence[str],
    index: int,
) -> dict[str, Any]:
    record = _probe_epoch(cache_root_text, bridge_path_text, navigation_path_texts, index)
    return {"index": index, "pid": os.getpid(), "max_rss_bytes": _max_rss_bytes(),
            "record": record}


def _proc_key_values(path: Path) -> dict[str, int]:
    values: dict[str, int] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.replace(":", "").split()
        if len(fields) >= 2:
            try:
                value = int(fields[1])
            except ValueError:
                continue
            if len(fields) >= 3 and fields[2].lower() == "kb":
                value *= 1024
            values[fields[0]] = value
    return values


def _thermal_snapshot() -> dict[str, Any]:
    rows = []
    for path in sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp")):
        try:
            raw = float(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            continue
        rows.append({"zone": path.parent.name, "temperature_c": raw / 1000.0})
    return {"status": "AVAILABLE", "zones": rows} if rows else {
        "status": "UNAVAILABLE", "zones": [],
    }


def _disk_snapshot(path: Path) -> dict[str, Any]:
    stat = os.statvfs(path)
    return {
        "path": str(path), "total_bytes": stat.f_blocks * stat.f_frsize,
        "available_bytes": stat.f_bavail * stat.f_frsize,
        "free_bytes": stat.f_bfree * stat.f_frsize,
    }


def _system_resource_snapshot(storage_root: Path) -> dict[str, Any]:
    memory = _proc_key_values(Path("/proc/meminfo"))
    vmstat = _proc_key_values(Path("/proc/vmstat"))
    load = os.getloadavg() if hasattr(os, "getloadavg") else (math.nan,) * 3
    swap_total = int(memory.get("SwapTotal", 0))
    swap_free = int(memory.get("SwapFree", 0))
    return {
        "ram_total_bytes": int(memory.get("MemTotal", 0)),
        "ram_available_bytes": int(memory.get("MemAvailable", 0)),
        "swap_total_bytes": swap_total,
        "swap_used_bytes": max(0, swap_total - swap_free),
        "swap_free_bytes": swap_free,
        "swap_in_pages": int(vmstat.get("pswpin", 0)),
        "swap_out_pages": int(vmstat.get("pswpout", 0)),
        "cpu_count": os.cpu_count(),
        "load_average_1m_5m_15m": [float(item) for item in load],
        "thermal": _thermal_snapshot(),
        "configured_clean_storage": _disk_snapshot(storage_root),
    }


def _measure_cache_read(cache_root: Path) -> dict[str, Any]:
    paths = [
        cache_root / "paired_epochs.npy", cache_root / "receiver1_measurements.npy",
        cache_root / "receiver2_measurements.npy",
    ]
    started = time.perf_counter()
    digest = hashlib.sha256()
    byte_count = 0
    for path in paths:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                byte_count += len(chunk)
                digest.update(chunk)
    elapsed = time.perf_counter() - started
    return {
        "file_count": len(paths), "bytes_read": byte_count,
        "elapsed_seconds": elapsed,
        "throughput_bytes_per_second": byte_count / max(elapsed, 1.0e-12),
        "combined_read_sha256": digest.hexdigest(),
        "worker_raw_csv_read_count": 0,
        "memory_map_mode": "read_only",
    }


def _temperature_stability(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
) -> dict[str, Any]:
    before_thermal = before.get("thermal", {})
    after_thermal = after.get("thermal", {})
    before_zones = {
        str(row["zone"]): float(row["temperature_c"])
        for row in before_thermal.get("zones", [])
        if "zone" in row and "temperature_c" in row
    }
    after_zones = {
        str(row["zone"]): float(row["temperature_c"])
        for row in after_thermal.get("zones", [])
        if "zone" in row and "temperature_c" in row
    }
    common = sorted(set(before_zones) & set(after_zones))
    deltas = {zone: after_zones[zone] - before_zones[zone] for zone in common}
    available = (
        before_thermal.get("status") == "AVAILABLE"
        and after_thermal.get("status") == "AVAILABLE"
        and bool(common)
        and set(before_zones) == set(after_zones)
        and all(math.isfinite(value) for value in (*before_zones.values(), *after_zones.values()))
    )
    maximum_delta = max((abs(value) for value in deltas.values()), default=None)
    stable = bool(
        available
        and maximum_delta is not None
        and maximum_delta <= MAX20_TEMPERATURE_STABILITY_C
    )
    return {
        "available": available,
        "stable": stable,
        "maximum_absolute_delta_c": maximum_delta,
        "stability_limit_c": MAX20_TEMPERATURE_STABILITY_C,
        "zone_delta_c": deltas,
    }


def _resource_admission_evidence(
    *,
    workers: int,
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    cache_read: Mapping[str, Any],
    peak_per_worker_rss_bytes: int,
    worker_failure_count: int,
    actual_process_count: int,
) -> dict[str, Any]:
    available_ram = min(
        int(before.get("ram_available_bytes", 0)),
        int(after.get("ram_available_bytes", 0)),
    )
    projected_rss = int(peak_per_worker_rss_bytes) * workers
    rss_limit = int(math.floor(RESOURCE_RSS_AVAILABLE_FRACTION_LIMIT * available_ram))
    disk_before = before.get("configured_clean_storage", {})
    disk_after = after.get("configured_clean_storage", {})
    disk_available = min(
        int(disk_before.get("available_bytes", 0)),
        int(disk_after.get("available_bytes", 0)),
    )
    projected_output = (
        EXPECTED_PAIR_COUNT * RESOURCE_PROJECTED_BYTES_PER_EPOCH
        + RESOURCE_PROJECTED_FIXED_BYTES
    )
    required_disk = projected_output + RESOURCE_DISK_SAFETY_RESERVE_BYTES
    swap_delta = {
        "in": int(after.get("swap_in_pages", 0)) - int(before.get("swap_in_pages", 0)),
        "out": int(after.get("swap_out_pages", 0)) - int(before.get("swap_out_pages", 0)),
    }
    temperature = _temperature_stability(before, after)
    checks = {
        "zero_worker_failures": {
            "passed": worker_failure_count == 0, "observed": worker_failure_count,
            "required": 0,
        },
        "actual_process_count_matches_requested": {
            "passed": actual_process_count == workers, "observed": actual_process_count,
            "required": workers,
        },
        "projected_rss_below_70_percent_available_ram": {
            "passed": available_ram > 0 and projected_rss < rss_limit,
            "projected_rss_bytes": projected_rss,
            "available_ram_bytes_conservative": available_ram,
            "exclusive_limit_bytes": rss_limit,
            "limit_fraction": RESOURCE_RSS_AVAILABLE_FRACTION_LIMIT,
        },
        "positive_cache_read_io": {
            "passed": (
                int(cache_read.get("bytes_read", 0)) > 0
                and float(cache_read.get("elapsed_seconds", 0.0)) > 0.0
                and float(cache_read.get("throughput_bytes_per_second", 0.0)) > 0.0
            ),
            "bytes_read": int(cache_read.get("bytes_read", 0)),
            "elapsed_seconds": float(cache_read.get("elapsed_seconds", 0.0)),
            "throughput_bytes_per_second": float(
                cache_read.get("throughput_bytes_per_second", 0.0)
            ),
        },
        "adequate_disk_for_deterministic_output_projection": {
            "passed": disk_available >= required_disk,
            "available_bytes_conservative": disk_available,
            "required_available_bytes": required_disk,
        },
        "maximum20_zero_swap_activity": {
            "required_for_selected_workers": workers == MAX_WORKERS,
            "passed": workers != MAX_WORKERS or (swap_delta["in"] == 0 and swap_delta["out"] == 0),
            "swap_activity_delta_pages": swap_delta,
        },
        "maximum20_temperature_available_and_stable": {
            "required_for_selected_workers": workers == MAX_WORKERS,
            "passed": workers != MAX_WORKERS or temperature["stable"],
            "temperature_evidence": temperature,
        },
    }
    rejection_reasons = [name for name, check in checks.items() if not check["passed"]]
    return {
        "schema": "horizontal_literature.phase2.resource_admission.v1",
        "selected_workers": workers,
        "admitted": not rejection_reasons,
        "rejection_reasons": rejection_reasons,
        "checks": checks,
        "deterministic_output_size_projection": {
            "paired_epoch_count": EXPECTED_PAIR_COUNT,
            "bytes_per_epoch": RESOURCE_PROJECTED_BYTES_PER_EPOCH,
            "fixed_bytes": RESOURCE_PROJECTED_FIXED_BYTES,
            "projected_output_bytes": projected_output,
            "disk_safety_reserve_bytes": RESOURCE_DISK_SAFETY_RESERVE_BYTES,
            "required_available_bytes": required_disk,
            "formula": "1509*bytes_per_epoch+fixed_bytes+disk_safety_reserve_bytes",
        },
        "maximum20_extra_gate_applied": workers == MAX_WORKERS,
    }


def resource_determinism_probe(
    cache_root: Path,
    bridge_path: Path,
    navigation_paths: Sequence[Path],
    *,
    workers: int,
    storage_root: Path | None = None,
) -> dict[str, Any]:
    reader = CompactCacheReader(cache_root)
    if len(reader) == 0:
        raise Phase2RunnerError("determinism probe cannot use an empty cache")
    sample_count = max(16, workers)
    sample_indices = [
        int(item) for item in np.linspace(0, len(reader) - 1, num=sample_count, dtype=int)
    ]
    if len(set(sample_indices)) != sample_count:
        raise Phase2RunnerError("determinism probe input-only epoch selection is not unique")
    storage = Path(storage_root) if storage_root is not None else cache_root
    before = _system_resource_snapshot(storage)
    cache_read = _measure_cache_read(cache_root)
    sequential: dict[int, dict[str, Any]] = {}
    with RtklibBroadcastProvider(bridge_path, navigation_paths) as provider:
        for index in sample_indices:
            left, right = reader.pair(index)
            sequential[index] = _solve_native_epoch(index, left, right, provider)
    parallel: dict[int, dict[str, Any]] = {}
    worker_pids: set[int] = set()
    worker_rss: dict[int, int] = {}
    worker_failures: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(
                _probe_epoch_with_resources, str(cache_root), str(bridge_path),
                [str(path) for path in navigation_paths], index,
            ): index
            for index in sample_indices
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                payload = future.result()
            except BaseException as exc:  # preserve the exact worker failure count
                worker_failures.append({
                    "epoch_index": index, "error_type": type(exc).__name__,
                    "error": str(exc),
                })
                continue
            pid = int(payload["pid"])
            worker_pids.add(pid)
            worker_rss[pid] = max(worker_rss.get(pid, 0), int(payload["max_rss_bytes"]))
            parallel[index] = payload["record"]
    after = _system_resource_snapshot(storage)
    row_order_complete = list(sorted(parallel)) == sample_indices
    comparisons = {
        str(index): (
            index in parallel
            and _scientific_part(sequential[index]) == _scientific_part(parallel[index])
        )
        for index in sample_indices
    }
    digest = _fingerprint({
        str(index): _scientific_part(sequential[index]) for index in sample_indices
    })
    per_worker_peak = max(worker_rss.values(), default=0)
    projected_rss = per_worker_peak * workers
    admission = _resource_admission_evidence(
        workers=workers, before=before, after=after, cache_read=cache_read,
        peak_per_worker_rss_bytes=per_worker_peak,
        worker_failure_count=len(worker_failures), actual_process_count=len(worker_pids),
    )
    determinism_rejections = []
    if not row_order_complete:
        determinism_rejections.append("PARALLEL_ROW_ORDER_OR_CONSERVATION")
    if not all(comparisons.values()):
        determinism_rejections.append("SCIENTIFIC_1_VS_REQUESTED_MISMATCH")
    rejection_reasons = [
        *[f"RESOURCE::{item}" for item in admission["rejection_reasons"]],
        *[f"DETERMINISM::{item}" for item in determinism_rejections],
    ]
    result = {
        "status": "PASS" if not rejection_reasons else "REJECTED",
        "sample_original_epoch_indices": sample_indices,
        "workers_reference": 1,
        "workers_compared": workers,
        "actual_process_count": len(worker_pids),
        "probe_worker_failure_count": len(worker_failures),
        "probe_worker_failures": worker_failures,
        "worker_pids": sorted(worker_pids),
        "per_worker_max_rss_bytes": dict(sorted(worker_rss.items())),
        "peak_per_worker_rss_bytes": per_worker_peak,
        "projected_total_worker_rss_bytes": projected_rss,
        "resource_before": before,
        "resource_after": after,
        "swap_activity_delta_pages": {
            "in": after["swap_in_pages"] - before["swap_in_pages"],
            "out": after["swap_out_pages"] - before["swap_out_pages"],
        },
        "cache_read_io_probe": cache_read,
        "resource_admission": admission,
        "rejection_reasons": rejection_reasons,
        "worker_selection": {
            "default_workers": DEFAULT_WORKERS, "maximum_workers": MAX_WORKERS,
            "selected_workers": workers, "maximum_20_used": workers == MAX_WORKERS,
            "decision": (
                "DEFAULT_16_SELECTED_MAX20_NOT_USED"
                if workers == DEFAULT_WORKERS else "EXPLICIT_NONDEFAULT_WITHIN_MAXIMUM"
            ),
        },
        "scientific_comparisons": comparisons,
        "scientific_digest": digest,
        "excluded_fields": [
            "runtime_seconds", "worker_pid", "worker_max_rss_bytes", "shard_id",
        ],
    }
    if rejection_reasons:
        raise ResourceAdmissionError(result)
    return result


def execute_shards(
    cache_root: Path,
    bridge_path: Path,
    navigation_paths: Sequence[Path],
    part_root: Path,
    *,
    source_fingerprint: str,
    workers: int,
    resume: bool,
) -> list[dict[str, Any]]:
    pair_count = len(CompactCacheReader(cache_root))
    shards = deterministic_shards(pair_count, workers)
    if part_root.exists() and not resume:
        raise Phase2RunnerError("part root exists outside resume mode")
    part_root.mkdir(parents=True, exist_ok=resume)
    expected_names = {
        path.name
        for shard_id, start, stop in shards
        for path in _part_paths(part_root, shard_id, start, stop)
    }
    unexpected = [path.name for path in part_root.iterdir() if path.name not in expected_names]
    if unexpected:
        raise Phase2RunnerError(f"unexpected resume part files: {sorted(unexpected)}")
    pending: list[tuple[int, int, int]] = []
    for shard_id, start, stop in shards:
        data_path, manifest_path = _part_paths(part_root, shard_id, start, stop)
        if data_path.exists() or manifest_path.exists():
            if not resume:
                raise Phase2RunnerError("part collision outside resume mode")
            validate_part(
                data_path, manifest_path, source_fingerprint=source_fingerprint,
                shard_id=shard_id, start=start, stop=stop,
            )
        else:
            pending.append((shard_id, start, stop))
    if pending:
        with ProcessPoolExecutor(max_workers=min(workers, len(pending))) as executor:
            futures = {
                executor.submit(
                    _process_shard, str(cache_root), str(bridge_path),
                    [str(path) for path in navigation_paths], str(part_root),
                    source_fingerprint, shard_id, start, stop,
                ): (shard_id, start, stop)
                for shard_id, start, stop in pending
            }
            for future in as_completed(futures):
                future.result()
    records: list[dict[str, Any]] = []
    for shard_id, start, stop in shards:
        data_path, manifest_path = _part_paths(part_root, shard_id, start, stop)
        records.extend(validate_part(
            data_path, manifest_path, source_fingerprint=source_fingerprint,
            shard_id=shard_id, start=start, stop=stop,
        ))
    if [record["epoch_index"] for record in records] != list(range(pair_count)):
        raise Phase2RunnerError("final shard merge violated original-index order")
    return records


FAILURE_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "method_id", "case_id",
    "failure_code", "failure_detail",
)
RUNTIME_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "runtime_seconds",
    "worker_pid", "worker_max_rss_bytes", "shard_id",
)
DD_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "failure_code",
    "common_raw_satellite_count", "common_pr_valid_satellite_count",
    "common_cp_valid_satellite_count", "common_pr_cp_valid_satellite_count",
    "common_half_cycle_valid_satellite_count",
    "common_integer_compatible_satellite_count",
    "common_rtklib_phase_compatible_satellite_count",
    "satellite_state_available_count", "elevation_eligible_satellite_count",
    "dd_eligible_satellite_count", "receiver_ecef_m_raw_code_spp",
    "baseline_ecef_m", "baseline_direction_ecef",
    "receiver_spp_residual_rms_m", "pivot_identity",
    "ambiguity_signal_identities", "dd_dimension", "backend_order",
    "code_dd_m", "phase_dd_m", "design_m_per_m",
    "covariance_code_phase_m2", "gps_l1_wavelength_m",
    "covariance_condition", "whitened_design_rank", "whitened_design_condition",
)
CANDIDATE_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "failure_code",
    "phase_row_count", "integer_option_count_per_row", "circle_count",
    "circle_pair_count", "intersecting_pair_count",
    "near_tangent_candidate_count", "degenerate_pair_count", "raw_candidate_count",
    "unique_candidate_count", "selected_candidate_index",
    "exact_objective_tie_count", "converged_candidate_count",
    "failed_candidate_count", "search_complete", "K_policy", "candidate_diagnostics",
)
REFINEMENT_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "failure_code",
    "candidate_count", "converged_candidate_count", "failed_candidate_count",
    "total_iteration_count", "selected_candidate_index",
    "selected_iteration_count", "selected_convergence_state",
    "search_complete", "refinement_iterations",
)
OBJECTIVE_ORACLE_FIELDS = (
    "epoch_index", "oracle_subset_selection", "oracle_status", "formal_objective",
    "oracle_objective", "oracle_minus_formal", "comparison_tolerance",
    "comparison_pass", "grid_direction_count", "objective_path",
    "algorithm1_candidates_used", "oracle_direction_ecef",
    "oracle_refined_integer_region_count", "oracle_selected_iterations",
)
TRACKING_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "method_id", "case_id",
    "pivot_identity", "pivot_switched", "satellite_set_changed",
    "ambiguity_reinitialized_by_method",
    "r1_measurement_count", "r1_used_carrier_count", "r1_excluded_cp_invalid_count",
    "r1_excluded_half_cycle_unknown_count", "r1_sub_half_cycle_set_count",
    "r1_actual_lock_reset_count", "r1_actual_cycle_slip_count",
    "r1_half_cycle_state_change_count",
    "r2_measurement_count", "r2_used_carrier_count", "r2_excluded_cp_invalid_count",
    "r2_excluded_half_cycle_unknown_count", "r2_sub_half_cycle_set_count",
    "r2_actual_lock_reset_count", "r2_actual_cycle_slip_count",
    "r2_half_cycle_state_change_count", "receiver_clock_reset",
)


def _identity_from_text(value: str) -> SignalIdentity:
    fields = value.split(":")
    if len(fields) != 4:
        raise Phase2RunnerError(f"invalid signal identity text: {value}")
    return SignalIdentity(*(int(item) for item in fields))


def _tracking_rows(
    cache_root: Path,
    records: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    reader = CompactCacheReader(cache_root)
    continuity1, continuity2 = TrackingContinuity(), TrackingContinuity()
    previous_pivot: str | None = None
    previous_satellites: tuple[str, ...] | None = None
    rows: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        left, right = reader.pair(index)
        heading, dd = record["heading"], record["dd"]
        pivot = heading.get("pivot_identity")
        satellites = tuple(dd.get("ambiguity_signal_identities") or ())
        used_text = tuple(([pivot] if pivot else []) + list(satellites))
        used = tuple(_identity_from_text(item) for item in used_text)
        accepted = bool(heading.get("method_native_accepted"))
        pivot_switched = bool(
            accepted and previous_pivot is not None and pivot != previous_pivot
        )
        satellite_set_changed = bool(
            accepted and previous_satellites is not None and satellites != previous_satellites
        )
        summary1 = tracking_epoch_summary(
            continuity1, 1, left, used,
            ambiguity_reinitialized_by_method=accepted,
            pivot_changed=pivot_switched,
            satellite_set_changed=satellite_set_changed,
        )
        summary2 = tracking_epoch_summary(
            continuity2, 2, right, used,
            ambiguity_reinitialized_by_method=accepted,
            pivot_changed=pivot_switched,
            satellite_set_changed=satellite_set_changed,
        )
        if accepted:
            previous_pivot, previous_satellites = str(pivot), satellites
        heading["pivot_switched"] = pivot_switched
        heading["lock_reset"] = bool(
            summary1.actual_lock_reset_count or summary2.actual_lock_reset_count
        )
        heading["cycle_slip"] = bool(
            summary1.actual_cycle_slip_count or summary2.actual_cycle_slip_count
        )
        heading["arc_reset"] = bool(
            heading["cycle_slip"] or heading["receiver_clock_reset"]
        )
        heading["half_cycle_subtracted"] = bool(
            summary1.sub_half_cycle_set_count or summary2.sub_half_cycle_set_count
        )
        rows.append({
            "epoch_index": index, "gps_week": left.gps_week,
            "gps_tow_seconds": left.gps_tow_seconds, "method_id": METHOD_ID,
            "case_id": CASE_ID, "pivot_identity": pivot,
            "pivot_switched": pivot_switched,
            "satellite_set_changed": satellite_set_changed,
            "ambiguity_reinitialized_by_method": accepted,
            "r1_measurement_count": summary1.measurement_count,
            "r1_used_carrier_count": summary1.used_carrier_count,
            "r1_excluded_cp_invalid_count": summary1.excluded_cp_invalid_count,
            "r1_excluded_half_cycle_unknown_count": summary1.excluded_half_cycle_unknown_count,
            "r1_sub_half_cycle_set_count": summary1.sub_half_cycle_set_count,
            "r1_actual_lock_reset_count": summary1.actual_lock_reset_count,
            "r1_actual_cycle_slip_count": summary1.actual_cycle_slip_count,
            "r1_half_cycle_state_change_count": summary1.half_cycle_state_change_count,
            "r2_measurement_count": summary2.measurement_count,
            "r2_used_carrier_count": summary2.used_carrier_count,
            "r2_excluded_cp_invalid_count": summary2.excluded_cp_invalid_count,
            "r2_excluded_half_cycle_unknown_count": summary2.excluded_half_cycle_unknown_count,
            "r2_sub_half_cycle_set_count": summary2.sub_half_cycle_set_count,
            "r2_actual_lock_reset_count": summary2.actual_lock_reset_count,
            "r2_actual_cycle_slip_count": summary2.actual_cycle_slip_count,
            "r2_half_cycle_state_change_count": summary2.half_cycle_state_change_count,
            "receiver_clock_reset": heading["receiver_clock_reset"],
        })
    return rows


def _validate_native_records(records: Sequence[dict[str, Any]], pair_count: int) -> None:
    if len(records) != pair_count or [row.get("epoch_index") for row in records] != list(
        range(pair_count)
    ):
        raise Phase2RunnerError("native row conservation/original ordering failed")
    success = 0
    for record in records:
        heading = record.get("heading")
        if not isinstance(heading, dict):
            raise Phase2RunnerError("native record lacks heading row")
        accepted = heading.get("method_native_accepted") is True
        if accepted:
            success += 1
            if (
                heading.get("method_id") != METHOD_ID
                or heading.get("solution_state") != "accepted_wrapped_solution"
                or heading.get("solution_type") != "accepted_wrapped_solution"
                or heading.get("ambiguity_correctness_known") is not False
                or heading.get("search_complete") is not True
                or float(heading.get("common_backbone_yaw_std_deg"))
                != COMMON_BACKBONE_YAW_STD_DEG
            ):
                raise Phase2RunnerError("accepted EXT02 heading label drift")
            vector = np.asarray(heading.get("baseline_ned_m"), dtype=float)
            if vector.shape != (3,) or abs(float(np.linalg.norm(vector)) - BASELINE_LENGTH_M) > 1e-9:
                raise Phase2RunnerError("accepted baseline violates 0.350 m hard constraint")
        else:
            if heading.get("solution_state") != "invalid" or record.get("failure") is None:
                raise Phase2RunnerError("invalid native row lacks failure ledger entry")
    failure_count = sum(record.get("failure") is not None for record in records)
    if pair_count != success + failure_count:
        raise Phase2RunnerError("paired = accepted + failure conservation failed")
    failed_oracles = [
        record["epoch_index"] for record in records
        if record.get("objective_oracle", {}).get("comparison_pass") is False
    ]
    if failed_oracles:
        raise Phase2RunnerError(f"OBJECTIVE_ORACLE_MISMATCH at epochs {failed_oracles}")


def _native_provenance(
    preflight: PreflightResult,
    provider_hashes: Mapping[str, str],
) -> dict[str, Any]:
    return {
        "data_mode": DATA_MODE,
        "raw_source_hashes": preflight.raw_source_hashes,
        "provider_hashes": dict(sorted(provider_hashes.items())),
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "code_commit": preflight.code_commit,
        "code_commit_role": "BASE_HEAD_ONLY_NOT_COMPLETE_RUNTIME_SOURCE_IDENTITY",
        "source_fingerprint": preflight.source_fingerprint,
        "runtime_source_hashes": dict(sorted(preflight.runtime_source_hashes.items())),
        "git_source_state": dict(preflight.git_source_state),
        "config_hash": preflight.config_hash,
        "contract_hash": preflight.contract_hash,
        "heading_schema_hash": preflight.schema_hash,
        "trace_open_count": 0,
        "HPPOSECEF_semantic_decode_count": 0,
        "HPPOSECEF_solver_input": False,
        "status_baseline_solver_input": False,
        "Go2_yaw_solver_input": False,
        "EXT01_output_solver_input": False,
        "RTKLIB_position_solver_input": False,
        "phase_bias_calibration": "NONE",
    }


def _auxiliary_hashes(attempt: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for root_name in (
        "ATTEMPT_IDENTITY.json", "RESOURCE_DETERMINISM_PROBE.json",
        "COMPACT_CACHE", "SOURCE_BACKEND", "PARTS",
    ):
        root = attempt / root_name
        paths = [root] if root.is_file() else sorted(path for path in root.rglob("*") if path.is_file())
        for path in paths:
            result[str(path.relative_to(attempt))] = _sha256_file(path)
    return result


def _fail_on_target_collisions(paths: Mapping[str, Path], *, label: str) -> None:
    collisions = sorted(path.name for path in paths.values() if _path_lexists(path))
    if collisions:
        raise Phase2RunnerError(f"{label} target collision: {collisions}")


def write_native_outputs(
    attempt: Path,
    cache_root: Path,
    records: list[dict[str, Any]],
    *,
    preflight: PreflightResult,
    cache_manifest: Mapping[str, Any],
    provider_hashes: Mapping[str, str],
    determinism_probe: Mapping[str, Any],
    workers: int,
) -> dict[str, Any]:
    output_paths = {name: attempt / filename for name, filename in NATIVE_FILE_NAMES.items()}
    _fail_on_target_collisions(output_paths, label="native output")
    pair_count = int(cache_manifest["pair_count"])
    tracking = _tracking_rows(cache_root, records)
    _validate_native_records(records, pair_count)
    schema = _load_mapping(HEADING_SCHEMA_PATH)
    heading_fields = ("epoch_index", *tuple(schema["fields"].keys()))
    headings = [record["heading"] for record in records]
    failures = [record["failure"] for record in records if record["failure"] is not None]
    runtimes = [record["runtime"] for record in records]
    dd_rows = [record["dd"] for record in records]
    candidates = []
    refinements = []
    for record in records:
        heading = record["heading"]
        candidate_rows = record["candidates"]
        refinement_rows = record["refinements"]
        failed_candidate_count = sum(
            not (
                row.get("converged") is True
                and row.get("failure_code") is None
                and row.get("objective") is not None
                and math.isfinite(float(row["objective"]))
            )
            for row in candidate_rows
        )
        selected_rows = [row for row in candidate_rows if row.get("selected")]
        selected = selected_rows[0] if len(selected_rows) == 1 else None
        common = {
            "epoch_index": record["epoch_index"],
            "gps_week": heading["gps_week"],
            "gps_tow_seconds": heading["gps_tow_seconds"],
            "failure_code": heading["failure_code"],
        }
        candidates.append({
            **common,
            "phase_row_count": candidate_rows[0]["phase_row_count"] if candidate_rows else 0,
            "integer_option_count_per_row": (
                candidate_rows[0]["integer_option_count_per_row"] if candidate_rows else []
            ),
            "circle_count": candidate_rows[0]["circle_count"] if candidate_rows else 0,
            "circle_pair_count": candidate_rows[0]["circle_pair_count"] if candidate_rows else 0,
            "intersecting_pair_count": (
                candidate_rows[0]["intersecting_pair_count"] if candidate_rows else 0
            ),
            "near_tangent_candidate_count": (
                candidate_rows[0]["near_tangent_candidate_count"] if candidate_rows else 0
            ),
            "degenerate_pair_count": (
                candidate_rows[0]["degenerate_pair_count"] if candidate_rows else 0
            ),
            "raw_candidate_count": candidate_rows[0]["raw_candidate_count"] if candidate_rows else 0,
            "unique_candidate_count": len(candidate_rows),
            "selected_candidate_index": None if selected is None else selected["coarse_index"],
            "exact_objective_tie_count": (
                candidate_rows[0]["exact_objective_tie_count"] if candidate_rows else None
            ),
            "converged_candidate_count": sum(bool(row["converged"]) for row in candidate_rows),
            "failed_candidate_count": failed_candidate_count,
            "search_complete": heading.get("search_complete") is True,
            "K_policy": "ALL_UNIQUE_CANDIDATES",
            "candidate_diagnostics": candidate_rows,
        })
        selected_iterations = (
            [row for row in refinement_rows if row["coarse_index"] == selected["coarse_index"]]
            if selected is not None else []
        )
        refinements.append({
            **common, "candidate_count": len(candidate_rows),
            "converged_candidate_count": sum(bool(row["converged"]) for row in candidate_rows),
            "failed_candidate_count": failed_candidate_count,
            "total_iteration_count": len(refinement_rows),
            "selected_candidate_index": None if selected is None else selected["coarse_index"],
            "selected_iteration_count": len(selected_iterations),
            "selected_convergence_state": None if selected is None else selected["convergence_state"],
            "search_complete": heading.get("search_complete") is True,
            "refinement_iterations": refinement_rows,
        })
    oracles = [record["objective_oracle"] for record in records]
    evaluated_oracles = [
        row for row in oracles if row.get("oracle_status") == "EVALUATED_DENSE_FULL_SPHERE"
    ]
    _atomic_write_csv(output_paths["heading_results"], headings, heading_fields)
    _atomic_write_csv(output_paths["failure_ledger"], failures, FAILURE_FIELDS)
    _atomic_write_csv(output_paths["runtime"], runtimes, RUNTIME_FIELDS)
    _atomic_write_csv(output_paths["dd_diagnostics"], dd_rows, DD_FIELDS)
    _atomic_write_csv(output_paths["candidate_diagnostics"], candidates, CANDIDATE_FIELDS)
    _atomic_write_csv(output_paths["refinement_diagnostics"], refinements, REFINEMENT_FIELDS)
    _atomic_write_csv(
        output_paths["objective_oracle_diagnostics"], oracles, OBJECTIVE_ORACLE_FIELDS,
    )
    _atomic_write_csv(output_paths["tracking_diagnostics"], tracking, TRACKING_FIELDS)
    success_count = sum(row["method_native_accepted"] is True for row in headings)
    failure_count = len(failures)
    accepted_headings = [row for row in headings if row["method_native_accepted"] is True]
    failure_code_counts: dict[str, int] = {}
    for row in failures:
        code = str(row["failure_code"])
        failure_code_counts[code] = failure_code_counts.get(code, 0) + 1
    accepted_indices = [int(row["epoch_index"]) for row in accepted_headings]
    accepted_tows = [float(row["gps_tow_seconds"]) for row in accepted_headings]
    accepted_lengths = [
        float(np.linalg.norm(np.asarray(row["baseline_ned_m"], dtype=float)))
        for row in accepted_headings
    ]
    native_statistics = {
        "accepted_coverage": success_count / pair_count,
        "accepted_continuity": _continuity_metrics(accepted_indices, accepted_tows),
        "baseline_length_hard_constraint": {
            "identity_m": BASELINE_LENGTH_M,
            "count": len(accepted_lengths),
            "minimum_m": min(accepted_lengths) if accepted_lengths else None,
            "maximum_m": max(accepted_lengths) if accepted_lengths else None,
            "maximum_absolute_norm_error_m": (
                max(abs(value - BASELINE_LENGTH_M) for value in accepted_lengths)
                if accepted_lengths else None
            ),
        },
        "baseline_heading_wrapaware_deg": _circular_statistics_deg(
            float(row["baseline_heading_deg"]) for row in accepted_headings
        ),
        "body_yaw_wrapaware_deg": _circular_statistics_deg(
            float(row["body_yaw_deg"]) for row in accepted_headings
        ),
        "baseline_elevation_deg": _numeric_statistics(
            float(row["baseline_elevation_deg"]) for row in accepted_headings
        ),
        "constrained_objective": _numeric_statistics(
            float(row["constrained_objective"]) for row in accepted_headings
        ),
        "wrapped_phase_rms_cycles": _numeric_statistics(
            float(row["wrapped_phase_rms_cycles"]) for row in accepted_headings
        ),
        "wrapped_phase_p95_cycles": _numeric_statistics(
            float(row["wrapped_phase_p95_cycles"]) for row in accepted_headings
        ),
        "wrapped_phase_max_abs_cycles": _numeric_statistics(
            float(row["wrapped_phase_max_abs_cycles"]) for row in accepted_headings
        ),
        "pseudorange_residual_rms_m": _numeric_statistics(
            float(row["pseudorange_residual_rms_m"]) for row in accepted_headings
        ),
        "raw_candidate_count": _numeric_statistics(
            float(row["raw_candidate_count"]) for row in accepted_headings
        ),
        "unique_candidate_count": _numeric_statistics(
            float(row["unique_candidate_count"]) for row in accepted_headings
        ),
        "refined_candidate_count": _numeric_statistics(
            float(row["refined_candidate_count"]) for row in accepted_headings
        ),
        "phase_row_count": _numeric_statistics(float(row["phase_row_count"]) for row in candidates),
        "circle_count": _numeric_statistics(float(row["circle_count"]) for row in candidates),
        "circle_pair_count": _numeric_statistics(
            float(row["circle_pair_count"]) for row in candidates
        ),
        "intersecting_pair_count": _numeric_statistics(
            float(row["intersecting_pair_count"]) for row in candidates
        ),
        "near_tangent_candidate_count": _numeric_statistics(
            float(row["near_tangent_candidate_count"]) for row in candidates
        ),
        "degenerate_pair_count": _numeric_statistics(
            float(row["degenerate_pair_count"]) for row in candidates
        ),
        "selected_refinement_iterations": _numeric_statistics(
            float(row["refinement_iterations"]) for row in accepted_headings
        ),
        "runtime_seconds": _numeric_statistics(float(row["runtime_seconds"]) for row in runtimes),
        "worker_max_rss_bytes": _numeric_statistics(
            float(row["worker_max_rss_bytes"]) for row in runtimes
        ),
        "failure_code_counts": dict(sorted(failure_code_counts.items())),
        "candidate_search_completion": {
            "accepted_count": success_count,
            "accepted_search_complete_count": sum(
                row.get("search_complete") is True for row in accepted_headings
            ),
            "all_accepted_search_complete": (
                None if not accepted_headings
                else all(row.get("search_complete") is True for row in accepted_headings)
            ),
            "rejected_incomplete_search_epoch_count": sum(
                row.get("search_complete") is not True and int(row["unique_candidate_count"]) > 0
                for row in headings
            ),
        },
        "gps_l1_dd_stage_counts": {
            name: _numeric_statistics(
                float(row[name]) for row in dd_rows if row.get(name) is not None
            )
            for name in (
                "common_raw_satellite_count", "common_pr_valid_satellite_count",
                "common_cp_valid_satellite_count", "common_pr_cp_valid_satellite_count",
                "common_half_cycle_valid_satellite_count",
                "common_integer_compatible_satellite_count",
                "satellite_state_available_count", "elevation_eligible_satellite_count",
                "dd_eligible_satellite_count", "dd_dimension",
            )
        },
    }
    csv_hashes = {
        name: _sha256_file(path)
        for name, path in output_paths.items()
        if name not in {"native_summary", "native_freeze"}
    }
    provenance = _native_provenance(preflight, provider_hashes)
    summary = {
        "schema_version": "horizontal_literature.phase2.native_summary.v1",
        "phase_id": "PHASE2", "method_id": METHOD_ID, "case_id": CASE_ID,
        "terminal_status": PASS_READY, "evaluation": "NOT_EVALUATED",
        "ready_for_paper_claims": False,
        "paired_epoch_count": pair_count,
        "success_row_count": success_count,
        "failure_row_count": failure_count,
        "row_conservation": pair_count == success_count + failure_count,
        "accepted_wrapped_solution_count": success_count,
        "accepted_wrapped_solution_rate": success_count / pair_count,
        "native_metric": "accepted_wrapped_solution_rate",
        "ambiguity_correctness_known": False,
        "ambiguity_success_rate": "NA", "fixed_rate": "NA", "float_rate": "NA",
        "baseline_length_m": BASELINE_LENGTH_M,
        "common_backbone_yaw_std_deg": COMMON_BACKBONE_YAW_STD_DEG,
        "K_policy": "ALL_UNIQUE_CANDIDATES",
        "official_code_search": preflight.contract["paper_source"]["official_code_search"],
        "paper_source_identity": preflight.contract["paper_source"],
        "objective_oracle_indices": sorted(ORACLE_INDICES),
        "objective_oracle_selected_count": len(ORACLE_INDICES),
        "objective_oracle_evaluated_count": len(evaluated_oracles),
        "objective_oracle_not_evaluated_count": len(ORACLE_INDICES) - len(evaluated_oracles),
        "objective_oracle_all_comparisons_pass": (
            None if not evaluated_oracles
            else all(row.get("comparison_pass") is True for row in evaluated_oracles)
        ),
        "native_descriptive_statistics": native_statistics,
        "workers": workers,
        "thread_environment": {
            name: os.environ[name] for name in (
                "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS",
            )
        },
        "determinism_probe": dict(determinism_probe),
        "cache_fingerprint": preflight.source_fingerprint,
        "output_hashes": csv_hashes,
        **provenance,
    }
    _atomic_write_json(output_paths["native_summary"], summary)
    frozen_hashes = {
        name: _sha256_file(path)
        for name, path in output_paths.items()
        if name != "native_freeze"
    }
    freeze = {
        "schema_version": "horizontal_literature.phase2.native_freeze.v1",
        "phase_id": "PHASE2", "method_id": METHOD_ID, "case_id": CASE_ID,
        "freeze_validated": True,
        "native_file_count_excluding_freeze": len(frozen_hashes),
        "native_output_hashes": frozen_hashes,
        "native_file_inventory": [
            NATIVE_FILE_NAMES[name] for name in NATIVE_FILE_NAMES if name != "native_freeze"
        ],
        "auxiliary_evidence_hashes": _auxiliary_hashes(attempt),
        "paired_epoch_count": pair_count,
        "success_row_count": success_count,
        "failure_row_count": failure_count,
        "trace_open_count_before_freeze": 0,
        "HPPOSECEF_semantic_decode_count_before_freeze": 0,
        "native_outputs_mutable_after_freeze": False,
        **provenance,
    }
    _atomic_write_json(output_paths["native_freeze"], freeze)
    return summary


def validate_native_freeze(native_root: Path) -> dict[str, Any]:
    root = Path(native_root)
    freeze_path = root / NATIVE_FILE_NAMES["native_freeze"]
    if not freeze_path.is_file():
        raise Phase2RunnerError("native freeze manifest is absent")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    if (
        freeze.get("schema_version") != "horizontal_literature.phase2.native_freeze.v1"
        or freeze.get("freeze_validated") is not True
        or freeze.get("trace_open_count_before_freeze") != 0
        or freeze.get("HPPOSECEF_semantic_decode_count_before_freeze") != 0
    ):
        raise Phase2RunnerError("native freeze contract is invalid")
    expected = {
        NATIVE_FILE_NAMES[name] for name in NATIVE_FILE_NAMES if name != "native_freeze"
    }
    if set(freeze.get("native_output_hashes", {})) != {
        name for name in NATIVE_FILE_NAMES if name != "native_freeze"
    }:
        raise Phase2RunnerError("native freeze logical inventory mismatch")
    if set(freeze.get("native_file_inventory", ())) != expected:
        raise Phase2RunnerError("native freeze filename inventory mismatch")
    for logical, digest in freeze["native_output_hashes"].items():
        path = root / NATIVE_FILE_NAMES[logical]
        if not path.is_file() or _sha256_file(path) != digest:
            raise Phase2RunnerError(f"native freeze hash mismatch: {logical}")
    for relative, digest in freeze.get("auxiliary_evidence_hashes", {}).items():
        candidate = (root / relative).resolve()
        _require_contained(candidate, root.resolve(), "native auxiliary evidence")
        if not candidate.is_file() or _sha256_file(candidate) != digest:
            raise Phase2RunnerError(f"native auxiliary evidence hash mismatch: {relative}")
    pair_count = int(freeze.get("paired_epoch_count", -1))
    if pair_count != EXPECTED_PAIR_COUNT:
        raise Phase2RunnerError("native freeze paired-epoch count is not 1509")
    exact_epoch_streams = (
        "heading_results", "runtime", "dd_diagnostics", "candidate_diagnostics",
        "refinement_diagnostics", "objective_oracle_diagnostics", "tracking_diagnostics",
    )
    rows_by_name: dict[str, list[dict[str, str]]] = {}
    expected_indices = list(range(pair_count))
    for logical in exact_epoch_streams:
        rows = _read_csv_rows(root / NATIVE_FILE_NAMES[logical])
        rows_by_name[logical] = rows
        if len(rows) != pair_count:
            raise Phase2RunnerError(f"native {logical} row count is not 1509")
        if [int(row.get("epoch_index", -1)) for row in rows] != expected_indices:
            raise Phase2RunnerError(f"native {logical} original-index order mismatch")
    headings = rows_by_name["heading_results"]
    invalid_indices = [
        int(row["epoch_index"]) for row in headings
        if row.get("method_native_accepted") != "true"
    ]
    failure_rows = _read_csv_rows(root / NATIVE_FILE_NAMES["failure_ledger"])
    failure_indices = [int(row.get("epoch_index", -1)) for row in failure_rows]
    if failure_indices != invalid_indices or len(failure_rows) != int(
        freeze.get("failure_row_count", -1)
    ):
        raise Phase2RunnerError("failure ledger is not the ordered invalid-heading subset")
    success_count = sum(row.get("method_native_accepted") == "true" for row in headings)
    if success_count != int(freeze.get("success_row_count", -1)):
        raise Phase2RunnerError("native success count disagrees with freeze")
    summary = json.loads((root / NATIVE_FILE_NAMES["native_summary"]).read_text(encoding="utf-8"))
    if (
        int(summary.get("paired_epoch_count", -1)) != pair_count
        or int(summary.get("success_row_count", -1)) != success_count
        or int(summary.get("failure_row_count", -1)) != len(failure_rows)
        or summary.get("row_conservation") is not True
    ):
        raise Phase2RunnerError("native summary count/conservation mismatch")
    return freeze


def _atomic_finalize_attempt(attempt: Path, final: Path) -> None:
    if _path_lexists(final):
        raise Phase2RunnerError("final native root appeared before atomic finalize")
    if attempt.parent != final.parent:
        raise Phase2RunnerError("attempt/final roots must share a filesystem parent")
    validate_native_freeze(attempt)
    _atomic_install_noreplace(
        attempt, final, label="final native root", kind="directory",
    )
    validate_native_freeze(final)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    prior_limit = csv.field_size_limit()
    try:
        csv.field_size_limit(CSV_FIELD_SIZE_LIMIT)
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames is None:
                raise Phase2RunnerError(f"CSV lacks a header: {path}")
            return list(reader)
    except csv.Error as exc:
        raise Phase2RunnerError(
            f"CSV_PARSE_ERROR for {path}: csv.Error: {exc}; "
            f"frozen_field_size_limit={CSV_FIELD_SIZE_LIMIT}"
        ) from exc
    finally:
        csv.field_size_limit(prior_limit)


def _json_cell(value: str, *, expected: type = list) -> Any:
    try:
        decoded = json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise Phase2RunnerError("native JSON-in-CSV cell is invalid") from exc
    if not isinstance(decoded, expected):
        raise Phase2RunnerError("native JSON-in-CSV cell has the wrong type")
    return decoded


def _proxy_common_grid_associations(
    rawx_itows_ms: Sequence[int],
    receiver1_itows_ms: Sequence[int],
    receiver2_itows_ms: Sequence[int],
) -> list[dict[str, Any]]:
    r1 = [int(value) for value in receiver1_itows_ms]
    r2 = [int(value) for value in receiver2_itows_ms]
    if len(r1) != len(set(r1)):
        raise Phase2RunnerError("GNSS1 HPPOSECEF iTOW stream contains duplicates")
    if len(r2) != len(set(r2)):
        raise Phase2RunnerError("GNSS2 HPPOSECEF iTOW stream contains duplicates")
    common = sorted(set(r1).intersection(r2))
    common_index = {value: index for index, value in enumerate(common)}
    rows: list[dict[str, Any]] = []
    for raw_value in rawx_itows_ms:
        raw = int(raw_value)
        base: dict[str, Any] = {
            "rawx_itow_ms": raw,
            "proxy_itow_ms": None,
            "proxy_itow_minus_rawx_ms": None,
            "proxy_local_common_grid_cadence_ms": None,
            "proxy_local_half_cadence_bound_ms": None,
            "proxy_association_policy": PROXY_ASSOCIATION_POLICY,
            "proxy_association_status": "UNAVAILABLE_NO_COMMON_HPPOSECEF_ITOW",
        }
        if not common:
            rows.append(base)
            continue
        insertion = bisect.bisect_left(common, raw)
        candidates = []
        if insertion:
            candidates.append(common[insertion - 1])
        if insertion < len(common):
            candidates.append(common[insertion])
        minimum_distance = min(abs(value - raw) for value in candidates)
        nearest = [value for value in candidates if abs(value - raw) == minimum_distance]
        if len(nearest) != 1:
            base["proxy_association_status"] = "UNAVAILABLE_MIDPOINT_TIE"
            rows.append(base)
            continue
        selected = nearest[0]
        index = common_index[selected]
        adjacent_gaps = []
        if index:
            adjacent_gaps.append(selected - common[index - 1])
        if index + 1 < len(common):
            adjacent_gaps.append(common[index + 1] - selected)
        offset = selected - raw
        base.update({
            "proxy_itow_ms": selected,
            "proxy_itow_minus_rawx_ms": offset,
        })
        if not adjacent_gaps:
            base["proxy_association_status"] = "UNAVAILABLE_NO_LOCAL_COMMON_GRID_CADENCE"
            rows.append(base)
            continue
        local_cadence = min(adjacent_gaps)
        half_cadence = 0.5 * local_cadence
        base.update({
            "proxy_local_common_grid_cadence_ms": local_cadence,
            "proxy_local_half_cadence_bound_ms": half_cadence,
        })
        if abs(offset) >= half_cadence:
            base["proxy_association_status"] = "UNAVAILABLE_HALF_CADENCE_BOUND"
        else:
            base["proxy_association_status"] = "ASSOCIATED_UNIQUE_NEAREST_COMMON_ITOW"
        rows.append(base)

    associated = [
        row for row in rows
        if row["proxy_association_status"] == "ASSOCIATED_UNIQUE_NEAREST_COMMON_ITOW"
    ]
    counts: dict[int, int] = {}
    for row in associated:
        selected = int(row["proxy_itow_ms"])
        counts[selected] = counts.get(selected, 0) + 1
    for row in associated:
        if counts[int(row["proxy_itow_ms"])] != 1:
            row["proxy_association_status"] = "UNAVAILABLE_NONUNIQUE_ASSIGNMENT"

    associated = [
        row for row in rows
        if row["proxy_association_status"] == "ASSOCIATED_UNIQUE_NEAREST_COMMON_ITOW"
    ]
    selected_sequence = [int(row["proxy_itow_ms"]) for row in associated]
    if any(
        right <= left for left, right in zip(
            selected_sequence, selected_sequence[1:], strict=False,
        )
    ):
        for row in associated:
            row["proxy_association_status"] = "UNAVAILABLE_NONMONOTONIC_ASSIGNMENT"
    return rows


def _hpposecef_proxy_rows(
    paths: Phase2Paths,
    headings: Sequence[Mapping[str, str]],
    dd_rows: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, Any]], int]:
    # This function is called only after validate_native_freeze.  Semantic
    # decoding is intentionally explicit here and nowhere in the native path.
    reconstruction1 = reconstruct_ubx_stream(
        paths.gnss1_raw, decode_nav_hpposecef_semantics=True,
    )
    reconstruction2 = reconstruct_ubx_stream(
        paths.gnss2_raw, decode_nav_hpposecef_semantics=True,
    )
    epochs1 = list(reconstruction1.nav_hpposecef_epochs)
    epochs2 = list(reconstruction2.nav_hpposecef_epochs)
    map1 = {epoch.itow_ms: epoch for epoch in epochs1}
    map2 = {epoch.itow_ms: epoch for epoch in epochs2}
    rawx_itows = [
        int(round((float(heading["gps_tow_seconds"]) % 604800.0) * 1000.0))
        % 604800000
        for heading in headings
    ]
    associations = _proxy_common_grid_associations(
        rawx_itows,
        [epoch.itow_ms for epoch in epochs1],
        [epoch.itow_ms for epoch in epochs2],
    )
    rows: list[dict[str, Any]] = []
    from .ext02_cwls import adapt_metric_double_differences, wrapped_objective

    for heading, dd, association in zip(headings, dd_rows, associations, strict=True):
        index = int(heading["epoch_index"])
        tow = float(heading["gps_tow_seconds"])
        base: dict[str, Any] = {
            "epoch_index": index, "gps_week": int(heading["gps_week"]),
            "gps_tow_seconds": tow, "proxy_source": "NAV_HPPOSECEF_POST_NATIVE_ONLY",
            **association,
        }
        if association["proxy_association_status"] != (
            "ASSOCIATED_UNIQUE_NEAREST_COMMON_ITOW"
        ):
            rows.append({
                **base, "proxy_status": "UNAVAILABLE_ASSOCIATION",
                "proxy_baseline_ecef_m": None, "proxy_baseline_ned_m": None,
                "proxy_length_m": None, "proxy_heading_deg": None,
                "proxy_elevation_deg": None, "proxy_body_yaw_deg": None,
                "native_proxy_vector_angle_deg": None,
                "native_minus_proxy_heading_wrapsafe_deg": None,
                "native_minus_proxy_body_yaw_wrapsafe_deg": None,
                "production_objective": None, "proxy_objective": None,
                "proxy_minus_production_objective": None,
                "materiality_tolerance": None, "proxy_materially_lower": False,
                "oracle_gated_epoch": index in ORACLE_INDICES,
            })
            continue
        proxy_itow = int(association["proxy_itow_ms"])
        receiver = map1[proxy_itow].position_ecef_m
        vector_ecef = map2[proxy_itow].position_ecef_m - receiver
        length = float(np.linalg.norm(vector_ecef))
        if not math.isfinite(length) or length <= 0.0:
            raise Phase2RunnerError("post-native HPPOSECEF proxy baseline is nonfinite")
        vector_ned = _ecef_vector_to_ned(vector_ecef, receiver)
        proxy_heading, proxy_elevation, proxy_body_yaw = _baseline_angles(vector_ned)
        formal_ecef = None
        if dd.get("baseline_ecef_m"):
            formal_ecef = np.asarray(_json_cell(dd["baseline_ecef_m"]), dtype=float)
        angle = None
        if formal_ecef is not None and formal_ecef.shape == (3,):
            cosine = float(np.dot(formal_ecef, vector_ecef) / (
                np.linalg.norm(formal_ecef) * np.linalg.norm(vector_ecef)
            ))
            angle = math.degrees(math.acos(float(np.clip(cosine, -1.0, 1.0))))
        production_objective = None
        proxy_objective = None
        tolerance = None
        materially_lower = False
        native_minus_proxy_heading = None
        native_minus_proxy_yaw = None
        if heading.get("method_native_accepted") == "true":
            code = np.asarray(_json_cell(dd["code_dd_m"]), dtype=float)
            phase = np.asarray(_json_cell(dd["phase_dd_m"]), dtype=float)
            design = np.asarray(_json_cell(dd["design_m_per_m"]), dtype=float)
            covariance = np.asarray(_json_cell(dd["covariance_code_phase_m2"]), dtype=float)
            model = adapt_metric_double_differences(
                code_m=code, phase_m=phase, design_m_per_m=design,
                covariance_code_phase_m2=covariance,
                wavelength_m=float(dd["gps_l1_wavelength_m"]),
                baseline_length_m=BASELINE_LENGTH_M,
            )
            production_objective = float(heading["constrained_objective"])
            proxy_objective = float(wrapped_objective(model, vector_ecef / length))
            tolerance = max(
                1.0e-9,
                1.0e-9 * max(1.0, abs(production_objective), abs(proxy_objective)),
            )
            materially_lower = proxy_objective < production_objective - tolerance
            native_minus_proxy_heading = _wrap180(
                float(heading["baseline_heading_deg"]) - proxy_heading
            )
            native_minus_proxy_yaw = _wrap180(
                float(heading["body_yaw_deg"]) - proxy_body_yaw
            )
        rows.append({
            **base, "proxy_status": "AVAILABLE_DESCRIPTIVE_ONLY",
            "proxy_baseline_ecef_m": vector_ecef.tolist(),
            "proxy_baseline_ned_m": vector_ned.tolist(),
            "proxy_length_m": length, "proxy_heading_deg": proxy_heading,
            "proxy_elevation_deg": proxy_elevation,
            "proxy_body_yaw_deg": proxy_body_yaw,
            "native_proxy_vector_angle_deg": angle,
            "native_minus_proxy_heading_wrapsafe_deg": native_minus_proxy_heading,
            "native_minus_proxy_body_yaw_wrapsafe_deg": native_minus_proxy_yaw,
            "production_objective": production_objective,
            "proxy_objective": proxy_objective,
            "proxy_minus_production_objective": (
                None if proxy_objective is None else proxy_objective - production_objective
            ),
            "materiality_tolerance": tolerance,
            "proxy_materially_lower": materially_lower,
            "oracle_gated_epoch": index in ORACLE_INDICES,
        })
    decode_count = len(epochs1) + len(epochs2)
    return rows, decode_count


def _locked_trace_bytes(paths: Phase2Paths) -> tuple[bytes, str]:
    rows = _raw_hash_lock_rows(paths.raw_hash_lock)
    try:
        relative = paths.trace.relative_to(paths.raw_root).as_posix()
    except ValueError as exc:
        raise Phase2RunnerError("trace lies outside configured raw_root") from exc
    locked = rows.get(relative)
    if locked is None:
        raise Phase2RunnerError("trace is absent from the raw hash lock")
    payload = paths.trace.read_bytes()  # exactly one post-freeze trace open
    digest = hashlib.sha256(payload).hexdigest()
    if digest != locked["sha256"] or len(payload) != int(locked["size_bytes"]):
        raise Phase2RunnerError("post-native trace hash-lock mismatch")
    return payload, digest


def _trace_reference(
    trace_payload: bytes,
    headings: Sequence[Mapping[str, str]],
    *,
    leap_seconds: int,
) -> list[dict[str, Any]]:
    if (
        not isinstance(leap_seconds, int)
        or isinstance(leap_seconds, bool)
        or leap_seconds != EXPECTED_GPS_UTC_LEAP_SECONDS
    ):
        raise Phase2RunnerError("fixed trace evaluator received unverified leap seconds")
    reader = csv.DictReader(io.StringIO(trace_payload.decode("utf-8-sig")))
    fieldnames = reader.fieldnames
    if fieldnames != list(TRACE_CSV_COLUMNS):
        raise Phase2RunnerError(
            "fixed trace evaluator requires exact columns "
            f"{TRACE_CSV_COLUMNS}; timestamp is not accepted"
        )
    raw = list(reader)
    times = np.asarray([float(row["time"]) for row in raw], dtype=float)
    yaw_enu = np.asarray([float(row["yaw"]) for row in raw], dtype=float)
    if (
        times.size < 2 or np.any(~np.isfinite(times)) or np.any(~np.isfinite(yaw_enu))
        or np.any(np.diff(times) <= 0.0)
    ):
        raise Phase2RunnerError("fixed trace time/yaw stream is invalid")
    base_time = 1772784000.0
    lower, upper = base_time + 66.0, base_time + 340.0
    # The frozen evaluator unwraps the complete validated trace before any
    # native-epoch window gate.  The 66..340 s gate applies to native epochs;
    # each matched epoch must additionally be bracketed by the trace stream.
    yaw_unwrapped_deg = np.degrees(np.unwrap(np.radians(yaw_enu)))
    rows: list[dict[str, Any]] = []
    for heading in headings:
        tow = float(heading["gps_tow_seconds"])
        week = int(heading["gps_week"])
        absolute_time = (
            GPS_EPOCH_UNIX_SECONDS + week * 604800.0 + tow - leap_seconds
        )
        matched = lower <= absolute_time <= upper and times[0] <= absolute_time <= times[-1]
        reference = None
        error = None
        if matched:
            interpolated_enu = float(np.interp(absolute_time, times, yaw_unwrapped_deg))
            reference = _wrap360(90.0 - interpolated_enu)
            if heading.get("method_native_accepted") == "true":
                error = _wrap180(float(heading["body_yaw_deg"]) - reference)
        rows.append({
            "epoch_index": int(heading["epoch_index"]),
            "gps_week": week, "gps_tow_seconds": tow,
            "absolute_time_unix_seconds": absolute_time,
            "fixed_window_matched": matched,
            "trace_body_yaw_ned_deg": reference,
            "native_body_yaw_deg": (
                float(heading["body_yaw_deg"])
                if heading.get("method_native_accepted") == "true" else None
            ),
            "native_minus_trace_wrapsafe_deg": error,
            "trace_role": "FIXPOSITION_SAME_SOURCE_DESCRIPTIVE_REFERENCE_NOT_TRUTH",
            "alignment_search_used": False, "time_offset_seconds": 0.0,
            "epoch_deleted": False,
        })
    return rows


def _validated_compact_cache_leap_seconds(cache_root: Path) -> tuple[int, dict[str, Any]]:
    cache = CompactCacheReader(cache_root)
    r1 = np.asarray(cache.epochs["r1_leap"], dtype=np.int64)
    r2 = np.asarray(cache.epochs["r2_leap"], dtype=np.int64)
    if len(cache) != EXPECTED_PAIR_COUNT or r1.size != r2.size or r1.size == 0:
        raise Phase2RunnerError("compact-cache leap-second evidence is incomplete")
    values = np.unique(np.concatenate((r1, r2)))
    if values.tolist() != [EXPECTED_GPS_UTC_LEAP_SECONDS]:
        raise Phase2RunnerError(
            "compact-cache receiver leap-second evidence is inconsistent or unexpected"
        )
    return EXPECTED_GPS_UTC_LEAP_SECONDS, {
        "source": "COMPACT_CACHE_PAIRED_EPOCHS_R1_R2_LEAP_FIELDS",
        "expected_and_observed_leap_seconds": EXPECTED_GPS_UTC_LEAP_SECONDS,
        "paired_epoch_count_verified": len(cache),
        "receiver_epoch_field_count_verified": int(r1.size + r2.size),
        "all_receiver_epoch_values_identical": True,
    }


def _fractional_dd_rows(
    headings: Sequence[Mapping[str, str]],
    dd_rows: Sequence[Mapping[str, str]],
    tracking_rows: Sequence[Mapping[str, str]],
    proxy_rows: Sequence[Mapping[str, Any]],
    cache_root: Path,
) -> list[dict[str, Any]]:
    from .ext02_cwls import adapt_metric_double_differences

    rows: list[dict[str, Any]] = []
    cache = CompactCacheReader(cache_root)
    for heading, dd, tracking, proxy in zip(
        headings, dd_rows, tracking_rows, proxy_rows, strict=True,
    ):
        index = int(heading["epoch_index"])
        left_epoch, right_epoch = cache.pair(index)
        left_measurements = {identity_text(item.identity): item for item in left_epoch.measurements}
        right_measurements = {identity_text(item.identity): item for item in right_epoch.measurements}
        sub1 = int(tracking["r1_sub_half_cycle_set_count"])
        sub2 = int(tracking["r2_sub_half_cycle_set_count"])
        if sub1 and sub2:
            sub_half_class = "BOTH_RECEIVERS"
        elif sub1:
            sub_half_class = "GNSS1_ONLY"
        elif sub2:
            sub_half_class = "GNSS2_ONLY"
        else:
            sub_half_class = "NEITHER_RECEIVER"
        lock_reset = bool(
            int(tracking["r1_actual_lock_reset_count"])
            or int(tracking["r2_actual_lock_reset_count"])
        )
        cycle_slip = bool(
            int(tracking["r1_actual_cycle_slip_count"])
            or int(tracking["r2_actual_cycle_slip_count"])
        )
        dd_dimension = int(dd["dd_dimension"]) if dd.get("dd_dimension") else 0
        base = {
            "epoch_index": index, "gps_week": int(heading["gps_week"]),
            "gps_tow_seconds": float(heading["gps_tow_seconds"]),
            "phase_bias_calibration": "NONE", "descriptive_only": True,
            "pivot_identity": dd.get("pivot_identity") or None,
            "ambiguity_satellite_identities": (
                _json_cell(dd["ambiguity_signal_identities"])
                if dd.get("ambiguity_signal_identities") else []
            ),
            "sub_half_cycle_combination": sub_half_class,
            "lock_reset_present": lock_reset,
            "cycle_slip_present": cycle_slip,
            "pivot_changed": tracking["pivot_switched"] == "true",
            "dd_dimension": dd_dimension,
            "low_dd_dimension": 0 < dd_dimension <= 3,
            "low_dd_dimension_definition": "DD_DIMENSION_LE_3",
        }
        if heading.get("method_native_accepted") != "true":
            rows.append({
                **base, "status": "NATIVE_INVALID", "dd_count": 0,
                "fractional_dd_cycles": None, "mean_cycles": None,
                "rms_cycles": None, "max_abs_cycles": None,
                "proxy_implied_fractional_dd_cycles": None,
                "proxy_implied_mean_cycles": None,
                "proxy_implied_rms_cycles": None,
                "proxy_implied_max_abs_cycles": None,
                "identity_fractional_pairs": [],
            })
            continue
        code = np.asarray(_json_cell(dd["code_dd_m"]), dtype=float)
        phase = np.asarray(_json_cell(dd["phase_dd_m"]), dtype=float)
        design = np.asarray(_json_cell(dd["design_m_per_m"]), dtype=float)
        covariance = np.asarray(_json_cell(dd["covariance_code_phase_m2"]), dtype=float)
        model = adapt_metric_double_differences(
            code_m=code, phase_m=phase, design_m_per_m=design,
            covariance_code_phase_m2=covariance,
            wavelength_m=float(dd["gps_l1_wavelength_m"]),
            baseline_length_m=BASELINE_LENGTH_M,
        )
        direction = np.asarray(_json_cell(dd["baseline_direction_ecef"]), dtype=float)
        prediction = BASELINE_LENGTH_M * model.design_cycles_per_m @ direction
        raw = model.phase_cycles - prediction
        fractional = raw - np.ceil(raw - 0.5)
        identities = _json_cell(dd["ambiguity_signal_identities"])
        proxy_fractional = None
        if proxy.get("proxy_baseline_ecef_m") is not None:
            proxy_vector_ecef = np.asarray(proxy["proxy_baseline_ecef_m"], dtype=float)
            proxy_raw = model.phase_cycles - model.design_cycles_per_m @ proxy_vector_ecef
            proxy_fractional = proxy_raw - np.ceil(proxy_raw - 0.5)
        identity_rows = []
        for item_index, (identity, value) in enumerate(zip(identities, fractional, strict=True)):
            left_measurement = left_measurements.get(identity)
            right_measurement = right_measurements.get(identity)
            identity_rows.append({
                "pivot_identity": dd["pivot_identity"],
                "satellite_identity": identity,
                "production_fractional_cycles": float(value),
                "proxy_implied_fractional_cycles": (
                    None if proxy_fractional is None else float(proxy_fractional[item_index])
                ),
                "r1_subHalfCyc": (
                    None if left_measurement is None else left_measurement.half_cycle_subtracted
                ),
                "r2_subHalfCyc": (
                    None if right_measurement is None else right_measurement.half_cycle_subtracted
                ),
                "r1_locktime_ms": (
                    None if left_measurement is None else left_measurement.locktime_ms
                ),
                "r2_locktime_ms": (
                    None if right_measurement is None else right_measurement.locktime_ms
                ),
            })
        rows.append({
            **base, "status": "AVAILABLE", "dd_count": len(fractional),
            "fractional_dd_cycles": fractional.tolist(),
            "proxy_implied_fractional_dd_cycles": (
                None if proxy_fractional is None else proxy_fractional.tolist()
            ),
            "proxy_implied_mean_cycles": (
                None if proxy_fractional is None else float(np.mean(proxy_fractional))
            ),
            "proxy_implied_rms_cycles": (
                None if proxy_fractional is None
                else float(np.sqrt(np.mean(proxy_fractional**2)))
            ),
            "proxy_implied_max_abs_cycles": (
                None if proxy_fractional is None else float(np.max(np.abs(proxy_fractional)))
            ),
            "identity_fractional_pairs": identity_rows,
            "mean_cycles": float(np.mean(fractional)),
            "rms_cycles": float(np.sqrt(np.mean(fractional**2))),
            "max_abs_cycles": float(np.max(np.abs(fractional))),
        })
    return rows


def _circular_cycle_statistics(values: Sequence[float]) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    array = array[np.isfinite(array)]
    if array.size == 0:
        return {"count": 0, "circular_mean_cycles": None,
                "resultant_length": None, "circular_scatter_cycles": None}
    angles = 2.0 * math.pi * array
    mean_sine = float(np.mean(np.sin(angles)))
    mean_cosine = float(np.mean(np.cos(angles)))
    resultant = math.hypot(mean_sine, mean_cosine)
    mean = math.atan2(mean_sine, mean_cosine) / (2.0 * math.pi)
    if mean <= -0.5:
        mean += 1.0
    scatter = (
        math.sqrt(max(0.0, -2.0 * math.log(resultant))) / (2.0 * math.pi)
        if resultant > 0.0 else None
    )
    return {
        "count": int(array.size), "circular_mean_cycles": mean,
        "resultant_length": resultant, "circular_scatter_cycles": scatter,
    }


def _fractional_group_statistics(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    stable: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    strata: dict[str, dict[str, Any]] = {}

    def add_stratum(name: str, epoch_index: int, production: Sequence[float], proxy: Sequence[float]) -> None:
        entry = strata.setdefault(name, {"epochs": set(), "production": [], "proxy": []})
        entry["epochs"].add(epoch_index)
        entry["production"].extend(float(item) for item in production)
        entry["proxy"].extend(float(item) for item in proxy)

    for row in rows:
        if row["status"] != "AVAILABLE":
            continue
        index = int(row["epoch_index"])
        production = [float(item) for item in row["fractional_dd_cycles"]]
        proxy = (
            [] if row["proxy_implied_fractional_dd_cycles"] is None
            else [float(item) for item in row["proxy_implied_fractional_dd_cycles"]]
        )
        labels = (
            f"subHalfCyc={row['sub_half_cycle_combination']}",
            f"lock_reset={str(bool(row['lock_reset_present'])).lower()}",
            f"cycle_slip={str(bool(row['cycle_slip_present'])).lower()}",
            f"pivot_changed={str(bool(row['pivot_changed'])).lower()}",
            f"low_dd_dimension={str(bool(row['low_dd_dimension'])).lower()}",
        )
        for label in labels:
            add_stratum(label, index, production, proxy)
        for identity_row in row["identity_fractional_pairs"]:
            key = (
                str(identity_row["pivot_identity"]),
                str(identity_row["satellite_identity"]),
                str(identity_row["r1_subHalfCyc"]),
                str(identity_row["r2_subHalfCyc"]),
            )
            entry = stable.setdefault(key, {"epochs": [], "production": [], "proxy": []})
            entry["epochs"].append(index)
            entry["production"].append(float(identity_row["production_fractional_cycles"]))
            if identity_row["proxy_implied_fractional_cycles"] is not None:
                entry["proxy"].append(float(identity_row["proxy_implied_fractional_cycles"]))
    stable_rows = []
    for (pivot, satellite, r1_state, r2_state), entry in sorted(stable.items()):
        stable_rows.append({
            "pivot_identity": pivot, "satellite_identity": satellite,
            "r1_subHalfCyc": r1_state, "r2_subHalfCyc": r2_state,
            "epoch_count": len(set(entry["epochs"])),
            "observation_count": len(entry["production"]),
            "first_epoch_index": min(entry["epochs"]),
            "last_epoch_index": max(entry["epochs"]),
            "persistent_multiple_epochs": len(set(entry["epochs"])) >= 2,
            "production_fractional_circular": _circular_cycle_statistics(entry["production"]),
            "proxy_implied_fractional_circular": _circular_cycle_statistics(entry["proxy"]),
        })
    stratum_rows = {}
    for name, entry in sorted(strata.items()):
        stratum_rows[name] = {
            "epoch_count": len(entry["epochs"]),
            "production_observation_count": len(entry["production"]),
            "proxy_observation_count": len(entry["proxy"]),
            "production_linear": _numeric_statistics(entry["production"]),
            "production_circular": _circular_cycle_statistics(entry["production"]),
            "proxy_linear": _numeric_statistics(entry["proxy"]),
            "proxy_circular": _circular_cycle_statistics(entry["proxy"]),
        }
    return {
        "stable_satellite_pivot_subHalfCyc_groups": stable_rows,
        "stratified_tracking_and_dimension_statistics": stratum_rows,
        "phase_bias_calibration": "NONE",
        "role": "POST_NATIVE_DESCRIPTIVE_ONLY_NO_CORRECTION_OR_SELECTION",
    }


PROXY_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "proxy_source", "rawx_itow_ms",
    "proxy_itow_ms", "proxy_itow_minus_rawx_ms",
    "proxy_local_common_grid_cadence_ms", "proxy_local_half_cadence_bound_ms",
    "proxy_association_policy", "proxy_association_status",
    "proxy_status", "proxy_baseline_ecef_m", "proxy_baseline_ned_m",
    "proxy_length_m", "proxy_heading_deg", "proxy_elevation_deg",
    "proxy_body_yaw_deg", "native_proxy_vector_angle_deg", "production_objective",
    "native_minus_proxy_heading_wrapsafe_deg",
    "native_minus_proxy_body_yaw_wrapsafe_deg",
    "proxy_objective", "proxy_minus_production_objective", "materiality_tolerance",
    "proxy_materially_lower", "oracle_gated_epoch",
)
POST_OBJECTIVE_FIELDS = (
    "epoch_index", "formal_objective", "native_oracle_objective", "proxy_objective",
    "proxy_minus_formal", "materiality_tolerance", "proxy_materially_lower",
    "oracle_gated_epoch",
)
TRACE_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "absolute_time_unix_seconds",
    "fixed_window_matched", "trace_body_yaw_ned_deg", "native_body_yaw_deg",
    "native_minus_trace_wrapsafe_deg", "trace_role", "alignment_search_used",
    "time_offset_seconds", "epoch_deleted",
)
FRACTIONAL_FIELDS = (
    "epoch_index", "gps_week", "gps_tow_seconds", "phase_bias_calibration",
    "descriptive_only", "pivot_identity", "ambiguity_satellite_identities",
    "sub_half_cycle_combination", "lock_reset_present", "cycle_slip_present",
    "pivot_changed", "dd_dimension", "low_dd_dimension",
    "low_dd_dimension_definition", "status", "dd_count",
    "fractional_dd_cycles", "proxy_implied_fractional_dd_cycles",
    "identity_fractional_pairs", "mean_cycles", "rms_cycles", "max_abs_cycles",
    "proxy_implied_mean_cycles", "proxy_implied_rms_cycles",
    "proxy_implied_max_abs_cycles",
)


def _write_report_and_status(
    paths: Phase2Paths,
    *,
    destinations: PostNativeDestinations,
    terminal_status: str,
    summary: Mapping[str, Any],
    post_manifest: Mapping[str, Any],
) -> None:
    if _path_lexists(destinations.report) or _path_lexists(destinations.status):
        raise Phase2RunnerError("final Phase-2 report/status already exists")
    contract = load_phase2_contract()
    native_stats = summary["native_descriptive_statistics"]
    aggregates = post_manifest["descriptive_aggregates"]
    fractional_groups = aggregates["fractional_dd_tracking_identity_groups"]
    formal_invocation = (
        "python3 scripts/paper_rebuild/run_horizontal_literature_phase2.py "
        "--paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml "
        "--method-id EXT02_CWLS --case-id C00 "
        "--trace-mode disabled --workers 16"
    )
    recovery_suffix = (
        "" if destinations.recovery_id is None
        else f" --post-recovery-id {destinations.recovery_id}"
    )
    post_only_recovery_invocation = (
        "python3 scripts/paper_rebuild/run_horizontal_literature_phase2.py "
        "--paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml "
        "--mode post-native-diagnostics --method-id EXT02_CWLS --case-id C00 "
        f"--trace-mode disabled --workers 16{recovery_suffix}"
    )
    lines = [
        "# Phase 2 EXT02 C-WLS C00 report"
        + (
            "" if destinations.recovery_id is None
            else f" — post recovery {destinations.recovery_id}"
        ),
        "",
        f"Terminal: `{terminal_status}`.",
        "",
        "This is a faithful-algorithm reproduction and BY2 C00 applicability result, "
        "not a paper claim or an independent-ground-truth evaluation.",
        "",
        f"Paired epochs: {summary['paired_epoch_count']}; accepted wrapped solutions: "
        f"{summary['success_row_count']}; explicit failures: {summary['failure_row_count']}.",
        f"Accepted coverage: {summary['native_descriptive_statistics']['accepted_coverage']}; "
        f"maximum baseline-norm error: "
        f"{summary['native_descriptive_statistics']['baseline_length_hard_constraint']['maximum_absolute_norm_error_m']} m.",
        f"Unique candidate-count median: "
        f"{summary['native_descriptive_statistics']['unique_candidate_count']['median']}; "
        f"runtime median: {summary['native_descriptive_statistics']['runtime_seconds']['median']} s.",
        "Ambiguity correctness is unknown; ambiguity success/fixed/float rates are NA.",
        "",
        "Native outputs were hash-frozen with zero trace and NAV-HPPOSECEF semantic opens. "
        "Only after revalidation were HPPOSECEF and the fixed same-source trace opened "
        "for descriptive diagnostics. Native outputs were not mutated or substituted.",
        "Post-native open/decode counters in this report cover this successful invocation "
        "only; prior failed post-native attempts are explicitly excluded and must be "
        "accounted for in lifecycle recovery evidence.",
        f"Successful invocation HPPOSECEF receiver-stream decode passes/semantic records: "
        f"{post_manifest['successful_post_native_invocation_hpposecef_decode_pass_count']}/"
        f"{post_manifest['successful_post_native_invocation_hpposecef_semantic_decode_count']}; "
        f"trace opens: {post_manifest['successful_post_native_invocation_trace_open_count']}.",
        "",
        f"Proxy materially-lower eligible accepted epochs: "
        f"{post_manifest['proxy_materially_lower_eligible_accepted_epochs']}.",
        f"Proxy availability: {post_manifest['descriptive_aggregates']['proxy_available_count']}/"
        f"{summary['paired_epoch_count']}; trace/native matched accepted count: "
        f"{post_manifest['descriptive_aggregates']['trace_native_yaw_error_deg']['matched_count']}.",
        f"Independent oracle evaluated: {summary['objective_oracle_evaluated_count']}/"
        f"{summary['objective_oracle_selected_count']} selected input-only epochs; "
        f"proxy objective evaluated: {post_manifest['proxy_objective_evaluated_count']} "
        "eligible accepted epochs.",
        f"Applicability classification: `{post_manifest['applicability_classification']}`; "
        "zero availability is validated poor applicability, not automatic unsupported status.",
        "",
        "Trace conversion is fixed to unwrap ENU yaw, interpolate at absolute solver "
        "time, then wrap360(90-yaw); no search, alignment, offset, or epoch deletion was used.",
        "",
        "## Paper, source, and equation identity",
        "",
        "```json",
        json.dumps({
            "paper_source": contract["paper_source"],
            "equation_map": contract["equation_map"],
            "formal_reproduction_level": contract["formal_reproduction_level"],
            "native_runtime_source_provenance": {
                "code_commit": summary["code_commit"],
                "code_commit_role": summary["code_commit_role"],
                "source_fingerprint": post_manifest["native_source_fingerprint"],
                "runtime_source_hashes": summary["runtime_source_hashes"],
                "git_source_state": summary["git_source_state"],
            },
            "post_native_runtime_source_provenance": {
                "code_commit": post_manifest["post_native_code_commit"],
                "source_fingerprint": post_manifest[
                    "post_native_source_fingerprint"
                ],
                "runtime_source_hashes": post_manifest[
                    "post_native_runtime_source_hashes"
                ],
                "git_source_state": post_manifest["post_native_git_source_state"],
                "diverged_from_native_for_post_only_code": post_manifest[
                    "post_only_source_fingerprint_diverged_from_native"
                ],
            },
        }, indent=2, sort_keys=True, ensure_ascii=False),
        "```",
        "",
        "## GPS-L1 eligibility and native failure accounting",
        "",
        "```json",
        json.dumps({
            "gps_l1_dd_stage_counts": native_stats["gps_l1_dd_stage_counts"],
            "failure_code_counts": native_stats["failure_code_counts"],
            "accepted_coverage": native_stats["accepted_coverage"],
            "accepted_continuity": native_stats["accepted_continuity"],
            "baseline": native_stats["baseline_length_hard_constraint"],
            "heading": native_stats["baseline_heading_wrapaware_deg"],
            "body_yaw": native_stats["body_yaw_wrapaware_deg"],
            "elevation": native_stats["baseline_elevation_deg"],
        }, indent=2, sort_keys=True),
        "```",
        "",
        "## Candidate, refinement, oracle, and runtime evidence",
        "",
        "K policy is `ALL_UNIQUE_CANDIDATES`; no best-K truncation was used.",
        "",
        "```json",
        json.dumps({
            "candidate_and_refinement_statistics": {
                key: value for key, value in native_stats.items()
                if any(token in key for token in (
                    "candidate", "circle", "phase_row", "tangent", "degenerate",
                    "refinement", "objective",
                ))
            },
            "objective_oracle_indices": summary["objective_oracle_indices"],
            "objective_oracle_selected_count": summary["objective_oracle_selected_count"],
            "objective_oracle_evaluated_count": summary["objective_oracle_evaluated_count"],
            "objective_oracle_not_evaluated_count": summary[
                "objective_oracle_not_evaluated_count"
            ],
            "objective_oracle_all_comparisons_pass": (
                summary["objective_oracle_all_comparisons_pass"]
            ),
            "runtime_seconds": native_stats["runtime_seconds"],
            "worker_max_rss_bytes": native_stats["worker_max_rss_bytes"],
            "workers_1_vs_16_and_resources": summary["determinism_probe"],
        }, indent=2, sort_keys=True),
        "```",
        "",
        "## Post-native proxy and fixed-trace metrics",
        "",
        "```json",
        json.dumps({
            "proxy_length_m": aggregates["proxy_length_m"],
            "native_proxy_vector_angle_deg": aggregates["native_proxy_vector_angle_deg"],
            "native_minus_proxy_heading_wrapsafe": (
                aggregates["native_minus_proxy_heading_wrapsafe"]
            ),
            "native_minus_proxy_body_yaw_wrapsafe": (
                aggregates["native_minus_proxy_body_yaw_wrapsafe"]
            ),
            "proxy_minus_production_objective": (
                aggregates["proxy_minus_production_objective"]
            ),
            "proxy_objective_evaluated_count": aggregates[
                "proxy_objective_evaluated_count"
            ],
            "oracle_gated_proxy_objective_evaluated_count": aggregates[
                "oracle_gated_proxy_objective_evaluated_count"
            ],
            "trace_native_yaw_error_deg": aggregates["trace_native_yaw_error_deg"],
            "fixed_evaluator_contract": post_manifest["fixed_evaluator_contract"],
        }, indent=2, sort_keys=True),
        "```",
        "",
        "## Fractional-DD descriptive relationships",
        "",
        "No phase-bias calibration, correction, selection, or substitution was applied.",
        "",
        "```json",
        json.dumps({
            "production_epoch_rms": aggregates["fractional_dd_epoch_rms_cycles"],
            "proxy_implied_epoch_rms": aggregates[
                "proxy_implied_fractional_dd_epoch_rms_cycles"
            ],
            "relationships": aggregates["fractional_dd_relationships"],
            "stratified_tracking_and_dimension_statistics": fractional_groups[
                "stratified_tracking_and_dimension_statistics"
            ],
            "stable_group_count": len(
                fractional_groups["stable_satellite_pivot_subHalfCyc_groups"]
            ),
        }, indent=2, sort_keys=True),
        "```",
        "",
        "## Paths and reproduction",
        "",
        f"- Native root: `{paths.native_root}`",
        f"- Native freeze: `{paths.native_files['native_freeze']}`",
        f"- Post-native manifest: "
        f"`{destinations.post_native_files['post_native_manifest']}`",
        f"- Report: `{destinations.report}`",
        f"- Status: `{destinations.status}`",
        "- Exact formal invocation (default `full`; produced the frozen native C00 "
        f"before its post-native failure): `{formal_invocation}`",
        "- Exact post-only recovery invocation (separate source fingerprint; produces "
        f"post-native outputs only): `{post_only_recovery_invocation}`",
        "",
        "## Explicit non-use and scope boundary",
        "",
        "EXT01 code/output, status baseline/yaw, Go2 yaw, receiver IMU, RTKLIB ordinary "
        "position output, final_v23 output, LegSA output, trace online input, and "
        "NAV-HPPOSECEF native input were not used. EXT03/EXT04, Classic-18, the common "
        "backbone, Canonical-541, per-case tuning, output-only correction, and "
        "metric-driven epoch deletion remain out of scope.",
    ]
    _atomic_write_bytes(destinations.report, ("\n".join(lines) + "\n").encode("utf-8"))
    status = {
        "schema_version": "horizontal_literature.phase2.status.v1",
        "terminal_status": terminal_status, "method_id": METHOD_ID, "case_id": CASE_ID,
        "ready_for_paper_claims": False,
        "native_freeze_sha256": _sha256_file(
            paths.native_files["native_freeze"]
        ),
        "post_native_manifest_sha256": _sha256_file(
            destinations.post_native_files["post_native_manifest"]
        ),
        "post_recovery_id": destinations.recovery_id,
        "post_output_root": str(destinations.output_root),
        "supersedes_for_proxy_diagnostics_only": post_manifest[
            "supersedes_for_proxy_diagnostics_only"
        ],
        "native_source_fingerprint": post_manifest["native_source_fingerprint"],
        "post_native_source_fingerprint": post_manifest[
            "post_native_source_fingerprint"
        ],
        "post_only_source_fingerprint_diverged_from_native": post_manifest[
            "post_only_source_fingerprint_diverged_from_native"
        ],
        "successful_post_native_invocation_attempt_count": post_manifest[
            "successful_post_native_invocation_attempt_count"
        ],
        "successful_post_native_invocation_hpposecef_decode_pass_count": post_manifest[
            "successful_post_native_invocation_hpposecef_decode_pass_count"
        ],
        "successful_post_native_invocation_hpposecef_decode_pass_count_unit": (
            post_manifest[
                "successful_post_native_invocation_hpposecef_decode_pass_count_unit"
            ]
        ),
        "successful_post_native_invocation_hpposecef_semantic_decode_count": (
            post_manifest[
                "successful_post_native_invocation_hpposecef_semantic_decode_count"
            ]
        ),
        "successful_post_native_invocation_trace_open_count": post_manifest[
            "successful_post_native_invocation_trace_open_count"
        ],
        "prior_failed_post_native_attempts_not_in_successful_invocation_counts": True,
        "paired_epoch_count": summary["paired_epoch_count"],
        "success_row_count": summary["success_row_count"],
        "failure_row_count": summary["failure_row_count"],
        "objective_oracle_evaluated_count": summary["objective_oracle_evaluated_count"],
        "proxy_objective_evaluated_count": post_manifest[
            "proxy_objective_evaluated_count"
        ],
        "applicability_classification": post_manifest["applicability_classification"],
        "ambiguity_correctness_known": False,
        "ambiguity_success_rate": "NA", "fixed_rate": "NA", "float_rate": "NA",
        "trace_used_online": False, "old_runtime_input_count": 0,
    }
    _atomic_write_json(destinations.status, status)


def _post_evaluation_counts(
    headings: Sequence[Mapping[str, Any]],
    proxy_rows: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    accepted_count = sum(row.get("method_native_accepted") == "true" for row in headings)
    evaluated = [
        row for row in proxy_rows
        if row.get("production_objective") is not None and row.get("proxy_objective") is not None
    ]
    oracle_gated_accepted_count = sum(
        row.get("method_native_accepted") == "true"
        and int(row["epoch_index"]) in ORACLE_INDICES
        for row in headings
    )
    return {
        "accepted_count": accepted_count,
        "proxy_objective_eligible_accepted_count": len(evaluated),
        "proxy_objective_evaluated_count": len(evaluated),
        "proxy_objective_not_evaluated_accepted_count": accepted_count - len(evaluated),
        "oracle_gated_accepted_count": oracle_gated_accepted_count,
        "oracle_gated_proxy_objective_evaluated_count": sum(
            bool(row.get("oracle_gated_epoch")) for row in evaluated
        ),
    }


def _post_native_source_identity(
    preflight: PreflightResult,
    freeze: Mapping[str, Any],
    native_summary: Mapping[str, Any],
) -> dict[str, Any]:
    freeze_fingerprint = freeze.get("source_fingerprint")
    summary_fingerprint = native_summary.get("source_fingerprint")
    if (
        not isinstance(freeze_fingerprint, str)
        or len(freeze_fingerprint) != 64
        or not isinstance(summary_fingerprint, str)
        or summary_fingerprint != freeze_fingerprint
    ):
        raise Phase2RunnerError(
            "native freeze and native summary source fingerprints do not match"
        )
    freeze_commit = freeze.get("code_commit")
    summary_commit = native_summary.get("code_commit")
    if freeze_commit != summary_commit:
        raise Phase2RunnerError(
            "native freeze and native summary base-HEAD identities do not match"
        )
    return {
        "native_source_fingerprint": freeze_fingerprint,
        "native_source_fingerprint_verified_against_native_summary": True,
        "native_code_commit": summary_commit,
        "native_runtime_source_hashes": dict(
            native_summary.get("runtime_source_hashes", {})
        ),
        "post_native_source_fingerprint": preflight.source_fingerprint,
        "post_native_code_commit": preflight.code_commit,
        "post_native_runtime_source_hashes": dict(preflight.runtime_source_hashes),
        "post_native_git_source_state": dict(preflight.git_source_state),
        "post_only_source_fingerprint_diverged_from_native": (
            preflight.source_fingerprint != freeze_fingerprint
        ),
        "compact_cache_validation_fingerprint_role": "NATIVE_SOURCE_FINGERPRINT",
    }


def _validate_post_native_compact_cache(
    paths: Phase2Paths,
    source_identity: Mapping[str, Any],
) -> dict[str, Any]:
    return validate_compact_cache(
        paths.native_root / "COMPACT_CACHE",
        source_fingerprint=str(source_identity["native_source_fingerprint"]),
        expected_pair_count=EXPECTED_PAIR_COUNT,
    )


def _successful_post_native_invocation_accounting(
    hpposecef_semantic_decode_count: int,
) -> dict[str, Any]:
    if (
        not isinstance(hpposecef_semantic_decode_count, int)
        or isinstance(hpposecef_semantic_decode_count, bool)
        or hpposecef_semantic_decode_count < 0
    ):
        raise Phase2RunnerError("post-native HPPOSECEF semantic decode count is invalid")
    return {
        "successful_post_native_invocation_attempt_count": 1,
        "successful_post_native_invocation_hpposecef_decode_pass_count": 2,
        "successful_post_native_invocation_hpposecef_decode_pass_count_unit": (
            "GNSS_RECEIVER_STREAM"
        ),
        "successful_post_native_invocation_hpposecef_semantic_decode_count": (
            hpposecef_semantic_decode_count
        ),
        "successful_post_native_invocation_trace_open_count": 1,
        "prior_failed_post_native_attempts_not_in_successful_invocation_counts": True,
    }


def run_post_native_diagnostics(
    preflight: PreflightResult,
    *,
    post_recovery_id: str | None = None,
) -> dict[str, Any]:
    paths = preflight.paths
    destinations = _post_native_destinations(paths, post_recovery_id)
    if destinations.is_recovery:
        _validate_recovery_targets_absent(destinations)
    prior_post_inventory = (
        _primary_post_inventory(paths) if destinations.is_recovery else None
    )
    freeze = validate_native_freeze(paths.native_root)
    post_paths = dict(destinations.post_native_files)
    existing = [path.name for path in post_paths.values() if path.exists()]
    if existing:
        raise Phase2RunnerError(f"post-native output already exists: {existing}")
    summary = json.loads(paths.native_files["native_summary"].read_text(encoding="utf-8"))
    source_identity = _post_native_source_identity(preflight, freeze, summary)
    headings = _read_csv_rows(paths.native_files["heading_results"])
    dd_rows = _read_csv_rows(paths.native_files["dd_diagnostics"])
    oracle_rows = _read_csv_rows(paths.native_files["objective_oracle_diagnostics"])
    tracking_native_rows = _read_csv_rows(paths.native_files["tracking_diagnostics"])
    if not len(headings) == len(dd_rows) == len(oracle_rows) == len(
        tracking_native_rows
    ) == EXPECTED_PAIR_COUNT:
        raise Phase2RunnerError("post-native input row conservation failed")
    # Reject a cache/source mismatch before opening either diagnostic source.
    _validate_post_native_compact_cache(paths, source_identity)
    leap_seconds, leap_second_evidence = _validated_compact_cache_leap_seconds(
        paths.native_root / "COMPACT_CACHE"
    )
    # Revalidate immediately before opening the first diagnostic source.
    validate_native_freeze(paths.native_root)
    proxy_rows, hpposecef_decode_count = _hpposecef_proxy_rows(paths, headings, dd_rows)
    invocation_accounting = _successful_post_native_invocation_accounting(
        hpposecef_decode_count
    )
    # Revalidate again before the trace is opened exactly once.
    validate_native_freeze(paths.native_root)
    trace_payload, trace_hash = _locked_trace_bytes(paths)
    trace_rows = _trace_reference(
        trace_payload, headings, leap_seconds=leap_seconds,
    )
    # The compact cache is native evidence.  Revalidate it immediately before
    # post-native fractional use against the immutable native identity, even
    # when the current post-only source fingerprint legitimately differs.
    _validate_post_native_compact_cache(paths, source_identity)
    fractional_rows = _fractional_dd_rows(
        headings, dd_rows, tracking_native_rows, proxy_rows,
        paths.native_root / "COMPACT_CACHE",
    )
    objective_rows = []
    for oracle, proxy in zip(oracle_rows, proxy_rows, strict=True):
        formal = float(oracle["formal_objective"]) if oracle.get("formal_objective") else None
        oracle_value = float(oracle["oracle_objective"]) if oracle.get("oracle_objective") else None
        objective_rows.append({
            "epoch_index": int(proxy["epoch_index"]), "formal_objective": formal,
            "native_oracle_objective": oracle_value,
            "proxy_objective": proxy["proxy_objective"],
            "proxy_minus_formal": (
                None if proxy["proxy_objective"] is None or formal is None
                else proxy["proxy_objective"] - formal
            ),
            "materiality_tolerance": proxy["materiality_tolerance"],
            "proxy_materially_lower": proxy["proxy_materially_lower"],
            "oracle_gated_epoch": proxy["oracle_gated_epoch"],
        })
    trace_by_index = {int(row["epoch_index"]): row for row in trace_rows}
    proxy_by_index = {int(row["epoch_index"]): row for row in proxy_rows}
    heading_by_index = {int(row["epoch_index"]): row for row in headings}
    fractional_by_index = {int(row["epoch_index"]): row for row in fractional_rows}
    relationship_values: dict[str, tuple[list[float], list[float]]] = {
        "fractional_rms_vs_native_objective": ([], []),
        "fractional_rms_vs_unique_candidate_count": ([], []),
        "fractional_rms_vs_proxy_vector_angle": ([], []),
        "fractional_rms_vs_abs_trace_yaw_error": ([], []),
        "proxy_objective_gap_vs_vector_angle": ([], []),
    }
    for index in range(EXPECTED_PAIR_COUNT):
        fractional = fractional_by_index[index]
        heading = heading_by_index[index]
        proxy = proxy_by_index[index]
        trace = trace_by_index[index]
        if fractional["rms_cycles"] is not None and heading.get("constrained_objective") not in (None, ""):
            relationship_values["fractional_rms_vs_native_objective"][0].append(
                float(fractional["rms_cycles"])
            )
            relationship_values["fractional_rms_vs_native_objective"][1].append(
                float(heading["constrained_objective"])
            )
        if fractional["rms_cycles"] is not None and heading.get("unique_candidate_count") not in (None, ""):
            relationship_values["fractional_rms_vs_unique_candidate_count"][0].append(
                float(fractional["rms_cycles"])
            )
            relationship_values["fractional_rms_vs_unique_candidate_count"][1].append(
                float(heading["unique_candidate_count"])
            )
        if fractional["rms_cycles"] is not None and proxy["native_proxy_vector_angle_deg"] is not None:
            relationship_values["fractional_rms_vs_proxy_vector_angle"][0].append(
                float(fractional["rms_cycles"])
            )
            relationship_values["fractional_rms_vs_proxy_vector_angle"][1].append(
                float(proxy["native_proxy_vector_angle_deg"])
            )
        if fractional["rms_cycles"] is not None and trace["native_minus_trace_wrapsafe_deg"] is not None:
            relationship_values["fractional_rms_vs_abs_trace_yaw_error"][0].append(
                float(fractional["rms_cycles"])
            )
            relationship_values["fractional_rms_vs_abs_trace_yaw_error"][1].append(
                abs(float(trace["native_minus_trace_wrapsafe_deg"]))
            )
        if (
            proxy["proxy_minus_production_objective"] is not None
            and proxy["native_proxy_vector_angle_deg"] is not None
        ):
            relationship_values["proxy_objective_gap_vs_vector_angle"][0].append(
                float(proxy["proxy_minus_production_objective"])
            )
            relationship_values["proxy_objective_gap_vs_vector_angle"][1].append(
                float(proxy["native_proxy_vector_angle_deg"])
            )
    evaluation_counts = _post_evaluation_counts(headings, proxy_rows)
    accepted_count = evaluation_counts["accepted_count"]
    trace_error_rows = [
        row for row in trace_rows if row["native_minus_trace_wrapsafe_deg"] is not None
    ]
    proxy_heading_error_rows = [
        row for row in proxy_rows
        if row["native_minus_proxy_heading_wrapsafe_deg"] is not None
    ]
    proxy_yaw_error_rows = [
        row for row in proxy_rows
        if row["native_minus_proxy_body_yaw_wrapsafe_deg"] is not None
    ]
    proxy_objective_rows = [
        row for row in proxy_rows
        if row["production_objective"] is not None and row["proxy_objective"] is not None
    ]
    oracle_gated_proxy_objective_rows = [
        row for row in proxy_objective_rows if row["oracle_gated_epoch"]
    ]
    fixed_window_input_count = sum(bool(row["fixed_window_matched"]) for row in trace_rows)
    association_statuses = sorted({
        str(row["proxy_association_status"]) for row in proxy_rows
    })
    descriptive_aggregates = {
        "proxy_available_count": sum(
            row["proxy_status"] == "AVAILABLE_DESCRIPTIVE_ONLY" for row in proxy_rows
        ),
        "proxy_association_policy": PROXY_ASSOCIATION_POLICY,
        "proxy_association_status_counts": {
            status: sum(
                row["proxy_association_status"] == status for row in proxy_rows
            )
            for status in association_statuses
        },
        "proxy_itow_minus_rawx_ms": _numeric_statistics(
            float(row["proxy_itow_minus_rawx_ms"])
            for row in proxy_rows
            if row["proxy_association_status"]
            == "ASSOCIATED_UNIQUE_NEAREST_COMMON_ITOW"
        ),
        "proxy_objective_eligible_accepted_count": evaluation_counts[
            "proxy_objective_eligible_accepted_count"
        ],
        "proxy_objective_evaluated_count": evaluation_counts[
            "proxy_objective_evaluated_count"
        ],
        "proxy_objective_not_evaluated_accepted_count": evaluation_counts[
            "proxy_objective_not_evaluated_accepted_count"
        ],
        "oracle_gated_accepted_count": evaluation_counts["oracle_gated_accepted_count"],
        "oracle_gated_proxy_objective_evaluated_count": evaluation_counts[
            "oracle_gated_proxy_objective_evaluated_count"
        ],
        "proxy_length_m": _numeric_statistics(
            float(row["proxy_length_m"]) for row in proxy_rows if row["proxy_length_m"] is not None
        ),
        "native_proxy_vector_angle_deg": _numeric_statistics(
            float(row["native_proxy_vector_angle_deg"])
            for row in proxy_rows if row["native_proxy_vector_angle_deg"] is not None
        ),
        "native_minus_proxy_heading_wrapsafe": _wrapsafe_error_metrics(
            [float(row["native_minus_proxy_heading_wrapsafe_deg"]) for row in proxy_heading_error_rows],
            [int(row["epoch_index"]) for row in proxy_heading_error_rows],
            [float(row["gps_tow_seconds"]) for row in proxy_heading_error_rows],
            valid_denominator=accepted_count,
        ),
        "native_minus_proxy_body_yaw_wrapsafe": _wrapsafe_error_metrics(
            [float(row["native_minus_proxy_body_yaw_wrapsafe_deg"]) for row in proxy_yaw_error_rows],
            [int(row["epoch_index"]) for row in proxy_yaw_error_rows],
            [float(row["gps_tow_seconds"]) for row in proxy_yaw_error_rows],
            valid_denominator=accepted_count,
        ),
        "proxy_minus_production_objective": _numeric_statistics(
            float(row["proxy_minus_production_objective"])
            for row in proxy_rows if row["proxy_minus_production_objective"] is not None
        ),
        "trace_window_match_count": sum(row["fixed_window_matched"] for row in trace_rows),
        "trace_native_yaw_error_deg": _wrapsafe_error_metrics(
            [float(row["native_minus_trace_wrapsafe_deg"]) for row in trace_error_rows],
            [int(row["epoch_index"]) for row in trace_error_rows],
            [float(row["gps_tow_seconds"]) for row in trace_error_rows],
            valid_denominator=fixed_window_input_count,
        ),
        "fractional_dd_epoch_rms_cycles": _numeric_statistics(
            float(row["rms_cycles"]) for row in fractional_rows if row["rms_cycles"] is not None
        ),
        "fractional_dd_epoch_mean_cycles": _numeric_statistics(
            float(row["mean_cycles"]) for row in fractional_rows if row["mean_cycles"] is not None
        ),
        "proxy_implied_fractional_dd_epoch_rms_cycles": _numeric_statistics(
            float(row["proxy_implied_rms_cycles"])
            for row in fractional_rows if row["proxy_implied_rms_cycles"] is not None
        ),
        "fractional_dd_tracking_identity_groups": _fractional_group_statistics(
            fractional_rows
        ),
        "fractional_dd_relationships": {
            name: _relationship(left, right)
            for name, (left, right) in relationship_values.items()
        },
        "relationship_role": "DESCRIPTIVE_ONLY_NOT_ASSUMPTION_THRESHOLD_OR_TUNING",
    }
    if prior_post_inventory is not None:
        _revalidate_primary_post_inventory(paths, prior_post_inventory)
    _prepare_recovery_output_root(destinations)
    _atomic_write_csv(post_paths["proxy_diagnostics"], proxy_rows, PROXY_FIELDS)
    _atomic_write_csv(
        post_paths["objective_diagnostics"], objective_rows, POST_OBJECTIVE_FIELDS,
    )
    _atomic_write_csv(post_paths["trace_diagnostics"], trace_rows, TRACE_FIELDS)
    _atomic_write_csv(
        post_paths["fractional_dd_diagnostics"], fractional_rows, FRACTIONAL_FIELDS,
    )
    materially_lower = [
        int(row["epoch_index"]) for row in proxy_rows
        if row["production_objective"] is not None and row["proxy_materially_lower"]
    ]
    if materially_lower:
        terminal_status = f"{BLOCKED_PREFIX}PROXY_OBJECTIVE_MATERIALLY_LOWER"
    else:
        terminal_status = PASS_VALIDATED
    applicability_classification = (
        "POOR_AVAILABILITY_ZERO_ACCEPTED_WRAPPED_SOLUTIONS"
        if accepted_count == 0 else "OBSERVED_ACCEPTED_WRAPPED_SOLUTION_AVAILABILITY"
    )
    post_hashes = {
        name: _sha256_file(path) for name, path in post_paths.items()
        if name != "post_native_manifest"
    }
    manifest = {
        "schema_version": "horizontal_literature.phase2.post_native_diagnostics.v1",
        "terminal_status": terminal_status,
        "native_freeze_revalidated_before_proxy_open": True,
        "native_freeze_revalidated_before_trace_open": True,
        "native_freeze_sha256": _sha256_file(paths.native_files["native_freeze"]),
        "native_output_hashes_revalidated": freeze["native_output_hashes"],
        "native_outputs_mutated": False,
        "post_recovery_id": destinations.recovery_id,
        "post_output_root": str(destinations.output_root),
        "post_report_path": str(destinations.report),
        "post_status_path": str(destinations.status),
        "supersedes_for_proxy_diagnostics_only": destinations.is_recovery,
        "prior_primary_post_inventory": prior_post_inventory,
        "prior_primary_post_inventory_revalidated_immediately_before_recovery_write": (
            prior_post_inventory is not None
        ),
        **source_identity,
        **invocation_accounting,
        "HPPOSECEF_solver_input": False,
        "trace_sha256": trace_hash,
        "trace_used_online": False,
        "fixed_evaluator_contract": {
            "base_time_unix_seconds": 1772784000.0,
            "window_seconds": [66.0, 340.0],
            "gps_to_unix_seconds": (
                "315964800 + gps_week*604800 + gps_tow_seconds - leap_seconds"
            ),
            "leap_second_evidence": leap_second_evidence,
            "trace_csv": {
                "observed_column_count": len(TRACE_CSV_COLUMNS),
                "first_column": "time",
                "exact_columns": list(TRACE_CSV_COLUMNS),
                "timestamp_alias_accepted": False,
            },
            "yaw": "unwrap_enu_then_interpolate_then_wrap360(90-yaw)",
            "trace_unwrap_domain": (
                "FULL_VALIDATED_MONOTONIC_TRACE_BEFORE_NATIVE_WINDOW_GATE"
            ),
            "native_epoch_match_gate_seconds": [66.0, 340.0],
            "matched_native_time_must_be_bracketed_by_trace": True,
            "time_offset_seconds": 0.0, "search_or_alignment": False,
            "epoch_deleted": False,
        },
        "proxy_materially_lower_eligible_accepted_epochs": materially_lower,
        "proxy_materially_lower_oracle_gated_epochs": [
            int(row["epoch_index"]) for row in proxy_rows
            if row["oracle_gated_epoch"] and row["proxy_materially_lower"]
        ],
        "fractional_dd_epoch_row_count": len(fractional_rows),
        "objective_oracle_selected_count": summary["objective_oracle_selected_count"],
        "objective_oracle_evaluated_count": summary["objective_oracle_evaluated_count"],
        "objective_oracle_not_evaluated_count": summary[
            "objective_oracle_not_evaluated_count"
        ],
        "proxy_objective_evaluated_count": len(proxy_objective_rows),
        "oracle_gated_proxy_objective_evaluated_count": len(
            oracle_gated_proxy_objective_rows
        ),
        "applicability_classification": applicability_classification,
        "zero_availability_is_validated_poor_applicability_not_unsupported": True,
        "descriptive_aggregates": descriptive_aggregates,
        "post_native_output_hashes": post_hashes,
        "ready_for_paper_claims": False,
    }
    _atomic_write_json(post_paths["post_native_manifest"], manifest)
    # Final revalidation proves the separately added diagnostics did not mutate
    # any member of the native freeze inventory.
    validate_native_freeze(paths.native_root)
    if prior_post_inventory is not None:
        _revalidate_primary_post_inventory(paths, prior_post_inventory)
    _write_report_and_status(
        paths, destinations=destinations, terminal_status=terminal_status,
        summary=summary, post_manifest=manifest,
    )
    if prior_post_inventory is not None:
        _revalidate_primary_post_inventory(paths, prior_post_inventory)
    return {
        "terminal_status": terminal_status,
        "paired_epoch_count": summary["paired_epoch_count"],
        "success_row_count": summary["success_row_count"],
        "failure_row_count": summary["failure_row_count"],
        "proxy_materially_lower_eligible_accepted_epochs": materially_lower,
        "objective_oracle_evaluated_count": summary["objective_oracle_evaluated_count"],
        "proxy_objective_evaluated_count": len(proxy_objective_rows),
        "applicability_classification": applicability_classification,
        "native_source_fingerprint": source_identity["native_source_fingerprint"],
        "post_native_source_fingerprint": source_identity[
            "post_native_source_fingerprint"
        ],
        "post_recovery_id": destinations.recovery_id,
        "post_output_root": str(destinations.output_root),
        "post_report_path": str(destinations.report),
        "post_status_path": str(destinations.status),
        "supersedes_for_proxy_diagnostics_only": destinations.is_recovery,
        "prior_primary_post_inventory_sha256": (
            None if prior_post_inventory is None
            else prior_post_inventory["inventory_sha256"]
        ),
        **invocation_accounting,
        "trace_used_online": False, "ready_for_paper_claims": False,
    }


def _blocked_item(exc: BaseException) -> str:
    text = str(exc).lower()
    mappings = (
        ("raw hash", "RAW_HASH_LOCK"), ("raw source", "RAW_SOURCE"),
        ("symlink", "SYMLINK_PATH"), ("contain", "PATH_CONTAINMENT"),
        ("final native root", "EXISTING_FINAL_NATIVE_OUTPUT"),
        ("final phase-2", "EXISTING_FINAL_TERMINAL_OUTPUT"),
        ("rtklib", "RTKLIB_DEPENDENCY"), ("bridge", "RTKLIB_BRIDGE"),
        ("cache", "CACHE_FINGERPRINT_OR_INTEGRITY"),
        ("resume", "RESUME_INTEGRITY"), ("pair", "PAIR_CONSERVATION"),
        ("resource admission", "RESOURCE_ADMISSION"),
        ("oracle", "OBJECTIVE_ORACLE"), ("determinism", "DETERMINISM_PROBE"),
        ("trace", "POST_NATIVE_TRACE"), ("hpposecef", "POST_NATIVE_HPPOSECEF"),
        ("freeze", "NATIVE_FREEZE"), ("part", "ATOMIC_PART"),
    )
    for token, item in mappings:
        if token in text:
            return item
    return "RUNTIME_FAILURE"


def _load_or_run_probe(
    attempt: Path,
    cache_root: Path,
    preflight: PreflightResult,
    navigation_paths: Sequence[Path],
    *,
    workers: int,
    resume: bool,
) -> dict[str, Any]:
    path = attempt / "RESOURCE_DETERMINISM_PROBE.json"
    if path.exists():
        if not resume:
            raise Phase2RunnerError("resource/determinism probe exists outside resume mode")
        value = json.loads(path.read_text(encoding="utf-8"))
        if (
            value.get("source_fingerprint") != preflight.source_fingerprint
            or value.get("workers_compared") != workers
            or value.get("status") != "PASS"
            or value.get("resource_admission", {}).get("admitted") is not True
        ):
            raise Phase2RunnerError("resume resource/determinism probe mismatch")
        return value
    try:
        value = resource_determinism_probe(
            cache_root, preflight.paths.rtklib_bridge, navigation_paths, workers=workers,
            storage_root=preflight.paths.clean_root,
        )
    except ResourceAdmissionError as exc:
        value = dict(exc.evidence)
        value["source_fingerprint"] = preflight.source_fingerprint
        _atomic_write_json(path, value)
        raise
    value["source_fingerprint"] = preflight.source_fingerprint
    _atomic_write_json(path, value)
    return value


def _partial_attempt_evidence(attempt: Path | None) -> tuple[bool, list[str]]:
    if attempt is None or not attempt.is_dir():
        return False, []
    try:
        entries = sorted(path.name for path in attempt.iterdir())
    except OSError:
        entries = []
    return True, entries


def run_phase2(
    config_path: Path,
    *,
    mode: str = "full",
    method_id: str = METHOD_ID,
    case_id: str = CASE_ID,
    trace_mode: str = "disabled",
    workers: int = DEFAULT_WORKERS,
    resume: bool = False,
    post_recovery_id: str | None = None,
) -> dict[str, Any]:
    attempt: Path | None = None
    try:
        preflight = preflight_phase2(
            config_path, mode=mode, workers=workers, method_id=method_id,
            case_id=case_id, trace_mode=trace_mode,
            post_recovery_id=post_recovery_id,
        )
        if mode == "preflight":
            return {
                "terminal_status": "PASS_PHASE2_EXT02_PREFLIGHT",
                "method_id": METHOD_ID, "case_id": CASE_ID,
                "source_fingerprint": preflight.source_fingerprint,
                "native_root": str(preflight.paths.native_root),
                "trace_open_count": 0,
                "HPPOSECEF_semantic_decode_count": 0,
                "ready_for_paper_claims": False,
            }
        if mode == "post-native-diagnostics":
            return run_post_native_diagnostics(
                preflight, post_recovery_id=post_recovery_id,
            )
        attempt = _attempt_root(preflight)
        attempt = _open_attempt(preflight, resume=resume)
        cache_root, navigation_paths, cache_manifest, derived_hashes = (
            _prepare_or_resume_cache(preflight, attempt, resume=resume)
        )
        _require_contained(cache_root, attempt, "compact cache")
        probe = _load_or_run_probe(
            attempt, cache_root, preflight, navigation_paths,
            workers=workers, resume=resume,
        )
        if mode == "resource-determinism-probe":
            return {
                "terminal_status": "PASS_PHASE2_EXT02_RESOURCE_DETERMINISM_PROBE",
                "source_fingerprint": preflight.source_fingerprint,
                "attempt_root": str(attempt),
                "paired_epoch_count": cache_manifest["pair_count"],
                "trace_open_count": 0,
                "HPPOSECEF_semantic_decode_count": 0,
                "probe": probe,
                "ready_for_paper_claims": False,
            }
        part_root = attempt / "PARTS"
        _require_contained(part_root, attempt, "atomic part root")
        records = execute_shards(
            cache_root, preflight.paths.rtklib_bridge, navigation_paths, part_root,
            source_fingerprint=preflight.source_fingerprint,
            workers=workers, resume=resume,
        )
        provider_hashes = {**preflight.provider_hashes, **derived_hashes}
        summary = write_native_outputs(
            attempt, cache_root, records, preflight=preflight,
            cache_manifest=cache_manifest, provider_hashes=provider_hashes,
            determinism_probe=probe, workers=workers,
        )
        if preflight.paths.final_status.exists() or preflight.paths.final_report.exists():
            raise Phase2RunnerError("final Phase-2 terminal output appeared before finalize")
        _atomic_finalize_attempt(attempt, preflight.paths.native_root)
        attempt = None
        if mode == "native-only":
            return {
                "terminal_status": PASS_READY,
                "paired_epoch_count": summary["paired_epoch_count"],
                "success_row_count": summary["success_row_count"],
                "failure_row_count": summary["failure_row_count"],
                "native_root": str(preflight.paths.native_root),
                "trace_used_online": False, "trace_open_count": 0,
                "HPPOSECEF_semantic_decode_count": 0,
                "ready_for_paper_claims": False,
            }
        return run_post_native_diagnostics(preflight)
    except (OSError, ValueError, Phase2RunnerError, subprocess.SubprocessError) as exc:
        blocked = f"{BLOCKED_PREFIX}{_blocked_item(exc)}"
        partial_preserved, evidence_entries = _partial_attempt_evidence(attempt)
        terminal_write_error = None
        if partial_preserved and attempt is not None:
            terminal = attempt / "ATTEMPT_TERMINAL.json"
            if not _path_lexists(terminal):
                try:
                    _atomic_write_json(terminal, {
                        "terminal_status": blocked, "error_type": type(exc).__name__,
                        "error": str(exc), "partial_attempt_preserved": True,
                        "partial_attempt_evidence_entries_before_terminal": evidence_entries,
                        "trace_used_online": False,
                        "ready_for_paper_claims": False,
                    })
                except (OSError, Phase2RunnerError) as terminal_exc:
                    terminal_write_error = (
                        f"{type(terminal_exc).__name__}: {terminal_exc}"
                    )
            partial_preserved, evidence_entries = _partial_attempt_evidence(attempt)
        return {
            "terminal_status": blocked, "error_type": type(exc).__name__,
            "error": str(exc), "partial_attempt_preserved": partial_preserved,
            "partial_attempt_evidence_entries": evidence_entries,
            "attempt_terminal_write_error": terminal_write_error,
            "trace_used_online": False, "ready_for_paper_claims": False,
        }
