"""Phase-4 EXT04 Wu-2025 real BY2 C00 execution and freeze lifecycle.

The native path reads only hash-locked RAWX/SFRBX-derived material.  It builds
one compact memory-map cache, evaluates independent epochs with the exact
Section II-A constrained objective, and installs a hash freeze before any
semantic NAV-HPPOSECEF decode, trace open, or RTKLIB relative diagnostic.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import io
import json
import math
import os

for _thread_name in (
    "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
):
    os.environ[_thread_name] = "1"

import shlex
import subprocess
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, fields, is_dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import yaml

from . import phase2_runner as phase2
from .ext01_clambda import (
    RTKLIBLambdaBridge,
    joint_gls,
    search_strict_lambda,
    wrap_safe_residual_degrees,
)
from .ext04_wu2025 import (
    BASELINE_LENGTH_M,
    FAR_POLICY_IDENTITY,
    POLICY_IDENTITY,
    PRIMARY_POLICY,
    REPRODUCTION_LEVEL,
    SEARCH_BUDGET_CLOCK,
    SENSITIVITY_POLICIES,
    AmbiguityIdentity,
    DDObservationBlock,
    PolicyDecision,
    PolicyParameters,
    Wu2025Error,
    all_policy_decisions,
    attitude_from_ned_baseline,
    build_observation_model,
    build_search_chain,
    evaluate_subset,
    subset_observation_model,
)
from .phase3_signal_inventory import (
    SIGNAL_GROUPS,
    SignalInventoryResult,
    audit_signal_availability,
    integer_compatible,
)
from .shared_raw_backend import (
    PntPosBridgeError,
    RawBackendError,
    RawxEpoch,
    RawxMeasurement,
    RtklibBroadcastProvider,
    RTKLIB_NAVSYS_BDS,
    RTKLIB_NAVSYS_GPS,
    RTKLIB_NAVSYS_GPS_BDS,
    azimuth_elevation,
    correlated_dd_covariance,
    earth_rotation_correct_satellite,
    ecef_to_geodetic,
    identity_text,
    integer_compatible_carrier_cycles,
    rawx_standard_deviations,
    reconstruct_ubx_stream,
    rinex_satellite_id,
    wavelength_m,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "configs/paper_rebuild/horizontal_literature/PHASE4_EXT04_WU2025_CONTRACT_V1.yaml"
)
CLI_PATH = REPOSITORY_ROOT / "scripts/paper_rebuild/run_horizontal_literature_phase4.py"
METHOD_ID = "EXT04_WU2025"
CASE_ID = "C00"
TASK_START_HEAD = "82b8035863ab3f40a694d4ac0ce55c9166671941"
EXPECTED_BRANCH = "stage/clean3-math-repair"
EXPECTED_COMMIT_SUBJECT = "Add EXT04 Wu 2025 constrained FAR PAR BY2 C00 reproduction"
APPROVED_TRACKED_PATHS = (
    "configs/paper_rebuild/horizontal_literature/PHASE4_EXT04_WU2025_CONTRACT_V1.yaml",
    "src/legsa_gins/paper_rebuild/horizontal_literature/ext04_wu2025.py",
    "src/legsa_gins/paper_rebuild/horizontal_literature/phase4_runner.py",
    "scripts/paper_rebuild/run_horizontal_literature_phase4.py",
    "tests/paper_rebuild/test_horizontal_ext04_wu2025.py",
    "tests/paper_rebuild/test_horizontal_phase4_c00.py",
)
PRESERVED_UNTRACKED_PATHS = frozenset({
    "scripts/paper_rebuild/run_canonical541_offline_eval_aggregate.py",
    "src/legsa_gins/paper_rebuild/canonical541/offline_eval_aggregate.py",
})
EXECUTION_LOCK_SCHEMA = "horizontal_literature.phase4.execution_lock.v2"
ARTIFACT_ROOT_IDENTITY_SCHEMA = "horizontal_literature.phase4.artifact_root.v1"
ARTIFACT_ROOT_IDENTITY_NAME = "EXT04_PHASE4_ARTIFACT_ROOT_IDENTITY.json"
POST_NATIVE_R1_IDENTITY = "POST_NATIVE_R1_RTKLIB_FIXED_ASSOCIATION"
R2_REPORT_NAME = "PHASE4_EXT04_C00_R2_REPORT.md"
R2_STATUS_NAME = "PHASE4_STATUS_R2.json"
R3_REPORT_NAME = "PHASE4_EXT04_C00_R3_REPORT.md"
R3_STATUS_NAME = "PHASE4_STATUS_R3.json"
R4_REPORT_NAME = "PHASE4_EXT04_C00_R4_REPORT.md"
R4_STATUS_NAME = "PHASE4_STATUS_R4.json"
R5_REPORT_NAME = "PHASE4_EXT04_C00_R5_REPORT.md"
R5_STATUS_NAME = "PHASE4_STATUS_R5.json"
R6_REPORT_NAME = "PHASE4_EXT04_C00_R6_REPORT.md"
R6_STATUS_NAME = "PHASE4_STATUS_R6.json"
R2_EXECUTION_LOCK_NAME = "PHASE4_EXT04_EXECUTION_LOCK_R2F.json"
CANONICAL_ARCHIVE_NAME = "PHASE4_EXT04_PENDING_ARCHIVE_R6"
CANONICAL_ARCHIVE_SCHEMA = "horizontal_literature.phase4.pending_archive.v2"
CANONICAL_ARCHIVE_IDENTITY = "PHASE4_EXT04_CANONICAL_PENDING_R6_APPROVAL"
FAILED_R5_CANONICAL_ATTEMPT_NAME = (
    ".PHASE4_EXT04_PENDING_ARCHIVE_R5.tmp.084a84d90278dfa57249"
)
FAILED_R5_CANONICAL_ATTEMPT_FILE_COUNT = 13
FAILED_R5_CANONICAL_ATTEMPT_BYTES = 2_693_141
FAILED_R5_CANONICAL_ATTEMPT_AGGREGATE_SHA256 = (
    "6d6a2868648defdb572c974c8c16ad7da5887fcc07e910c89c8d60ac051e6b23"
)
ORIGINAL_PENDING_REPORT_SHA256 = "5c6d8cfac07a6673706fa2d995592a57099d9824542a865d2d8ea3ff64c0cef0"
ORIGINAL_PENDING_STATUS_SHA256 = "0de037b7f379a2f03372d1f312ebd227d90e25a13e3dbaf7858ca9f35cef1eb5"
R1_PENDING_REPORT_SHA256 = "4173ab5fb65f3a3b0d1a7ae7926515c4b18dd0fed66c60661c28b6f472ec0957"
R1_PENDING_STATUS_SHA256 = "f34f4772c3c37941878a9e7267bad7dc9c69b588de9ed2bd7118f6393aeb7a49"
R2_PENDING_REPORT_SHA256 = "95c578a18e2c6e8794563587842e2ac8e1b24e15fa7662066e19f6fd40061560"
R2_PENDING_STATUS_SHA256 = "18dfa467936064d28b16c4800c5d6a38171646dc74915c0a369558c4e8e29935"
R3_PENDING_REPORT_SHA256 = "edfaf4dc2d587315594cf80c92f10782794f8285da809b3b10420aeb5eed4e09"
R3_PENDING_STATUS_SHA256 = "9edb73c4f3e456325feae1116390d14ed5b29449bf363477b607f4a0fa3e50fd"
R4_PENDING_REPORT_SHA256 = "c3fb5aa71a4ef1b4392071d8679e4ea3f2271a5f69937e40e43f2005d45dc947"
R4_PENDING_STATUS_SHA256 = "8063e63434b124382b824f0fd23f091d184072cf8cd7f286479f9d908523d96d"
R5_PENDING_REPORT_SHA256 = "db3d9454317d84c5e54c09935ae1cc6ef4c99a000ea2d75e325992c3748eacc5"
R5_PENDING_STATUS_SHA256 = "082a09649f9103538bfa8a8ee59be04640e0bf1d4bc7b0aed1313b6ec362ff93"
DEFAULT_WORKERS = 16
MAX_WORKERS = 20
AUTHORIZED_WORKERS = 16
EXPECTED_PAIR_COUNT = 1509
SYSTEM_MODES = (
    "GPS_DUAL_FREQUENCY",
    "BDS_DUAL_FREQUENCY",
    "GPS_BDS_DUAL_FREQUENCY",
)
POLICY_ORDER = (
    FAR_POLICY_IDENTITY,
    POLICY_IDENTITY,
    *(policy.policy_identity for policy in SENSITIVITY_POLICIES),
)
EXPECTED_HEADING_ROWS = EXPECTED_PAIR_COUNT * len(SYSTEM_MODES) * len(POLICY_ORDER)
ALLOWED_MODES = frozenset({
    "preflight", "resource-determinism-probe", "native-only",
    "post-native-diagnostics", "post-native-r1-diagnostics",
    "create-execution-lock", "full", "finalize-r1-pending",
    "finalize-canonical-after-review",
})

PASS_DECLARED = "PASS_PHASE4_EXT04_CORE_VALIDATED_DECLARED_PAR_POLICY_C00_COMPLETE"
PASS_POOR = "PASS_PHASE4_EXT04_IMPLEMENTATION_VALIDATED_BY2_C00_APPLICABILITY_RESULT"
BLOCKED_PREFIX = "BLOCKED_PHASE4_EXT04_"

NATIVE_FILE_NAMES = {
    "heading_results": "EXT04_C00_NATIVE_HEADING_RESULTS.csv",
    "failure_ledger": "EXT04_C00_FAILURE_LEDGER.csv",
    "runtime": "EXT04_C00_RUNTIME.csv",
    "signal_availability": "EXT04_C00_SIGNAL_AVAILABILITY.csv",
    "dd_diagnostics": "EXT04_C00_DD_DIAGNOSTICS.csv",
    "float_diagnostics": "EXT04_C00_FLOAT_DIAGNOSTICS.csv",
    "far_diagnostics": "EXT04_C00_FAR_DIAGNOSTICS.csv",
    "par_diagnostics": "EXT04_C00_PAR_DIAGNOSTICS.csv",
    "search_certificates": "EXT04_C00_SEARCH_CERTIFICATES.csv",
    "quality_control_diagnostics": "EXT04_C00_QUALITY_CONTROL_DIAGNOSTICS.csv",
    "policy_summary": "EXT04_C00_POLICY_SUMMARY.csv",
    "sensitivity_summary": "EXT04_C00_SENSITIVITY_SUMMARY.csv",
    "stochastic_registry": "EXT04_STOCHASTIC_PARAMETER_REGISTRY.csv",
    "policy_registry": "EXT04_POLICY_PARAMETER_REGISTRY.csv",
    "native_summary": "EXT04_C00_NATIVE_SUMMARY.json",
    "native_freeze": "EXT04_C00_NATIVE_FREEZE.json",
}
FREEZE_HASH_KEYS = tuple(key for key in NATIVE_FILE_NAMES if key != "native_freeze")
POST_FILE_NAMES = {
    "proxy_diagnostics": "EXT04_C00_PROXY_DIAGNOSTICS.csv",
    "trace_diagnostics": "EXT04_C00_TRACE_DIAGNOSTICS.csv",
    "trace_summary": "EXT04_C00_TRACE_SUMMARY.csv",
    "fractional_phase": "EXT04_C00_FRACTIONAL_PHASE_DIAGNOSTICS.csv",
    "rtklib_summary": "EXT04_C00_RTKLIB_DIAGNOSTIC.json",
    "post_native_summary": "EXT04_C00_POST_NATIVE_SUMMARY.json",
    "post_native_freeze": "EXT04_C00_POST_NATIVE_FREEZE.json",
}
POST_FREEZE_HASH_KEYS = tuple(
    key for key in POST_FILE_NAMES if key != "post_native_freeze"
)
POST_R1_FILE_NAMES = {
    "proxy_diagnostics": "EXT04_C00_R1_PROXY_DIAGNOSTICS.csv",
    "trace_diagnostics": "EXT04_C00_R1_TRACE_DIAGNOSTICS.csv",
    "trace_summary": "EXT04_C00_R1_TRACE_SUMMARY.csv",
    "fractional_phase": "EXT04_C00_R1_FRACTIONAL_PHASE_DIAGNOSTICS.csv",
    "rtklib_summary": "EXT04_C00_R1_RTKLIB_DIAGNOSTIC.json",
    "post_native_summary": "EXT04_C00_R1_POST_NATIVE_SUMMARY.json",
    "post_native_freeze": "EXT04_C00_R1_POST_NATIVE_FREEZE.json",
}
POST_R1_FREEZE_HASH_KEYS = tuple(
    key for key in POST_R1_FILE_NAMES if key != "post_native_freeze"
)

PREEXISTING_MANIFEST_NAME = "EXT04_PREEXISTING_STAGE_HASH_MANIFEST.sha256"
PREEXISTING_MANIFEST_SHA256 = "470629e9c0e2f973d3b5e78dde574a5222698018d52a38a8df9ee9ce14c9519c"


class Phase4RunnerError(RuntimeError):
    pass


class EpochObservationError(RawBackendError):
    def __init__(self, code: str, detail: str):
        self.code = code
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class Phase4Paths:
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
    lambda_library: Path
    bridge_root: Path
    configured_stage_root: Path
    stage_root: Path
    artifact_root_overridden: bool
    native_root: Path
    report_root: Path
    final_report: Path
    final_status: Path
    post_r1_root: Path
    r1_report: Path
    r1_status: Path
    r2_report: Path
    r2_status: Path
    r3_report: Path
    r3_status: Path
    r4_report: Path
    r4_status: Path
    r5_report: Path
    r5_status: Path
    r6_report: Path
    r6_status: Path
    canonical_archive_root: Path
    execution_lock: Path
    preexisting_manifest_default: Path
    paper_pdf: Path
    paper_render_root: Path
    paper_text: Path
    paper_registry: Path


@dataclass(frozen=True)
class PreflightResult:
    paths: Phase4Paths
    contract: Mapping[str, Any]
    code_commit: str
    contract_hash: str
    config_hash: str
    raw_source_hashes: Mapping[str, str]
    provider_hashes: Mapping[str, str]
    paper_hashes: Mapping[str, str]
    runtime_source_hashes: Mapping[str, str]
    runtime_dependency_hashes: Mapping[str, str]
    worktree_overlay_identity: Mapping[str, Any]
    source_fingerprint: str
    task_start_head: str
    execution_head: str
    provenance_mode: str
    runtime_content_fingerprint: str
    approved_file_hashes: Mapping[str, str]
    execution_lock_evidence: Mapping[str, Any]
    preexisting_manifest_path: Path
    preexisting_manifest_sha256: str
    artifact_root_evidence: Mapping[str, Any]


def _sha256(path: Path) -> str:
    return phase2._sha256_file(Path(path))


def _canonical(value: Any) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {item.name: _jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list, set, frozenset)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def terminal_json(value: Mapping[str, Any]) -> str:
    return json.dumps(_jsonable(value), sort_keys=True, ensure_ascii=False)


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "horizontal_literature.phase4_ext04_wu2025.v1"
        or value.get("method_id") != METHOD_ID
        or value.get("case_id") != CASE_ID
    ):
        raise Phase4RunnerError("Phase-4 contract identity drift")
    if value.get("implemented_policy_identity") != POLICY_IDENTITY:
        raise Phase4RunnerError("declared policy identity drift")
    if value.get("implemented_reproduction_level") != REPRODUCTION_LEVEL:
        raise Phase4RunnerError("declared reproduction level drift")
    if value.get("paper_exact_policy_status") != "NOT_IMPLEMENTED_UNDER_SPECIFIED":
        raise Phase4RunnerError("paper-exact under-specification boundary drift")
    if tuple(value.get("native_policy_order", ())) != POLICY_ORDER:
        raise Phase4RunnerError("policy ordering drift")
    if value.get("runtime_topology", {}).get("native_files") != NATIVE_FILE_NAMES:
        raise Phase4RunnerError("native output inventory drift")
    if value.get("runtime_topology", {}).get("post_native_files") != POST_FILE_NAMES:
        raise Phase4RunnerError("post-native output inventory drift")
    if (
        value.get("runtime_topology", {}).get("post_native_r1", {}).get("files")
        != POST_R1_FILE_NAMES
    ):
        raise Phase4RunnerError("post-native R1 output inventory drift")
    topology = value.get("runtime_topology", {})
    if (
        topology.get("R2_report_file") != R2_REPORT_NAME
        or topology.get("R2_status_file") != R2_STATUS_NAME
        or topology.get("R3_report_file") != R3_REPORT_NAME
        or topology.get("R3_status_file") != R3_STATUS_NAME
        or topology.get("R4_report_file") != R4_REPORT_NAME
        or topology.get("R4_status_file") != R4_STATUS_NAME
        or topology.get("R5_report_file") != R5_REPORT_NAME
        or topology.get("R5_status_file") != R5_STATUS_NAME
        or topology.get("R6_report_file") != R6_REPORT_NAME
        or topology.get("R6_status_file") != R6_STATUS_NAME
        or topology.get("execution_lock_file") != R2_EXECUTION_LOCK_NAME
        or topology.get("canonical_required_report_file")
        != "PHASE4_EXT04_C00_REPORT.md"
        or topology.get("canonical_required_status_file") != "PHASE4_STATUS.json"
        or topology.get("canonical_pending_archive_root") != CANONICAL_ARCHIVE_NAME
    ):
        raise Phase4RunnerError("Phase-4 pending/final output identity drift")
    transaction = topology.get("canonical_transaction", {})
    if (
        transaction.get("archive_schema") != CANONICAL_ARCHIVE_SCHEMA
        or transaction.get("exact_path_install")
        != "CAS_TEMP_FSYNC_SAME_DIRECTORY_REPLACE"
        or transaction.get("two_file_recovery")
        != "ARCHIVE_BACKED_IDEMPOTENT_RESUME"
        or transaction.get("every_pending_input_hash_required") is not True
        or transaction.get("pending_generations")
        != ["ORIGINAL", "R1", "R2", "R3", "R4", "R5", "R6"]
        or transaction.get("pre_mutation_freeze_validation")
        != ["NATIVE", "ORIGINAL_POST_NATIVE", "CORRECTED_R1_POST_NATIVE"]
        or transaction.get("deterministic_temporary_paths_inspected_before_mutation")
        is not True
        or transaction.get("unknown_temporary_bytes") != "FAIL_CLOSED"
        or transaction.get("archive_writer")
        != "FINAL_DIRECTORY_EXCLUSIVE_MKDIR_DIRECT_XB_FSYNC_MANIFEST_LAST"
        or transaction.get("archive_nested_atomic_helper_used") is not False
        or transaction.get("archive_windows_dotnet_move_used") is not False
        or transaction.get("incomplete_archive_retry") != "NEW_IDENTITY_REQUIRED"
    ):
        raise Phase4RunnerError("canonical transaction contract drift")
    if tuple(value.get("lifecycle_modes", ())) != tuple([
        "preflight", "resource-determinism-probe", "native-only",
        "post-native-diagnostics", "post-native-r1-diagnostics",
        "create-execution-lock", "full", "finalize-r1-pending",
        "finalize-canonical-after-review",
    ]):
        raise Phase4RunnerError("Phase-4 lifecycle mode drift")
    provenance = value.get("execution_provenance", {})
    if (
        provenance.get("task_start_head") != TASK_START_HEAD
        or provenance.get("branch") != EXPECTED_BRANCH
        or provenance.get("committed_mode", {}).get("exact_commit_subject")
        != EXPECTED_COMMIT_SUBJECT
        or provenance.get("committed_mode", {}).get("execution_lock_schema")
        != EXECUTION_LOCK_SCHEMA
        or provenance.get("fresh_artifact_root", {}).get("role")
        != "PHASE4_OUTPUT_AND_REPORT_LAYOUT_ONLY"
    ):
        raise Phase4RunnerError("execution provenance contract drift")
    parallel = value.get("parallel_execution", {})
    if (
        int(parallel.get("default_workers", -1)) != DEFAULT_WORKERS
        or int(parallel.get("maximum_workers", -1)) != MAX_WORKERS
        or int(parallel.get("authorized_workers_this_run", -1)) != AUTHORIZED_WORKERS
    ):
        raise Phase4RunnerError("worker authorization drift")
    flags = value.get("data_flags", {})
    forbidden = (
        "trace_used_online", "receiver_imu_as_body_imu",
        "final_v23_output_solver_input", "LegSA_output_solver_input",
        "per_case_tuning", "output_only_correction", "epoch_deleted_for_metric",
        "HPPOSECEF_solver_input", "status_baseline_solver_input",
        "Go2_yaw_solver_input", "EXT01_output_solver_input",
        "EXT02_output_solver_input", "EXT03_output_solver_input",
        "RTKLIB_diagnostic_output_solver_input", "phase_bias_calibration",
    )
    if any(flags.get(name) is not False for name in forbidden):
        raise Phase4RunnerError("forbidden native-input flag drift")
    if int(flags.get("old_runtime_input_count", -1)) != 0:
        raise Phase4RunnerError("old runtime input count drift")
    return value


def load_paths(config_path: Path, artifact_root: Path | None = None) -> Phase4Paths:
    document = yaml.safe_load(Path(config_path).resolve().read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema_version") != "paper_rebuild.paths.v1":
        raise Phase4RunnerError("unsupported local paths schema")
    values = document.get("paths", {})
    required = (
        "code_root", "raw_root", "by2_fix_root", "clean_root",
        "horizontal_literature_rtklib_root", "horizontal_literature_convbin",
        "horizontal_literature_rtklib_bridge", "horizontal_literature_lambda_library",
        "horizontal_literature_bridge_root",
    )
    if any(not isinstance(values.get(name), str) for name in required):
        raise Phase4RunnerError("local paths lack an EXT04 dependency")

    def absolute(name: str) -> Path:
        path = Path(values[name])
        if not path.is_absolute():
            raise Phase4RunnerError(f"local path is not absolute: {name}")
        return path.resolve(strict=False)

    by2 = absolute("by2_fix_root")
    clean = absolute("clean_root")
    configured_stage = clean / "stages/CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
    if artifact_root is None:
        stage = configured_stage
        artifact_override = False
    else:
        requested = Path(artifact_root)
        if not requested.is_absolute() or ".." in requested.parts:
            raise Phase4RunnerError("artifact root must be an absolute normalized path")
        stage = Path(os.path.abspath(os.fspath(requested)))
        artifact_override = True
    report = stage / "11_REPORT"
    external_root = absolute("horizontal_literature_bridge_root").parent
    paper_source_root = external_root / "papers"
    paper_root = paper_source_root / "EXT04_WU2025"
    native_root = stage / "05_EXT04_WU2025_MODULE/C00"
    return Phase4Paths(
        Path(config_path).resolve(), absolute("code_root"), absolute("raw_root"), by2,
        clean, clean / "01_RAW_HASH_LOCK/RAW_FILE_HASH_LOCK.csv",
        by2 / "gnss1-raw.csv", by2 / "gnss2-raw.csv",
        by2 / "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv",
        absolute("horizontal_literature_rtklib_root"),
        absolute("horizontal_literature_convbin"),
        absolute("horizontal_literature_rtklib_bridge"),
        absolute("horizontal_literature_lambda_library"),
        absolute("horizontal_literature_bridge_root"),
        configured_stage, stage, artifact_override, native_root, report,
        report / "PHASE4_EXT04_C00_REPORT.md", report / "PHASE4_STATUS.json",
        native_root / POST_NATIVE_R1_IDENTITY,
        report / "PHASE4_EXT04_C00_R1_REPORT.md",
        report / "PHASE4_STATUS_R1.json",
        report / R2_REPORT_NAME, report / R2_STATUS_NAME,
        report / R3_REPORT_NAME, report / R3_STATUS_NAME,
        report / R4_REPORT_NAME, report / R4_STATUS_NAME,
        report / R5_REPORT_NAME, report / R5_STATUS_NAME,
        report / R6_REPORT_NAME, report / R6_STATUS_NAME,
        report / CANONICAL_ARCHIVE_NAME,
        configured_stage / "11_REPORT" / R2_EXECUTION_LOCK_NAME,
        configured_stage / "05_EXT04_WU2025_MODULE/C00" / PREEXISTING_MANIFEST_NAME,
        paper_source_root / "EXT04_WU2025_PAPER.pdf",
        paper_root / "rendered_pages_200dpi",
        paper_root / "EXT04_WU2025_EXTRACTED_TEXT_PYMUPDF.txt",
        paper_root / "EXT04_WU2025_EQUATION_POLICY_REGISTRY.md",
    )


def _runtime_dependency_hashes(paths: Phase4Paths) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in (
        paths.rtklib_bridge,
        paths.lambda_library,
        paths.bridge_root / "EXT03_PNTPOS_BRIDGE.patch",
        paths.bridge_root / "Makefile",
    ):
        if not path.is_file():
            raise Phase4RunnerError(f"runtime dependency absent: {path}")
        key = (
            path.relative_to(paths.bridge_root).as_posix()
            if path.is_relative_to(paths.bridge_root) else str(path)
        )
        result[key] = _sha256(path)
    return result


def _paper_audit(paths: Phase4Paths, contract: Mapping[str, Any]) -> dict[str, str]:
    paper = contract["paper_source"]
    if not paths.paper_pdf.is_file() or _sha256(paths.paper_pdf) != paper["pdf_sha256"]:
        raise Phase4RunnerError("formal PDF hash mismatch")
    rendered = sorted(paths.paper_render_root.glob("page_*.png"))
    if len(rendered) != 14 or [path.name for path in rendered] != [f"page_{i:02d}.png" for i in range(1, 15)]:
        raise Phase4RunnerError("formal PDF 14-page render inventory incomplete")
    for path in (paths.paper_text, paths.paper_registry):
        if not path.is_file() or path.stat().st_size <= 0:
            raise Phase4RunnerError(f"paper closure artifact absent: {path.name}")
    render_hash = hashlib.sha256(
        _canonical({path.name: _sha256(path) for path in rendered}).encode()
    ).hexdigest()
    if (
        _sha256(paths.paper_text) != paper.get("text_extraction_sha256")
        or _sha256(paths.paper_registry)
        != paper.get("equation_policy_registry_sha256")
        or render_hash != paper.get("render_inventory_sha256")
    ):
        raise Phase4RunnerError("paper closure artifact hash mismatch")
    search = paper.get("official_code_search", {})
    if search.get("searched_once") is not True or search.get("result") != "NO_ATTRIBUTABLE_OFFICIAL_IMPLEMENTATION_FOUND":
        raise Phase4RunnerError("official-code search evidence drift")
    return {
        "pdf_sha256": _sha256(paths.paper_pdf),
        "text_sha256": _sha256(paths.paper_text),
        "registry_sha256": _sha256(paths.paper_registry),
        "render_inventory_sha256": render_hash,
    }


def _git_stdout(code_root: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=code_root, text=True,
        capture_output=True, check=True,
    ).stdout


def _git_status_entries(code_root: Path) -> tuple[tuple[str, str], ...]:
    raw = _git_stdout(
        code_root, "status", "--porcelain=v1", "--untracked-files=all", "-z",
    )
    entries: list[tuple[str, str]] = []
    for record in raw.split("\0"):
        if not record:
            continue
        if len(record) < 4 or record[2] != " ":
            raise Phase4RunnerError("unparseable Git status record")
        status, path = record[:2], record[3:]
        if "R" in status or "C" in status:
            raise Phase4RunnerError("rename/copy status is outside Phase-4 scope")
        entries.append((status, path))
    return tuple(entries)


def _validate_development_status(
    entries: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    allowed = set(APPROVED_TRACKED_PATHS) | set(PRESERVED_UNTRACKED_PATHS)
    unexpected = [(status, path) for status, path in entries if path not in allowed]
    if unexpected:
        raise Phase4RunnerError(
            f"development worktree has unrelated drift: {unexpected}"
        )
    invalid = [
        (status, path) for status, path in entries
        if status != "??"
    ]
    if invalid:
        raise Phase4RunnerError(
            f"development Phase-4 paths must be untracked additions: {invalid}"
        )
    return {
        "allowed_dirty_entries": [
            {"status": status, "path": path} for status, path in entries
        ],
        "unrelated_dirty_entry_count": 0,
        "preserved_untracked_paths_content_read": False,
    }


def _validate_committed_worktree_status(
    entries: Sequence[tuple[str, str]],
) -> dict[str, Any]:
    unexpected = [
        (status, path) for status, path in entries
        if path not in PRESERVED_UNTRACKED_PATHS or status != "??"
    ]
    if unexpected:
        raise Phase4RunnerError(
            f"committed reproduction has unrelated dirty drift: {unexpected}"
        )
    return {
        "preserved_untracked_entries": [
            {"status": status, "path": path} for status, path in entries
        ],
        "unrelated_dirty_entry_count": 0,
        "approved_paths_clean": True,
        "preserved_untracked_paths_content_read": False,
    }


def _required_sha256(value: str | None, label: str) -> str:
    text = str(value or "").lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise Phase4RunnerError(f"{label} requires an exact SHA-256")
    return text


def _validated_external_file(
    path: Path, expected_sha256: str, *, label: str,
) -> tuple[Path, str]:
    candidate = Path(path)
    if not candidate.is_absolute():
        raise Phase4RunnerError(f"{label} path must be absolute")
    _reject_symlink_components(candidate)
    if candidate.is_symlink() or not candidate.is_file():
        raise Phase4RunnerError(f"{label} must be a regular non-symlink file")
    expected = _required_sha256(expected_sha256, label)
    observed = _sha256(candidate)
    if observed != expected:
        raise Phase4RunnerError(f"{label} SHA-256 mismatch")
    return candidate, observed


def _resolve_preexisting_manifest(
    paths: Phase4Paths, explicit_path: Path | None,
    explicit_sha256: str | None,
) -> tuple[Path, str]:
    if paths.artifact_root_overridden and (
        explicit_path is None or explicit_sha256 is None
    ):
        raise Phase4RunnerError(
            "fresh artifact root requires explicit pre-existing manifest path and SHA-256"
        )
    if (explicit_path is None) != (explicit_sha256 is None):
        raise Phase4RunnerError(
            "pre-existing manifest path and SHA-256 must be supplied together"
        )
    path = explicit_path or paths.preexisting_manifest_default
    expected = explicit_sha256 or PREEXISTING_MANIFEST_SHA256
    if _required_sha256(expected, "pre-existing manifest") != PREEXISTING_MANIFEST_SHA256:
        raise Phase4RunnerError("pre-existing manifest expected identity drift")
    return _validated_external_file(
        Path(path), PREEXISTING_MANIFEST_SHA256, label="pre-existing manifest",
    )


def _artifact_root_protected_collision(paths: Phase4Paths) -> str | None:
    root = paths.stage_root
    exact_or_containing = (
        paths.code_root, paths.raw_root, paths.by2_fix_root, paths.clean_root,
        paths.bridge_root, paths.configured_stage_root,
    )
    for protected in exact_or_containing:
        if root == protected or protected.is_relative_to(root):
            return str(protected)
    for protected in (
        paths.code_root, paths.raw_root, paths.by2_fix_root,
        paths.bridge_root, paths.configured_stage_root,
    ):
        if root.is_relative_to(protected):
            return str(protected)
    return None


def _reject_symlink_components(path: Path) -> None:
    current = Path(path)
    while True:
        if os.path.lexists(current) and current.is_symlink():
            raise Phase4RunnerError(f"artifact root path contains symlink: {current}")
        if current.parent == current:
            return
        current = current.parent


def _artifact_root_identity_payload(
    paths: Phase4Paths, *, source_fingerprint: str,
    runtime_content_fingerprint: str, execution_head: str,
    execution_lock_sha256: str, preexisting_manifest_path: Path,
    preexisting_manifest_sha256: str,
) -> dict[str, Any]:
    return {
        "schema_version": ARTIFACT_ROOT_IDENTITY_SCHEMA,
        "artifact_root": str(paths.stage_root),
        "layout": {
            "native_root": "05_EXT04_WU2025_MODULE/C00",
            "report_root": "11_REPORT",
        },
        "output_only_override": True,
        "configured_clean_root_unchanged": str(paths.clean_root),
        "task_start_head": TASK_START_HEAD,
        "execution_head": execution_head,
        "source_fingerprint": source_fingerprint,
        "runtime_content_fingerprint": runtime_content_fingerprint,
        "execution_lock_sha256": execution_lock_sha256,
        "preexisting_manifest_path": str(preexisting_manifest_path),
        "preexisting_manifest_sha256": preexisting_manifest_sha256,
    }


def _prepare_fresh_artifact_root(
    paths: Phase4Paths, identity: Mapping[str, Any], *,
    resume: bool, initialize: bool,
) -> dict[str, Any]:
    if not paths.artifact_root_overridden:
        return {
            "overridden": False, "artifact_root": str(paths.stage_root),
            "configured_clean_root_unchanged": True,
        }
    root = paths.stage_root
    if root == Path("/") or len(root.parts) < 4:
        raise Phase4RunnerError("artifact root is dangerously broad")
    _reject_symlink_components(root)
    collision = _artifact_root_protected_collision(paths)
    if collision is not None:
        raise Phase4RunnerError(f"artifact root collides with protected root: {collision}")
    marker = root / ARTIFACT_ROOT_IDENTITY_NAME
    if root.exists():
        if not root.is_dir():
            raise Phase4RunnerError("artifact root exists and is not a directory")
        entries = sorted(path.name for path in root.iterdir())
        if not entries:
            state = "EXISTING_EMPTY"
        elif resume:
            allowed = {
                ARTIFACT_ROOT_IDENTITY_NAME,
                "05_EXT04_WU2025_MODULE", "11_REPORT",
            }
            if set(entries) != allowed or marker.is_symlink() or not marker.is_file():
                raise Phase4RunnerError("artifact resume inventory drift")
            observed = json.loads(marker.read_text(encoding="utf-8"))
            if observed != dict(identity):
                raise Phase4RunnerError("artifact root identity mismatch")
            return {
                "overridden": True, "artifact_root": str(root),
                "state": "VALIDATED_RESUME", "initialized": True,
                "identity_sha256": _sha256(marker),
                "configured_clean_root_unchanged": True,
            }
        else:
            raise Phase4RunnerError("fresh artifact root is not absent or empty")
    else:
        if not root.parent.is_dir():
            raise Phase4RunnerError("artifact root parent must already exist")
        state = "ABSENT"
    if resume:
        raise Phase4RunnerError("artifact resume requested before initialization")
    if not initialize:
        return {
            "overridden": True, "artifact_root": str(root),
            "state": f"VALIDATED_{state}_NOT_INITIALIZED", "initialized": False,
            "configured_clean_root_unchanged": True,
        }
    encoded = (
        json.dumps(_jsonable(identity), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    if state == "ABSENT":
        temporary = root.with_name(f".{root.name}.tmp.{os.getpid()}")
        if os.path.lexists(temporary):
            raise Phase4RunnerError("artifact-root temporary collision")
        temporary.mkdir()
        (temporary / "05_EXT04_WU2025_MODULE/C00").mkdir(parents=True)
        (temporary / "11_REPORT").mkdir()
        phase2._atomic_write_bytes(
            temporary / ARTIFACT_ROOT_IDENTITY_NAME, encoded,
        )
        phase2._atomic_install_noreplace(
            temporary, root, label="Phase-4 artifact root", kind="directory",
        )
    else:
        (root / "05_EXT04_WU2025_MODULE/C00").mkdir(parents=True)
        (root / "11_REPORT").mkdir()
        phase2._atomic_write_bytes(marker, encoded)
    if json.loads(marker.read_text(encoding="utf-8")) != dict(identity):
        raise Phase4RunnerError("artifact-root initialization read-back mismatch")
    return {
        "overridden": True, "artifact_root": str(root),
        "state": f"INITIALIZED_FROM_{state}", "initialized": True,
        "identity_sha256": _sha256(marker),
        "configured_clean_root_unchanged": True,
    }


def _read_execution_lock(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase4RunnerError(f"execution lock is unreadable: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != EXECUTION_LOCK_SCHEMA:
        raise Phase4RunnerError("execution lock schema mismatch")
    return value


def _validate_execution_lock_content(
    lock: Mapping[str, Any], *, approved_hashes: Mapping[str, str],
    runtime_content_fingerprint: str, preexisting_manifest_sha256: str,
) -> None:
    expected = {
        "schema_version": EXECUTION_LOCK_SCHEMA,
        "task_start_head": TASK_START_HEAD,
        "branch": EXPECTED_BRANCH,
        "required_descendant_commit_count": 1,
        "required_commit_subject": EXPECTED_COMMIT_SUBJECT,
        "approved_diff_paths": list(APPROVED_TRACKED_PATHS),
        "approved_file_sha256": dict(sorted(approved_hashes.items())),
        "runtime_content_fingerprint": runtime_content_fingerprint,
        "preexisting_manifest_sha256": preexisting_manifest_sha256,
        "artifact_root_policy": "EXPLICIT_FRESH_PHASE4_OUTPUT_ONLY",
    }
    drift = {
        key: {"expected": value, "observed": lock.get(key)}
        for key, value in expected.items() if lock.get(key) != value
    }
    if drift:
        raise Phase4RunnerError(f"execution lock content drift: {drift}")


def _validate_committed_provenance_state(
    *, branch: str, execution_head: str, ancestor_ok: bool,
    descendant_count: int, commit_subject: str,
    diff_paths: Sequence[str], dirty_approved_paths: Sequence[str],
    lock: Mapping[str, Any], approved_hashes: Mapping[str, str],
    runtime_content_fingerprint: str,
) -> dict[str, Any]:
    if branch != EXPECTED_BRANCH:
        raise Phase4RunnerError("committed reproduction branch drift")
    if execution_head == TASK_START_HEAD or not ancestor_ok:
        raise Phase4RunnerError("task-start HEAD is not a strict execution ancestor")
    if descendant_count != 1:
        raise Phase4RunnerError("committed reproduction must be exactly one descendant commit")
    if commit_subject != EXPECTED_COMMIT_SUBJECT:
        raise Phase4RunnerError("committed reproduction subject drift")
    if tuple(sorted(diff_paths)) != tuple(sorted(APPROVED_TRACKED_PATHS)):
        raise Phase4RunnerError("committed reproduction diff scope drift")
    if dirty_approved_paths:
        raise Phase4RunnerError("approved committed paths are dirty")
    _validate_execution_lock_content(
        lock, approved_hashes=approved_hashes,
        runtime_content_fingerprint=runtime_content_fingerprint,
        preexisting_manifest_sha256=PREEXISTING_MANIFEST_SHA256,
    )
    return {
        "task_start_is_ancestor": True,
        "descendant_commit_count": 1,
        "commit_subject": commit_subject,
        "approved_diff_paths": list(sorted(diff_paths)),
        "approved_paths_clean": True,
    }


def _execution_lock_payload(preflight: PreflightResult) -> dict[str, Any]:
    return {
        "schema_version": EXECUTION_LOCK_SCHEMA,
        "task_start_head": TASK_START_HEAD,
        "branch": EXPECTED_BRANCH,
        "required_descendant_commit_count": 1,
        "required_commit_subject": EXPECTED_COMMIT_SUBJECT,
        "approved_diff_paths": list(APPROVED_TRACKED_PATHS),
        "approved_file_sha256": dict(sorted(preflight.approved_file_hashes.items())),
        "runtime_content_fingerprint": preflight.runtime_content_fingerprint,
        "preexisting_manifest_sha256": preflight.preexisting_manifest_sha256,
        "artifact_root_policy": "EXPLICIT_FRESH_PHASE4_OUTPUT_ONLY",
        "created_from_execution_head": preflight.execution_head,
        "created_from_provenance_mode": preflight.provenance_mode,
        "does_not_pin_unknown_commit_hash": True,
    }


def create_execution_lock(preflight: PreflightResult, destination: Path) -> dict[str, Any]:
    destination = Path(destination).absolute()
    if destination != preflight.paths.execution_lock:
        raise Phase4RunnerError("execution-lock path is outside the exact Phase-4 identity")
    payload = _execution_lock_payload(preflight)
    phase2._atomic_write_json(destination, payload)
    observed = _read_execution_lock(destination)
    if observed != payload:
        raise Phase4RunnerError("execution lock failed read-after-write validation")
    return {
        "terminal_status": "PASS_PHASE4_EXT04_EXECUTION_LOCK_CREATED",
        "execution_lock": str(destination),
        "execution_lock_sha256": _sha256(destination),
        "runtime_content_fingerprint": preflight.runtime_content_fingerprint,
        "task_start_head": preflight.task_start_head,
        "execution_head": preflight.execution_head,
        "provenance_mode": preflight.provenance_mode,
    }


def preflight_phase4(
    config_path: Path, *, allow_native_existing: bool = False,
    allow_report_existing: bool = False,
    execution_lock: Path | None = None,
    execution_lock_sha256: str | None = None,
    preexisting_manifest: Path | None = None,
    preexisting_manifest_sha256: str | None = None,
    artifact_root: Path | None = None,
    artifact_resume: bool = False,
    initialize_artifact_root: bool = False,
) -> PreflightResult:
    paths = load_paths(config_path, artifact_root=artifact_root)
    contract = load_contract()
    if paths.code_root != REPOSITORY_ROOT.resolve():
        raise Phase4RunnerError("configured code_root is not this worktree")
    branch = _git_stdout(paths.code_root, "branch", "--show-current").strip()
    if branch != EXPECTED_BRANCH:
        raise Phase4RunnerError("unexpected branch")
    execution_head = _git_stdout(paths.code_root, "rev-parse", "HEAD").strip()
    approved_files = {
        path: paths.code_root / path for path in APPROVED_TRACKED_PATHS
    }
    if any(not path.is_file() for path in approved_files.values()):
        missing = [key for key, path in approved_files.items() if not path.is_file()]
        raise Phase4RunnerError(f"approved Phase-4 source absent: {missing}")
    approved_hashes = {
        key: _sha256(path) for key, path in approved_files.items()
    }
    manifest_path, manifest_sha256 = _resolve_preexisting_manifest(
        paths, preexisting_manifest, preexisting_manifest_sha256,
    )
    if (execution_lock is None) != (execution_lock_sha256 is None):
        raise Phase4RunnerError(
            "execution lock path and exact SHA-256 must be supplied together"
        )
    lock_path: Path | None = None
    lock_value: dict[str, Any] | None = None
    lock_sha256: str | None = None
    if execution_lock is not None:
        lock_path, lock_sha256 = _validated_external_file(
            Path(execution_lock), str(execution_lock_sha256),
            label="execution lock",
        )
        lock_value = _read_execution_lock(lock_path)
    if paths.artifact_root_overridden and lock_value is None:
        raise Phase4RunnerError(
            "fresh artifact root requires explicit execution lock path and SHA-256"
        )
    if execution_head == TASK_START_HEAD:
        provenance_mode = "DEVELOPMENT_TASK_START_HEAD_BOUNDED_ADDITIONS"
        provenance_detail = _validate_development_status(
            _git_status_entries(paths.code_root)
        )
    else:
        provenance_mode = "COMMITTED_ONE_DESCENDANT_EXECUTION_LOCKED"
        if lock_path is None or lock_value is None:
            raise Phase4RunnerError(
                "committed reproduction requires an existing --execution-lock"
            )
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", TASK_START_HEAD, execution_head],
            cwd=paths.code_root, check=False,
        ).returncode == 0
        committed_worktree = _validate_committed_worktree_status(
            _git_status_entries(paths.code_root)
        )
        provenance_detail = {
            "task_start_is_ancestor": ancestor,
            "descendant_commit_count": int(_git_stdout(
                paths.code_root, "rev-list", "--count",
                f"{TASK_START_HEAD}..{execution_head}",
            ).strip()),
            "commit_subject": _git_stdout(
                paths.code_root, "log", "-1", "--format=%s", execution_head,
            ).strip(),
            "approved_diff_paths": sorted(_git_stdout(
                paths.code_root, "diff", "--name-only", TASK_START_HEAD,
                execution_head,
            ).splitlines()),
            "dirty_approved_paths": [
                path for _status, path in _git_status_entries(paths.code_root)
                if path in set(APPROVED_TRACKED_PATHS)
            ],
            "committed_worktree": committed_worktree,
        }
    raw_hashes = phase2._verify_locked_raw(paths)
    provider_hashes = phase2._external_provider_audit(paths)
    rnx2rtkp = paths.rtklib_root / "app/consapp/rnx2rtkp/gcc/rnx2rtkp"
    if not rnx2rtkp.is_file():
        raise Phase4RunnerError("unmodified RTKLIB diagnostic binary absent")
    provider_hashes = {
        **provider_hashes,
        "lambda_library_sha256": _sha256(paths.lambda_library),
        "rnx2rtkp_sha256": _sha256(rnx2rtkp),
    }
    paper_hashes = _paper_audit(paths, contract)
    runtime_paths = (
        CONTRACT_PATH,
        CLI_PATH,
        Path(__file__).resolve(),
        Path(__file__).with_name("ext04_wu2025.py"),
        Path(__file__).with_name("ext01_clambda.py"),
        Path(__file__).with_name("shared_raw_backend.py"),
        Path(__file__).with_name("phase3_signal_inventory.py"),
        Path(__file__).with_name("phase2_runner.py"),
        REPOSITORY_ROOT / "tests/paper_rebuild/test_horizontal_ext04_wu2025.py",
        REPOSITORY_ROOT / "tests/paper_rebuild/test_horizontal_phase4_c00.py",
    )
    if any(not path.is_file() for path in runtime_paths):
        missing = [str(path) for path in runtime_paths if not path.is_file()]
        raise Phase4RunnerError(f"runtime source absent: {missing}")
    runtime_sources = {
        path.relative_to(REPOSITORY_ROOT).as_posix(): _sha256(path)
        for path in runtime_paths
    }
    runtime_dependencies = _runtime_dependency_hashes(paths)
    scoped = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all", "--", *runtime_sources],
        cwd=paths.code_root, text=True, capture_output=True, check=True,
    ).stdout
    global_status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=paths.code_root, text=True, capture_output=True, check=True,
    ).stdout
    overlay = {
        "code_commit_semantics": "IMMUTABLE_TASK_START_HEAD_PLUS_VALIDATED_EXECUTION_STATE",
        "provenance_mode": provenance_mode,
        "task_start_head": TASK_START_HEAD,
        "execution_head": execution_head,
        "scope": "ENUMERATED_PHASE4_RUNTIME_SOURCES_ONLY",
        "scoped_status_sha256": hashlib.sha256(scoped.encode()).hexdigest(),
        "scoped_status_entries": len(scoped.splitlines()),
        "runtime_source_overlay_sha256": hashlib.sha256(_canonical(runtime_sources).encode()).hexdigest(),
        "runtime_dependency_overlay_sha256": hashlib.sha256(_canonical(runtime_dependencies).encode()).hexdigest(),
        "global_worktree_audit_metadata": {
            "excluded_from_scientific_fingerprint": True,
            "status_sha256": hashlib.sha256(global_status.encode()).hexdigest(),
            "entry_count": len(global_status.splitlines()),
        },
        "provenance_detail": provenance_detail,
    }
    runtime_content_payload = {
        "approved_file_sha256": dict(sorted(approved_hashes.items())),
        "runtime_source_hashes": dict(sorted(runtime_sources.items())),
        "runtime_dependency_hashes": dict(sorted(runtime_dependencies.items())),
    }
    runtime_content_fingerprint = hashlib.sha256(
        _canonical(runtime_content_payload).encode()
    ).hexdigest()
    if provenance_mode == "COMMITTED_ONE_DESCENDANT_EXECUTION_LOCKED":
        provenance_detail = _validate_committed_provenance_state(
            branch=branch, execution_head=execution_head,
            ancestor_ok=bool(provenance_detail["task_start_is_ancestor"]),
            descendant_count=int(provenance_detail["descendant_commit_count"]),
            commit_subject=str(provenance_detail["commit_subject"]),
            diff_paths=provenance_detail["approved_diff_paths"],
            dirty_approved_paths=provenance_detail["dirty_approved_paths"],
            lock=lock_value or {}, approved_hashes=approved_hashes,
            runtime_content_fingerprint=runtime_content_fingerprint,
        )
        overlay["provenance_detail"] = provenance_detail
    elif lock_value is not None:
        _validate_execution_lock_content(
            lock_value, approved_hashes=approved_hashes,
            runtime_content_fingerprint=runtime_content_fingerprint,
            preexisting_manifest_sha256=manifest_sha256,
        )
    execution_lock_evidence = {
        "provided": lock_path is not None,
        "exists": lock_value is not None,
        "path": str(lock_path) if lock_path is not None else None,
        "sha256": lock_sha256,
        "required_sha256": execution_lock_sha256,
        "validated": lock_value is not None,
        "path_independent_of_artifact_root": True,
    }
    fingerprint_payload = {
        "method": METHOD_ID, "case": CASE_ID,
        "task_start_head": TASK_START_HEAD,
        "contract": _sha256(CONTRACT_PATH), "config": _sha256(paths.config_path),
        "raw": raw_hashes, "providers": provider_hashes, "paper": paper_hashes,
        "runtime_sources": runtime_sources, "runtime_dependencies": runtime_dependencies,
        "runtime_content_fingerprint": runtime_content_fingerprint,
        "preexisting_manifest_sha256": manifest_sha256,
        "artifact_output_policy": "EXPLICIT_FRESH_PHASE4_OUTPUT_ONLY",
    }
    fingerprint = hashlib.sha256(_canonical(fingerprint_payload).encode()).hexdigest()
    artifact_identity = _artifact_root_identity_payload(
        paths, source_fingerprint=fingerprint,
        runtime_content_fingerprint=runtime_content_fingerprint,
        execution_head=execution_head,
        execution_lock_sha256=str(lock_sha256 or "NOT_APPLICABLE_DEVELOPMENT"),
        preexisting_manifest_path=manifest_path,
        preexisting_manifest_sha256=manifest_sha256,
    )
    artifact_evidence = _prepare_fresh_artifact_root(
        paths, artifact_identity, resume=artifact_resume,
        initialize=initialize_artifact_root,
    )
    if not paths.artifact_root_overridden and not paths.native_root.is_dir():
        raise Phase4RunnerError("pre-existing C00 root is absent")
    if paths.native_root.is_dir():
        native_existing = [
            name for name in NATIVE_FILE_NAMES.values()
            if (paths.native_root / name).exists()
        ]
        if native_existing and not allow_native_existing:
            raise Phase4RunnerError(
                f"no-replace native output collision: {native_existing}"
            )
        if (
            allow_native_existing and native_existing
            and len(native_existing) != len(NATIVE_FILE_NAMES)
        ):
            raise Phase4RunnerError("partial published native inventory is unsafe")
        post_existing = [
            name for name in POST_FILE_NAMES.values()
            if (paths.native_root / name).exists()
        ]
        if post_existing and not allow_native_existing:
            raise Phase4RunnerError(
                f"no-replace post-native output collision: {post_existing}"
            )
    report_existing = [
        path.name for path in (paths.final_report, paths.final_status) if path.exists()
    ]
    if report_existing and not allow_report_existing:
        raise Phase4RunnerError(f"Phase-4 report/status collision: {report_existing}")
    if allow_report_existing and report_existing and len(report_existing) != 2:
        raise Phase4RunnerError("partial original report/status inventory is unsafe")
    return PreflightResult(
        paths, contract, TASK_START_HEAD, _sha256(CONTRACT_PATH), _sha256(paths.config_path),
        raw_hashes, provider_hashes, paper_hashes, runtime_sources,
        runtime_dependencies, overlay, fingerprint, TASK_START_HEAD,
        execution_head, provenance_mode, runtime_content_fingerprint,
        approved_hashes, execution_lock_evidence,
        manifest_path, manifest_sha256, artifact_evidence,
    )


def _attempt_root(preflight: PreflightResult) -> Path:
    return preflight.paths.native_root / f".EXT04_ATTEMPT_{preflight.source_fingerprint[:20]}"


def _open_attempt(preflight: PreflightResult, *, resume: bool) -> Path:
    attempt = _attempt_root(preflight)
    identity = {
        "schema_version": "horizontal_literature.phase4.attempt_identity.v1",
        "source_fingerprint": preflight.source_fingerprint,
        "base_head": preflight.code_commit,
        "task_start_head": preflight.task_start_head,
        "execution_head": preflight.execution_head,
        "provenance_mode": preflight.provenance_mode,
        "runtime_content_fingerprint": preflight.runtime_content_fingerprint,
        "execution_lock_evidence": dict(preflight.execution_lock_evidence),
        "runtime_source_hashes": dict(sorted(preflight.runtime_source_hashes.items())),
        "final_native_root": str(preflight.paths.native_root),
    }
    path = attempt / "ATTEMPT_IDENTITY.json"
    if attempt.exists():
        if not resume or not path.is_file():
            raise Phase4RunnerError("fingerprinted attempt exists; --resume is required")
        observed = json.loads(path.read_text(encoding="utf-8"))
        if observed != identity:
            raise Phase4RunnerError("resume attempt identity mismatch")
        return attempt
    if resume:
        raise Phase4RunnerError("--resume requested but fingerprinted attempt is absent")
    attempt.mkdir()
    phase2._atomic_write_json(path, identity)
    return attempt


def _ecef_vector_to_ned(vector: Sequence[float], reference_ecef_m: Sequence[float]) -> np.ndarray:
    lat, lon, _height = ecef_to_geodetic(reference_ecef_m)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_lon, cos_lon = math.sin(lon), math.cos(lon)
    rotation = np.asarray([
        [-sin_lat * cos_lon, -sin_lat * sin_lon, cos_lat],
        [-sin_lon, cos_lon, 0.0],
        [-cos_lat * cos_lon, -cos_lat * sin_lon, -sin_lat],
    ])
    return rotation @ np.asarray(vector, dtype=float)


def _saastamoinen_m(
    receiver_ecef_m: Sequence[float], satellite_ecef_m: Sequence[float],
    *, relative_humidity: float = 0.0,
) -> float:
    lat, _lon, height = ecef_to_geodetic(receiver_ecef_m)
    height = min(10000.0, max(-100.0, height))
    _az, elevation = azimuth_elevation(receiver_ecef_m, satellite_ecef_m)
    if elevation <= 0.0:
        raise RawBackendError("Saastamoinen requires positive elevation")
    pressure = 1013.25 * (1.0 - 2.2557e-5 * height) ** 5.2568
    temperature = 15.0 - 6.5e-3 * height + 273.16
    vapour = 6.108 * relative_humidity * math.exp(
        (17.15 * temperature - 4684.0) / (temperature - 38.45)
    )
    sine = math.sin(elevation)
    dry = 0.0022768 * pressure / (
        1.0 - 0.00266 * math.cos(2.0 * lat) - 0.00028 * height / 1000.0
    ) / sine
    wet = 0.002277 * (1255.0 / temperature + 0.05) * vapour / sine
    return dry + wet


def _mode_constellations(system_mode: str) -> tuple[str, ...]:
    if system_mode == "GPS_BDS_DUAL_FREQUENCY":
        return "GPS", "BDS"
    if system_mode == "GPS_DUAL_FREQUENCY":
        return ("GPS",)
    if system_mode == "BDS_DUAL_FREQUENCY":
        return ("BDS",)
    raise EpochObservationError("UNSUPPORTED_SYSTEM_MODE", system_mode)


def _best_by_sv(epoch: RawxEpoch, group: str) -> dict[int, RawxMeasurement]:
    allowed = set(SIGNAL_GROUPS[group])
    result: dict[int, RawxMeasurement] = {}
    for measurement in epoch.measurements:
        identity = measurement.identity
        key = (identity.gnss_id, identity.sig_id, identity.freq_id)
        if (
            key not in allowed or not integer_compatible(measurement)
            or measurement.cno_dbhz < 20 or measurement.locktime_ms <= 0
        ):
            continue
        previous = result.get(identity.sv_id)
        if previous is None or (
            -measurement.cno_dbhz, key
        ) < (
            -previous.cno_dbhz,
            (previous.identity.gnss_id, previous.identity.sig_id, previous.identity.freq_id),
        ):
            result[identity.sv_id] = measurement
    return result


def _best_common_by_sv(
    receiver1: RawxEpoch, receiver2: RawxEpoch, group: str,
) -> dict[int, tuple[RawxMeasurement, RawxMeasurement]]:
    """Select one exact shared RAWX signal identity per satellite/group."""

    allowed = set(SIGNAL_GROUPS[group])
    def eligible(epoch: RawxEpoch) -> dict[Any, RawxMeasurement]:
        result: dict[Any, RawxMeasurement] = {}
        for measurement in epoch.measurements:
            identity = measurement.identity
            if (
                (identity.gnss_id, identity.sig_id, identity.freq_id) not in allowed
                or not integer_compatible(measurement)
                or measurement.cno_dbhz < 20 or measurement.locktime_ms <= 0
            ):
                continue
            if identity in result:
                raise EpochObservationError(
                    "DUPLICATE_RAWX_SIGNAL_IDENTITY", identity_text(identity)
                )
            result[identity] = measurement
        return result

    left, right = eligible(receiver1), eligible(receiver2)
    candidates: dict[int, list[tuple[RawxMeasurement, RawxMeasurement]]] = defaultdict(list)
    for identity in set(left).intersection(right):
        candidates[identity.sv_id].append((left[identity], right[identity]))
    return {
        satellite: min(
            values,
            key=lambda pair: (
                -min(pair[0].cno_dbhz, pair[1].cno_dbhz),
                -min(pair[0].locktime_ms, pair[1].locktime_ms),
                pair[0].identity.sig_id, pair[0].identity.freq_id,
            ),
        )
        for satellite, values in candidates.items()
    }


def _pntpos(
    provider: RtklibBroadcastProvider, epoch: RawxEpoch,
    system_mode: str, receiver: str,
) -> Any:
    navsys = {
        "GPS_DUAL_FREQUENCY": RTKLIB_NAVSYS_GPS,
        "BDS_DUAL_FREQUENCY": RTKLIB_NAVSYS_BDS,
        "GPS_BDS_DUAL_FREQUENCY": RTKLIB_NAVSYS_GPS_BDS,
    }[system_mode]
    try:
        result = provider.pntpos_rawx_epoch(epoch, navsys, np.zeros(3))
    except PntPosBridgeError as exc:
        raise EpochObservationError(f"{receiver}_{exc.code}", str(exc)) from exc
    if not result.accepted or result.position_ecef_m is None:
        raise EpochObservationError(
            f"{receiver}_PNTPOS_REJECTED",
            f"solstat={result.solution_status} valid={result.valid_satellite_count} "
            f"obs={result.constructed_observation_count} message={result.message}",
        )
    return result


def build_epoch_blocks(
    receiver1: RawxEpoch,
    receiver2: RawxEpoch,
    provider: RtklibBroadcastProvider,
    system_mode: str,
    spp1_ecef_m: Sequence[float],
    spp2_ecef_m: Sequence[float],
) -> tuple[DDObservationBlock, ...]:
    """Generalize the audited raw DD chain to GPS/BDS dual frequency."""

    if (receiver1.gps_week, receiver1.gps_tow_seconds) != (
        receiver2.gps_week, receiver2.gps_tow_seconds
    ):
        raise EpochObservationError("NONEXACT_EPOCH_PAIR", "week/TOW differ")
    mean_receiver = 0.5 * (np.asarray(spp1_ecef_m) + np.asarray(spp2_ecef_m))
    groups_by_constellation = {
        "GPS": ("GPS_L1", "GPS_L2"),
        "BDS": ("BDS_B1", "BDS_B2"),
    }
    blocks: list[DDObservationBlock] = []
    for constellation in _mode_constellations(system_mode):
        groups = groups_by_constellation[constellation]
        paired_maps = {
            group: _best_common_by_sv(receiver1, receiver2, group)
            for group in groups
        }
        common = set.intersection(*(
            set(paired_maps[group]) for group in groups
        ))
        if len(common) < 2:
            raise EpochObservationError(
                f"INSUFFICIENT_{constellation}_DUAL_FREQUENCY_COMMON_SATELLITES",
                f"common={len(common)}",
            )
        states: dict[int, np.ndarray] = {}
        elevations: dict[int, float] = {}
        for satellite in sorted(common):
            measurement1, measurement2 = paired_maps[groups[0]][satellite]
            mean_range = 0.5 * (
                measurement1.pr_mes_m + measurement2.pr_mes_m
            )
            try:
                state = provider.state(
                    measurement1.identity, receiver1.gps_week,
                    receiver1.gps_tow_seconds, mean_range,
                )
                corrected = earth_rotation_correct_satellite(
                    state.position_ecef_m, mean_range / 299_792_458.0
                )
                _az, elevation = azimuth_elevation(mean_receiver, corrected)
            except RawBackendError:
                continue
            if state.health == 0 and elevation >= math.radians(10.0):
                states[satellite] = corrected
                elevations[satellite] = elevation
        if len(states) < 2:
            raise EpochObservationError(
                f"INSUFFICIENT_{constellation}_DUAL_FREQUENCY_SATELLITE_STATES",
                f"usable={len(states)}",
            )
        pivot = min(
            states,
            key=lambda satellite: (
                -elevations[satellite],
                -min(
                    measurement.locktime_ms
                    for group in groups
                    for measurement in paired_maps[group][satellite]
                ),
                satellite,
            ),
        )
        nonpivots = tuple(satellite for satellite in sorted(states) if satellite != pivot)
        for group in groups:
            first = {
                satellite: paired_maps[group][satellite][0] for satellite in states
            }
            second = {
                satellite: paired_maps[group][satellite][1] for satellite in states
            }
            labels = {
                satellite: rinex_satellite_id(first[satellite].identity)
                for satellite in states
            }
            los = {
                labels[satellite]: _ecef_vector_to_ned(
                    (states[satellite] - mean_receiver)
                    / np.linalg.norm(states[satellite] - mean_receiver),
                    mean_receiver,
                )
                for satellite in states
            }

            def corrected_sd(satellite: int, *, phase: bool) -> float:
                measurement1 = first[satellite]
                measurement2 = second[satellite]
                try:
                    trop1 = _saastamoinen_m(spp1_ecef_m, states[satellite])
                    trop2 = _saastamoinen_m(spp2_ecef_m, states[satellite])
                except RawBackendError as exc:
                    raise EpochObservationError("DD_TROPOSPHERE_MODEL_FAILURE", str(exc)) from exc
                value1 = (
                    integer_compatible_carrier_cycles(measurement1)
                    * wavelength_m(measurement1.identity)
                    if phase else measurement1.pr_mes_m
                )
                value2 = (
                    integer_compatible_carrier_cycles(measurement2)
                    * wavelength_m(measurement2.identity)
                    if phase else measurement2.pr_mes_m
                )
                return (value2 - trop2) - (value1 - trop1)

            code_pivot = corrected_sd(pivot, phase=False)
            phase_pivot = corrected_sd(pivot, phase=True)
            code = np.asarray([
                corrected_sd(satellite, phase=False) - code_pivot
                for satellite in nonpivots
            ])
            phase_values = np.asarray([
                corrected_sd(satellite, phase=True) - phase_pivot
                for satellite in nonpivots
            ])

            def variances(satellite: int) -> tuple[float, float]:
                pr1, cp1, _dop1 = rawx_standard_deviations(first[satellite])
                pr2, cp2, _dop2 = rawx_standard_deviations(second[satellite])
                lam = wavelength_m(first[satellite].identity)
                return pr1 * pr1 + pr2 * pr2, (cp1 * lam) ** 2 + (cp2 * lam) ** 2

            pivot_code, pivot_phase = variances(pivot)
            variances_nonpivot = [variances(satellite) for satellite in nonpivots]
            code_covariance = correlated_dd_covariance(
                [item[0] for item in variances_nonpivot], pivot_code
            )
            phase_covariance = correlated_dd_covariance(
                [item[1] for item in variances_nonpivot], pivot_phase
            )
            zeros = np.zeros((len(nonpivots), len(nonpivots)))
            covariance = np.block([
                [code_covariance, zeros],
                [zeros, phase_covariance],
            ])
            cno = {
                labels[satellite]: float(min(
                    first[satellite].cno_dbhz, second[satellite].cno_dbhz
                ))
                for satellite in nonpivots
            }
            elevation = {
                labels[satellite]: float(elevations[satellite])
                for satellite in nonpivots
            }
            signals = {
                labels[satellite]: identity_text(first[satellite].identity)
                for satellite in nonpivots
            }
            blocks.append(DDObservationBlock(
                constellation, group, labels[pivot],
                tuple(labels[satellite] for satellite in nonpivots),
                wavelength_m(first[pivot].identity), los, code, phase_values,
                covariance, cno, elevation, signals,
            ))
    return tuple(blocks)


_WORKER_READER: Any = None
_WORKER_PROVIDER: RtklibBroadcastProvider | None = None
_WORKER_LAMBDA: RTKLIBLambdaBridge | None = None


def _worker_initialize(
    cache_root: str, navigation_paths: Sequence[str],
    provider_bridge: str, lambda_library: str,
) -> None:
    global _WORKER_READER, _WORKER_PROVIDER, _WORKER_LAMBDA
    _WORKER_READER = phase2.CompactCacheReader(Path(cache_root))
    _WORKER_PROVIDER = RtklibBroadcastProvider(
        Path(provider_bridge), tuple(Path(path) for path in navigation_paths)
    )
    _WORKER_LAMBDA = RTKLIBLambdaBridge(Path(lambda_library))


def _identity_list(values: Sequence[AmbiguityIdentity]) -> list[str]:
    return [item.text for item in values]


def _decision_row(
    decision: PolicyDecision,
    *,
    system_mode: str,
    epoch_index: int,
    epoch: RawxEpoch,
    full_ambiguity_count: int,
    mode_runtime_seconds: float,
) -> dict[str, Any]:
    evaluation = decision.selected
    metrics = evaluation.quality_metrics
    # A timeout incumbent is neither a certified solution nor a heading.  Its
    # raw progress remains available in SEARCH_CERTIFICATES/chain diagnostics,
    # but solution-facing fields must stay blank for INVALID rows.
    candidate = evaluation.best if evaluation.search_certified else None
    attitude = None if candidate is None else attitude_from_ned_baseline(candidate.baseline)
    policy = decision.policy
    failure_code = evaluation.failure_code if decision.solution_state == "INVALID" else None
    if decision.solution_state == "PAR_EXHAUSTED":
        failure_code = "DECLARED_POLICY_GATES_NOT_SATISFIED"
    elif decision.solution_state == "FAR_REJECTED":
        failure_code = "DECLARED_POLICY_GATES_NOT_SATISFIED"
    return {
        "method_id": METHOD_ID,
        "case_id": CASE_ID,
        "policy_identity": policy.policy_identity,
        "reproduction_level": policy.reproduction_level,
        "primary_or_sensitivity": policy.primary_or_sensitivity,
        "changed_parameter": policy.changed_parameter,
        "system_mode": system_mode,
        "epoch_index": epoch_index,
        "gps_week": epoch.gps_week,
        "gps_tow_seconds": epoch.gps_tow_seconds,
        "solution_state": decision.solution_state,
        "accepted_by_policy": decision.accepted,
        "ambiguity_correctness_known": False,
        "full_ambiguity_count": full_ambiguity_count,
        "subset_step": len(evaluation.removed_identities),
        "active_ambiguity_count": len(evaluation.active_identities),
        "removed_ambiguity_count": len(evaluation.removed_identities),
        "active_ambiguity_identities": _identity_list(evaluation.active_identities),
        "removed_ambiguity_identities": _identity_list(evaluation.removed_identities),
        "float_ambiguities_cycles": evaluation.float_solution.ambiguity,
        "integer_ambiguities": None if candidate is None else candidate.ambiguity,
        "baseline_n_m": None if candidate is None else float(candidate.baseline[0]),
        "baseline_e_m": None if candidate is None else float(candidate.baseline[1]),
        "baseline_d_m": None if candidate is None else float(candidate.baseline[2]),
        "baseline_length_m": None if metrics is None else metrics.constrained_baseline_length_m,
        "baseline_yaw_deg": None if attitude is None else attitude.baseline_yaw_deg,
        "body_yaw_deg": None if attitude is None else attitude.body_yaw_deg,
        "pitch_deg": None if attitude is None else attitude.pitch_deg,
        "best_objective": None if metrics is None else metrics.best_objective,
        "second_objective": None if metrics is None else metrics.second_objective,
        "second_over_best": None if metrics is None else metrics.second_over_best,
        "best_over_second": None if metrics is None else metrics.best_over_second,
        "objective_acceptance_convention": "SECOND_OVER_BEST_GE_THRESHOLD",
        "ratio_threshold": policy.ratio_threshold,
        "unconstrained_conditional_baseline_ned_m": None if metrics is None else metrics.unconstrained_conditional_baseline_ned_m,
        "unconstrained_conditional_baseline_norm_m": None if metrics is None else metrics.unconstrained_conditional_baseline_norm_m,
        "baseline_validation_residual_m": None if metrics is None else metrics.baseline_validation_residual_m,
        "baseline_tolerance_m": policy.baseline_tolerance_m,
        "posterior_residual_statistic": None if metrics is None else metrics.whitened_squared_residual,
        "posterior_degrees_of_freedom": None if metrics is None else metrics.degrees_of_freedom,
        "posterior_p_value": None if metrics is None else metrics.chi_square_p_value,
        "posterior_alpha": policy.posterior_alpha,
        "code_residual_rms_m": None if metrics is None else metrics.code_residual_rms_m,
        "phase_residual_rms_m": None if metrics is None else metrics.phase_residual_rms_m,
        "residual_vector_m": None if metrics is None else metrics.residual_vector_m,
        "ambiguity_log_determinant": None if metrics is None else metrics.ambiguity_log_determinant,
        "ADOP_ambiguity_dimension": None if metrics is None else metrics.ambiguity_dimension,
        "ADOP_cycles": None if metrics is None else metrics.adop_cycles,
        "ADOP_threshold_cycles": policy.adop_threshold_cycles,
        "objective_equivalence_pass": decision.gates.objective_equivalence_pass,
        "baseline_validation_pass": decision.gates.baseline_validation_pass,
        "posterior_residual_pass": decision.gates.posterior_residual_pass,
        "ADOP_pass": decision.gates.adop_pass,
        "global_optimum_certified": evaluation.search_certificate.global_optimum_certified,
        "subset_runtime_seconds": evaluation.runtime_seconds,
        "mode_runtime_seconds": mode_runtime_seconds,
        "failure_code": failure_code,
    }


def _invalid_policy_rows(
    *, system_mode: str, epoch_index: int, epoch: RawxEpoch,
    failure_code: str, failure_detail: str, mode_runtime_seconds: float,
) -> list[dict[str, Any]]:
    policies = (
        PolicyParameters(
            FAR_POLICY_IDENTITY,
            reproduction_level="FAITHFUL_MODULE_MATHEMATICAL_CORE_WITH_DECLARED_QC_GATES",
            primary_or_sensitivity="FAR",
        ),
        PRIMARY_POLICY,
        *SENSITIVITY_POLICIES,
    )
    return [{
        "method_id": METHOD_ID, "case_id": CASE_ID,
        "policy_identity": policy.policy_identity,
        "reproduction_level": policy.reproduction_level,
        "primary_or_sensitivity": policy.primary_or_sensitivity,
        "changed_parameter": policy.changed_parameter,
        "system_mode": system_mode, "epoch_index": epoch_index,
        "gps_week": epoch.gps_week, "gps_tow_seconds": epoch.gps_tow_seconds,
        "solution_state": "INVALID", "accepted_by_policy": False,
        "ambiguity_correctness_known": False,
        "full_ambiguity_count": 0, "active_ambiguity_count": 0,
        "subset_step": None,
        "removed_ambiguity_count": 0, "active_ambiguity_identities": [],
        "removed_ambiguity_identities": [], "float_ambiguities_cycles": None,
        "integer_ambiguities": None,
        "baseline_n_m": None, "baseline_e_m": None, "baseline_d_m": None,
        "baseline_length_m": None, "baseline_yaw_deg": None,
        "body_yaw_deg": None, "pitch_deg": None,
        "best_objective": None, "second_objective": None,
        "second_over_best": None, "best_over_second": None,
        "objective_acceptance_convention": "SECOND_OVER_BEST_GE_THRESHOLD",
        "ratio_threshold": policy.ratio_threshold,
        "unconstrained_conditional_baseline_ned_m": None,
        "unconstrained_conditional_baseline_norm_m": None,
        "baseline_validation_residual_m": None,
        "baseline_tolerance_m": policy.baseline_tolerance_m,
        "posterior_residual_statistic": None,
        "posterior_degrees_of_freedom": None,
        "posterior_p_value": None, "posterior_alpha": policy.posterior_alpha,
        "code_residual_rms_m": None, "phase_residual_rms_m": None,
        "residual_vector_m": None, "ambiguity_log_determinant": None,
        "ADOP_ambiguity_dimension": None,
        "ADOP_cycles": None, "ADOP_threshold_cycles": policy.adop_threshold_cycles,
        "objective_equivalence_pass": False, "baseline_validation_pass": False,
        "posterior_residual_pass": False, "ADOP_pass": False,
        "global_optimum_certified": False, "subset_runtime_seconds": None,
        "mode_runtime_seconds": mode_runtime_seconds,
        "failure_code": failure_code, "failure_detail": failure_detail,
    } for policy in policies]


def _compute_epoch(epoch_index: int) -> dict[str, Any]:
    if _WORKER_READER is None or _WORKER_PROVIDER is None or _WORKER_LAMBDA is None:
        raise Phase4RunnerError("worker was not initialized")
    receiver1, receiver2 = _WORKER_READER.pair(epoch_index)
    modes: list[dict[str, Any]] = []
    for system_mode in SYSTEM_MODES:
        started = time.perf_counter()
        spp_audit: dict[str, Any] = {}
        try:
            spp1_result = _pntpos(_WORKER_PROVIDER, receiver1, system_mode, "GNSS1")
            spp2_result = _pntpos(_WORKER_PROVIDER, receiver2, system_mode, "GNSS2")
            spp_audit = {"GNSS1": _jsonable(spp1_result), "GNSS2": _jsonable(spp2_result)}
            spp1 = np.asarray(spp1_result.position_ecef_m, dtype=float)
            spp2 = np.asarray(spp2_result.position_ecef_m, dtype=float)
            blocks = build_epoch_blocks(
                receiver1, receiver2, _WORKER_PROVIDER, system_mode, spp1, spp2,
            )
            model = build_observation_model(blocks)
            chain = build_search_chain(
                model, bridge=_WORKER_LAMBDA, baseline_length_m=BASELINE_LENGTH_M,
                timeout_seconds=1.0, strict=True,
            )
            mode_runtime = time.perf_counter() - started
            decisions = all_policy_decisions(chain)
            rows = [
                _decision_row(
                    decision, system_mode=system_mode, epoch_index=epoch_index,
                    epoch=receiver1, full_ambiguity_count=model.ambiguity_count,
                    mode_runtime_seconds=mode_runtime,
                )
                for decision in decisions
            ]
            dd = {
                "method_id": METHOD_ID, "case_id": CASE_ID,
                "policy_identity": "SHARED_NATIVE_OBSERVATION_MODEL",
                "system_mode": system_mode, "epoch_index": epoch_index,
                "gps_week": receiver1.gps_week,
                "gps_tow_seconds": receiver1.gps_tow_seconds,
                "valid": True, "failure_code": None,
                "block_count": len(blocks),
                "blocks": _jsonable(blocks),
                "observation_count": int(model.observation_m.size),
                "full_ambiguity_count": model.ambiguity_count,
                "baseline_geometry_rank": int(np.linalg.matrix_rank(model.baseline_design)),
                "observation_covariance_condition": float(np.linalg.cond(model.covariance_m2)),
                "cross_system_DD": False,
                "separate_constellation_pivots": True,
                "spp_audit": spp_audit,
            }
            chain_rows = []
            for step, evaluation in enumerate(chain):
                metrics = evaluation.quality_metrics
                floating = evaluation.float_solution
                chain_rows.append({
                    "method_id": METHOD_ID, "case_id": CASE_ID,
                    "policy_identity": "SEARCH_CHAIN_SHARED",
                    "system_mode": system_mode, "epoch_index": epoch_index,
                    "gps_week": receiver1.gps_week,
                    "gps_tow_seconds": receiver1.gps_tow_seconds,
                    "subset_step": step,
                    "active_ambiguity_count": len(evaluation.active_identities),
                    "active_ambiguity_identities": _identity_list(evaluation.active_identities),
                    "removed_ambiguity_identities": _identity_list(evaluation.removed_identities),
                    "float_baseline_ned_m": floating.baseline,
                    "float_ambiguities_cycles": floating.ambiguity,
                    "Q_bhat_bhat": floating.covariance[-3:, -3:],
                    "Q_Nhat_Nhat_diagonal": np.diag(floating.covariance_aa),
                    "Q_bhat_Nhat_shape": list(floating.covariance_ba.shape),
                    "Q_bhat_Nhat_frobenius": float(np.linalg.norm(floating.covariance_ba)),
                    "Q_conditional_bhat_bhat": floating.conditional_covariance_b,
                    "float_residual_objective": floating.residual_objective,
                    "ambiguity_quality": _jsonable(evaluation.ambiguity_quality),
                    "search_certificate": _jsonable(evaluation.search_certificate),
                    "best_integer_ambiguities": None if evaluation.best is None else evaluation.best.ambiguity,
                    "second_integer_ambiguities": None if evaluation.second is None else evaluation.second.ambiguity,
                    "quality_metrics": None if metrics is None else _jsonable(metrics),
                    "failure_code": evaluation.failure_code,
                    "runtime_seconds": evaluation.runtime_seconds,
                })
            modes.append({
                "system_mode": system_mode, "rows": rows, "dd": dd,
                "chain": chain_rows, "failure": None,
            })
        except (RawBackendError, Wu2025Error, ValueError, np.linalg.LinAlgError) as exc:
            mode_runtime = time.perf_counter() - started
            failure_code = getattr(exc, "code", None) or (
                "NUMERICAL_LINEAR_ALGEBRA_FAILURE"
                if isinstance(exc, np.linalg.LinAlgError) else "EXT04_EPOCH_FAILURE"
            )
            rows = _invalid_policy_rows(
                system_mode=system_mode, epoch_index=epoch_index, epoch=receiver1,
                failure_code=failure_code, failure_detail=str(exc),
                mode_runtime_seconds=mode_runtime,
            )
            modes.append({
                "system_mode": system_mode, "rows": rows,
                "dd": {
                    "method_id": METHOD_ID, "case_id": CASE_ID,
                    "policy_identity": "SHARED_NATIVE_OBSERVATION_MODEL",
                    "system_mode": system_mode, "epoch_index": epoch_index,
                    "gps_week": receiver1.gps_week,
                    "gps_tow_seconds": receiver1.gps_tow_seconds,
                    "valid": False, "failure_code": failure_code,
                    "failure_detail": str(exc), "block_count": 0,
                    "observation_count": 0, "full_ambiguity_count": 0,
                    "baseline_geometry_rank": 0, "cross_system_DD": False,
                    "separate_constellation_pivots": True, "spp_audit": spp_audit,
                },
                "chain": [], "failure": {"code": failure_code, "detail": str(exc)},
            })
    return {
        "schema_version": "horizontal_literature.phase4.epoch_part.payload.v1",
        "epoch_index": epoch_index,
        "gps_week": receiver1.gps_week,
        "gps_tow_seconds": receiver1.gps_tow_seconds,
        "modes": modes,
    }


def _resource_probe(paths: Phase4Paths) -> dict[str, Any]:
    memory: dict[str, int] = {}
    with Path("/proc/meminfo").open("r", encoding="utf-8") as stream:
        for line in stream:
            key, value = line.split(":", 1)
            fields_value = value.strip().split()
            if fields_value and fields_value[0].isdigit():
                memory[key] = int(fields_value[0]) * 1024
    cpu_count = int(os.cpu_count() or 0)
    load1, load5, load15 = os.getloadavg()
    thermal = sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp"))
    thermal_values: list[float] = []
    for path in thermal:
        try:
            value = float(path.read_text(encoding="ascii").strip())
            thermal_values.append(value / 1000.0 if abs(value) > 1000 else value)
        except (OSError, ValueError):
            continue
    probe = {
        "cpu_count": cpu_count,
        "load_average_1m": load1,
        "load_average_5m": load5,
        "load_average_15m": load15,
        "memory_total_bytes": memory.get("MemTotal"),
        "memory_available_bytes": memory.get("MemAvailable"),
        "swap_total_bytes": memory.get("SwapTotal"),
        "swap_free_bytes": memory.get("SwapFree"),
        "thermal_readings_c": thermal_values,
        "stage_filesystem": subprocess.run(
            ["findmnt", "-n", "-T", str(paths.native_root), "-o", "FSTYPE"],
            text=True, capture_output=True, check=False,
        ).stdout.strip(),
        "workers_16_authorized": cpu_count >= 16,
        "workers_20_authorized": False,
        "workers_20_rejection_reason": (
            "NO_THERMAL_READING" if not thermal_values else "HUMAN_AUTHORIZATION_FIXED_TO_16"
        ),
        "selected_workers": AUTHORIZED_WORKERS,
    }
    load_gate = load1 <= max(2.0, 0.5 * cpu_count) and load5 <= max(3.0, 0.65 * cpu_count)
    memory_gate = (
        memory.get("MemAvailable", 0) >= max(4 * 1024**3, int(0.25 * memory.get("MemTotal", 0)))
    )
    probe.update({
        "stable_load_gate": load_gate,
        "stable_memory_gate": memory_gate,
        "stable_workers_16_launch_gate": bool(cpu_count >= 16 and load_gate and memory_gate),
        "load_gate_definition": "load1<=0.5*CPU_AND_load5<=0.65*CPU",
        "memory_gate_definition": "MemAvailable>=max(4GiB,0.25*MemTotal)",
    })
    if cpu_count < AUTHORIZED_WORKERS:
        raise Phase4RunnerError("resource probe cannot support the authorized 16 workers")
    return probe


def _prepare_cache(
    preflight: PreflightResult, attempt: Path, *, resume: bool,
) -> tuple[Path, tuple[Path, Path], dict[str, Any], dict[str, str]]:
    # The helper creates a new Phase-4-owned cache under this attempt.  It does
    # not read any EXT01/02/03 result or stage output.
    return phase2._prepare_or_resume_cache(preflight, attempt, resume=resume)


def _part_path(attempt: Path, epoch_index: int) -> Path:
    return attempt / "EPOCH_PARTS" / f"epoch_{epoch_index:04d}.json"


def _write_part(
    path: Path, source_fingerprint: str, payload: Mapping[str, Any],
) -> None:
    serial = _jsonable(payload)
    envelope = {
        "schema_version": "horizontal_literature.phase4.epoch_part.v1",
        "source_fingerprint": source_fingerprint,
        "epoch_index": int(payload["epoch_index"]),
        "payload_sha256": hashlib.sha256(_canonical(serial).encode()).hexdigest(),
        "payload": serial,
    }
    # These are restart shards, not published native evidence.  DrvFS lacks
    # renameat2(RENAME_NOREPLACE), and invoking the Windows/.NET fallback for
    # every completed worker result can time out while the pool is saturated.
    # O_EXCL gives the required no-replace property without cross-OS IPC.  A
    # crash-partial file is deliberately unrecoverable in place and fails the
    # strict JSON/self-hash validation below.
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(os.fspath(path)):
        raise Phase4RunnerError(f"epoch-part no-replace collision: {path.name}")
    data = (
        json.dumps(envelope, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError as exc:
        raise Phase4RunnerError(
            f"epoch-part no-replace collision: {path.name}"
        ) from exc


def _read_part(
    path: Path, source_fingerprint: str, epoch_index: int,
) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase4RunnerError("epoch-part envelope is partial or unreadable") from exc
    if (
        value.get("schema_version") != "horizontal_literature.phase4.epoch_part.v1"
        or value.get("source_fingerprint") != source_fingerprint
        or int(value.get("epoch_index", -1)) != epoch_index
    ):
        raise Phase4RunnerError("epoch-part identity mismatch")
    payload = value.get("payload")
    if hashlib.sha256(_canonical(payload).encode()).hexdigest() != value.get("payload_sha256"):
        raise Phase4RunnerError("epoch-part payload hash mismatch")
    if payload.get("epoch_index") != epoch_index or len(payload.get("modes", ())) != len(SYSTEM_MODES):
        raise Phase4RunnerError("epoch-part row conservation mismatch")
    return payload


DETERMINISM_RUNTIME_EXCLUSIONS = (
    "runtime_seconds", "subset_runtime_seconds", "mode_runtime_seconds",
)
DETERMINISM_INCOMPLETE_TIMEOUT_PROGRESS_EXCLUSIONS = (
    "lambda_seed_count_returned",
    "branch_and_bound_nodes_expanded",
    "integer_leaves_evaluated",
    "unique_integer_candidates_evaluated",
    "frontier_lower_bound_at_termination",
    "best_total_objective",
    "second_total_objective",
    "best_integer_ambiguities",
    "second_integer_ambiguities",
)
_DETERMINISM_EXCLUDED = "EXCLUDED_INCOMPLETE_TIMEOUT_PROGRESS"


def _scrub_runtime(value: Any) -> Any:
    """Normalize only non-scientific timing and incomplete timeout progress.

    State, timeout/certification status, subset identities, every float field,
    and every globally certified candidate/QC value remain in the equality
    comparison.  Raw timeout progress is preserved in production diagnostics;
    it is excluded only here because a CPU budget may expire between adjacent
    nodes without changing the explicit INVALID/SEARCH_TIMEOUT result.
    """

    if isinstance(value, Mapping):
        output = {
            key: _scrub_runtime(item)
            for key, item in value.items()
            if key not in DETERMINISM_RUNTIME_EXCLUSIONS
        }
        certificate = output.get("search_certificate")
        if isinstance(certificate, Mapping) and (
            certificate.get("termination_reason") == "SEARCH_TIMEOUT"
            and certificate.get("global_optimum_certified") is False
            and certificate.get("runtime_budget_exhausted") is True
        ):
            for key in ("best_integer_ambiguities", "second_integer_ambiguities"):
                if key in output:
                    output[key] = _DETERMINISM_EXCLUDED
        if (
            output.get("termination_reason") == "SEARCH_TIMEOUT"
            and output.get("global_optimum_certified") is False
            and output.get("runtime_budget_exhausted") is True
        ):
            for key in DETERMINISM_INCOMPLETE_TIMEOUT_PROGRESS_EXCLUSIONS:
                if key in output:
                    output[key] = _DETERMINISM_EXCLUDED
        return output
    if isinstance(value, list):
        return [_scrub_runtime(item) for item in value]
    return value


def _determinism_probe(
    cache_root: Path, navigation_paths: Sequence[Path], preflight: PreflightResult,
) -> dict[str, Any]:
    indices = tuple(round(index * (EXPECTED_PAIR_COUNT - 1) / 7) for index in range(8))
    initializer = (
        str(cache_root), tuple(str(path) for path in navigation_paths),
        str(preflight.paths.rtklib_bridge), str(preflight.paths.lambda_library),
    )
    _worker_initialize(*initializer)
    sequential = [_compute_epoch(index) for index in indices]
    with ProcessPoolExecutor(
        max_workers=AUTHORIZED_WORKERS,
        initializer=_worker_initialize,
        initargs=initializer,
    ) as executor:
        parallel = list(executor.map(_compute_epoch, indices, chunksize=1))
    left = _canonical(_scrub_runtime(sequential))
    right = _canonical(_scrub_runtime(parallel))
    exact = left == right
    result = {
        "indices": list(indices),
        "workers_compared": [1, AUTHORIZED_WORKERS],
        "scientific_fields_exact": exact,
        "workers_1_sha256": hashlib.sha256(left.encode()).hexdigest(),
        "workers_16_sha256": hashlib.sha256(right.encode()).hexdigest(),
        "runtime_fields_excluded": [
            *DETERMINISM_RUNTIME_EXCLUSIONS,
        ],
        "incomplete_timeout_progress_fields_excluded": [
            *DETERMINISM_INCOMPLETE_TIMEOUT_PROGRESS_EXCLUSIONS,
        ],
        "search_budget_clock": SEARCH_BUDGET_CLOCK,
        "certification_state_subset_and_certified_scientific_fields_compared": True,
    }
    if not exact:
        raise Phase4RunnerError("workers 1 versus 16 scientific determinism failed")
    return result


def _ext01_core_equivalence(
    cache_root: Path, navigation_paths: Sequence[Path], preflight: PreflightResult,
) -> dict[str, Any]:
    """Cross-check one real GPS-L1-only model without reading EXT01 outputs."""

    reader = phase2.CompactCacheReader(cache_root)
    provider = RtklibBroadcastProvider(preflight.paths.rtklib_bridge, navigation_paths)
    bridge = RTKLIBLambdaBridge(preflight.paths.lambda_library)
    selected_index: int | None = None
    model = None
    failure_counts: Counter[str] = Counter()
    for index in range(len(reader)):
        receiver1, receiver2 = reader.pair(index)
        try:
            spp1 = _pntpos(provider, receiver1, "GPS_DUAL_FREQUENCY", "GNSS1")
            spp2 = _pntpos(provider, receiver2, "GPS_DUAL_FREQUENCY", "GNSS2")
            blocks = build_epoch_blocks(
                receiver1, receiver2, provider, "GPS_DUAL_FREQUENCY",
                spp1.position_ecef_m, spp2.position_ecef_m,
            )
            l1 = tuple(block for block in blocks if block.frequency == "GPS_L1")
            full_model = build_observation_model(l1)
            if full_model.ambiguity_count < 3:
                continue
            candidate_model = None
            for active in combinations(full_model.source_ambiguity_indices, 3):
                try:
                    proposed = subset_observation_model(full_model, active)
                    joint_gls(
                        proposed.observation_m, proposed.ambiguity_design_m,
                        proposed.baseline_design, proposed.covariance_m2,
                    )
                except (Wu2025Error, ValueError, np.linalg.LinAlgError):
                    continue
                candidate_model = proposed
                break
            if candidate_model is None:
                continue
            model = candidate_model
            selected_index = index
            break
        except (RawBackendError, Wu2025Error) as exc:
            failure_counts[getattr(exc, "code", type(exc).__name__)] += 1
    if model is None or selected_index is None:
        raise Phase4RunnerError("no deterministic real GPS-L1 subset for EXT01 equivalence")

    ext04 = evaluate_subset(
        model, model.source_ambiguity_indices, bridge=bridge,
        timeout_seconds=5.0, strict=True,
    )
    floating = joint_gls(
        model.observation_m, model.ambiguity_design_m,
        model.baseline_design, model.covariance_m2,
    )
    ext01 = search_strict_lambda(
        floating, bridge, BASELINE_LENGTH_M,
        initial_candidate_count=8, node_limit=None, timeout_seconds=5.0,
    )
    if not ext04.search_certified or not ext01.certificate.global_optimum_certified:
        raise Phase4RunnerError("EXT01 equivalence subset did not certify both searches")
    if ext04.best is None or ext04.second is None or ext01.best is None or ext01.second is None:
        raise Phase4RunnerError("EXT01 equivalence subset lacks two candidates")
    checks = {
        "best_integer_equal": bool(np.array_equal(ext04.best.ambiguity, ext01.best.ambiguity)),
        "second_integer_equal": bool(np.array_equal(ext04.second.ambiguity, ext01.second.ambiguity)),
        "best_baseline_equal": bool(np.allclose(ext04.best.baseline, ext01.best.baseline, rtol=0.0, atol=1e-12)),
        "best_objective_equal": bool(math.isclose(ext04.best.objective, ext01.best.objective, rel_tol=1e-12, abs_tol=1e-12)),
        "second_objective_equal": bool(math.isclose(ext04.second.objective, ext01.second.objective, rel_tol=1e-12, abs_tol=1e-12)),
    }
    if not all(checks.values()):
        raise Phase4RunnerError(f"EXT04/EXT01 strict-core equivalence failed: {checks}")
    return {
        "role": "INPUT_ONLY_REAL_GPS_L1_STRICT_CORE_EQUIVALENCE",
        "epoch_index": selected_index,
        "ambiguity_dimension": model.ambiguity_count,
        "checks": checks,
        "EXT01_stage_outputs_read": False,
        "EXT01_stage_outputs_modified": False,
        "EXT01_runner_invoked": False,
        "eligible_search_failure_counts_before_selection": dict(failure_counts),
    }


def _run_epoch_parts(
    preflight: PreflightResult,
    attempt: Path,
    cache_root: Path,
    navigation_paths: Sequence[Path],
    *,
    workers: int,
    resume: bool,
) -> list[dict[str, Any]]:
    if workers != AUTHORIZED_WORKERS:
        raise Phase4RunnerError("formal Phase-4 run is fixed to 16 workers")
    parts_root = attempt / "EPOCH_PARTS"
    parts_root.mkdir(exist_ok=True)
    completed: dict[int, dict[str, Any]] = {}
    for index in range(EXPECTED_PAIR_COUNT):
        path = _part_path(attempt, index)
        if path.exists():
            if not resume:
                raise Phase4RunnerError("epoch part exists outside resume mode")
            completed[index] = _read_part(path, preflight.source_fingerprint, index)
    missing = [index for index in range(EXPECTED_PAIR_COUNT) if index not in completed]
    if missing:
        initializer = (
            str(cache_root), tuple(str(path) for path in navigation_paths),
            str(preflight.paths.rtklib_bridge), str(preflight.paths.lambda_library),
        )
        started = time.perf_counter()
        with ProcessPoolExecutor(
            max_workers=workers,
            initializer=_worker_initialize,
            initargs=initializer,
        ) as executor:
            futures = {executor.submit(_compute_epoch, index): index for index in missing}
            for ordinal, future in enumerate(as_completed(futures), start=1):
                index = futures[future]
                payload = future.result()
                _write_part(
                    _part_path(attempt, index), preflight.source_fingerprint, payload,
                )
                completed[index] = payload
                if ordinal % 50 == 0 or ordinal == len(missing):
                    elapsed = time.perf_counter() - started
                    print(
                        f"EXT04 epoch parts {ordinal}/{len(missing)} new; "
                        f"total {len(completed)}/{EXPECTED_PAIR_COUNT}; elapsed={elapsed:.1f}s",
                        flush=True,
                    )
    ordered = [
        completed.get(index)
        or _read_part(_part_path(attempt, index), preflight.source_fingerprint, index)
        for index in range(EXPECTED_PAIR_COUNT)
    ]
    if any(payload is None for payload in ordered):
        raise Phase4RunnerError("epoch-part conservation failed")
    return [dict(payload) for payload in ordered]


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    preferred = (
        "method_id", "case_id", "policy_identity", "reproduction_level",
        "primary_or_sensitivity", "changed_parameter", "system_mode",
        "epoch_index", "gps_week", "gps_tow_seconds", "solution_state",
        "accepted_by_policy", "failure_code",
    )
    names = set().union(*(row.keys() for row in rows)) if rows else set(preferred)
    ordered = [name for name in preferred if name in names]
    ordered.extend(sorted(names - set(ordered)))
    phase2._atomic_write_csv(path, rows, ordered)


def _numbers(rows: Sequence[Mapping[str, Any]], field: str) -> list[float]:
    result: list[float] = []
    for row in rows:
        value = row.get(field)
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            result.append(number)
    return result


def _distribution(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray([float(item) for item in values if math.isfinite(float(item))])
    if not array.size:
        return {
            "count": 0, "minimum": None, "median": None, "mean": None,
            "p90": None, "p95": None, "p99": None, "maximum": None,
        }
    return {
        "count": int(array.size), "minimum": float(np.min(array)),
        "median": float(np.median(array)), "mean": float(np.mean(array)),
        "p90": float(np.percentile(array, 90)),
        "p95": float(np.percentile(array, 95)),
        "p99": float(np.percentile(array, 99)), "maximum": float(np.max(array)),
    }


def _policy_summary(heading_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for policy in POLICY_ORDER:
        for mode in SYSTEM_MODES:
            rows = [
                row for row in heading_rows
                if row["policy_identity"] == policy and row["system_mode"] == mode
            ]
            counts = Counter(str(row["solution_state"]) for row in rows)
            failure_counts = Counter(
                str(row["failure_code"]) for row in rows if row.get("failure_code")
            )
            accepted = [row for row in rows if bool(row["accepted_by_policy"])]
            output.append({
                "method_id": METHOD_ID, "case_id": CASE_ID,
                "policy_identity": policy,
                "reproduction_level": rows[0]["reproduction_level"] if rows else None,
                "system_mode": mode, "row_count": len(rows),
                "expected_row_count": EXPECTED_PAIR_COUNT,
                "FAR_ACCEPTED_count": counts["FAR_ACCEPTED"],
                "PAR_ACCEPTED_count": counts["PAR_ACCEPTED"],
                "FAR_REJECTED_count": counts["FAR_REJECTED"],
                "PAR_EXHAUSTED_count": counts["PAR_EXHAUSTED"],
                "INVALID_count": counts["INVALID"],
                "failure_code_counts": dict(sorted(failure_counts.items())),
                "accepted_count": len(accepted),
                "accepted_rate": len(accepted) / EXPECTED_PAIR_COUNT,
                "global_optimum_certified_count": sum(
                    bool(row.get("global_optimum_certified")) for row in rows
                ),
                "objective_equivalence_pass_count": sum(
                    bool(row.get("objective_equivalence_pass")) for row in rows
                ),
                "baseline_validation_pass_count": sum(
                    bool(row.get("baseline_validation_pass")) for row in rows
                ),
                "posterior_residual_pass_count": sum(
                    bool(row.get("posterior_residual_pass")) for row in rows
                ),
                "ADOP_pass_count": sum(bool(row.get("ADOP_pass")) for row in rows),
                "full_ambiguity_count": _distribution(
                    _numbers(rows, "full_ambiguity_count")
                ),
                "active_ambiguity_count": _distribution(
                    _numbers(accepted, "active_ambiguity_count")
                ),
                "removed_ambiguity_count": _distribution(
                    _numbers(accepted, "removed_ambiguity_count")
                ),
                "all_rows_active_ambiguity_count": _distribution(
                    _numbers(rows, "active_ambiguity_count")
                ),
                "all_rows_removed_ambiguity_count": _distribution(
                    _numbers(rows, "removed_ambiguity_count")
                ),
                "second_over_best": _distribution(_numbers(accepted, "second_over_best")),
                "best_objective": _distribution(_numbers(accepted, "best_objective")),
                "second_objective": _distribution(_numbers(accepted, "second_objective")),
                "baseline_validation_residual_m": _distribution(
                    _numbers(accepted, "baseline_validation_residual_m")
                ),
                "posterior_p_value": _distribution(_numbers(accepted, "posterior_p_value")),
                "ADOP_cycles": _distribution(_numbers(accepted, "ADOP_cycles")),
                "shared_chain_mode_runtime_seconds_total": float(
                    sum(_numbers(rows, "mode_runtime_seconds"))
                ),
                "allocated_runtime_seconds_total": float(
                    sum(_numbers(rows, "mode_runtime_seconds"))
                ) / len(POLICY_ORDER),
                "subset_runtime_seconds": _distribution(
                    _numbers(rows, "subset_runtime_seconds")
                ),
            })
    return output


def _signal_rows(inventory: SignalInventoryResult) -> list[dict[str, Any]]:
    common = {"method_id": METHOD_ID, "case_id": CASE_ID,
              "policy_identity": "SIGNAL_AVAILABILITY_AUDIT"}
    rows = [{**common, **item.to_dict()} for item in inventory.rows]
    rows.extend({**common, **dict(item)} for item in inventory.epoch_rows)
    rows.extend({
        **common, "row_scope": "MODE_SUPPORT", **item.to_dict(),
    } for item in inventory.mode_support)
    rows.append({
        **common, "row_scope": "MODE_SUPPORT",
        "system_mode": "GALILEO_DUAL_FREQUENCY", "supported": False,
        "terminal_reason": "UNSUPPORTED_SUBMODE_NO_GALILEO_BROADCAST_EPHEMERIS",
        "required_frequency_groups": ["GALILEO_E1", "GALILEO_E5"],
        "eligible_epoch_count": 0,
    })
    return rows


def _stochastic_registry() -> list[dict[str, Any]]:
    rows = (
        ("baseline_length", 0.350, "m", "paper/project physical contract"),
        ("minimum_CNO", 20.0, "dB-Hz", "audited shared raw backend policy"),
        ("elevation_mask", 10.0, "deg", "audited Phase1R raw DD policy"),
        ("pseudorange_sigma", "max(0.50,0.01*2^prStdev)", "m", "shared_raw_backend.rawx_standard_deviations"),
        ("carrier_sigma", "max(0.004,0.004*cpStdev)", "cycles", "shared_raw_backend.rawx_standard_deviations"),
        ("DD_covariance", "diag(nonpivot_SD_variance)+pivot_SD_variance*11T", "m2", "shared raw backend"),
        ("DD_troposphere_relative_humidity", 0.0, "1", "Phase3 audited RTKLIB-zdres equivalent"),
        ("search_timeout_per_subset", 1.0, "s", "declared resource policy"),
        ("search_timeout_clock", SEARCH_BUDGET_CLOCK, "clock", "declared worker-determinism resource policy"),
        ("search_node_limit", "NONE", "node", "strict no-cap contract"),
        ("phase_bias_calibration", "NONE", "bool", "frozen prohibition"),
    )
    return [{
        "method_id": METHOD_ID, "case_id": CASE_ID,
        "policy_identity": "STOCHASTIC_REGISTRY", "parameter": parameter,
        "value": value, "unit": unit, "source": source, "trace_tuned": False,
    } for parameter, value, unit, source in rows]


def _policy_registry() -> list[dict[str, Any]]:
    policies = (
        PolicyParameters(
            FAR_POLICY_IDENTITY,
            reproduction_level="FAITHFUL_MODULE_MATHEMATICAL_CORE_WITH_DECLARED_QC_GATES",
            primary_or_sensitivity="FAR",
        ),
        PRIMARY_POLICY,
        *SENSITIVITY_POLICIES,
    )
    rows: list[dict[str, Any]] = []
    for policy in policies:
        sources = {
            "ratio_threshold": "PAPER_EXPERIMENTAL_VALUE",
            "baseline_tolerance_m": "PAPER_PARAMETER_TRANSPARENTLY_REPURPOSED",
            "posterior_alpha": "DECLARED_NOT_PAPER_DISCLOSED",
            "ADOP_threshold_cycles": "DECLARED_STANDARD_GNSS_POLICY_NOT_PAPER_DISCLOSED",
        }
        for parameter, value in (
            ("ratio_threshold", policy.ratio_threshold),
            ("baseline_tolerance_m", policy.baseline_tolerance_m),
            ("posterior_alpha", policy.posterior_alpha),
            ("ADOP_threshold_cycles", policy.adop_threshold_cycles),
        ):
            rows.append({
                "method_id": METHOD_ID, "case_id": CASE_ID,
                "policy_identity": policy.policy_identity,
                "reproduction_level": policy.reproduction_level,
                "primary_or_sensitivity": policy.primary_or_sensitivity,
                "changed_parameter": policy.changed_parameter,
                "parameter": parameter, "value": value,
                "source": sources[parameter],
                "selected_from_sensitivity": False,
                "ratio_acceptance_convention": "SECOND_OVER_BEST_GE_THRESHOLD",
                "prompt_literal_ratio_conflict_recorded": True,
            })
    rows.append({
        "method_id": METHOD_ID, "case_id": CASE_ID,
        "policy_identity": POLICY_IDENTITY,
        "reproduction_level": REPRODUCTION_LEVEL,
        "primary_or_sensitivity": "PRIMARY", "parameter": "removal_order",
        "value": [
            "lower_minimum_two_receiver_CNO", "lower_satellite_elevation",
            "larger_marginal_float_variance",
            "larger_absolute_normalized_phase_residual",
            "constellation", "satellite_ID", "signal_ID",
        ],
        "source": "DECLARED_DETERMINISTIC_POLICY_FROM_PAPER_QUALITATIVE_FACTORS",
        "selected_from_sensitivity": False,
    })
    rows.append({
        "method_id": METHOD_ID, "case_id": CASE_ID,
        "policy_identity": POLICY_IDENTITY,
        "reproduction_level": REPRODUCTION_LEVEL,
        "primary_or_sensitivity": "PRIMARY",
        "parameter": "re_rank_after_each_rebuilt_float_subset",
        "value": True,
        "source": "DECLARED_DETERMINISTIC_POLICY_INTERPRETATION_NOT_PAPER_DISCLOSED",
        "selected_from_sensitivity": False,
    })
    return rows


def _flatten_native(
    preflight: PreflightResult,
    attempt: Path,
    epoch_payloads: Sequence[Mapping[str, Any]],
    inventory: SignalInventoryResult,
    resource_probe: Mapping[str, Any],
    determinism_probe: Mapping[str, Any],
    ext01_core_equivalence: Mapping[str, Any],
    cache_manifest: Mapping[str, Any],
    derived_provider_hashes: Mapping[str, str],
) -> dict[str, Any]:
    native = attempt / "NATIVE"
    if native.exists():
        raise Phase4RunnerError("attempt native output already exists")
    native.mkdir()
    heading: list[dict[str, Any]] = []
    dd: list[dict[str, Any]] = []
    chain_rows: list[dict[str, Any]] = []
    for payload in epoch_payloads:
        for mode in payload["modes"]:
            heading.extend(dict(row) for row in mode["rows"])
            dd.append(dict(mode["dd"]))
            chain_rows.extend(dict(row) for row in mode["chain"])
    policy_index = {value: index for index, value in enumerate(POLICY_ORDER)}
    mode_index = {value: index for index, value in enumerate(SYSTEM_MODES)}
    heading.sort(key=lambda row: (
        policy_index[row["policy_identity"]], mode_index[row["system_mode"]],
        int(row["epoch_index"]),
    ))
    dd.sort(key=lambda row: (mode_index[row["system_mode"]], int(row["epoch_index"])))
    chain_rows.sort(key=lambda row: (
        mode_index[row["system_mode"]], int(row["epoch_index"]), int(row["subset_step"]),
    ))
    if len(heading) != EXPECTED_HEADING_ROWS:
        raise Phase4RunnerError(
            f"heading row conservation failed: {len(heading)} != {EXPECTED_HEADING_ROWS}"
        )
    counts = Counter((row["policy_identity"], row["system_mode"]) for row in heading)
    if set(counts.values()) != {EXPECTED_PAIR_COUNT} or len(counts) != len(POLICY_ORDER) * len(SYSTEM_MODES):
        raise Phase4RunnerError("policy/mode row conservation failed")
    required = {
        "method_id", "policy_identity", "reproduction_level", "system_mode",
        "epoch_index", "baseline_n_m", "baseline_e_m", "baseline_d_m",
        "baseline_length_m", "baseline_yaw_deg", "body_yaw_deg", "pitch_deg",
        "solution_state", "active_ambiguity_identities",
        "removed_ambiguity_identities", "best_objective", "second_objective",
        "second_over_best", "best_over_second",
        "unconstrained_conditional_baseline_norm_m",
        "baseline_validation_residual_m", "posterior_residual_statistic",
        "posterior_p_value", "ADOP_cycles", "mode_runtime_seconds", "failure_code",
    }
    if any(not required <= set(row) for row in heading):
        raise Phase4RunnerError("native heading schema is incomplete")

    runtime = [{
        key: row.get(key) for key in (
            "method_id", "case_id", "policy_identity", "reproduction_level",
            "system_mode", "epoch_index", "gps_week", "gps_tow_seconds",
            "solution_state", "subset_runtime_seconds", "mode_runtime_seconds",
            "failure_code",
        )
    } for row in heading]
    failures = [{
        key: row.get(key) for key in (
            "method_id", "case_id", "policy_identity", "reproduction_level",
            "system_mode", "epoch_index", "gps_week", "gps_tow_seconds",
            "solution_state", "failure_code", "failure_detail",
        )
    } for row in heading if row["solution_state"] in {
        "FAR_REJECTED", "PAR_EXHAUSTED", "INVALID",
    }]
    float_diagnostics = [{
        key: row.get(key) for key in (
            "method_id", "case_id", "policy_identity", "system_mode", "epoch_index",
            "gps_week", "gps_tow_seconds", "subset_step", "active_ambiguity_count",
            "active_ambiguity_identities", "removed_ambiguity_identities",
            "float_baseline_ned_m", "float_ambiguities_cycles", "Q_bhat_bhat",
            "Q_Nhat_Nhat_diagonal", "Q_bhat_Nhat_shape", "Q_bhat_Nhat_frobenius",
            "Q_conditional_bhat_bhat", "float_residual_objective",
            "ambiguity_quality", "failure_code", "runtime_seconds",
        )
    } for row in chain_rows]
    search_certificates = [{
        "method_id": row["method_id"], "case_id": row["case_id"],
        "policy_identity": row["policy_identity"], "system_mode": row["system_mode"],
        "epoch_index": row["epoch_index"], "gps_week": row["gps_week"],
        "gps_tow_seconds": row["gps_tow_seconds"], "subset_step": row["subset_step"],
        "active_ambiguity_count": row["active_ambiguity_count"],
        **dict(row.get("search_certificate") or {}),
        "failure_code": row.get("failure_code"),
    } for row in chain_rows]
    far = [dict(row) for row in heading if row["policy_identity"] == FAR_POLICY_IDENTITY]
    par = [dict(row) for row in heading if row["policy_identity"] != FAR_POLICY_IDENTITY]
    qc_fields = (
        "method_id", "case_id", "policy_identity", "reproduction_level",
        "system_mode", "epoch_index", "gps_week", "gps_tow_seconds",
        "solution_state", "accepted_by_policy", "active_ambiguity_count",
        "removed_ambiguity_count", "best_objective", "second_objective",
        "second_over_best", "best_over_second", "ratio_threshold",
        "objective_equivalence_pass", "unconstrained_conditional_baseline_ned_m",
        "unconstrained_conditional_baseline_norm_m", "baseline_validation_residual_m",
        "baseline_tolerance_m", "baseline_validation_pass",
        "residual_vector_m", "posterior_residual_statistic",
        "posterior_degrees_of_freedom", "posterior_p_value", "posterior_alpha",
        "posterior_residual_pass", "code_residual_rms_m", "phase_residual_rms_m",
        "ambiguity_log_determinant", "ADOP_cycles", "ADOP_threshold_cycles",
        "ADOP_ambiguity_dimension",
        "ADOP_pass", "failure_code",
    )
    qc = [{key: row.get(key) for key in qc_fields} for row in heading]
    summaries = _policy_summary(heading)
    sensitivity = [
        row for row in summaries
        if row["policy_identity"] in {policy.policy_identity for policy in SENSITIVITY_POLICIES}
    ]
    signal = _signal_rows(inventory)
    stochastic = _stochastic_registry()
    policy_registry = _policy_registry()
    files = {key: native / name for key, name in NATIVE_FILE_NAMES.items()}
    datasets = {
        "heading_results": heading, "failure_ledger": failures,
        "runtime": runtime, "signal_availability": signal,
        "dd_diagnostics": dd, "float_diagnostics": float_diagnostics,
        "far_diagnostics": far, "par_diagnostics": par,
        "search_certificates": search_certificates,
        "quality_control_diagnostics": qc, "policy_summary": summaries,
        "sensitivity_summary": sensitivity,
        "stochastic_registry": stochastic, "policy_registry": policy_registry,
    }
    for key, rows in datasets.items():
        _write_csv(files[key], rows)
    flags = {
        "data_mode": "real_by2_raw", "synthetic_data_used": False,
        "semisynthetic_data_used": False, "trace_used_online": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False, "per_case_tuning": False,
        "output_only_correction": False, "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0, "HPPOSECEF_solver_input": False,
        "status_baseline_solver_input": False, "Go2_yaw_solver_input": False,
        "EXT01_output_solver_input": False, "EXT02_output_solver_input": False,
        "EXT03_output_solver_input": False,
        "RTKLIB_diagnostic_output_solver_input": False,
        "phase_bias_calibration": False,
    }
    summary = {
        "schema_version": "horizontal_literature.phase4.native_summary.v1",
        "method_id": METHOD_ID, "case_id": CASE_ID,
        "policy_identity": POLICY_IDENTITY,
        "reproduction_level": REPRODUCTION_LEVEL,
        "paper_exact_policy_status": "NOT_IMPLEMENTED_UNDER_SPECIFIED",
        "official_code_search_result": "NO_ATTRIBUTABLE_OFFICIAL_IMPLEMENTATION_FOUND",
        "paired_epoch_count": EXPECTED_PAIR_COUNT,
        "system_modes": list(SYSTEM_MODES),
        "unsupported_submodes": [{
            "mode": "GALILEO_DUAL_FREQUENCY",
            "reason": "UNSUPPORTED_SUBMODE_NO_GALILEO_BROADCAST_EPHEMERIS",
        }],
        "policy_order": list(POLICY_ORDER),
        "heading_row_count": len(heading),
        "expected_heading_row_count": EXPECTED_HEADING_ROWS,
        "row_counts": {key: len(rows) for key, rows in datasets.items()},
        "policy_summary": summaries,
        "resource_probe": resource_probe,
        "worker_determinism": determinism_probe,
        "EXT01_core_equivalence": ext01_core_equivalence,
        "compact_cache": cache_manifest,
        "derived_provider_hashes": dict(derived_provider_hashes),
        "trace_open_count": 0, "HPPOSECEF_semantic_decode_count": 0,
        "native_freeze_installed_before_post_native": True,
        "paper_hashes": dict(preflight.paper_hashes),
        "raw_source_hashes": dict(preflight.raw_source_hashes),
        "provider_hashes": dict(preflight.provider_hashes),
        "code_commit": preflight.code_commit,
        "code_commit_semantics": "IMMUTABLE_TASK_START_HEAD_PLUS_VALIDATED_EXECUTION_STATE",
        "task_start_head": preflight.task_start_head,
        "execution_head": preflight.execution_head,
        "provenance_mode": preflight.provenance_mode,
        "runtime_content_fingerprint": preflight.runtime_content_fingerprint,
        "execution_lock_evidence": dict(preflight.execution_lock_evidence),
        "runtime_source_hashes": dict(preflight.runtime_source_hashes),
        "runtime_dependency_hashes": dict(preflight.runtime_dependency_hashes),
        "worktree_overlay_identity": dict(preflight.worktree_overlay_identity),
        "config_hash": preflight.config_hash,
        "contract_hash": preflight.contract_hash,
        "source_fingerprint": preflight.source_fingerprint,
        "data_flags": flags,
        "preexisting_manifest_path": str(preflight.preexisting_manifest_path),
        "preexisting_manifest_sha256": preflight.preexisting_manifest_sha256,
        "preexisting_manifest_content_read": False,
        "artifact_root_evidence": dict(preflight.artifact_root_evidence),
    }
    phase2._atomic_write_json(files["native_summary"], summary)
    native_hashes = {key: _sha256(files[key]) for key in FREEZE_HASH_KEYS}
    freeze = {
        "schema_version": "horizontal_literature.phase4.native_freeze.v1",
        "source_fingerprint": preflight.source_fingerprint,
        "task_start_head": preflight.task_start_head,
        "execution_head": preflight.execution_head,
        "provenance_mode": preflight.provenance_mode,
        "runtime_content_fingerprint": preflight.runtime_content_fingerprint,
        "execution_lock_evidence": dict(preflight.execution_lock_evidence),
        "native_hashes": native_hashes,
        "native_row_counts": {key: len(rows) for key, rows in datasets.items()},
        "paired_epoch_count": EXPECTED_PAIR_COUNT,
        "policy_count": len(POLICY_ORDER), "system_mode_count": len(SYSTEM_MODES),
        "heading_row_count": len(heading),
        "trace_open_count_at_freeze": 0,
        "HPPOSECEF_semantic_decode_count_at_freeze": 0,
        "status_baseline_solver_input": False, "Go2_yaw_solver_input": False,
        "EXT01_output_solver_input": False, "EXT02_output_solver_input": False,
        "EXT03_output_solver_input": False, "LegSA_output_solver_input": False,
        "RTKLIB_diagnostic_output_solver_input": False,
        "phase_bias_calibration": False,
        "ambiguity_correctness_known": False,
        "preexisting_manifest_path": str(preflight.preexisting_manifest_path),
        "preexisting_manifest_sha256": preflight.preexisting_manifest_sha256,
        "artifact_root_evidence": dict(preflight.artifact_root_evidence),
        "data_flags": flags,
    }
    phase2._atomic_write_json(files["native_freeze"], freeze)
    validate_native_freeze(native)
    return freeze


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def validate_native_freeze(root: Path) -> dict[str, Any]:
    path = Path(root) / NATIVE_FILE_NAMES["native_freeze"]
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        value.get("schema_version") != "horizontal_literature.phase4.native_freeze.v1"
        or value.get("trace_open_count_at_freeze") != 0
        or value.get("HPPOSECEF_semantic_decode_count_at_freeze") != 0
        or set(value.get("native_hashes", {})) != set(FREEZE_HASH_KEYS)
    ):
        raise Phase4RunnerError("invalid native freeze boundary")
    for key, digest in value["native_hashes"].items():
        if _sha256(Path(root) / NATIVE_FILE_NAMES[key]) != digest:
            raise Phase4RunnerError(f"native hash mismatch: {key}")
    expected = EXPECTED_PAIR_COUNT * len(POLICY_ORDER) * len(SYSTEM_MODES)
    if int(value.get("heading_row_count", -1)) != expected:
        raise Phase4RunnerError("native heading row conservation failed")
    headings = _read_csv(Path(root) / NATIVE_FILE_NAMES["heading_results"])
    if len(headings) != expected:
        raise Phase4RunnerError("native heading CSV row count mismatch")
    keys = Counter((row["policy_identity"], row["system_mode"]) for row in headings)
    if set(keys.values()) != {EXPECTED_PAIR_COUNT} or len(keys) != len(POLICY_ORDER) * len(SYSTEM_MODES):
        raise Phase4RunnerError("native per-policy/mode conservation failed")
    order = [
        (POLICY_ORDER.index(row["policy_identity"]), SYSTEM_MODES.index(row["system_mode"]), int(row["epoch_index"]))
        for row in headings
    ]
    if order != sorted(order):
        raise Phase4RunnerError("native heading ordering is nondeterministic")
    return value


def _publish_native(preflight: PreflightResult, attempt: Path) -> dict[str, Any]:
    source = attempt / "NATIVE"
    freeze = validate_native_freeze(source)
    if _sha256(preflight.preexisting_manifest_path) != preflight.preexisting_manifest_sha256:
        raise Phase4RunnerError("pre-existing stage manifest changed before publication")
    for key in (*FREEZE_HASH_KEYS, "native_freeze"):
        phase2._atomic_install_noreplace(
            source / NATIVE_FILE_NAMES[key],
            preflight.paths.native_root / NATIVE_FILE_NAMES[key],
            label=f"Phase-4 native {key}",
        )
    observed = validate_native_freeze(preflight.paths.native_root)
    if observed != freeze:
        raise Phase4RunnerError("published native freeze differs from attempt freeze")
    if _sha256(preflight.preexisting_manifest_path) != preflight.preexisting_manifest_sha256:
        raise Phase4RunnerError("pre-existing stage manifest changed during publication")
    return observed


def _nearest_hpposecef(reconstruction: Any, tow_seconds: float) -> tuple[Any, int]:
    target = round(tow_seconds * 1000.0)
    if not reconstruction.nav_hpposecef_epochs:
        raise Phase4RunnerError("NAV-HPPOSECEF diagnostic stream is absent")
    epoch = min(
        reconstruction.nav_hpposecef_epochs,
        key=lambda item: (abs(item.itow_ms - target), item.itow_ms),
    )
    offset = int(epoch.itow_ms - target)
    if abs(offset) > 10:
        raise Phase4RunnerError("NAV-HPPOSECEF violates fixed 10 ms association gate")
    return epoch, offset


def _vector_angle_degrees(first: Sequence[float], second: Sequence[float]) -> float | None:
    left = np.asarray(first, dtype=float)
    right = np.asarray(second, dtype=float)
    product = float(np.linalg.norm(left) * np.linalg.norm(right))
    if not math.isfinite(product) or product <= 0.0:
        return None
    return math.degrees(math.acos(float(np.clip(np.dot(left, right) / product, -1.0, 1.0))))


def _proxy_map(
    preflight: PreflightResult, attempt: Path, cache_root: Path,
    *, work_root: Path | None = None,
) -> tuple[dict[int, dict[str, Any]], dict[str, Any]]:
    validate_native_freeze(preflight.paths.native_root)
    post = Path(work_root) if work_root is not None else attempt / "POST_NATIVE_WORK"
    post.mkdir(exist_ok=True)
    ubx1 = post / "gnss1_hpposecef_semantic_decode.ubx"
    ubx2 = post / "gnss2_hpposecef_semantic_decode.ubx"
    if ubx1.exists() or ubx2.exists():
        raise Phase4RunnerError("post-native semantic-decode target collision")
    reconstruction1 = reconstruct_ubx_stream(
        preflight.paths.gnss1_raw, ubx1, decode_nav_hpposecef_semantics=True,
    )
    reconstruction2 = reconstruct_ubx_stream(
        preflight.paths.gnss2_raw, ubx2, decode_nav_hpposecef_semantics=True,
    )
    if not (
        reconstruction1.nav_hpposecef_semantic_decode_enabled
        and reconstruction2.nav_hpposecef_semantic_decode_enabled
    ):
        raise Phase4RunnerError("post-native HPPOSECEF semantic decode did not activate")
    hp1 = {item.itow_ms: item for item in reconstruction1.nav_hpposecef_epochs}
    hp2 = {item.itow_ms: item for item in reconstruction2.nav_hpposecef_epochs}
    if len(hp1) != len(reconstruction1.nav_hpposecef_epochs) or len(hp2) != len(reconstruction2.nav_hpposecef_epochs):
        raise Phase4RunnerError("duplicate HPPOSECEF iTOW in diagnostic stream")
    reader = phase2.CompactCacheReader(cache_root)
    raw_itows = [
        int(round(reader.pair(index)[0].gps_tow_seconds * 1000.0)) % 604_800_000
        for index in range(len(reader))
    ]
    associations = phase2._proxy_common_grid_associations(
        sorted(set(raw_itows)), list(hp1), list(hp2),
    )
    association_by_raw = {
        int(item["rawx_itow_ms"]): item for item in associations
    }
    observed_offsets = {
        item.get("proxy_itow_minus_rawx_ms") for item in associations
        if item.get("proxy_association_status")
        == "ASSOCIATED_UNIQUE_NEAREST_COMMON_ITOW"
    }
    if observed_offsets != {2}:
        raise Phase4RunnerError(
            f"audited HPPOSECEF fixed association is not +2 ms: {observed_offsets}"
        )
    rows: dict[int, dict[str, Any]] = {}
    for index in range(len(reader)):
        receiver1, _receiver2 = reader.pair(index)
        raw_itow = raw_itows[index]
        association = association_by_raw.get(raw_itow)
        if (
            association is None
            or association.get("proxy_association_status")
            != "ASSOCIATED_UNIQUE_NEAREST_COMMON_ITOW"
        ):
            raise Phase4RunnerError("HPPOSECEF fixed association unavailable")
        proxy_itow = int(association["proxy_itow_ms"])
        if proxy_itow not in hp1 or proxy_itow not in hp2:
            raise Phase4RunnerError("HPPOSECEF fixed association target absent")
        first, second = hp1[proxy_itow], hp2[proxy_itow]
        offset = int(association["proxy_itow_minus_rawx_ms"])
        baseline_ecef = second.position_ecef_m - first.position_ecef_m
        midpoint = 0.5 * (second.position_ecef_m + first.position_ecef_m)
        baseline_ned = _ecef_vector_to_ned(baseline_ecef, midpoint)
        attitude = attitude_from_ned_baseline(baseline_ned)
        rows[index] = {
            "epoch_index": index, "gps_week": receiver1.gps_week,
            "gps_tow_seconds": receiver1.gps_tow_seconds,
            "rawx_itow_ms": raw_itow,
            "proxy_itow_ms": proxy_itow,
            "hpposecef_offset_receiver1_ms": offset,
            "hpposecef_offset_receiver2_ms": offset,
            "proxy_baseline_ecef_m": baseline_ecef,
            "proxy_baseline_ned_m": baseline_ned,
            "proxy_length_m": float(np.linalg.norm(baseline_ned)),
            "proxy_baseline_yaw_deg": attitude.baseline_yaw_deg,
            "proxy_body_yaw_deg": attitude.body_yaw_deg,
            "proxy_pitch_deg": attitude.pitch_deg,
        }
    return rows, {
        "HPPOSECEF_semantic_decode_count": 2,
        "fixed_association_offset_ms": 2,
        "association_policy": "AUDITED_UNIQUE_NEAREST_COMMON_GRID_CONFIRMED_PLUS_2MS",
        "proxy_epoch_count": len(rows),
        "role": "FIXPOSITION_SAME_SOURCE_DESCRIPTIVE_REFERENCE_NOT_INDEPENDENT_TRUTH",
        "used_as_solver_input": False,
    }


def _strict_bool(value: Any) -> bool:
    if value in (True, "true", "True", "1", 1):
        return True
    if value in (False, "false", "False", "0", 0):
        return False
    raise Phase4RunnerError(f"invalid serialized boolean: {value!r}")


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _proxy_diagnostics(
    headings: Sequence[Mapping[str, str]], proxies: Mapping[int, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for native in headings:
        if not _strict_bool(native["accepted_by_policy"]):
            continue
        index = int(native["epoch_index"])
        proxy = proxies[index]
        baseline = np.asarray([
            float(native["baseline_n_m"]), float(native["baseline_e_m"]),
            float(native["baseline_d_m"]),
        ])
        angle = _vector_angle_degrees(baseline, proxy["proxy_baseline_ned_m"])
        body_error = wrap_safe_residual_degrees(
            float(native["body_yaw_deg"]), float(proxy["proxy_body_yaw_deg"])
        )
        pitch_error = float(native["pitch_deg"]) - float(proxy["proxy_pitch_deg"])
        row = {
            "method_id": METHOD_ID, "case_id": CASE_ID,
            "policy_identity": native["policy_identity"],
            "reproduction_level": native["reproduction_level"],
            "system_mode": native["system_mode"], "epoch_index": index,
            "gps_week": int(native["gps_week"]),
            "gps_tow_seconds": float(native["gps_tow_seconds"]),
            "solution_state": native["solution_state"],
            **dict(proxy),
            "native_baseline_ned_m": baseline,
            "native_proxy_vector_angle_deg": angle,
            "native_minus_proxy_body_yaw_error_deg": body_error,
            "native_minus_proxy_pitch_error_deg": pitch_error,
            "proxy_inconsistent_above_30_deg": angle is not None and angle > 30.0,
            "second_over_best": _optional_float(native.get("second_over_best")),
            "baseline_validation_residual_m": _optional_float(native.get("baseline_validation_residual_m")),
            "posterior_p_value": _optional_float(native.get("posterior_p_value")),
            "ADOP_cycles": _optional_float(native.get("ADOP_cycles")),
            "role": "POST_NATIVE_DESCRIPTIVE_ONLY",
            "used_to_alter_policy": False,
        }
        rows.append(row)
        consistency = "INCONSISTENT_GT30" if row["proxy_inconsistent_above_30_deg"] else "CONSISTENT_LE30"
        groups[(native["policy_identity"], native["system_mode"], consistency)].append(row)
    summary = {
        "accepted_proxy_row_count": len(rows),
        "proxy_inconsistent_above_30_deg_count": sum(
            bool(row["proxy_inconsistent_above_30_deg"]) for row in rows
        ),
        "groups": [{
            "policy_identity": policy, "system_mode": mode,
            "consistency_class": consistency, "count": len(values),
            "vector_angle_deg": _distribution(_numbers(values, "native_proxy_vector_angle_deg")),
            "body_yaw_error_deg": _distribution(
                abs(value) for value in _numbers(values, "native_minus_proxy_body_yaw_error_deg")
            ),
            "pitch_error_deg": _distribution(
                abs(value) for value in _numbers(values, "native_minus_proxy_pitch_error_deg")
            ),
            "second_over_best": _distribution(_numbers(values, "second_over_best")),
            "baseline_validation_residual_m": _distribution(
                _numbers(values, "baseline_validation_residual_m")
            ),
            "posterior_p_value": _distribution(_numbers(values, "posterior_p_value")),
            "ADOP_cycles": _distribution(_numbers(values, "ADOP_cycles")),
        } for (policy, mode, consistency), values in sorted(groups.items())],
    }
    return rows, summary


def _error_statistics(values: Iterable[float]) -> dict[str, Any]:
    array = np.asarray([float(item) for item in values if math.isfinite(float(item))])
    if not array.size:
        return {
            "count": 0, "bias": None, "RMSE": None, "MAE": None,
            "median_abs": None, "P90_abs": None, "P95_abs": None,
            "P99_abs": None, "max_abs": None,
        }
    absolute = np.abs(array)
    return {
        "count": int(array.size), "bias": float(np.mean(array)),
        "RMSE": float(np.sqrt(np.mean(array * array))),
        "MAE": float(np.mean(absolute)), "median_abs": float(np.median(absolute)),
        "P90_abs": float(np.percentile(absolute, 90)),
        "P95_abs": float(np.percentile(absolute, 95)),
        "P99_abs": float(np.percentile(absolute, 99)),
        "max_abs": float(np.max(absolute)),
    }


def _trace_diagnostics(
    preflight: PreflightResult, cache_root: Path,
    headings: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    validate_native_freeze(preflight.paths.native_root)
    leap_seconds, leap_evidence = phase2._validated_compact_cache_leap_seconds(
        cache_root
    )
    trace_payload, trace_sha256 = phase2._locked_trace_bytes(preflight.paths)
    stream = io.StringIO(trace_payload.decode("utf-8-sig"))
    reader = csv.DictReader(stream)
    if reader.fieldnames != list(phase2.TRACE_CSV_COLUMNS):
        raise Phase4RunnerError("trace schema differs from frozen evaluator")
    trace_rows = list(reader)
    if not trace_rows:
        raise Phase4RunnerError("trace contains no rows")
    times = np.asarray([float(row["time"]) for row in trace_rows])
    yaw = np.asarray([float(row["yaw"]) for row in trace_rows])
    if np.any(~np.isfinite(times)) or np.any(~np.isfinite(yaw)) or np.any(np.diff(times) <= 0):
        raise Phase4RunnerError("trace time/yaw is invalid")
    unwrapped = np.degrees(np.unwrap(np.radians(yaw)))
    base_time, start_offset, end_offset = 1772784000.0, 66.0, 340.0
    window_start, window_end = base_time + start_offset, base_time + end_offset
    rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    accepted_counts = Counter(
        (row["policy_identity"], row["system_mode"])
        for row in headings if _strict_bool(row["accepted_by_policy"])
    )
    for native in headings:
        if not _strict_bool(native["accepted_by_policy"]):
            continue
        unix_time = (
            315_964_800.0 + int(native["gps_week"]) * 604_800.0
            + float(native["gps_tow_seconds"]) - leap_seconds
        )
        if unix_time < window_start or unix_time > window_end:
            continue
        if unix_time < times[0] or unix_time > times[-1]:
            continue
        reference_enu = float(np.interp(unix_time, times, unwrapped))
        reference_ned = (90.0 - reference_enu) % 360.0
        error = wrap_safe_residual_degrees(float(native["body_yaw_deg"]), reference_ned)
        row = {
            "method_id": METHOD_ID, "case_id": CASE_ID,
            "policy_identity": native["policy_identity"],
            "reproduction_level": native["reproduction_level"],
            "system_mode": native["system_mode"],
            "epoch_index": int(native["epoch_index"]),
            "gps_week": int(native["gps_week"]),
            "gps_tow_seconds": float(native["gps_tow_seconds"]),
            "unix_time_seconds": unix_time,
            "native_body_yaw_deg": float(native["body_yaw_deg"]),
            "trace_yaw_enu_unwrapped_deg": reference_enu,
            "trace_yaw_reference_ned_deg": reference_ned,
            "native_minus_trace_body_yaw_error_deg": error,
            "base_time_unix_seconds": base_time,
            "window_start_seconds": start_offset,
            "window_end_seconds": end_offset,
            "time_search": False, "frame_search": False,
            "alignment": False, "constant_offset_correction": False,
            "error_based_epoch_deletion": False,
        }
        rows.append(row)
        grouped[(native["policy_identity"], native["system_mode"])].append(row)
    summaries: list[dict[str, Any]] = []
    for policy in POLICY_ORDER:
        for mode in SYSTEM_MODES:
            values = grouped.get((policy, mode), [])
            indices = sorted(int(row["epoch_index"]) for row in values)
            times_matched = sorted(float(row["unix_time_seconds"]) for row in values)
            errors = [float(row["native_minus_trace_body_yaw_error_deg"]) for row in values]
            accepted = accepted_counts[(policy, mode)]
            runs: list[int] = []
            current_run = 0
            prior_index: int | None = None
            for index in indices:
                current_run = current_run + 1 if prior_index is not None and index == prior_index + 1 else 1
                runs.append(current_run)
                prior_index = index
            summaries.append({
                "method_id": METHOD_ID, "case_id": CASE_ID,
                "policy_identity": policy, "system_mode": mode,
                "accepted_count": accepted, "matched_count": len(values),
                "coverage_of_accepted": len(values) / accepted if accepted else 0.0,
                **_error_statistics(errors),
                "continuity_matched_epoch_count": len(indices),
                "continuity_longest_consecutive_epoch_run": max(runs, default=0),
                "continuity_adjacent_pair_rate": (
                    sum(right == left + 1 for left, right in zip(indices, indices[1:]))
                    / (len(indices) - 1) if len(indices) >= 2 else None
                ),
                "maximum_epoch_index_gap": max(
                    (right - left for left, right in zip(indices, indices[1:])),
                    default=None,
                ),
                "maximum_time_gap_seconds": max(
                    (right - left for left, right in zip(times_matched, times_matched[1:])),
                    default=None,
                ),
                "base_time_unix_seconds": base_time,
                "window_start_seconds": start_offset,
                "window_end_seconds": end_offset,
            })
    return rows, summaries, {
        "trace_open_count": 1,
        "trace_sha256": trace_sha256, "trace_row_count": len(trace_rows),
        "leap_second_evidence": leap_evidence,
        "conversion": "wrap360(90-yaw_trace_enu)",
        "yaw_processing": "UNWRAP_THEN_INTERPOLATE",
        "time_search": False, "frame_search": False, "alignment": False,
        "constant_offset_correction": False, "error_based_epoch_deletion": False,
    }


def _circular_fraction_statistics(values: Sequence[float]) -> dict[str, Any]:
    array = np.asarray(values, dtype=float)
    if not array.size:
        return {"count": 0, "circular_mean_cycles": None, "circular_std_cycles": None,
                "median_absolute_cycles": None, "p90_absolute_cycles": None}
    radians = 2.0 * math.pi * array
    sine, cosine = float(np.mean(np.sin(radians))), float(np.mean(np.cos(radians)))
    resultant = min(1.0, math.hypot(sine, cosine))
    return {
        "count": int(array.size),
        "circular_mean_cycles": math.atan2(sine, cosine) / (2.0 * math.pi),
        "circular_std_cycles": math.sqrt(max(0.0, -2.0 * math.log(max(resultant, 1e-15)))) / (2.0 * math.pi),
        "median_absolute_cycles": float(np.median(np.abs(array))),
        "p90_absolute_cycles": float(np.percentile(np.abs(array), 90)),
    }


def _fractional_phase_relationship(
    preflight: PreflightResult, headings: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    validate_native_freeze(preflight.paths.native_root)
    output: list[dict[str, Any]] = []
    groups: dict[tuple[str, str, str, str, str], list[float]] = defaultdict(list)
    for row in headings:
        identities_text = row.get("active_ambiguity_identities", "")
        ambiguity_text = row.get("float_ambiguities_cycles", "")
        if not identities_text or not ambiguity_text:
            continue
        identities = json.loads(identities_text)
        ambiguities = json.loads(ambiguity_text)
        if len(identities) != len(ambiguities):
            raise Phase4RunnerError("fractional-phase ambiguity identity alignment failed")
        for identity, ambiguity in zip(identities, ambiguities):
            parts = str(identity).split(":")
            if len(parts) < 4:
                raise Phase4RunnerError("serialized ambiguity identity is invalid")
            constellation, _satellite, frequency = parts[:3]
            fractional = (float(ambiguity) + 0.5) % 1.0 - 0.5
            groups[(
                row["policy_identity"], row["system_mode"], row["solution_state"],
                constellation, frequency,
            )].append(fractional)
    output.extend({
        "method_id": METHOD_ID, "case_id": CASE_ID,
        "row_scope": "ACTIVE_EXT04_FLOAT_FRACTION_DESCRIPTION",
        "policy_identity": key[0], "system_mode": key[1],
        "solution_state": key[2], "constellation": key[3],
        "frequency": key[4], **_circular_fraction_statistics(values),
        "relationship_role": "POST_NATIVE_ACCEPTANCE_REJECTION_DESCRIPTION_ONLY",
        "phase_bias_calibration": False, "bias_subtracted": False,
        "used_to_alter_policy": False,
    } for key, values in sorted(groups.items()))

    frozen_root = (
        preflight.paths.configured_stage_root
        / "03_EXT02_CWLS/C00/POST_NATIVE_RECOVERY_PROXY_TIME_ASSOCIATION_R1"
    )
    frozen_path = frozen_root / "EXT02_C00_FRACTIONAL_DD_DIAGNOSTICS.csv"
    frozen_manifest = frozen_root / "EXT02_C00_POST_NATIVE_DIAGNOSTICS_MANIFEST.json"
    if not frozen_path.is_file() or not frozen_manifest.is_file():
        raise Phase4RunnerError("frozen fractional-DD group source is unavailable")
    frozen_rows = _read_csv(frozen_path)
    frozen_groups: dict[str, dict[str, Any]] = {}
    for row in frozen_rows:
        if not row.get("epoch_index", "").isdigit():
            continue
        index = int(row["epoch_index"])
        identity_pairs = json.loads(row.get("identity_fractional_pairs") or "[]")
        for identity_row in identity_pairs:
            fields_group = {
                name: identity_row.get(name) for name in (
                    "pivot_identity", "satellite_identity",
                    "r1_subHalfCyc", "r2_subHalfCyc",
                )
            }
            group = _canonical(fields_group)
            entry = frozen_groups.setdefault(group, {
                "group_kind": "TRACKING_IDENTITY", "group_fields": fields_group,
                "epochs": set(), "fractional": [],
            })
            entry["epochs"].add(index)
            entry["fractional"].append(
                float(identity_row["production_fractional_cycles"])
            )
        categorical = {
            name: row.get(name) for name in (
                "sub_half_cycle_combination", "lock_reset_present",
                "cycle_slip_present", "pivot_changed", "low_dd_dimension",
            )
        }
        group = _canonical(categorical)
        entry = frozen_groups.setdefault(group, {
            "group_kind": "CATEGORICAL_STRATUM", "group_fields": categorical,
            "epochs": set(), "fractional": [],
        })
        entry["epochs"].add(index)
        entry["fractional"].extend(
            float(value) for value in json.loads(row.get("fractional_dd_cycles") or "[]")
        )
    for group, entry in sorted(frozen_groups.items()):
        for policy in POLICY_ORDER:
            for mode in SYSTEM_MODES:
                selected = [
                    row for row in headings
                    if row["policy_identity"] == policy
                    and row["system_mode"] == mode
                    and int(row["epoch_index"]) in entry["epochs"]
                ]
                counts = Counter(row["solution_state"] for row in selected)
                accepted = [row for row in selected if _strict_bool(row["accepted_by_policy"])]
                output.append({
                    "method_id": METHOD_ID, "case_id": CASE_ID,
                    "row_scope": "FROZEN_FRACTIONAL_DD_GROUP_RELATIONSHIP",
                    "policy_identity": policy, "system_mode": mode,
                    "frozen_group_key": group,
                    "frozen_group_kind": entry["group_kind"],
                    "frozen_group_fields": entry["group_fields"],
                    "frozen_group_epoch_count": len(entry["epochs"]),
                    "frozen_fractional_observation_count": len(entry["fractional"]),
                    "frozen_fractional_statistics": _circular_fraction_statistics(
                        entry["fractional"]
                    ),
                    "native_rows_in_group": len(selected),
                    "FAR_ACCEPTED_count": counts["FAR_ACCEPTED"],
                    "PAR_ACCEPTED_count": counts["PAR_ACCEPTED"],
                    "FAR_REJECTED_count": counts["FAR_REJECTED"],
                    "PAR_EXHAUSTED_count": counts["PAR_EXHAUSTED"],
                    "INVALID_count": counts["INVALID"],
                    "accepted_count": len(accepted),
                    "accepted_rate": len(accepted) / len(selected) if selected else None,
                    "second_over_best": _distribution(
                        _numbers(selected, "second_over_best")
                    ),
                    "phase_bias_calibration": False, "bias_subtracted": False,
                    "previous_method_output_solver_input": False,
                    "relationship_role": "POST_NATIVE_FROZEN_GROUP_DESCRIPTION_ONLY",
                    "used_to_alter_policy": False,
                })
    return output, {
        "source_role": "FROZEN_PHASE2_RECOVERY_POST_NATIVE_RELATIONSHIP_ONLY",
        "source_relative_path": str(
            frozen_path.relative_to(preflight.paths.configured_stage_root)
        ),
        "source_sha256": _sha256(frozen_path),
        "source_post_manifest_sha256": _sha256(frozen_manifest),
        "source_opened_only_after_native_freeze": True,
        "frozen_group_count": len(frozen_groups),
        "phase_bias_calibration": False, "bias_subtracted": False,
        "previous_method_output_solver_input": False,
    }


RTKLIB_DIAGNOSTIC_CONFIG = """\
pos1-posmode       =movingbase
pos1-frequency     =l1+l2
pos1-soltype       =forward
pos1-elmask        =10
pos1-snrmask       =0
pos1-dynamics      =off
pos1-tidecorr      =off
pos1-ionoopt       =brdc
pos1-tropopt       =saas
pos1-sateph        =brdc
pos1-navsys        =33
pos2-armode        =instantaneous
pos2-gloarmode     =off
pos2-bdsarmode     =on
pos2-arthres       =3
pos2-arlockcnt     =0
pos2-arelmask      =0
pos2-aroutcnt      =5
pos2-arminfix      =1
pos2-slipthres     =0.05
pos2-maxage        =1
pos2-rejionno      =30
pos2-niter         =1
pos2-baselen       =0
pos2-basesig       =0
out-solformat      =enu
out-outhead        =on
out-outopt         =on
out-timesys        =gpst
out-timeform       =tow
out-timendec       =3
out-fieldsep       =,
out-solstatic      =all
out-outstat        =off
stats-eratio1      =100
stats-eratio2      =100
stats-errphase     =0.003
stats-errphaseel   =0.003
stats-errphasebl   =0
stats-errdoppler   =1
stats-stdbias      =30
stats-stdiono      =0.03
stats-stdtrop      =0.3
stats-prnaccelh    =0.1
stats-prnaccelv    =0.01
stats-prnbias      =0.0001
stats-prniono      =0.001
stats-prntrop      =0.0001
stats-prnpos       =0
stats-clkstab      =5e-12
ant1-postype       =single
ant1-anttype       =*
ant2-postype       =single
ant2-anttype       =*
misc-timeinterp    =on
misc-sbasatsel     =0
file-tracefile     =
"""


def _fixed_rtklib_proxy_matches(
    solution_rows: Sequence[Mapping[str, Any]],
    proxies: Mapping[int, Mapping[str, Any]],
) -> tuple[
    list[tuple[Mapping[str, Any], Mapping[str, Any]]],
    set[tuple[int, float]],
    list[tuple[int, float]],
]:
    """Join POS epochs only through the already-audited fixed +2 ms key."""

    week_ms = 604_800_000
    proxy_by_associated_key: dict[
        tuple[int, int], tuple[Mapping[str, Any], tuple[int, float]]
    ] = {}
    all_raw_keys: set[tuple[int, float]] = set()
    for proxy in proxies.values():
        if (
            int(proxy["hpposecef_offset_receiver1_ms"]) != 2
            or int(proxy["hpposecef_offset_receiver2_ms"]) != 2
        ):
            raise Phase4RunnerError("RTKLIB join requires the frozen +2 ms proxy mapping")
        raw_week = int(proxy["gps_week"])
        raw_tow = float(proxy["gps_tow_seconds"])
        raw_itow_ms = int(proxy["rawx_itow_ms"])
        associated_itow_ms = int(proxy["proxy_itow_ms"])
        if associated_itow_ms != (raw_itow_ms + 2) % week_ms:
            raise Phase4RunnerError("proxy associated iTOW is not raw iTOW +2 ms")
        carry = (raw_itow_ms + 2) // week_ms
        associated_key = (raw_week + carry, associated_itow_ms)
        raw_key = (raw_week, round(raw_tow, 3))
        if associated_key in proxy_by_associated_key or raw_key in all_raw_keys:
            raise Phase4RunnerError("duplicate fixed RTKLIB/proxy association key")
        proxy_by_associated_key[associated_key] = (proxy, raw_key)
        all_raw_keys.add(raw_key)

    matches: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
    matched_raw_keys: set[tuple[int, float]] = set()
    for solution in solution_rows:
        solution_key = (
            int(solution["gps_week"]),
            int(round(float(solution["gps_tow_seconds"]) * 1000.0)) % week_ms,
        )
        association = proxy_by_associated_key.get(solution_key)
        if association is None:
            continue
        proxy, raw_key = association
        if raw_key in matched_raw_keys:
            raise Phase4RunnerError("duplicate RTKLIB solution for one RAWX epoch")
        matched_raw_keys.add(raw_key)
        matches.append((solution, proxy))
    return matches, matched_raw_keys, sorted(all_raw_keys - matched_raw_keys)


def _run_rtklib_diagnostic(
    preflight: PreflightResult, attempt: Path,
    observation_paths: Sequence[Path], navigation_paths: Sequence[Path],
    proxies: Mapping[int, Mapping[str, Any]], headings: Sequence[Mapping[str, str]],
    *, work_root: Path | None = None,
) -> dict[str, Any]:
    validate_native_freeze(preflight.paths.native_root)
    work = Path(work_root) if work_root is not None else attempt / "POST_NATIVE_WORK"
    work.mkdir(parents=True, exist_ok=True)
    config = work / "RTKLIB_DIAGNOSTIC_GPS_BDS_DUAL.conf"
    output = work / "RTKLIB_DIAGNOSTIC_GPS_BDS_DUAL.pos"
    phase2._atomic_write_bytes(config, RTKLIB_DIAGNOSTIC_CONFIG.encode("utf-8"))
    temporary = output.with_suffix(".pos.tmp")
    if temporary.exists() or output.exists():
        raise Phase4RunnerError("RTKLIB diagnostic output collision")
    binary = preflight.paths.rtklib_root / "app/consapp/rnx2rtkp/gcc/rnx2rtkp"
    command = [
        str(binary), "-k", str(config), "-o", str(temporary),
        str(observation_paths[1]), str(observation_paths[0]),
        str(navigation_paths[0]), str(navigation_paths[1]),
    ]
    completed = subprocess.run(
        command, text=True, capture_output=True, check=False, timeout=900,
    )
    if completed.returncode != 0 or not temporary.is_file():
        return {
            "role": "UNMODIFIED_RTKLIB_RELATIVE_DIAGNOSTIC_ONLY",
            "status": "DIAGNOSTIC_FAILED", "returncode": completed.returncode,
            "stderr": completed.stderr[-4000:], "command": command,
            "used_as_solver_input": False,
        }
    phase2._atomic_install_noreplace(temporary, output, label="RTKLIB diagnostic POS")
    solution_rows: list[dict[str, Any]] = []
    for line in output.read_text(encoding="utf-8", errors="strict").splitlines():
        if not line.strip() or line.startswith("%"):
            continue
        values = [item.strip() for item in line.split(",")]
        if len(values) < 7:
            continue
        solution_rows.append({
            "gps_week": int(values[0]), "gps_tow_seconds": float(values[1]),
            "east_m": float(values[2]), "north_m": float(values[3]),
            "up_m": float(values[4]), "quality": int(values[5]),
            "satellite_count": int(values[6]),
        })
    matches, matched_raw_keys, missing_raw_keys = _fixed_rtklib_proxy_matches(
        solution_rows, proxies,
    )
    angles: list[float] = []
    ambiguity_dimension_proxy: list[int] = []
    for row, proxy in matches:
        ned = np.asarray([row["north_m"], row["east_m"], -row["up_m"]])
        angle = _vector_angle_degrees(ned, proxy["proxy_baseline_ned_m"])
        if angle is not None:
            angles.append(angle)
        ambiguity_dimension_proxy.append(max(0, 2 * (row["satellite_count"] - 1)))
    far_rows = [row for row in headings if row["policy_identity"] == FAR_POLICY_IDENTITY]
    native_dimensions = _numbers(far_rows, "full_ambiguity_count")
    return {
        "role": "UNMODIFIED_RTKLIB_RELATIVE_DIAGNOSTIC_ONLY",
        "status": "COMPLETE", "rtklib_commit": "180043ee24b6d2b168f98b64be15f69d50046b1a",
        "binary_sha256": _sha256(binary), "config_sha256": _sha256(config),
        "output_sha256": _sha256(output), "command": command,
        "output_row_count": len(solution_rows),
        "availability_of_1509": len(solution_rows) / EXPECTED_PAIR_COUNT,
        "quality_counts": dict(sorted(Counter(row["quality"] for row in solution_rows).items())),
        "matched_proxy_count": len(matched_raw_keys),
        "association_policy": "FIXED_PROXY_ITOW_PLUS_2MS_NO_TIME_SEARCH",
        "association_offset_ms": 2,
        "time_search": False,
        "baseline_direction_angle_to_proxy_deg": _distribution(angles),
        "ambiguity_dimension_diagnostic_proxy": _distribution(ambiguity_dimension_proxy),
        "ambiguity_dimension_proxy_definition": "2*(solution_satellite_count-1); standard POS lacks exact ambiguity-state count",
        "native_FAR_full_ambiguity_dimension": _distribution(native_dimensions),
        "failure_period_epoch_keys": [list(item) for item in missing_raw_keys],
        "used_as_solver_input": False, "fed_into_EXT04": False,
    }


def _post_native_diagnostics(
    preflight: PreflightResult, attempt: Path, cache_root: Path,
    observation_paths: Sequence[Path], navigation_paths: Sequence[Path],
) -> dict[str, Any]:
    freeze_before = validate_native_freeze(preflight.paths.native_root)
    hashes_before = dict(freeze_before["native_hashes"])
    headings = _read_csv(preflight.paths.native_root / NATIVE_FILE_NAMES["heading_results"])
    proxies, proxy_audit = _proxy_map(preflight, attempt, cache_root)
    proxy_rows, proxy_summary = _proxy_diagnostics(headings, proxies)
    trace_rows, trace_summary_rows, trace_audit = _trace_diagnostics(
        preflight, cache_root, headings,
    )
    fractional_rows, fractional_audit = _fractional_phase_relationship(
        preflight, headings,
    )
    rtklib = _run_rtklib_diagnostic(
        preflight, attempt, observation_paths, navigation_paths, proxies, headings,
    )
    destinations = {
        key: preflight.paths.native_root / name for key, name in POST_FILE_NAMES.items()
    }
    _write_csv(destinations["proxy_diagnostics"], proxy_rows)
    _write_csv(destinations["trace_diagnostics"], trace_rows)
    _write_csv(destinations["trace_summary"], trace_summary_rows)
    _write_csv(destinations["fractional_phase"], fractional_rows)
    phase2._atomic_write_json(destinations["rtklib_summary"], rtklib)
    freeze_after = validate_native_freeze(preflight.paths.native_root)
    if hashes_before != freeze_after["native_hashes"]:
        raise Phase4RunnerError("native files changed during post-native diagnostics")
    post_summary = {
        "schema_version": "horizontal_literature.phase4.post_native_summary.v1",
        "source_fingerprint": preflight.source_fingerprint,
        "native_hashes_before": hashes_before,
        "native_hashes_after": dict(freeze_after["native_hashes"]),
        "native_unchanged": True,
        "proxy_audit": proxy_audit, "proxy_summary": proxy_summary,
        "trace_audit": trace_audit, "trace_summary": trace_summary_rows,
        "fractional_phase_group_count": fractional_audit["frozen_group_count"],
        "fractional_phase_relationship_row_count": len(fractional_rows),
        "fractional_phase_audit": fractional_audit,
        "fractional_phase_used_for_calibration": False,
        "rtklib_diagnostic": rtklib,
        "post_native_file_hashes": {
            key: _sha256(path) for key, path in destinations.items()
            if key not in {"post_native_summary", "post_native_freeze"}
        },
    }
    phase2._atomic_write_json(destinations["post_native_summary"], post_summary)
    post_hashes = {
        key: _sha256(destinations[key]) for key in POST_FREEZE_HASH_KEYS
    }
    phase2._atomic_write_json(destinations["post_native_freeze"], {
        "schema_version": "horizontal_literature.phase4.post_native_freeze.v1",
        "source_fingerprint": preflight.source_fingerprint,
        "native_freeze_sha256": _sha256(
            preflight.paths.native_root / NATIVE_FILE_NAMES["native_freeze"]
        ),
        "post_native_hashes": post_hashes,
        "native_hashes_revalidated": True,
        "native_files_mutated": False,
        "phase_bias_calibration": False,
        "proxy_used_to_alter_policy": False,
        "trace_used_to_alter_policy": False,
        "RTKLIB_diagnostic_output_solver_input": False,
    })
    validate_post_native_freeze(preflight.paths.native_root)
    return post_summary


def validate_post_native_freeze(root: Path) -> dict[str, Any]:
    root = Path(root)
    value = json.loads(
        (root / POST_FILE_NAMES["post_native_freeze"]).read_text(encoding="utf-8")
    )
    if (
        value.get("schema_version")
        != "horizontal_literature.phase4.post_native_freeze.v1"
        or set(value.get("post_native_hashes", {})) != set(POST_FREEZE_HASH_KEYS)
        or value.get("native_files_mutated") is not False
        or value.get("phase_bias_calibration") is not False
    ):
        raise Phase4RunnerError("invalid post-native freeze boundary")
    for key, digest in value["post_native_hashes"].items():
        if _sha256(root / POST_FILE_NAMES[key]) != digest:
            raise Phase4RunnerError(f"post-native hash mismatch: {key}")
    native = validate_native_freeze(root)
    if _sha256(root / NATIVE_FILE_NAMES["native_freeze"]) != value.get(
        "native_freeze_sha256"
    ):
        raise Phase4RunnerError("post-native freeze points to another native freeze")
    if value.get("source_fingerprint") != native.get("source_fingerprint"):
        raise Phase4RunnerError("native/post-native source fingerprint mismatch")
    return value


def _post_native_r1_diagnostics(
    preflight: PreflightResult, native_attempt: Path, cache_root: Path,
    observation_paths: Sequence[Path], navigation_paths: Sequence[Path],
) -> dict[str, Any]:
    native_before = validate_native_freeze(preflight.paths.native_root)
    original_post = validate_post_native_freeze(preflight.paths.native_root)
    original_post_path = (
        preflight.paths.native_root / POST_FILE_NAMES["post_native_freeze"]
    )
    original_post_sha256 = _sha256(original_post_path)
    original_report_presence = (
        preflight.paths.final_report.is_file(), preflight.paths.final_status.is_file(),
    )
    if original_report_presence == (True, True):
        original_report_hashes: dict[str, str | None] = {
            "report": _sha256(preflight.paths.final_report),
            "status": _sha256(preflight.paths.final_status),
        }
        original_report_state = "PRESENT_AND_HASH_PINNED"
    elif original_report_presence == (False, False) and preflight.paths.artifact_root_overridden:
        original_report_hashes = {"report": None, "status": None}
        original_report_state = "ABSENT_AT_R1_FRESH_REPRODUCTION"
    else:
        raise Phase4RunnerError("partial or unexpected original pending report inventory")
    revision_root = preflight.paths.post_r1_root
    if revision_root.exists():
        raise Phase4RunnerError("post-native R1 no-replace root collision")
    revision_root.mkdir()
    work_root = revision_root / ".WORK"
    headings = _read_csv(
        preflight.paths.native_root / NATIVE_FILE_NAMES["heading_results"]
    )
    proxies, proxy_audit = _proxy_map(
        preflight, native_attempt, cache_root, work_root=work_root,
    )
    proxy_rows, proxy_summary = _proxy_diagnostics(headings, proxies)
    trace_rows, trace_summary_rows, trace_audit = _trace_diagnostics(
        preflight, cache_root, headings,
    )
    fractional_rows, fractional_audit = _fractional_phase_relationship(
        preflight, headings,
    )
    rtklib = _run_rtklib_diagnostic(
        preflight, native_attempt, observation_paths, navigation_paths,
        proxies, headings, work_root=work_root,
    )
    if (
        rtklib.get("status") != "COMPLETE"
        or int(rtklib.get("output_row_count", -1)) != 653
        or int(rtklib.get("matched_proxy_count", -1)) != 653
        or len(rtklib.get("failure_period_epoch_keys", ())) != 856
        or int(rtklib.get("baseline_direction_angle_to_proxy_deg", {}).get("count", -1))
        != 653
    ):
        raise Phase4RunnerError("corrected RTKLIB fixed-association conservation failed")
    destinations = {
        key: revision_root / name for key, name in POST_R1_FILE_NAMES.items()
    }
    _write_csv(destinations["proxy_diagnostics"], proxy_rows)
    _write_csv(destinations["trace_diagnostics"], trace_rows)
    _write_csv(destinations["trace_summary"], trace_summary_rows)
    _write_csv(destinations["fractional_phase"], fractional_rows)
    phase2._atomic_write_json(destinations["rtklib_summary"], rtklib)
    native_after = validate_native_freeze(preflight.paths.native_root)
    original_post_after = validate_post_native_freeze(preflight.paths.native_root)
    if (
        native_before["native_hashes"] != native_after["native_hashes"]
        or original_post != original_post_after
        or _sha256(original_post_path) != original_post_sha256
        or (
            original_report_state == "PRESENT_AND_HASH_PINNED"
            and (
                _sha256(preflight.paths.final_report) != original_report_hashes["report"]
                or _sha256(preflight.paths.final_status) != original_report_hashes["status"]
            )
        )
        or (
            original_report_state == "ABSENT_AT_R1_FRESH_REPRODUCTION"
            and (preflight.paths.final_report.exists() or preflight.paths.final_status.exists())
        )
    ):
        raise Phase4RunnerError("native/original post/report evidence changed during R1")
    summary = {
        "schema_version": "horizontal_literature.phase4.post_native_r1_summary.v1",
        "revision_identity": POST_NATIVE_R1_IDENTITY,
        "revision_source_fingerprint": preflight.source_fingerprint,
        "runtime_content_fingerprint": preflight.runtime_content_fingerprint,
        "task_start_head": preflight.task_start_head,
        "execution_head": preflight.execution_head,
        "provenance_mode": preflight.provenance_mode,
        "execution_lock_evidence": dict(preflight.execution_lock_evidence),
        "native_source_fingerprint": native_before["source_fingerprint"],
        "native_freeze_sha256": _sha256(
            preflight.paths.native_root / NATIVE_FILE_NAMES["native_freeze"]
        ),
        "native_hashes_before": dict(native_before["native_hashes"]),
        "native_hashes_after": dict(native_after["native_hashes"]),
        "native_unchanged": True,
        "original_post_native": {
            "freeze_path": str(original_post_path),
            "freeze_sha256": original_post_sha256,
            "preserved_byte_for_byte": True,
            "superseded_only_for": "RTKLIB_FIXED_ASSOCIATION_METRICS",
            "original_evidence_mutated": False,
        },
        "original_pending_reports": {
            "report_path": str(preflight.paths.final_report),
            "report_sha256": original_report_hashes["report"],
            "status_path": str(preflight.paths.final_status),
            "status_sha256": original_report_hashes["status"],
            "state": original_report_state,
            "preserved_byte_for_byte": (
                original_report_state == "PRESENT_AND_HASH_PINNED"
            ),
        },
        "correction": {
            "defect": "RTKLIB_POS_TOW_WAS_JOINED_TO_RAWX_TOW_WITHOUT_FROZEN_PLUS_2MS_MAPPING",
            "association": "POS_KEY_EQUALS_EXISTING_PROXY_ITOW_MS",
            "fixed_offset_ms": 2,
            "nearest_or_time_search": False,
            "raw_epoch_key_retained_for_failure_periods": True,
        },
        "proxy_audit": proxy_audit,
        "proxy_summary": proxy_summary,
        "trace_audit": trace_audit,
        "trace_summary": trace_summary_rows,
        "fractional_phase_group_count": fractional_audit["frozen_group_count"],
        "fractional_phase_relationship_row_count": len(fractional_rows),
        "fractional_phase_audit": fractional_audit,
        "fractional_phase_used_for_calibration": False,
        "rtklib_diagnostic": rtklib,
        "post_native_file_hashes": {
            key: _sha256(path) for key, path in destinations.items()
            if key not in {"post_native_summary", "post_native_freeze"}
        },
    }
    phase2._atomic_write_json(destinations["post_native_summary"], summary)
    revision_hashes = {
        key: _sha256(destinations[key]) for key in POST_R1_FREEZE_HASH_KEYS
    }
    phase2._atomic_write_json(destinations["post_native_freeze"], {
        "schema_version": "horizontal_literature.phase4.post_native_r1_freeze.v2",
        "revision_identity": POST_NATIVE_R1_IDENTITY,
        "revision_source_fingerprint": preflight.source_fingerprint,
        "runtime_content_fingerprint": preflight.runtime_content_fingerprint,
        "task_start_head": preflight.task_start_head,
        "execution_head": preflight.execution_head,
        "provenance_mode": preflight.provenance_mode,
        "execution_lock_evidence": dict(preflight.execution_lock_evidence),
        "native_source_fingerprint": native_before["source_fingerprint"],
        "native_freeze_sha256": summary["native_freeze_sha256"],
        "original_post_freeze_sha256": original_post_sha256,
        "original_pending_report_sha256": original_report_hashes["report"],
        "original_pending_status_sha256": original_report_hashes["status"],
        "original_pending_report_state": original_report_state,
        "original_post_preserved": True,
        "original_post_superseded_only_for_RTKLIB_metrics": True,
        "post_native_hashes": revision_hashes,
        "native_hashes_revalidated": True,
        "native_files_mutated": False,
        "phase_bias_calibration": False,
        "proxy_used_to_alter_policy": False,
        "trace_used_to_alter_policy": False,
        "RTKLIB_diagnostic_output_solver_input": False,
    })
    validate_post_native_r1_freeze(preflight.paths.native_root)
    return summary


def _canonical_archive_preserves_pending(
    report_root: Path, expected: Mapping[str, str],
) -> bool:
    archive = Path(report_root) / CANONICAL_ARCHIVE_NAME
    manifest_path = archive / "ARCHIVE_MANIFEST.json"
    if (
        archive.is_symlink() or not archive.is_dir()
        or manifest_path.is_symlink() or not manifest_path.is_file()
    ):
        return False
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if (
        manifest.get("schema_version") != CANONICAL_ARCHIVE_SCHEMA
        or manifest.get("archive_identity") != CANONICAL_ARCHIVE_IDENTITY
    ):
        return False
    entries = manifest.get("pending_files", {})
    approved = manifest.get("approved_payloads", {})
    if not isinstance(entries, Mapping) or not isinstance(approved, Mapping):
        return False
    if set(entries) != {
        "original_report", "original_status", "R1_report", "R1_status",
        "R2_report", "R2_status", "R3_report", "R3_status",
        "R4_report", "R4_status", "R5_report", "R5_status",
        "R6_report", "R6_status",
    } or set(approved) != {"report", "status"}:
        return False
    expected_names = {"ARCHIVE_MANIFEST.json"}
    for entry in (*entries.values(), *approved.values()):
        if not isinstance(entry, Mapping):
            return False
        archive_name = str(entry.get("archive_name", ""))
        candidate = archive / archive_name
        digest = str(entry.get("source_sha256", entry.get("sha256", "")))
        if (
            candidate.parent != archive or candidate.is_symlink()
            or not candidate.is_file() or _sha256(candidate) != digest
        ):
            return False
        expected_names.add(archive_name)
    if {entry.name for entry in archive.iterdir()} != expected_names:
        return False
    for name, digest in expected.items():
        entry = entries.get(name, {})
        if entry.get("source_sha256") != digest:
            return False
    return True


def validate_post_native_r1_freeze(root: Path) -> dict[str, Any]:
    native_root = Path(root)
    revision_root = native_root / POST_NATIVE_R1_IDENTITY
    freeze_path = revision_root / POST_R1_FILE_NAMES["post_native_freeze"]
    value = json.loads(freeze_path.read_text(encoding="utf-8"))
    if (
        value.get("schema_version") not in {
            "horizontal_literature.phase4.post_native_r1_freeze.v1",
            "horizontal_literature.phase4.post_native_r1_freeze.v2",
        }
        or value.get("revision_identity") != POST_NATIVE_R1_IDENTITY
        or set(value.get("post_native_hashes", {}))
        != set(POST_R1_FREEZE_HASH_KEYS)
        or value.get("native_files_mutated") is not False
        or value.get("original_post_preserved") is not True
        or value.get("phase_bias_calibration") is not False
    ):
        raise Phase4RunnerError("invalid post-native R1 freeze boundary")
    for key, digest in value["post_native_hashes"].items():
        if _sha256(revision_root / POST_R1_FILE_NAMES[key]) != digest:
            raise Phase4RunnerError(f"post-native R1 hash mismatch: {key}")
    native = validate_native_freeze(native_root)
    if value.get("native_source_fingerprint") != native.get("source_fingerprint"):
        raise Phase4RunnerError("post-native R1 points to another native source")
    if _sha256(native_root / NATIVE_FILE_NAMES["native_freeze"]) != value.get(
        "native_freeze_sha256"
    ):
        raise Phase4RunnerError("post-native R1 points to another native freeze")
    validate_post_native_freeze(native_root)
    if _sha256(native_root / POST_FILE_NAMES["post_native_freeze"]) != value.get(
        "original_post_freeze_sha256"
    ):
        raise Phase4RunnerError("original post-native freeze changed after R1")
    stage_root = native_root.parents[1]
    report_root = stage_root / "11_REPORT"
    report_path = report_root / "PHASE4_EXT04_C00_REPORT.md"
    status_path = report_root / "PHASE4_STATUS.json"
    report_state = value.get("original_pending_report_state")
    if value.get("schema_version") == "horizontal_literature.phase4.post_native_r1_freeze.v1":
        report_state = "PRESENT_AND_HASH_PINNED"
    if report_state == "PRESENT_AND_HASH_PINNED":
        expected_original = {
            "original_report": str(value.get("original_pending_report_sha256")),
            "original_status": str(value.get("original_pending_status_sha256")),
        }
        current_matches = (
            report_path.is_file() and status_path.is_file()
            and _sha256(report_path) == expected_original["original_report"]
            and _sha256(status_path) == expected_original["original_status"]
        )
        archived_matches = _canonical_archive_preserves_pending(
            report_root, expected_original,
        )
        if not current_matches and not archived_matches:
            raise Phase4RunnerError("original pending report/status changed after R1")
    elif report_state == "ABSENT_AT_R1_FRESH_REPRODUCTION":
        if report_path.exists() or status_path.exists():
            raise Phase4RunnerError("original pending reports appeared after fresh R1 freeze")
    else:
        raise Phase4RunnerError("post-native R1 original report state is invalid")
    return value


def _load_or_run_native_probes(
    preflight: PreflightResult, attempt: Path, cache_root: Path,
    navigation_paths: Sequence[Path], *, resume: bool,
    launch_resource_probe: Mapping[str, Any],
) -> dict[str, Any]:
    path = attempt / "RESOURCE_DETERMINISM_AND_EQUIVALENCE_PROBE.json"
    if path.exists():
        if not resume:
            raise Phase4RunnerError("native probe exists outside resume mode")
        value = json.loads(path.read_text(encoding="utf-8"))
        if (
            value.get("schema_version")
            != "horizontal_literature.phase4.native_probe.v1"
            or value.get("source_fingerprint") != preflight.source_fingerprint
            or value.get("worker_determinism", {}).get("scientific_fields_exact")
            is not True
            or not all(
                value.get("EXT01_core_equivalence", {}).get("checks", {}).values()
            )
        ):
            raise Phase4RunnerError("stored native probe evidence is invalid")
        return {**value, "launch_resource_probe": dict(launch_resource_probe)}
    value = {
        "schema_version": "horizontal_literature.phase4.native_probe.v1",
        "source_fingerprint": preflight.source_fingerprint,
        "resource_probe": dict(launch_resource_probe),
        "worker_determinism": _determinism_probe(
            cache_root, navigation_paths, preflight,
        ),
        "EXT01_core_equivalence": _ext01_core_equivalence(
            cache_root, navigation_paths, preflight,
        ),
    }
    phase2._atomic_write_json(path, value)
    return value


def _native_execution(
    preflight: PreflightResult, *, workers: int, resume: bool,
    probe_only: bool,
) -> dict[str, Any]:
    launch_resource_probe = _resource_probe(preflight.paths)
    if launch_resource_probe.get("stable_workers_16_launch_gate") is not True:
        raise Phase4RunnerError(
            "RESOURCE_PROBE_UNSTABLE_FOR_16_WORKERS: "
            f"load1={launch_resource_probe['load_average_1m']} "
            f"load5={launch_resource_probe['load_average_5m']} "
            f"available={launch_resource_probe['memory_available_bytes']}"
        )
    attempt = _open_attempt(preflight, resume=resume)
    cache_root, navigation_paths, cache_manifest, derived_hashes = _prepare_cache(
        preflight, attempt, resume=resume,
    )
    reader = phase2.CompactCacheReader(cache_root)
    if len(reader) != EXPECTED_PAIR_COUNT:
        raise Phase4RunnerError("compact cache does not conserve 1509 exact pairs")
    pairs = [reader.pair(index) for index in range(len(reader))]
    provider = RtklibBroadcastProvider(preflight.paths.rtklib_bridge, navigation_paths)
    inventory = audit_signal_availability(pairs, provider)
    supported = set(inventory.supported_modes())
    if set(SYSTEM_MODES) - supported:
        raise Phase4RunnerError(
            "UNSUPPORTED_EXT04_ON_BY2_REQUIRED_DUAL_FREQUENCY_MODE_ABSENT: "
            f"{sorted(set(SYSTEM_MODES) - supported)}"
        )
    probes = _load_or_run_native_probes(
        preflight, attempt, cache_root, navigation_paths, resume=resume,
        launch_resource_probe=launch_resource_probe,
    )
    if probe_only:
        return {
            "terminal_status": "PASS_PHASE4_EXT04_RESOURCE_DETERMINISM_PROBE_ONLY",
            "source_fingerprint": preflight.source_fingerprint,
            "attempt_root": str(attempt), "paired_epoch_count": len(reader),
            "formal_run_launched": False, "trace_open_count": 0,
            "HPPOSECEF_semantic_decode_count": 0, **probes,
        }
    started = time.perf_counter()
    epoch_payloads = _run_epoch_parts(
        preflight, attempt, cache_root, navigation_paths,
        workers=workers, resume=resume,
    )
    resource_probe = {
        **dict(launch_resource_probe),
        "initial_probe_evidence": dict(probes["resource_probe"]),
        "native_epoch_executor_wall_seconds": time.perf_counter() - started,
        "native_epoch_executor_workers": workers,
        "worker_raw_CSV_reread_count": 0,
        "compact_memory_map_shared": True,
    }
    if (attempt / "NATIVE").exists():
        if not resume:
            raise Phase4RunnerError("native attempt output exists outside resume mode")
        validate_native_freeze(attempt / "NATIVE")
    else:
        _flatten_native(
            preflight, attempt, epoch_payloads, inventory, resource_probe,
            probes["worker_determinism"], probes["EXT01_core_equivalence"],
            cache_manifest, derived_hashes,
        )
    freeze = _publish_native(preflight, attempt)
    return {
        "terminal_status": "PASS_PHASE4_EXT04_NATIVE_FROZEN_READY_FOR_POST_NATIVE",
        "source_fingerprint": preflight.source_fingerprint,
        "attempt_root": str(attempt), "paired_epoch_count": len(reader),
        "supported_modes": list(SYSTEM_MODES), "formal_run_launched": True,
        "native_freeze": freeze, "trace_open_count": 0,
        "HPPOSECEF_semantic_decode_count": 0,
    }


def _post_execution(preflight: PreflightResult) -> dict[str, Any]:
    validate_native_freeze(preflight.paths.native_root)
    attempt = _open_attempt(preflight, resume=True)
    cache_root = attempt / "COMPACT_CACHE"
    phase2.validate_compact_cache(
        cache_root, source_fingerprint=preflight.source_fingerprint,
        expected_pair_count=EXPECTED_PAIR_COUNT,
    )
    source = attempt / "SOURCE_BACKEND"
    observation_paths = (
        source / "gnss1_reconstructed.obs", source / "gnss2_reconstructed.obs",
    )
    navigation_paths = (
        source / "gnss1_reconstructed.nav", source / "gnss2_reconstructed.nav",
    )
    if any(not path.is_file() for path in (*observation_paths, *navigation_paths)):
        raise Phase4RunnerError("post-native derived OBS/NAV cache is incomplete")
    if any(
        (preflight.paths.native_root / name).exists()
        for name in POST_FILE_NAMES.values()
    ):
        raise Phase4RunnerError("post-native no-replace output collision")
    summary = _post_native_diagnostics(
        preflight, attempt, cache_root, observation_paths, navigation_paths,
    )
    freeze = validate_post_native_freeze(preflight.paths.native_root)
    return {
        "terminal_status": "PASS_PHASE4_EXT04_POST_NATIVE_READY_FOR_INDEPENDENT_REVIEW",
        "source_fingerprint": preflight.source_fingerprint,
        "post_native_summary": summary, "post_native_freeze": freeze,
        "native_unchanged": True,
    }


def _post_r1_execution(
    preflight: PreflightResult, *, resume: bool,
) -> dict[str, Any]:
    if not resume:
        raise Phase4RunnerError("post-native R1 requires --resume of frozen native evidence")
    native = validate_native_freeze(preflight.paths.native_root)
    original_post = validate_post_native_freeze(preflight.paths.native_root)
    if preflight.paths.post_r1_root.exists():
        raise Phase4RunnerError("post-native R1 no-replace output collision")
    native_fingerprint = str(native["source_fingerprint"])
    native_attempt = (
        preflight.paths.native_root
        / f".EXT04_ATTEMPT_{native_fingerprint[:20]}"
    )
    identity_path = native_attempt / "ATTEMPT_IDENTITY.json"
    if not identity_path.is_file():
        raise Phase4RunnerError("frozen native attempt identity is absent")
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    if identity.get("source_fingerprint") != native_fingerprint:
        raise Phase4RunnerError("frozen native attempt identity drift")
    cache_root = native_attempt / "COMPACT_CACHE"
    phase2.validate_compact_cache(
        cache_root, source_fingerprint=native_fingerprint,
        expected_pair_count=EXPECTED_PAIR_COUNT,
    )
    source = native_attempt / "SOURCE_BACKEND"
    observation_paths = (
        source / "gnss1_reconstructed.obs", source / "gnss2_reconstructed.obs",
    )
    navigation_paths = (
        source / "gnss1_reconstructed.nav", source / "gnss2_reconstructed.nav",
    )
    if any(not path.is_file() for path in (*observation_paths, *navigation_paths)):
        raise Phase4RunnerError("R1 derived OBS/NAV cache is incomplete")
    original_native_hashes = dict(native["native_hashes"])
    original_post_hashes = dict(original_post["post_native_hashes"])
    summary = _post_native_r1_diagnostics(
        preflight, native_attempt, cache_root, observation_paths, navigation_paths,
    )
    revision_freeze = validate_post_native_r1_freeze(preflight.paths.native_root)
    native_after = validate_native_freeze(preflight.paths.native_root)
    original_post_after = validate_post_native_freeze(preflight.paths.native_root)
    if (
        dict(native_after["native_hashes"]) != original_native_hashes
        or dict(original_post_after["post_native_hashes"]) != original_post_hashes
    ):
        raise Phase4RunnerError("R1 mutated native/original post payloads")
    return {
        "terminal_status": "PASS_PHASE4_EXT04_POST_NATIVE_R1_READY_FOR_SECOND_REVIEW",
        "revision_identity": POST_NATIVE_R1_IDENTITY,
        "revision_source_fingerprint": preflight.source_fingerprint,
        "runtime_content_fingerprint": preflight.runtime_content_fingerprint,
        "task_start_head": preflight.task_start_head,
        "execution_head": preflight.execution_head,
        "provenance_mode": preflight.provenance_mode,
        "post_native_summary": summary,
        "post_native_freeze": revision_freeze,
        "native_unchanged": True,
        "original_post_unchanged": True,
    }


def _method_preservation_proof(preflight: PreflightResult) -> dict[str, Any]:
    frozen_sources = (
        "src/legsa_gins/paper_rebuild/horizontal_literature/ext01_clambda.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/phase1r_runner.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/ext02_cwls.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/phase2_runner.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/ext03_yang2024.py",
        "src/legsa_gins/paper_rebuild/horizontal_literature/phase3_runner.py",
    )
    changed = subprocess.run(
        ["git", "diff", "--name-only", preflight.code_commit, "--", *frozen_sources],
        cwd=preflight.paths.code_root, text=True, capture_output=True, check=True,
    ).stdout.splitlines()
    return {
        "frozen_method_source_paths": list(frozen_sources),
        "changed_paths": changed, "unchanged": not changed,
        "EXT01_runner_invocation_count": 0,
        "EXT02_runner_invocation_count": 0,
        "EXT03_runner_invocation_count": 0,
        "EXT01_output_solver_input": False,
        "EXT02_output_solver_input": False,
        "EXT03_output_solver_input": False,
        "Classic_18_invocation_count": 0,
        "common_backbone_navigation_invocation_count": 0,
        "Canonical_541_invocation_count": 0,
    }


def _terminal_scientific_status(
    native_summary: Mapping[str, Any], post_summary: Mapping[str, Any],
) -> tuple[str, dict[str, Any]]:
    primary = [
        row for row in native_summary["policy_summary"]
        if row["policy_identity"] in {FAR_POLICY_IDENTITY, POLICY_IDENTITY}
    ]
    accepted = sum(int(row["accepted_count"]) for row in primary)
    inconsistent = int(
        post_summary["proxy_summary"]["proxy_inconsistent_above_30_deg_count"]
    )
    # Proxy summary includes sensitivities too, so derive the FAR/primary exact
    # count from its group records instead of comparing the aggregate directly.
    primary_proxy_groups = [
        row for row in post_summary["proxy_summary"]["groups"]
        if row["policy_identity"] in {FAR_POLICY_IDENTITY, POLICY_IDENTITY}
    ]
    primary_inconsistent = sum(
        int(row["count"]) for row in primary_proxy_groups
        if row["consistency_class"] == "INCONSISTENT_GT30"
    )
    poor = accepted == 0 or (accepted > 0 and primary_inconsistent == accepted)
    return (PASS_POOR if poor else PASS_DECLARED), {
        "FAR_and_primary_PAR_accepted_count": accepted,
        "FAR_and_primary_PAR_proxy_inconsistent_gt30_count": primary_inconsistent,
        "all_FAR_and_primary_PAR_accepted_rows_proxy_inconsistent": bool(
            accepted > 0 and primary_inconsistent == accepted
        ),
        "all_policy_proxy_inconsistent_gt30_count": inconsistent,
        "poor_applicability_rule": (
            "NO_FAR_OR_PRIMARY_PAR_ACCEPTANCE_OR_EVERY_SUCH_ACCEPTED_ROW_"
            "EXCEEDS_FIXED_30_DEG_PROXY_VECTOR_ANGLE"
        ),
    }


def _load_r1_post_summary(native_root: Path) -> dict[str, Any]:
    path = (
        Path(native_root) / POST_NATIVE_R1_IDENTITY
        / POST_R1_FILE_NAMES["post_native_summary"]
    )
    value = json.loads(path.read_text(encoding="utf-8"))
    if (
        value.get("schema_version")
        != "horizontal_literature.phase4.post_native_r1_summary.v1"
        or value.get("revision_identity") != POST_NATIVE_R1_IDENTITY
    ):
        raise Phase4RunnerError("R1 post-native summary identity drift")
    return value


def _pending_report_inventory(preflight: PreflightResult) -> dict[str, Any]:
    expected = {
        "original_report": (preflight.paths.final_report, ORIGINAL_PENDING_REPORT_SHA256),
        "original_status": (preflight.paths.final_status, ORIGINAL_PENDING_STATUS_SHA256),
        "R1_report": (preflight.paths.r1_report, R1_PENDING_REPORT_SHA256),
        "R1_status": (preflight.paths.r1_status, R1_PENDING_STATUS_SHA256),
        "R2_report": (preflight.paths.r2_report, R2_PENDING_REPORT_SHA256),
        "R2_status": (preflight.paths.r2_status, R2_PENDING_STATUS_SHA256),
        "R3_report": (preflight.paths.r3_report, R3_PENDING_REPORT_SHA256),
        "R3_status": (preflight.paths.r3_status, R3_PENDING_STATUS_SHA256),
        "R4_report": (preflight.paths.r4_report, R4_PENDING_REPORT_SHA256),
        "R4_status": (preflight.paths.r4_status, R4_PENDING_STATUS_SHA256),
        "R5_report": (preflight.paths.r5_report, R5_PENDING_REPORT_SHA256),
        "R5_status": (preflight.paths.r5_status, R5_PENDING_STATUS_SHA256),
    }
    present = {name: path.is_file() for name, (path, _digest) in expected.items()}
    if preflight.paths.artifact_root_overridden and not any(present.values()):
        return {
            "state": "ABSENT_IN_FRESH_REPRODUCTION",
            "preserved_byte_for_byte": True,
            "files": {},
        }
    if not all(present.values()):
        raise Phase4RunnerError("partial pending report inventory before R6")
    observed: dict[str, Any] = {}
    archived_original = _canonical_archive_preserves_pending(
        preflight.paths.report_root, {
            "original_report": ORIGINAL_PENDING_REPORT_SHA256,
            "original_status": ORIGINAL_PENDING_STATUS_SHA256,
        },
    )
    for name, (path, digest) in expected.items():
        if _sha256(path) == digest:
            observed[name] = {
                "path": str(path), "sha256": digest, "source": "DIRECT_PENDING_PATH",
            }
        elif name in {"original_report", "original_status"} and archived_original:
            observed[name] = {
                "path": str(preflight.paths.canonical_archive_root),
                "sha256": digest, "source": "IMMUTABLE_CANONICAL_ARCHIVE",
            }
        else:
            raise Phase4RunnerError(f"pending report hash drift: {name}")
    return {
        "state": "PRESENT_AND_HASH_PINNED",
        "preserved_byte_for_byte": True,
        "files": observed,
    }


def _fresh_reproduction_commands(preflight: PreflightResult) -> dict[str, Any]:
    lock_path = preflight.execution_lock_evidence.get("path")
    lock_sha = preflight.execution_lock_evidence.get("sha256")
    if not lock_path or not lock_sha:
        raise Phase4RunnerError("R6 report requires an exact execution lock")
    fresh_root = (
        preflight.paths.clean_root / "stages"
        / (
            "REPRO_PHASE4_EXT04_WU2025_C00_"
            + preflight.runtime_content_fingerprint[:16]
        )
    )
    common = (
        "python3 scripts/paper_rebuild/run_horizontal_literature_phase4.py "
        "--paths-config configs/paper_rebuild/DATA_PATHS.CLEAN3R4.local.yaml "
        f"--artifact-root {shlex.quote(str(fresh_root))} "
        f"--execution-lock {shlex.quote(str(lock_path))} "
        f"--execution-lock-sha256 {lock_sha} "
        f"--preexisting-manifest {shlex.quote(str(preflight.preexisting_manifest_path))} "
        f"--preexisting-manifest-sha256 {preflight.preexisting_manifest_sha256} "
        "--method-id EXT04_WU2025 --case-id C00 --trace-mode disabled --workers 16"
    )
    return {
        "artifact_root": str(fresh_root),
        "command_rendering_is_pure": True,
        "artifact_root_filesystem_probed_during_rendering": False,
        "initial_root_requirement": "ABSENT_OR_EMPTY",
        "initial_root_requirement_enforced_by": (
            "INITIAL_PREFLIGHT_AND_RESOURCE_PROBE_INITIALIZATION"
        ),
        "resume_root_requirement": (
            "EXACT_IDENTITY_LOCK_MANIFEST_SOURCE_RUNTIME_AND_LIFECYCLE_STATE"
        ),
        "finalizer_recreates_artifact_root": False,
        "preflight": f"{common} --mode preflight",
        "resource_determinism_probe": f"{common} --mode resource-determinism-probe",
        "native_only_resume": f"{common} --mode native-only --resume",
        "post_native_resume": f"{common} --mode post-native-diagnostics --resume",
        "post_native_R1_resume": f"{common} --mode post-native-r1-diagnostics --resume",
        "finalize_R6_pending": (
            f"{common} --mode finalize-r1-pending --resume "
            "--focused-tests PASS --full-tests PASS "
            "--focused-test-summary '<literal focused summary>' "
            "--full-test-summary '<literal full summary>'"
        ),
        "thread_environment": (
            "OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 "
            "NUMEXPR_NUM_THREADS=1"
        ),
        "resource_guard_required_before_probe_and_native": True,
    }


def finalize_r1_pending_reports(
    preflight: PreflightResult, *, focused_tests: str, full_tests: str,
    focused_test_summary: str, full_test_summary: str,
) -> dict[str, Any]:
    if focused_tests != "PASS" or full_tests != "PASS":
        raise Phase4RunnerError("R6 pending reports require passing focused and full tests")
    if not focused_test_summary.strip() or not full_test_summary.strip():
        raise Phase4RunnerError("R6 pending reports require literal test-result summaries")
    failed_r5_before = _failed_r5_canonical_attempt_evidence(
        preflight.paths.configured_stage_root / "11_REPORT"
    )
    native_freeze = validate_native_freeze(preflight.paths.native_root)
    original_post_freeze = validate_post_native_freeze(preflight.paths.native_root)
    r1_freeze = validate_post_native_r1_freeze(preflight.paths.native_root)
    native_summary = json.loads(
        (preflight.paths.native_root / NATIVE_FILE_NAMES["native_summary"])
        .read_text(encoding="utf-8")
    )
    post_summary = _load_r1_post_summary(preflight.paths.native_root)
    terminal_status, applicability = _terminal_scientific_status(
        native_summary, post_summary,
    )
    preservation = _method_preservation_proof(preflight)
    if not preservation["unchanged"]:
        raise Phase4RunnerError("frozen EXT01/EXT02/EXT03 source changed")
    if (
        _sha256(preflight.preexisting_manifest_path)
        != preflight.preexisting_manifest_sha256
    ):
        raise Phase4RunnerError("pre-existing stage manifest changed before report")
    pending_inventory = _pending_report_inventory(preflight)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=preflight.paths.code_root,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    branch = subprocess.run(
        ["git", "branch", "--show-current"], cwd=preflight.paths.code_root,
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    start_log = subprocess.run(
        ["git", "log", "-1", "--oneline", preflight.code_commit],
        cwd=preflight.paths.code_root, text=True, capture_output=True, check=True,
    ).stdout.strip()
    output_paths = {
        **{key: str(preflight.paths.native_root / name) for key, name in NATIVE_FILE_NAMES.items()},
        **{
            f"original_post_{key}": str(preflight.paths.native_root / name)
            for key, name in POST_FILE_NAMES.items()
        },
        **{
            f"R1_post_{key}": str(preflight.paths.post_r1_root / name)
            for key, name in POST_R1_FILE_NAMES.items()
        },
    }
    reproduction = _fresh_reproduction_commands(preflight)
    report_payload = {
        "terminal_status": terminal_status,
        "implementation_milestone": PASS_DECLARED,
        "review_gate": "PENDING_SEVENTH_INDEPENDENT_REVIEW",
        "post_native_revision_selected": POST_NATIVE_R1_IDENTITY,
        "defective_original_post_summary_used_for_metrics": False,
        "worktree": str(preflight.paths.code_root), "branch": branch,
        "task_start_HEAD": preflight.task_start_head,
        "execution_HEAD": preflight.execution_head,
        "new_HEAD": head,
        "provenance_mode": preflight.provenance_mode,
        "formal_source_fingerprint": preflight.source_fingerprint,
        "runtime_content_fingerprint": preflight.runtime_content_fingerprint,
        "execution_lock_evidence": dict(preflight.execution_lock_evidence),
        "task_start_git_log_oneline": start_log,
        "commit_created": False,
        "first_independent_review": "FAIL_REQUIRED_RTKLIB_AND_PROVENANCE_CORRECTIONS",
        "second_independent_review": "FAIL_REQUIRED_FRESH_ROOT_AND_R1_FINALIZER_CORRECTIONS",
        "third_independent_review": (
            "FAIL_REQUIRED_PURE_FRESH_COMMAND_RENDERING_AND_LIFECYCLE_TEST"
        ),
        "fourth_independent_review": (
            "FAIL_REQUIRED_EXACT_CANONICAL_PATH_CAS_ARCHIVE_TRANSACTION"
        ),
        "fifth_independent_review": (
            "FAIL_REQUIRED_UNCONDITIONAL_RETRY_FREEZE_AND_TEMP_VALIDATION"
        ),
        "sixth_independent_review": (
            "PASS_R5_R2E_UNCONDITIONAL_FREEZE_AND_TEMP_GUARDS"
        ),
        "failed_R5_canonical_attempt": failed_r5_before,
        "R5_canonical_attempt_terminal": "FAILED_CLOSED_BEFORE_CANONICAL_CAS",
        "R6_archive_repair_boundary": (
            "FINAL_DIRECTORY_EXCLUSIVE_MKDIR_DIRECT_XB_FSYNC_MANIFEST_LAST"
        ),
        "paper": preflight.contract["paper_source"],
        "paper_resolved_external_paths": {
            "PDF": str(preflight.paths.paper_pdf),
            "render_root": str(preflight.paths.paper_render_root),
            "text": str(preflight.paths.paper_text),
            "equation_policy_registry": str(preflight.paths.paper_registry),
        },
        "official_code_search_result": "NO_ATTRIBUTABLE_OFFICIAL_IMPLEMENTATION_FOUND",
        "module_boundary": preflight.contract["module_boundary"],
        "equation_to_code_map": preflight.contract["equation_code_map"],
        "declared_PAR_policy": preflight.contract["declared_par_policy"],
        "policy_reproduction_levels": {
            FAR_POLICY_IDENTITY: "FAITHFUL_MODULE_MATHEMATICAL_CORE_WITH_DECLARED_QC_GATES",
            POLICY_IDENTITY: REPRODUCTION_LEVEL,
            **{
                policy.policy_identity: REPRODUCTION_LEVEL
                for policy in SENSITIVITY_POLICIES
            },
            "EXT04_PAR_PAPER_EXACT": "NOT_IMPLEMENTED_UNDER_SPECIFIED",
        },
        "supported_modes": list(SYSTEM_MODES),
        "unsupported_modes": native_summary["unsupported_submodes"],
        "FAR_PAR_counts_and_quality": native_summary["policy_summary"],
        "sensitivity_no_selection": [
            row for row in native_summary["policy_summary"]
            if row["policy_identity"]
            in {policy.policy_identity for policy in SENSITIVITY_POLICIES}
        ],
        "native_row_counts": native_summary["row_counts"],
        "applicability": applicability,
        "proxy_descriptive": post_summary["proxy_summary"],
        "trace_descriptive": post_summary["trace_summary"],
        "fractional_phase_group_count": post_summary["fractional_phase_group_count"],
        "RTKLIB_diagnostic": post_summary["rtklib_diagnostic"],
        "runtime_16_workers": native_summary["resource_probe"],
        "workers_1_vs_16_determinism": native_summary["worker_determinism"],
        "EXT01_core_equivalence": native_summary["EXT01_core_equivalence"],
        "tests": {
            "focused": focused_tests,
            "focused_literal_summary": focused_test_summary,
            "all_tests_paper_rebuild": full_tests,
            "all_tests_literal_summary": full_test_summary,
        },
        "reviewer": {
            "verdict": "PENDING_SEVENTH_INDEPENDENT_REVIEW",
            "summary": "R6 direct-archive repair awaits seventh read-only review",
        },
        "native_freeze_sha256": _sha256(
            preflight.paths.native_root / NATIVE_FILE_NAMES["native_freeze"]
        ),
        "original_post_native_freeze_sha256": _sha256(
            preflight.paths.native_root / POST_FILE_NAMES["post_native_freeze"]
        ),
        "R1_post_native_freeze_sha256": _sha256(
            preflight.paths.post_r1_root / POST_R1_FILE_NAMES["post_native_freeze"]
        ),
        "original_post_native_superseded_only_for": "RTKLIB_FIXED_ASSOCIATION_METRICS",
        "preexisting_manifest_path": str(preflight.preexisting_manifest_path),
        "preexisting_manifest_sha256": preflight.preexisting_manifest_sha256,
        "preexisting_manifest_content_read": False,
        "pending_report_inventory": pending_inventory,
        "preservation_and_nonexecution_proof": preservation,
        "output_paths": output_paths,
        "artifact_root_evidence": dict(preflight.artifact_root_evidence),
        "exact_reproduction_commands": {
            **reproduction,
            "focused_tests": (
                "PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "
                "python3 -m pytest -q "
                "tests/paper_rebuild/test_horizontal_ext04_wu2025.py "
                "tests/paper_rebuild/test_horizontal_phase4_c00.py"
            ),
            "all_active_tests": (
                "PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 "
                "python3 -m pytest -q "
                "tests/paper_rebuild"
            ),
        },
    }
    report_text = (
        "# Phase 4 EXT04 Wu 2025 C00 R6 pending report\n\n"
        f"Terminal status: `{terminal_status}`\n\n"
        "Review gate: `PENDING_SEVENTH_INDEPENDENT_REVIEW`.\n\n"
        "This closes only Wu et al. Section II-A, Eqs. (1)-(4). The exact "
        "constrained C-LAMBDA mathematics is retained; the under-specified "
        "PAR/QC ordering and thresholds are transparently the declared "
        "`PAPER_DERIVED_POLICY_BASELINE`. Policy acceptance is not called a "
        "correct ambiguity fix.\n\n"
        "This finalizer validates native, superseded original-post, and corrected "
        "R1 freezes, and selects only `POST_NATIVE_R1_RTKLIB_FIXED_ASSOCIATION` "
        "for post-native metrics. The defective original post summary is never "
        "used for R6 metrics. The failed R5 canonical archive attempt is "
        "registered and preserved byte-for-byte; R6 uses direct exclusive "
        "archive writes with the manifest written last. Fresh-root command "
        "rendering is pure; initial "
        "absence/collision validation remains confined to initial preflight and "
        "initialization, while resume/finalization validates the sealed root "
        "identity and lifecycle evidence.\n\n"
        "## Complete evidence registry\n\n```json\n"
        + json.dumps(
            _jsonable(report_payload), indent=2, sort_keys=True,
            ensure_ascii=False,
        )
        + "\n```\n"
    )
    status_payload = _jsonable({
        "schema_version": "horizontal_literature.phase4.status_r6.v1",
        **report_payload,
        "report_path": str(preflight.paths.r6_report),
        "status_path": str(preflight.paths.r6_status),
        "native_freeze": native_freeze,
        "original_post_native_freeze": original_post_freeze,
        "R1_post_native_freeze": r1_freeze,
        "git_commit_created": False, "git_push_performed": False,
        "git_merge_performed": False, "git_tag_created": False,
    })
    preflight.paths.report_root.mkdir(parents=True, exist_ok=True)
    phase2._atomic_write_bytes(preflight.paths.r6_report, report_text.encode("utf-8"))
    status_payload["report_sha256"] = _sha256(preflight.paths.r6_report)
    phase2._atomic_write_json(preflight.paths.r6_status, status_payload)
    if (
        _sha256(preflight.preexisting_manifest_path)
        != preflight.preexisting_manifest_sha256
    ):
        raise Phase4RunnerError("pre-existing stage manifest changed during report finalization")
    validate_native_freeze(preflight.paths.native_root)
    validate_post_native_freeze(preflight.paths.native_root)
    validate_post_native_r1_freeze(preflight.paths.native_root)
    failed_r5_after = _failed_r5_canonical_attempt_evidence(
        preflight.paths.configured_stage_root / "11_REPORT"
    )
    if failed_r5_after != failed_r5_before:
        raise Phase4RunnerError("failed R5 canonical attempt changed during R6 report")
    return {
        "terminal_status": terminal_status,
        "review_gate": "PENDING_SEVENTH_INDEPENDENT_REVIEW",
        "post_native_revision_selected": POST_NATIVE_R1_IDENTITY,
        "report": str(preflight.paths.r6_report),
        "report_sha256": _sha256(preflight.paths.r6_report),
        "status": str(preflight.paths.r6_status),
        "status_sha256": _sha256(preflight.paths.r6_status),
    }


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _failed_r5_canonical_attempt_evidence(report_root: Path) -> dict[str, Any]:
    path = Path(report_root) / FAILED_R5_CANONICAL_ATTEMPT_NAME
    _reject_symlink_components(path)
    if path.is_symlink() or not path.is_dir():
        raise Phase4RunnerError("immutable failed R5 canonical attempt is absent or unsafe")
    files = sorted(path.iterdir(), key=lambda item: item.name)
    if any(item.is_symlink() or not item.is_file() for item in files):
        raise Phase4RunnerError("immutable failed R5 attempt inventory is unsafe")
    byte_count = sum(item.stat().st_size for item in files)
    digest = hashlib.sha256()
    file_hashes: dict[str, str] = {}
    for item in files:
        item_hash = _sha256(item)
        file_hashes[item.name] = item_hash
        digest.update(item.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(item_hash.encode("ascii"))
        digest.update(b"\0")
    aggregate = digest.hexdigest()
    if (
        len(files) != FAILED_R5_CANONICAL_ATTEMPT_FILE_COUNT
        or byte_count != FAILED_R5_CANONICAL_ATTEMPT_BYTES
        or aggregate != FAILED_R5_CANONICAL_ATTEMPT_AGGREGATE_SHA256
    ):
        raise Phase4RunnerError("immutable failed R5 canonical attempt drift")
    return {
        "identity": "FAILED_R5_CANONICAL_ARCHIVE_PUBLICATION_ATTEMPT",
        "path": str(path),
        "file_count": len(files),
        "byte_count": byte_count,
        "filename_hash_aggregate_sha256": aggregate,
        "files": file_hashes,
        "preserved_byte_for_byte": True,
        "retry_or_completion_permitted": False,
        "failure_class": "DRVFS_NESTED_ATOMIC_WINDOWS_MOVE_FILENOTFOUND",
    }


def _canonical_expected_sources(
    preflight: PreflightResult,
    expected_pending_sha256: Mapping[str, str | None],
) -> dict[str, tuple[Path, str]]:
    paths = {
        "original_report": preflight.paths.final_report,
        "original_status": preflight.paths.final_status,
        "R1_report": preflight.paths.r1_report,
        "R1_status": preflight.paths.r1_status,
        "R2_report": preflight.paths.r2_report,
        "R2_status": preflight.paths.r2_status,
        "R3_report": preflight.paths.r3_report,
        "R3_status": preflight.paths.r3_status,
        "R4_report": preflight.paths.r4_report,
        "R4_status": preflight.paths.r4_status,
        "R5_report": preflight.paths.r5_report,
        "R5_status": preflight.paths.r5_status,
        "R6_report": preflight.paths.r6_report,
        "R6_status": preflight.paths.r6_status,
    }
    if set(expected_pending_sha256) != set(paths):
        raise Phase4RunnerError("canonical expected pending-input inventory drift")
    expected = {
        name: _required_sha256(expected_pending_sha256[name], f"expected {name}")
        for name in paths
    }
    pinned = {
        "original_report": ORIGINAL_PENDING_REPORT_SHA256,
        "original_status": ORIGINAL_PENDING_STATUS_SHA256,
        "R1_report": R1_PENDING_REPORT_SHA256,
        "R1_status": R1_PENDING_STATUS_SHA256,
        "R2_report": R2_PENDING_REPORT_SHA256,
        "R2_status": R2_PENDING_STATUS_SHA256,
        "R3_report": R3_PENDING_REPORT_SHA256,
        "R3_status": R3_PENDING_STATUS_SHA256,
        "R4_report": R4_PENDING_REPORT_SHA256,
        "R4_status": R4_PENDING_STATUS_SHA256,
        "R5_report": R5_PENDING_REPORT_SHA256,
        "R5_status": R5_PENDING_STATUS_SHA256,
    }
    drift = {
        name: {"required": digest, "provided": expected[name]}
        for name, digest in pinned.items() if expected[name] != digest
    }
    if drift:
        raise Phase4RunnerError(f"canonical pinned pending-input hash drift: {drift}")
    return {name: (path, expected[name]) for name, path in paths.items()}


def _canonical_lock_evidence(preflight: PreflightResult) -> dict[str, Any]:
    evidence = dict(preflight.execution_lock_evidence)
    path_text = evidence.get("path")
    digest = evidence.get("sha256")
    if (
        evidence.get("validated") is not True or not path_text or not digest
        or Path(str(path_text)).absolute() != preflight.paths.execution_lock.absolute()
        or not preflight.paths.execution_lock.is_file()
        or _sha256(preflight.paths.execution_lock) != digest
    ):
        raise Phase4RunnerError("canonical finalizer requires the exact final execution lock")
    return {"path": str(preflight.paths.execution_lock), "sha256": str(digest)}


def _canonical_approved_payloads(
    preflight: PreflightResult, *, r6_report_bytes: bytes,
    r6_status_bytes: bytes, reviewer_summary: str,
    reviewer_summary_sha256: str, lock: Mapping[str, Any],
) -> tuple[bytes, bytes]:
    try:
        r6_status = json.loads(r6_status_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Phase4RunnerError(f"R6 status is unreadable: {exc}") from exc
    if (
        r6_status.get("schema_version")
        != "horizontal_literature.phase4.status_r6.v1"
        or r6_status.get("review_gate") != "PENDING_SEVENTH_INDEPENDENT_REVIEW"
    ):
        raise Phase4RunnerError("R6 pending status identity drift")
    approved_report = (
        r6_report_bytes.rstrip(b"\n")
        + b"\n\n## Independent reviewer approval\n\n"
        + reviewer_summary.encode("utf-8")
        + b"\n"
    )
    approved_report_sha256 = _sha256_bytes(approved_report)
    approved_status = _jsonable({
        **r6_status,
        "schema_version": "horizontal_literature.phase4.canonical_final.v2",
        "review_gate": "APPROVED",
        "reviewer": {
            "verdict": "APPROVED", "summary": reviewer_summary,
            "summary_sha256": reviewer_summary_sha256,
        },
        "execution_lock_evidence": dict(lock),
        "pending_archive": str(preflight.paths.canonical_archive_root),
        "canonical_required_report_path": str(preflight.paths.final_report),
        "canonical_required_status_path": str(preflight.paths.final_status),
        "canonical_final_report_sha256": approved_report_sha256,
        "report_path": str(preflight.paths.final_report),
        "status_path": str(preflight.paths.final_status),
        "report_sha256": approved_report_sha256,
        "canonical_pending_paths_replaced": True,
        "canonical_transaction_recovery": "ARCHIVE_BACKED_IDEMPOTENT_CAS",
        "git_commit_created": False, "git_push_performed": False,
        "git_merge_performed": False, "git_tag_created": False,
    })
    approved_status_bytes = (
        json.dumps(approved_status, indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    return approved_report, approved_status_bytes


def _canonical_archive_manifest(
    preflight: PreflightResult, *, sources: Mapping[str, tuple[Path, str]],
    reviewer_summary: str, reviewer_summary_sha256: str,
    lock: Mapping[str, Any], approved_report: bytes, approved_status: bytes,
) -> dict[str, Any]:
    files: dict[str, Any] = {}
    for name, (path, digest) in sources.items():
        files[name] = {
            "source_path": str(path), "source_sha256": digest,
            "archive_name": f"{name}_{digest}{path.suffix}",
        }
    report_sha = _sha256_bytes(approved_report)
    status_sha = _sha256_bytes(approved_status)
    return {
        "schema_version": CANONICAL_ARCHIVE_SCHEMA,
        "archive_identity": CANONICAL_ARCHIVE_IDENTITY,
        "reviewer_verdict": "APPROVED",
        "reviewer_summary": reviewer_summary,
        "reviewer_summary_sha256": reviewer_summary_sha256,
        "execution_lock": dict(lock),
        "pending_files": files,
        "approved_payloads": {
            "report": {
                "archive_name": f"APPROVED_CANONICAL_REPORT_{report_sha}.md",
                "sha256": report_sha,
            },
            "status": {
                "archive_name": f"APPROVED_CANONICAL_STATUS_{status_sha}.json",
                "sha256": status_sha,
            },
        },
        "transaction": {
            "archive_writer": (
                "FINAL_DIRECTORY_EXCLUSIVE_MKDIR_DIRECT_XB_FSYNC_MANIFEST_LAST"
            ),
            "archive_nested_atomic_helper_used": False,
            "archive_windows_dotnet_move_used": False,
            "archive_manifest_written_last": True,
            "incomplete_archive_retry": "NEW_IDENTITY_REQUIRED",
            "install_order": ["report", "status"],
            "report_target": str(preflight.paths.final_report),
            "status_target": str(preflight.paths.final_status),
            "report_expected_before_sha256": sources["original_report"][1],
            "status_expected_before_sha256": sources["original_status"][1],
            "report_approved_sha256": report_sha,
            "status_approved_sha256": status_sha,
            "install_primitive": "CAS_TEMP_FSYNC_SAME_DIRECTORY_REPLACE",
            "partial_recovery": "IDEMPOTENT_FROM_THIS_ARCHIVE",
        },
    }


def _validate_canonical_archive(
    archive: Path, expected_manifest: Mapping[str, Any],
) -> tuple[bytes, bytes]:
    archive = Path(archive)
    _reject_symlink_components(archive)
    manifest_path = archive / "ARCHIVE_MANIFEST.json"
    if not archive.is_dir() or manifest_path.is_symlink() or not manifest_path.is_file():
        raise Phase4RunnerError("canonical archive is absent or unsafe")
    try:
        observed = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise Phase4RunnerError(f"canonical archive manifest is unreadable: {exc}") from exc
    if observed != dict(expected_manifest):
        raise Phase4RunnerError("canonical archive manifest identity mismatch")
    expected_names = {"ARCHIVE_MANIFEST.json"}
    expected_names.update(
        str(entry["archive_name"])
        for entry in observed["pending_files"].values()
    )
    expected_names.update(
        str(entry["archive_name"])
        for entry in observed["approved_payloads"].values()
    )
    if {entry.name for entry in archive.iterdir()} != expected_names:
        raise Phase4RunnerError("canonical archive file inventory mismatch")
    for entry in observed["pending_files"].values():
        candidate = archive / entry["archive_name"]
        if candidate.parent != archive or candidate.is_symlink() or not candidate.is_file():
            raise Phase4RunnerError("canonical archived pending file is unsafe")
        if _sha256(candidate) != entry["source_sha256"]:
            raise Phase4RunnerError("canonical archived pending file hash mismatch")
    payloads: dict[str, bytes] = {}
    for name, entry in observed["approved_payloads"].items():
        candidate = archive / entry["archive_name"]
        if candidate.parent != archive or candidate.is_symlink() or not candidate.is_file():
            raise Phase4RunnerError("canonical approved archive payload is unsafe")
        payload = candidate.read_bytes()
        if _sha256_bytes(payload) != entry["sha256"]:
            raise Phase4RunnerError("canonical approved archive payload hash mismatch")
        payloads[name] = payload
    return payloads["report"], payloads["status"]


def _canonical_cas_temporary(target: Path, approved_payload: bytes) -> Path:
    approved_sha = _sha256_bytes(approved_payload)
    return Path(target).with_name(
        f".{Path(target).name}.canonical.{approved_sha[:20]}.tmp"
    )


def _inspect_canonical_transaction_temps(
    archive: Path, *, report_target: Path, report_expected_before_sha256: str,
    approved_report: bytes, status_target: Path,
    status_expected_before_sha256: str, approved_status: bytes,
) -> None:
    """Fail closed on every deterministic transaction path before mutation."""
    archive = Path(archive)
    _reject_symlink_components(archive)
    if os.path.lexists(archive) and not archive.is_dir():
        raise Phase4RunnerError("canonical archive path is unsafe")

    for target, expected_before, approved, label in (
        (
            Path(report_target), report_expected_before_sha256,
            approved_report, "canonical report",
        ),
        (
            Path(status_target), status_expected_before_sha256,
            approved_status, "canonical status",
        ),
    ):
        _reject_symlink_components(target)
        if target.is_symlink() or not target.is_file():
            raise Phase4RunnerError(f"{label} target is absent or unsafe")
        observed = _sha256(target)
        approved_sha = _sha256_bytes(approved)
        if observed not in {expected_before, approved_sha}:
            raise Phase4RunnerError(f"{label} CAS source hash mismatch")
        temporary = _canonical_cas_temporary(target, approved)
        if os.path.lexists(temporary):
            if temporary.is_symlink() or not temporary.is_file():
                raise Phase4RunnerError(f"{label} CAS temporary is unsafe")
            if _sha256(temporary) != approved_sha:
                raise Phase4RunnerError(f"{label} CAS temporary hash mismatch")
            if observed == approved_sha:
                raise Phase4RunnerError(
                    f"{label} CAS temporary is unexpected after approval"
                )


def _direct_exclusive_archive_write(
    path: Path, payload: bytes, *, expected_sha256: str, label: str,
) -> None:
    """Write one R6 archive payload without any rename or Windows fallback."""
    path = Path(path)
    if os.path.lexists(path):
        raise Phase4RunnerError(f"{label} direct archive target collision")
    with path.open("xb") as stream:
        view = memoryview(payload)
        offset = 0
        while offset < len(view):
            written = stream.write(view[offset:])
            if written is None or written <= 0:
                raise Phase4RunnerError(f"{label} direct archive short write")
            offset += written
        stream.flush()
        os.fsync(stream.fileno())
    if _sha256(path) != expected_sha256:
        raise Phase4RunnerError(f"{label} direct archive hash mismatch")


def _fsync_archive_directory(path: Path) -> None:
    directory_fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


def _install_canonical_archive(
    archive: Path, *, sources: Mapping[str, tuple[Path, str]],
    manifest: Mapping[str, Any], approved_report: bytes,
    approved_status: bytes,
) -> tuple[bytes, bytes]:
    archive = Path(archive)
    if os.path.lexists(archive):
        try:
            return _validate_canonical_archive(archive, manifest)
        except Exception as exc:
            raise Phase4RunnerError(
                "existing R6 archive is incomplete or invalid; new identity required"
            ) from exc
    archive.mkdir(mode=0o755, parents=False, exist_ok=False)
    for name in sorted(sources):
        path, digest = sources[name]
        if path.is_symlink() or not path.is_file() or _sha256(path) != digest:
            raise Phase4RunnerError(f"canonical source hash mismatch: {name}")
        archived_name = manifest["pending_files"][name]["archive_name"]
        _direct_exclusive_archive_write(
            archive / archived_name, path.read_bytes(),
            expected_sha256=digest, label=f"canonical pending archive {name}",
        )
    for name, payload in (
        ("report", approved_report), ("status", approved_status),
    ):
        archived_name = manifest["approved_payloads"][name]["archive_name"]
        _direct_exclusive_archive_write(
            archive / archived_name, payload,
            expected_sha256=_sha256_bytes(payload),
            label=f"canonical approved archive {name}",
        )
    manifest_payload = (
        json.dumps(_jsonable(manifest), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")
    _direct_exclusive_archive_write(
        archive / "ARCHIVE_MANIFEST.json", manifest_payload,
        expected_sha256=_sha256_bytes(manifest_payload),
        label="canonical archive manifest",
    )
    _fsync_archive_directory(archive)
    return _validate_canonical_archive(archive, manifest)


def _cas_install_canonical_file(
    target: Path, *, expected_before_sha256: str,
    approved_payload: bytes, label: str,
) -> str:
    target = Path(target)
    _reject_symlink_components(target)
    approved_sha = _sha256_bytes(approved_payload)
    temporary = _canonical_cas_temporary(target, approved_payload)
    if target.is_symlink() or not target.is_file():
        raise Phase4RunnerError(f"{label} target is absent or unsafe")
    observed = _sha256(target)
    if os.path.lexists(temporary):
        if temporary.is_symlink() or not temporary.is_file():
            raise Phase4RunnerError(f"{label} CAS temporary is unsafe")
        if _sha256(temporary) != approved_sha:
            raise Phase4RunnerError(f"{label} CAS temporary hash mismatch")
        if observed == approved_sha:
            raise Phase4RunnerError(
                f"{label} CAS temporary is unexpected after approval"
            )
    if observed == approved_sha:
        return "ALREADY_APPROVED"
    if observed != expected_before_sha256:
        raise Phase4RunnerError(f"{label} CAS source hash mismatch")
    if not os.path.lexists(temporary):
        with temporary.open("xb") as stream:
            view = memoryview(approved_payload)
            offset = 0
            while offset < len(view):
                written = stream.write(view[offset:])
                if written is None or written <= 0:
                    raise Phase4RunnerError(f"{label} CAS temporary short write")
                offset += written
            stream.flush()
            os.fsync(stream.fileno())
    if _sha256(target) != expected_before_sha256:
        raise Phase4RunnerError(f"{label} CAS target changed before replace")
    os.replace(temporary, target)
    directory_fd = os.open(target.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    if _sha256(target) != approved_sha:
        raise Phase4RunnerError(f"{label} CAS replacement hash mismatch")
    return "INSTALLED"


def finalize_canonical_after_review(
    preflight: PreflightResult, *, reviewer_verdict: str,
    reviewer_summary: str, reviewer_summary_sha256: str | None,
    expected_pending_sha256: Mapping[str, str | None],
) -> dict[str, Any]:
    summary = reviewer_summary.strip()
    summary_sha = _required_sha256(
        reviewer_summary_sha256, "reviewer summary",
    )
    if (
        reviewer_verdict != "APPROVED" or not summary
        or _sha256_bytes(summary.encode("utf-8")) != summary_sha
    ):
        raise Phase4RunnerError(
            "canonical finalization requires reviewer PASS and exact summary hash"
        )
    if preflight.paths.artifact_root_overridden:
        raise Phase4RunnerError("canonical finalization is restricted to the configured stage")
    lock = _canonical_lock_evidence(preflight)
    failed_r5_before = _failed_r5_canonical_attempt_evidence(
        preflight.paths.configured_stage_root / "11_REPORT"
    )
    sources = _canonical_expected_sources(preflight, expected_pending_sha256)
    archive = preflight.paths.canonical_archive_root
    archive_exists = archive.exists()
    direct_required = (
        {name for name in sources if name not in {"original_report", "original_status"}}
        if archive_exists else set(sources)
    )
    for name in sorted(direct_required):
        path, digest = sources[name]
        if path.is_symlink() or not path.is_file() or _sha256(path) != digest:
            raise Phase4RunnerError(f"canonical source hash mismatch: {name}")
    r6_report_bytes = preflight.paths.r6_report.read_bytes()
    r6_status_bytes = preflight.paths.r6_status.read_bytes()
    approved_report, approved_status = _canonical_approved_payloads(
        preflight, r6_report_bytes=r6_report_bytes,
        r6_status_bytes=r6_status_bytes, reviewer_summary=summary,
        reviewer_summary_sha256=summary_sha, lock=lock,
    )
    manifest = _canonical_archive_manifest(
        preflight, sources=sources, reviewer_summary=summary,
        reviewer_summary_sha256=summary_sha, lock=lock,
        approved_report=approved_report, approved_status=approved_status,
    )
    _inspect_canonical_transaction_temps(
        archive, report_target=preflight.paths.final_report,
        report_expected_before_sha256=sources["original_report"][1],
        approved_report=approved_report,
        status_target=preflight.paths.final_status,
        status_expected_before_sha256=sources["original_status"][1],
        approved_status=approved_status,
    )
    if archive_exists:
        try:
            _validate_canonical_archive(archive, manifest)
        except Exception as exc:
            raise Phase4RunnerError(
                "existing R6 archive is incomplete or invalid; new identity required"
            ) from exc

    # These scientific freezes are hard preconditions on every invocation,
    # including archive-backed retries and already-approved idempotent calls.
    validate_native_freeze(preflight.paths.native_root)
    validate_post_native_freeze(preflight.paths.native_root)
    validate_post_native_r1_freeze(preflight.paths.native_root)
    _load_r1_post_summary(preflight.paths.native_root)
    approved_report, approved_status = _install_canonical_archive(
        archive, sources=sources, manifest=manifest,
        approved_report=approved_report, approved_status=approved_status,
    )
    report_state = _cas_install_canonical_file(
        preflight.paths.final_report,
        expected_before_sha256=sources["original_report"][1],
        approved_payload=approved_report, label="canonical report",
    )
    status_state = _cas_install_canonical_file(
        preflight.paths.final_status,
        expected_before_sha256=sources["original_status"][1],
        approved_payload=approved_status, label="canonical status",
    )
    _validate_canonical_archive(archive, manifest)
    validate_native_freeze(preflight.paths.native_root)
    validate_post_native_freeze(preflight.paths.native_root)
    validate_post_native_r1_freeze(preflight.paths.native_root)
    failed_r5_after = _failed_r5_canonical_attempt_evidence(
        preflight.paths.configured_stage_root / "11_REPORT"
    )
    if failed_r5_after != failed_r5_before:
        raise Phase4RunnerError("failed R5 attempt changed during canonical transaction")
    final_status = json.loads(preflight.paths.final_status.read_text(encoding="utf-8"))
    if (
        _sha256(preflight.paths.final_report) != _sha256_bytes(approved_report)
        or _sha256(preflight.paths.final_status) != _sha256_bytes(approved_status)
        or final_status.get("review_gate") != "APPROVED"
    ):
        raise Phase4RunnerError("canonical two-file transaction did not converge")
    return {
        "terminal_status": str(final_status["terminal_status"]),
        "review_gate": "APPROVED",
        "canonical_final_report": str(preflight.paths.final_report),
        "canonical_final_report_sha256": _sha256(preflight.paths.final_report),
        "canonical_final_status": str(preflight.paths.final_status),
        "canonical_final_status_sha256": _sha256(preflight.paths.final_status),
        "pending_archive": str(archive),
        "pending_archive_manifest_sha256": _sha256(
            archive / "ARCHIVE_MANIFEST.json"
        ),
        "failed_R5_canonical_attempt": failed_r5_after,
        "transaction_states": {"report": report_state, "status": status_state},
    }


def run_phase4(
    config_path: Path, *, mode: str = "full", method_id: str = METHOD_ID,
    case_id: str = CASE_ID, trace_mode: str = "disabled",
    workers: int = DEFAULT_WORKERS, resume: bool = False,
    execution_lock: Path | None = None,
    execution_lock_sha256: str | None = None,
    preexisting_manifest: Path | None = None,
    preexisting_manifest_sha256: str | None = None,
    artifact_root: Path | None = None,
    reviewer_verdict: str = "PENDING", reviewer_summary: str = "",
    reviewer_summary_sha256: str | None = None,
    focused_tests: str = "NOT_RUN", full_tests: str = "NOT_RUN",
    focused_test_summary: str = "", full_test_summary: str = "",
    expected_original_report_sha256: str | None = None,
    expected_original_status_sha256: str | None = None,
    expected_r1_report_sha256: str | None = None,
    expected_r1_status_sha256: str | None = None,
    expected_r2_report_sha256: str | None = None,
    expected_r2_status_sha256: str | None = None,
    expected_r3_report_sha256: str | None = None,
    expected_r3_status_sha256: str | None = None,
    expected_r4_report_sha256: str | None = None,
    expected_r4_status_sha256: str | None = None,
    expected_r5_report_sha256: str | None = None,
    expected_r5_status_sha256: str | None = None,
    expected_r6_report_sha256: str | None = None,
    expected_r6_status_sha256: str | None = None,
) -> dict[str, Any]:
    if (
        method_id != METHOD_ID or case_id != CASE_ID or mode not in ALLOWED_MODES
        or workers != AUTHORIZED_WORKERS or trace_mode != "disabled"
    ):
        raise Phase4RunnerError("invalid Phase-4 invocation")
    allow_existing = mode in {
        "post-native-diagnostics", "post-native-r1-diagnostics",
        "create-execution-lock", "finalize-r1-pending",
        "finalize-canonical-after-review",
    }
    allow_reports = mode in {
        "post-native-r1-diagnostics", "create-execution-lock",
        "finalize-r1-pending", "finalize-canonical-after-review",
    }
    if mode == "full":
        # A one-shot full invocation starts from an empty output inventory.
        allow_existing = False
    lock_input = None if mode == "create-execution-lock" else execution_lock
    lock_sha_input = (
        None if mode == "create-execution-lock" else execution_lock_sha256
    )
    preflight = preflight_phase4(
        config_path, allow_native_existing=allow_existing,
        allow_report_existing=allow_reports, execution_lock=lock_input,
        execution_lock_sha256=lock_sha_input,
        preexisting_manifest=preexisting_manifest,
        preexisting_manifest_sha256=preexisting_manifest_sha256,
        artifact_root=artifact_root,
        artifact_resume=bool(artifact_root is not None and resume),
        initialize_artifact_root=bool(
            artifact_root is not None and not resume
            and mode not in {"preflight", "create-execution-lock"}
        ),
    )
    if mode == "preflight":
        return {
            "terminal_status": "PASS_PHASE4_EXT04_PREFLIGHT_ONLY",
            "source_fingerprint": preflight.source_fingerprint,
            "runtime_content_fingerprint": preflight.runtime_content_fingerprint,
            "task_start_head": preflight.task_start_head,
            "execution_head": preflight.execution_head,
            "provenance_mode": preflight.provenance_mode,
            "execution_lock_evidence": dict(preflight.execution_lock_evidence),
            "preexisting_manifest_path": str(preflight.preexisting_manifest_path),
            "preexisting_manifest_sha256": preflight.preexisting_manifest_sha256,
            "artifact_root_evidence": dict(preflight.artifact_root_evidence),
            "formal_run_launched": False, "trace_open_count": 0,
            "HPPOSECEF_semantic_decode_count": 0,
        }
    if mode == "create-execution-lock":
        if execution_lock is None:
            raise Phase4RunnerError("create-execution-lock requires --execution-lock")
        return create_execution_lock(preflight, execution_lock)
    if mode == "finalize-r1-pending":
        return finalize_r1_pending_reports(
            preflight, focused_tests=focused_tests,
            full_tests=full_tests, focused_test_summary=focused_test_summary,
            full_test_summary=full_test_summary,
        )
    if mode == "finalize-canonical-after-review":
        return finalize_canonical_after_review(
            preflight, reviewer_verdict=reviewer_verdict,
            reviewer_summary=reviewer_summary,
            reviewer_summary_sha256=reviewer_summary_sha256,
            expected_pending_sha256={
                "original_report": expected_original_report_sha256,
                "original_status": expected_original_status_sha256,
                "R1_report": expected_r1_report_sha256,
                "R1_status": expected_r1_status_sha256,
                "R2_report": expected_r2_report_sha256,
                "R2_status": expected_r2_status_sha256,
                "R3_report": expected_r3_report_sha256,
                "R3_status": expected_r3_status_sha256,
                "R4_report": expected_r4_report_sha256,
                "R4_status": expected_r4_status_sha256,
                "R5_report": expected_r5_report_sha256,
                "R5_status": expected_r5_status_sha256,
                "R6_report": expected_r6_report_sha256,
                "R6_status": expected_r6_status_sha256,
            },
        )
    if mode == "post-native-diagnostics":
        return _post_execution(preflight)
    if mode == "post-native-r1-diagnostics":
        return _post_r1_execution(preflight, resume=resume)
    native = _native_execution(
        preflight, workers=workers, resume=resume,
        probe_only=mode == "resource-determinism-probe",
    )
    if mode in {"resource-determinism-probe", "native-only"}:
        return native
    post = _post_execution(preflight)
    return {
        "terminal_status": "PASS_PHASE4_EXT04_EXECUTION_READY_FOR_INDEPENDENT_REVIEW",
        "native": native, "post_native": post,
        "reports_finalized": False, "independent_review": "PENDING",
    }


def terminalize_failure(
    config_path: Path, mode: str, exc: BaseException,
    execution_lock: Path | None = None,
    execution_lock_sha256: str | None = None,
    preexisting_manifest: Path | None = None,
    preexisting_manifest_sha256: str | None = None,
    artifact_root: Path | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": "horizontal_literature.phase4.failed_attempt.v1",
        "terminal_status": f"{BLOCKED_PREFIX}{type(exc).__name__.upper()}",
        "mode": mode, "exception_type": type(exc).__name__,
        "exception_message": str(exc), "timestamp_ns": time.time_ns(),
        "native_or_post_success_claimed": False,
    }
    try:
        lock_input = None if mode == "create-execution-lock" else execution_lock
        lock_sha_input = (
            None if mode == "create-execution-lock" else execution_lock_sha256
        )
        preflight = preflight_phase4(
            config_path, allow_native_existing=True,
            allow_report_existing=True, execution_lock=lock_input,
            execution_lock_sha256=lock_sha_input,
            preexisting_manifest=preexisting_manifest,
            preexisting_manifest_sha256=preexisting_manifest_sha256,
            artifact_root=artifact_root,
            artifact_resume=artifact_root is not None,
        )
        marker_root = (
            preflight.paths.post_r1_root
            if mode == "post-native-r1-diagnostics"
            else _attempt_root(preflight)
        )
        if marker_root.is_dir():
            phase2._atomic_write_json(
                marker_root / f"FAILED_ATTEMPT_{payload['timestamp_ns']}.json", payload,
            )
    except Exception as marker_exc:
        payload["failure_marker_error"] = (
            f"{type(marker_exc).__name__}: {marker_exc}"
        )
    return payload
