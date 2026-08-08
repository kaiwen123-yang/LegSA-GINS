"""CLEAN3R3 governance preflight and one-shot S3 AB0000 parity orchestration.

This module exposes exactly two operations: a zero-data governance preflight
and a separately gated, one-shot S3 parity attempt.  The preflight never runs
the formal solver; neither operation imports an evaluator, generates providers,
reads performance metrics, or routes to CLEAN2 execution entrypoints.
"""

from __future__ import annotations

import json
import ast
import contextlib
import fcntl
import os
import stat
import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .clean1r2r1_formal import module_counters
from .evidence import BY2_TRACE_RELATIVE_PATH
from .final_v23_clean_parity import active_runtime_config
from .manifest import read_hash_lock, sha256_file, write_json_atomic
from .paths import is_within, legacy_reason
from .subprocess_guard import run_process_group


STAGE_ID = "CLEAN3R3_MATH_REPAIR_PORT_ROLE_FILL_IF_EMPTY_HARDCODE_SWEEP_AND_S3_RESUME"
PROTOCOL_ID = "CLEAN3_S3_AB0000_PARITY"
CASE_ID = "CLEAN1_BY2_CLEAN_NORMAL"
RUN_ID = "CLEAN3_S3_AB0000"
METHOD_ID = "AB0000"
DATA_MODE = "real_clean"

REPAIR_IMPLEMENTATION_COMMIT = "0d8cc2bdccfd89b236ab4badeef9db5344dcf4d3"
B0_COMMIT = "683d355db4fe5194d479cda155e01de1b47a2b17"
AMENDMENT_PARENT_HEAD = "d311f7457d5b5b9be72ef2101cfa0db47e28614f"
CODE_FREEZE_COMMIT = "d1fc2d4ac3070129595c81bea7e261c4f3b586f6"
REJECTED_RUNNER_FREEZE_COMMIT = "0f8d12ec6465105e56309a0df62c1f165e01aa63"
C2R1_COMMIT = "187e92796db8aa2a479b62249d7c1a945f4ad721"
C2R2_COMMIT = "f3c5baff07beb9f20faaefd89c4e7ad4a05a7ab0"
C2R3_COMMIT = "244872ae18ebd3fdbb33aa8e035fba93f1dcfcd5"
C2R4_COMMIT = "218059452c7774b3d4dc23bc722a9a2f6f8c9ae7"
PRIOR_REVIEWED_CPP_TREE = "a3716d22acf95fb1e6028ae82acb2ae73e138bfc"
RUNTIME_COUNTER_PATH = "cpp/legsa_v23_port_core/src/runtime/port_runtime.cpp"
LOADER_EXTENSION_PATH = "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp"
FREEZE_PATH = "docs/paper_rebuild/CLEAN3R3/CLEAN3R3_S3_EXECUTION_FREEZE.json"
AUTHORIZATION_PATH = "docs/paper_rebuild/CLEAN3R3/CLEAN3R3_S3_EXECUTION_AUTHORIZATION.md"
FROZEN_CODE_PATHS = (
    RUNTIME_COUNTER_PATH,
    LOADER_EXTENSION_PATH,
    "src/legsa_gins/paper_rebuild/clean3_math_repair.py",
    "scripts/paper_rebuild/run_clean3_math_repair.py",
    "tests/paper_rebuild/test_clean3r2_counter_contract_routing.py",
    "tests/paper_rebuild/test_clean3r3_port_role_governance.py",
    "tests/paper_rebuild/test_clean3_s3_parity_runner.py",
)
S0_CODE_FREEZE_CHANGED_PATHS = (
    RUNTIME_COUNTER_PATH,
    LOADER_EXTENSION_PATH,
    "tests/paper_rebuild/test_clean3r3_port_role_governance.py",
)
RUNNER_FREEZE_CHANGED_PATHS = (
    "src/legsa_gins/paper_rebuild/clean3_math_repair.py",
    "scripts/paper_rebuild/run_clean3_math_repair.py",
    "tests/paper_rebuild/test_clean3_s3_parity_runner.py",
)
C2R1_CHANGED_PATHS = (
    "src/legsa_gins/paper_rebuild/clean3_math_repair.py",
    "tests/paper_rebuild/test_clean3_s3_parity_runner.py",
)
C2R2_CHANGED_PATHS = C2R1_CHANGED_PATHS
C2R3_CHANGED_PATHS = C2R1_CHANGED_PATHS
C2R4_CHANGED_PATHS = C2R1_CHANGED_PATHS
C2R5_CHANGED_PATHS = C2R1_CHANGED_PATHS
A0_CHANGED_PATHS = (
    "docs/paper_rebuild/CLEAN3R3/HARDCODE_INVENTORY.md",
    "docs/paper_rebuild/CLEAN3R3/AMENDMENT_1_SCOPE_AND_IMPLEMENTATION_AUTHORIZATION.md",
)
PREFLIGHT_RELATIVE = Path("00_GOVERNANCE_PREFLIGHT") / STAGE_ID
PREFLIGHT_REPORT_SCHEMA = "paper_rebuild.clean3r3_governance_preflight.v2"
PREFLIGHT_LEDGER_SCHEMA = "paper_rebuild.clean3r3_zero_data_loader_ledger.v1"
PREFLIGHT_SEAL_SCHEMA = "paper_rebuild.clean3r3_governance_preflight_seal.v1"
PREFLIGHT_CLAIM_SCHEMA = "paper_rebuild.clean3r3_governance_preflight_claim.v1"
PREFLIGHT_TERMINAL_SCHEMA = "paper_rebuild.clean3r3_governance_preflight_terminal.v1"
PREFLIGHT_FAILURE_SCHEMA = "paper_rebuild.clean3r3_governance_preflight_failure.v1"
PREFLIGHT_LEDGER_FIELDS = frozenset({
    "schema_version", "trace_subject", "exec_paths", "expected_exec_path", "exact_exec_subject",
    "read_attempt_paths", "write_attempt_paths", "accepting_config_open_count",
    "negative_config_open_count", "raw_paths", "provider_paths", "reference_trace_paths",
    "legacy_paths", "unexpected_write_paths", "unexpected_read_paths", "path_classifications",
    "classification_roots", "raw_open_count", "provider_open_count", "reference_trace_open_count",
    "legacy_open_count", "unexpected_write_count", "unexpected_read_count",
    "bound_artifact_sha256", "formal_solver_executed", "passed",
})

FAILED_ATTEMPT_STAGE_ID = "CLEAN3_MATH_REPAIR_RP_JACOBIAN_RD_LEVERARM_SA_CLEAN_SILENCE"
FAILED_ATTEMPT_TERMINAL = "FAILED_TECHNICAL_S3_AB0000_FORMAL_COUNTER_CONTRACT_UNROUTED"
FAILED_ATTEMPT_PARITY = "NOT_EVALUATED"
FAILED_ATTEMPT_EXECUTION_COMMIT = "3110131cbbb64caff71a4e493a0b64365e6fb936"
FAILED_ATTEMPT_RUNNER_FREEZE_COMMIT = "e28899156b03b32d3840476bf57ac01807494086"

PARENT_PROVIDER_STAGE_ID = "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD"
PARENT_PROVIDER_PROTOCOL_ID = "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION"
CLEAN_INPUT_STAGE_ID = "CLEAN1R2R1_CLEAN_REAL_FINAL_V23_PARITY_AND_FOUR_METHOD_EXECUTION"
CLEAN_INPUT_PROTOCOL_ID = "CLEAN_REAL_DATA_FINAL_V23"
PARENT_PARITY_STAGE_ID = "CLEAN2R2A1_RAW_DOPPLER_CANONICAL_PARITY_AND_CLEAN_ABLATION_RESUME"
PARENT_PARITY_PROTOCOL_ID = "CLEAN2R2A1_BY2_CLEAN_MODULE_ABLATION_RESUME"

EXPECTED_MANIFEST_HASHES = {
    "clean_input_manifest": "d018ffe9ee30a7ae0b08d7c57ac062d37c5b0d3a7be71cbcabc97a580a10bc2c",
    "auxiliary_manifest": "80bffb19ebc8627dac26e81e76131ec9a8f4c5c0ce0f244827512ee8612000ad",
    "provider_parity_report": "f42acb20ce0aa8741999601d7f812938a2f35045e665d1ddf65574c5e3af3358",
}
EXPECTED_PROVIDER_HASHES = {
    "imu": "a46fe2b50a5a99d550392f42e3952c871a7562c6d5625ea1b377691009ab643b",
    "gnss": "f4070ba795825cc243402e4acb551c62c6aad109e7040582bf57781226420e22",
    "raw_doppler": "847d6c0ed6c28c59c661b07d59707faf76c3a5adb2b45fac9802a190b8b00fc4",
    "go2_roll_pitch": "2329770b8e9bc61c02fbf943e2e5fd9ea233d6fd8a3550f7a22410a536155c7a",
    "go2_horizontal_velocity": "f390c8e51f1bec1162c0f6c628ebbcd0449923cfbf9211bebb36004dc2b2aab0",
}
EXPECTED_FULL_RAW_LOCK_SHA256 = "f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7"
EXPECTED_BY2_RAW_LOCK_SHA256 = "7103880ff53eb195c7d9acdbb87292a7be20e4a58b764da29f848e80a84ecb6c"
EXPECTED_FULL_RAW_ROWS = 9980
EXPECTED_BY2_RAW_ROWS = 22
EXPECTED_ANCHOR_HASHES = {
    "KF_GINS_Navresult.nav": "800f0dc12d77fe01ff5262c4261457e1ec178344dba3efb249464ed16696ebc0",
    "KF_GINS_STD.txt": "04ebff455853a89e3a32ebed5510a5c3b86acfa3b569448acd6c7b29c18a05e2",
}

PASS_TERMINAL = "PASS_CLEAN3_S3_AB0000_BYTE_PARITY"
MISMATCH_TERMINAL = "BLOCKED_PARITY_REGRESSION_AB0000_MISMATCH"


class Clean3S3Error(RuntimeError):
    """A CLEAN3 S3 gate failed closed."""

    def __init__(self, message: str, *, terminal_status: str, report_path: Path | None = None):
        super().__init__(message)
        self.terminal_status = terminal_status
        self.report_path = report_path


class _TechnicalFailure(RuntimeError):
    def __init__(self, reason: str, message: str):
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True)
class S3Inputs:
    repo_root: Path
    clean_root: Path
    raw_root: Path
    full_raw_lock: Path
    by2_raw_lock: Path
    clean_input_manifest: Path
    auxiliary_manifest: Path
    provider_parity_report: Path
    jobs: int = 2
    timeout_seconds: int = 1800


CommandRunner = Callable[[Sequence[str], Path, float], subprocess.CompletedProcess[str]]


def _default_command_runner(
    command: Sequence[str], cwd: Path, timeout_seconds: float,
) -> subprocess.CompletedProcess[str]:
    return run_process_group(
        command,
        cwd=cwd,
        timeout_seconds=timeout_seconds,
        timeout_message="CLEAN3 S3 command timeout; process group terminated",
        launch_failure_message="CLEAN3 S3 command launch failure",
    )


def _git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, capture_output=True, text=True, timeout=30,
    )


def _guard_git(repo: Path) -> dict[str, Any]:
    head = _git(repo, "rev-parse", "HEAD").stdout.strip()
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
        raise Clean3S3Error("Git HEAD is not a full lowercase SHA", terminal_status="FAILED_TECHNICAL_GIT_IDENTITY")
    if _git(repo, "status", "--porcelain").stdout.strip():
        raise Clean3S3Error("S3 requires an exact clean Git HEAD", terminal_status="FAILED_TECHNICAL_DIRTY_WORKTREE")
    freeze_path = repo / FREEZE_PATH
    if not freeze_path.is_file() or freeze_path.is_symlink():
        raise Clean3S3Error("tracked execution freeze is missing", terminal_status="FAILED_TECHNICAL_FREEZE_MISSING")
    freeze = _load_json(freeze_path)
    required = {
        "schema_version": "paper_rebuild.clean3r3_s3_execution_freeze.v1",
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": CASE_ID,
        "algorithm_id": METHOD_ID,
        "run_id": RUN_ID,
        "repair_implementation_commit": REPAIR_IMPLEMENTATION_COMMIT,
        "b0_commit": B0_COMMIT,
        "amendment_parent_head": AMENDMENT_PARENT_HEAD,
        "code_freeze_commit": CODE_FREEZE_COMMIT,
        "failed_attempt_stage_id": FAILED_ATTEMPT_STAGE_ID,
        "failed_attempt_terminal": FAILED_ATTEMPT_TERMINAL,
        "failed_attempt_parity": FAILED_ATTEMPT_PARITY,
        "failed_attempt_execution_commit": FAILED_ATTEMPT_EXECUTION_COMMIT,
        "failed_attempt_runner_freeze_commit": FAILED_ATTEMPT_RUNNER_FREEZE_COMMIT,
        "authorization_document": AUTHORIZATION_PATH,
        "authorization_hash_algorithm": "sha256",
        "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER",
        "g_c2": "REPORTING_ONLY",
        "g_c3": "HARD_UNCHANGED",
        "sealed_governance_preflight_required": True,
        "old_attempt_overwritten": False,
        "ready_for_s4": False,
        "ready_for_paper_claims": False,
    }
    if any(freeze.get(key) != value for key, value in required.items()):
        raise Clean3S3Error("execution freeze lineage mismatch", terminal_status="FAILED_TECHNICAL_FREEZE_CONTRACT")
    runner_freeze = freeze.get("runner_freeze_commit")
    if (not isinstance(runner_freeze, str) or len(runner_freeze) != 40
            or any(ch not in "0123456789abcdef" for ch in runner_freeze)):
        raise Clean3S3Error("execution freeze commit is invalid", terminal_status="FAILED_TECHNICAL_FREEZE_CONTRACT")
    def require_single_parent(commit: str, parent: str, label: str) -> None:
        fields = _git(repo, "rev-list", "--parents", "-n", "1", commit).stdout.strip().split()
        if fields != [commit, parent]:
            raise Clean3S3Error(f"{label} is not an exact single-parent commit",
                                terminal_status="FAILED_TECHNICAL_FREEZE_LINEAGE")

    require_single_parent(AMENDMENT_PARENT_HEAD, B0_COMMIT, "CLEAN3R3 A0")
    require_single_parent(CODE_FREEZE_COMMIT, AMENDMENT_PARENT_HEAD, "CLEAN3R3 C1")
    require_single_parent(REJECTED_RUNNER_FREEZE_COMMIT, CODE_FREEZE_COMMIT, "preserved CLEAN3R3 C2")
    require_single_parent(C2R1_COMMIT, REJECTED_RUNNER_FREEZE_COMMIT, "preserved CLEAN3R3 C2R1")
    require_single_parent(C2R2_COMMIT, C2R1_COMMIT, "preserved CLEAN3R3 C2R2")
    require_single_parent(C2R3_COMMIT, C2R2_COMMIT, "preserved CLEAN3R3 C2R3")
    require_single_parent(C2R4_COMMIT, C2R3_COMMIT, "preserved CLEAN3R3 C2R4")
    require_single_parent(runner_freeze, C2R4_COMMIT, "CLEAN3R3 C2R5")
    require_single_parent(head, runner_freeze, "CLEAN3R3 C3")
    if _git(repo, "rev-parse", f"{head}^").stdout.strip() != runner_freeze:
        raise Clean3S3Error("execution HEAD is not exactly one authorization commit after runner freeze",
                            terminal_status="FAILED_TECHNICAL_FREEZE_LINEAGE")
    changed = tuple(_git(repo, "diff", "--name-only", f"{runner_freeze}..{head}").stdout.splitlines())
    authorization_paths = freeze.get("authorization_commit_paths")
    if (not isinstance(authorization_paths, list) or not authorization_paths or
            FREEZE_PATH not in authorization_paths or AUTHORIZATION_PATH not in authorization_paths or
            tuple(sorted(changed)) != tuple(sorted(str(item) for item in authorization_paths))):
        raise Clean3S3Error("authorization commit scope differs from the frozen C3 documents",
                            terminal_status="FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT")
    a0_changed = tuple(sorted(
        _git(repo, "diff", "--name-only", f"{B0_COMMIT}..{AMENDMENT_PARENT_HEAD}").stdout.splitlines()
    ))
    if a0_changed != tuple(sorted(A0_CHANGED_PATHS)):
        raise Clean3S3Error("A0 scope differs from the approved two documents",
                            terminal_status="FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT")
    code_freeze_changed = tuple(sorted(
        _git(repo, "diff", "--name-only", f"{AMENDMENT_PARENT_HEAD}..{CODE_FREEZE_COMMIT}")
        .stdout.splitlines()
    ))
    if code_freeze_changed != tuple(sorted(S0_CODE_FREEZE_CHANGED_PATHS)):
        raise Clean3S3Error("C1 code freeze diff is outside the approved three repair paths",
                            terminal_status="FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT")
    runner_changed = tuple(sorted(
        _git(repo, "diff", "--name-only", f"{CODE_FREEZE_COMMIT}..{REJECTED_RUNNER_FREEZE_COMMIT}")
        .stdout.splitlines()
    ))
    if runner_changed != tuple(sorted(RUNNER_FREEZE_CHANGED_PATHS)):
        raise Clean3S3Error("C2 runner freeze diff is outside the approved three runner paths",
                            terminal_status="FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT")
    repair_changed = tuple(sorted(
        _git(repo, "diff", "--name-only", f"{REJECTED_RUNNER_FREEZE_COMMIT}..{C2R1_COMMIT}")
        .stdout.splitlines()
    ))
    if repair_changed != tuple(sorted(C2R1_CHANGED_PATHS)):
        raise Clean3S3Error("C2R1 diff is outside the approved two repair paths",
                            terminal_status="FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT")
    repair2_changed = tuple(sorted(
        _git(repo, "diff", "--name-only", f"{C2R1_COMMIT}..{C2R2_COMMIT}").stdout.splitlines()
    ))
    if repair2_changed != tuple(sorted(C2R2_CHANGED_PATHS)):
        raise Clean3S3Error("C2R2 diff is outside the approved two repair paths",
                            terminal_status="FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT")
    repair3_changed = tuple(sorted(
        _git(repo, "diff", "--name-only", f"{C2R2_COMMIT}..{C2R3_COMMIT}").stdout.splitlines()
    ))
    if repair3_changed != tuple(sorted(C2R3_CHANGED_PATHS)):
        raise Clean3S3Error("C2R3 diff is outside the approved two repair paths",
                            terminal_status="FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT")
    repair4_changed = tuple(sorted(
        _git(repo, "diff", "--name-only", f"{C2R3_COMMIT}..{C2R4_COMMIT}").stdout.splitlines()
    ))
    if repair4_changed != tuple(sorted(C2R4_CHANGED_PATHS)):
        raise Clean3S3Error("C2R4 diff is outside the approved two repair paths",
                            terminal_status="FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT")
    repair5_changed = tuple(sorted(
        _git(repo, "diff", "--name-only", f"{C2R4_COMMIT}..{runner_freeze}").stdout.splitlines()
    ))
    if repair5_changed != tuple(sorted(C2R5_CHANGED_PATHS)):
        raise Clean3S3Error("C2R5 diff is outside the approved two repair paths",
                            terminal_status="FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT")
    for tracked in (FREEZE_PATH, AUTHORIZATION_PATH):
        if _git(repo, "ls-files", "--error-unmatch", tracked, check=False).returncode != 0:
            raise Clean3S3Error("execution freeze or authorization is not tracked",
                                terminal_status="FAILED_TECHNICAL_FREEZE_UNTRACKED")
    for ancestor in (
        runner_freeze, C2R4_COMMIT, C2R3_COMMIT, C2R2_COMMIT, C2R1_COMMIT,
        REJECTED_RUNNER_FREEZE_COMMIT,
        CODE_FREEZE_COMMIT,
        REPAIR_IMPLEMENTATION_COMMIT,
        AMENDMENT_PARENT_HEAD,
    ):
        if _git(repo, "merge-base", "--is-ancestor", ancestor, head, check=False).returncode != 0:
            raise Clean3S3Error(
                f"HEAD does not descend from required context {ancestor}",
                terminal_status="FAILED_TECHNICAL_WRONG_CODE_LINEAGE",
            )
    if _git(
        repo, "merge-base", "--is-ancestor", REPAIR_IMPLEMENTATION_COMMIT,
        AMENDMENT_PARENT_HEAD, check=False,
    ).returncode != 0:
        raise Clean3S3Error(
            "amendment parent does not inherit the reviewed repair implementation",
            terminal_status="FAILED_TECHNICAL_WRONG_CODE_LINEAGE",
        )
    cpp_tree = _git(repo, "rev-parse", f"{head}:cpp").stdout.strip()
    if freeze.get("final_cpp_tree") != cpp_tree:
        raise Clean3S3Error("frozen C++ tree mismatch", terminal_status="FAILED_TECHNICAL_CPP_TREE_DRIFT")
    authorization_path = repo / AUTHORIZATION_PATH
    if not authorization_path.is_file() or authorization_path.is_symlink():
        raise Clean3S3Error("authorization document is missing or unsafe",
                            terminal_status="FAILED_TECHNICAL_AUTHORIZATION_MISSING")
    if freeze.get("authorization_sha256") != sha256_file(authorization_path):
        raise Clean3S3Error("authorization document hash mismatch",
                            terminal_status="FAILED_TECHNICAL_AUTHORIZATION_HASH_MISMATCH")
    frozen_hashes = freeze.get("tracked_file_sha256")
    if not isinstance(frozen_hashes, Mapping) or set(frozen_hashes) != set(FROZEN_CODE_PATHS):
        raise Clean3S3Error("frozen tracked-file ledger is incomplete", terminal_status="FAILED_TECHNICAL_FREEZE_CONTRACT")
    actual_hashes = {relative: sha256_file(repo / relative) for relative in FROZEN_CODE_PATHS}
    if actual_hashes != frozen_hashes:
        raise Clean3S3Error("tracked runner bytes differ from execution freeze",
                            terminal_status="FAILED_TECHNICAL_RUNNER_BYTE_DRIFT")
    changed_cpp = tuple(sorted(
        row for row in _git(
            repo, "diff", "--name-only", f"{AMENDMENT_PARENT_HEAD}..{runner_freeze}", "--", "cpp",
        ).stdout.splitlines() if row
    ))
    if changed_cpp != tuple(sorted((RUNTIME_COUNTER_PATH, LOADER_EXTENSION_PATH))):
        raise Clean3S3Error(
            "C++ diff from amendment parent is not the exact counter and loader repair",
            terminal_status="FAILED_TECHNICAL_CPP_SCOPE_DRIFT",
        )
    prior_tree = _git(repo, "rev-parse", f"{REPAIR_IMPLEMENTATION_COMMIT}:cpp").stdout.strip()
    if prior_tree != PRIOR_REVIEWED_CPP_TREE:
        raise Clean3S3Error(
            "reviewed S2 C++ tree identity drifted",
            terminal_status="FAILED_TECHNICAL_REVIEWED_CPP_TREE_MISMATCH",
        )
    expected_authorization = {
        "s3_solver_allowed_now": True,
        "maximum_solver_executions": 1,
        "evaluator_allowed_now": False,
        "reference_trace_allowed_now": False,
        "canonical_541_allowed_now": False,
        "provider_regeneration_allowed_now": False,
        "retry_allowed_now": False,
    }
    authorization = freeze.get("execution_authorization")
    if not isinstance(authorization, Mapping) or dict(authorization) != expected_authorization:
        raise Clean3S3Error("execution authorization is not the exact one-shot S3 contract",
                            terminal_status="FAILED_TECHNICAL_AUTHORIZATION_CONTRACT")
    return {
        "execution_head": head,
        "code_freeze_commit": CODE_FREEZE_COMMIT,
        "runner_freeze_commit": runner_freeze,
        "authorization_commit": head,
        "authorization_document": AUTHORIZATION_PATH,
        "authorization_sha256": freeze["authorization_sha256"],
        "execution_freeze_sha256": sha256_file(freeze_path),
        "frozen_tracked_file_sha256": dict(frozen_hashes),
        "repair_implementation_commit": REPAIR_IMPLEMENTATION_COMMIT,
        "amendment_parent_head": AMENDMENT_PARENT_HEAD,
        "prior_reviewed_cpp_tree": PRIOR_REVIEWED_CPP_TREE,
        "final_execution_cpp_tree": cpp_tree,
        "cpp_diff_from_amendment_parent": list(changed_cpp),
        "failed_attempt_stage_id": FAILED_ATTEMPT_STAGE_ID,
        "failed_attempt_terminal": FAILED_ATTEMPT_TERMINAL,
        "failed_attempt_parity": FAILED_ATTEMPT_PARITY,
        "maximum_solver_executions": 1,
    }


def _require_no_symlink_chain(path: Path) -> None:
    candidate = path.absolute()
    for item in (candidate, *candidate.parents):
        if item.exists() and item.is_symlink():
            raise Clean3S3Error(
                f"symlink component is forbidden: {item}",
                terminal_status="FAILED_TECHNICAL_PATH_SYMLINK",
            )


def _exact_paths(inputs: S3Inputs) -> dict[str, Path]:
    for supplied in (inputs.repo_root, inputs.clean_root, inputs.raw_root, inputs.full_raw_lock,
                     inputs.by2_raw_lock, inputs.clean_input_manifest, inputs.auxiliary_manifest,
                     inputs.provider_parity_report):
        _require_no_symlink_chain(Path(supplied))
    repo = inputs.repo_root.resolve(strict=True)
    clean = inputs.clean_root.resolve(strict=True)
    raw = inputs.raw_root.resolve(strict=True)
    stage = clean / "stages" / STAGE_ID
    _require_no_symlink_chain(stage.parent)
    if stage.exists() or stage.is_symlink():
        raise Clean3S3Error(
            "CLEAN3 S3 stage root already exists; resume/overwrite is forbidden",
            terminal_status="FAILED_TECHNICAL_STAGE_ROOT_PREEXISTS",
        )
    expected = {
        "full_raw_lock": clean / "01_RAW_HASH_LOCK" / "RAW_FILE_HASH_LOCK.csv",
        "by2_raw_lock": clean / "01_RAW_HASH_LOCK" / "BY2_HASH_LOCK.csv",
        "clean_input_manifest": clean / "stages" / PARENT_PROVIDER_STAGE_ID / "04_BASE_PROVIDER"
        / "FINAL_V23_CLEAN_CLEAN2R2A" / "FINAL_V23_CLEAN_INPUT_MANIFEST.json",
        "auxiliary_manifest": clean / "stages" / PARENT_PROVIDER_STAGE_ID / "04_BASE_PROVIDER"
        / "FRESH_AUXILIARIES_CLEAN2R2A" / "CLEAN1R2R1_AUXILIARY_MANIFEST.json",
        "provider_parity_report": clean / "stages" / PARENT_PARITY_STAGE_ID / "04_BASE_PROVIDER"
        / "CLEAN2R2A1_BASE_PROVIDER_PARITY.json",
    }
    supplied = {
        "full_raw_lock": inputs.full_raw_lock,
        "by2_raw_lock": inputs.by2_raw_lock,
        "clean_input_manifest": inputs.clean_input_manifest,
        "auxiliary_manifest": inputs.auxiliary_manifest,
        "provider_parity_report": inputs.provider_parity_report,
    }
    resolved: dict[str, Path] = {"repo": repo, "clean_root": clean, "raw_root": raw, "stage_root": stage}
    for role, expected_path in expected.items():
        _require_no_symlink_chain(Path(supplied[role]))
        candidate = Path(supplied[role]).resolve(strict=True)
        if candidate != expected_path.resolve(strict=True):
            raise Clean3S3Error(
                f"{role} is not the exact inherited path",
                terminal_status="FAILED_TECHNICAL_INHERITED_PATH_MISMATCH",
            )
        resolved[role] = candidate
    anchor = clean / "17_LOGS" / "CLEAN1R2R1_FINAL" / "04_FOUR_METHOD_RUNTIME" / "03_strong_dual_yaw_EKF"
    _require_no_symlink_chain(anchor / "KF_GINS_Navresult.nav")
    _require_no_symlink_chain(anchor / "KF_GINS_STD.txt")
    resolved["anchor_nav"] = (anchor / "KF_GINS_Navresult.nav").resolve(strict=True)
    resolved["anchor_std"] = (anchor / "KF_GINS_STD.txt").resolve(strict=True)
    for path in (repo, clean, raw, resolved["anchor_nav"], resolved["anchor_std"]):
        _require_no_symlink_chain(path)
    return resolved


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _TechnicalFailure("MANIFEST_SCHEMA", f"invalid JSON object: {path.name}") from exc
    if not isinstance(payload, dict):
        raise _TechnicalFailure("MANIFEST_SCHEMA", f"manifest is not an object: {path.name}")
    return payload


def _manifest_and_provider_guard(paths: Mapping[str, Path]) -> dict[str, Any]:
    manifest_paths = {role: paths[role] for role in EXPECTED_MANIFEST_HASHES}
    actual_manifest_hashes = {role: sha256_file(path) for role, path in manifest_paths.items()}
    if actual_manifest_hashes != EXPECTED_MANIFEST_HASHES:
        raise Clean3S3Error(
            "inherited manifest byte identity mismatch",
            terminal_status="FAILED_TECHNICAL_INHERITED_MANIFEST_HASH_MISMATCH",
        )
    clean = _load_json(paths["clean_input_manifest"])
    auxiliary = _load_json(paths["auxiliary_manifest"])
    parity = _load_json(paths["provider_parity_report"])
    if (
        clean.get("stage_id") != CLEAN_INPUT_STAGE_ID
        or clean.get("protocol_id") != CLEAN_INPUT_PROTOCOL_ID
        or auxiliary.get("stage_id") != PARENT_PROVIDER_STAGE_ID
        or auxiliary.get("protocol_id") != PARENT_PROVIDER_PROTOCOL_ID
        or parity.get("stage_id") != PARENT_PARITY_STAGE_ID
        or parity.get("protocol_id") != PARENT_PARITY_PROTOCOL_ID
        or parity.get("passed") is not True
        or parity.get("provider_payload_modified_after_generation") is not False
        or parity.get("trace_open_count") != 0
    ):
        raise Clean3S3Error(
            "inherited provider manifests failed identity/status gates",
            terminal_status="FAILED_TECHNICAL_INHERITED_MANIFEST_CONTRACT",
        )
    artifacts = clean.get("artifacts")
    aux_artifacts = auxiliary.get("auxiliary_artifacts")
    if not isinstance(artifacts, Mapping) or not isinstance(aux_artifacts, Mapping):
        raise _TechnicalFailure("MANIFEST_SCHEMA", "provider artifact maps are missing")
    provider_root = paths["clean_input_manifest"].parent.parent.resolve(strict=True)
    provider_candidates = {
        "imu": paths["clean_input_manifest"].parent / str(artifacts["imu"]["relative_path"]),
        "gnss": paths["clean_input_manifest"].parent / str(artifacts["gnss"]["relative_path"]),
        "raw_doppler": Path(str(aux_artifacts["raw_doppler_provider"]["path"])),
        "go2_roll_pitch": Path(str(aux_artifacts["go2_attitude_prior"]["path"])),
        "go2_horizontal_velocity": Path(str(aux_artifacts["go2_horizontal_velocity_prior"]["path"])),
    }
    for candidate in provider_candidates.values():
        _require_no_symlink_chain(candidate)
    provider_paths = {role: path.resolve(strict=True) for role, path in provider_candidates.items()}
    if any(not is_within(path, provider_root) for path in provider_paths.values()):
        raise Clean3S3Error(
            "provider artifact escaped the exact inherited provider root",
            terminal_status="FAILED_TECHNICAL_PROVIDER_PATH_ESCAPE",
        )
    provider_hashes = {role: sha256_file(path) for role, path in provider_paths.items()}
    declared_provider_hashes = {
        "imu": artifacts.get("imu", {}).get("sha256"),
        "gnss": artifacts.get("gnss", {}).get("sha256"),
        "raw_doppler": aux_artifacts.get("raw_doppler_provider", {}).get("sha256"),
        "go2_roll_pitch": aux_artifacts.get("go2_attitude_prior", {}).get("sha256"),
        "go2_horizontal_velocity": aux_artifacts.get("go2_horizontal_velocity_prior", {}).get("sha256"),
    }
    if (
        provider_hashes != EXPECTED_PROVIDER_HASHES
        or declared_provider_hashes != provider_hashes
        or parity.get("actual_hashes") != provider_hashes
    ):
        raise Clean3S3Error(
            "inherited provider byte identity mismatch",
            terminal_status="FAILED_TECHNICAL_PROVIDER_HASH_MISMATCH",
        )
    raw_source_hashes = clean.get("raw_source_hashes")
    if (
        not isinstance(raw_source_hashes, Mapping)
        or len(raw_source_hashes) != EXPECTED_BY2_RAW_ROWS
        or auxiliary.get("raw_source_hashes") != raw_source_hashes
        or parity.get("raw_source_hashes") != raw_source_hashes
        or parity.get("clean_input_manifest_sha256") != actual_manifest_hashes["clean_input_manifest"]
        or parity.get("auxiliary_manifest_sha256") != actual_manifest_hashes["auxiliary_manifest"]
        or Path(str(auxiliary.get("clean_input_manifest_path", ""))).resolve(strict=True)
        != paths["clean_input_manifest"]
        or auxiliary.get("clean_input_manifest_sha256") != actual_manifest_hashes["clean_input_manifest"]
        or Path(str(parity.get("clean_input_manifest_path", ""))).resolve(strict=True)
        != paths["clean_input_manifest"]
        or Path(str(parity.get("auxiliary_manifest_path", ""))).resolve(strict=True)
        != paths["auxiliary_manifest"]
    ):
        raise Clean3S3Error(
            "provider/raw lineage does not close",
            terminal_status="FAILED_TECHNICAL_PROVIDER_LINEAGE_MISMATCH",
        )
    return {
        "manifest_hashes": actual_manifest_hashes,
        "provider_hashes": provider_hashes,
        "provider_paths": provider_paths,
        "provider_root": provider_root,
        "raw_source_hashes": dict(raw_source_hashes),
    }


def _raw_guard(paths: Mapping[str, Path], expected_provider_raw: Mapping[str, str]) -> dict[str, str]:
    if sha256_file(paths["full_raw_lock"]) != EXPECTED_FULL_RAW_LOCK_SHA256:
        raise Clean3S3Error("full raw lock hash mismatch", terminal_status="FAILED_TECHNICAL_RAW_LOCK_MISMATCH")
    if sha256_file(paths["by2_raw_lock"]) != EXPECTED_BY2_RAW_LOCK_SHA256:
        raise Clean3S3Error("BY2 raw lock hash mismatch", terminal_status="FAILED_TECHNICAL_RAW_LOCK_MISMATCH")
    full = read_hash_lock(paths["full_raw_lock"])
    subset = read_hash_lock(paths["by2_raw_lock"])
    if len(full) != EXPECTED_FULL_RAW_ROWS or len(subset) != EXPECTED_BY2_RAW_ROWS:
        raise Clean3S3Error("raw lock row count mismatch", terminal_status="FAILED_TECHNICAL_RAW_LOCK_MISMATCH")
    full_by2 = {relative: row for relative, row in full.items() if row.get("dataset") == "BY2"}
    if set(full_by2) != set(subset):
        raise Clean3S3Error("full/BY2 raw lock path sets differ", terminal_status="FAILED_TECHNICAL_RAW_LOCK_MISMATCH")
    for relative, row in subset.items():
        if any(row.get(key) != full_by2[relative].get(key) for key in ("size_bytes", "sha256")):
            raise Clean3S3Error("full/BY2 raw lock rows differ", terminal_status="FAILED_TECHNICAL_RAW_LOCK_MISMATCH")
    verified: dict[str, str] = {}
    raw_root = paths["raw_root"]
    for relative, row in subset.items():
        lexical = raw_root / relative
        _require_no_symlink_chain(lexical)
        candidate = lexical.resolve(strict=True)
        if not is_within(candidate, raw_root) or candidate.is_symlink():
            raise Clean3S3Error("raw path escaped or is a symlink", terminal_status="FAILED_TECHNICAL_RAW_PATH")
        if candidate.stat().st_size != int(row["size_bytes"]):
            raise Clean3S3Error("raw size mismatch", terminal_status="FAILED_TECHNICAL_RAW_MUTATION_DETECTED")
        digest = sha256_file(candidate)
        if digest != row["sha256"]:
            raise Clean3S3Error("raw hash mismatch", terminal_status="FAILED_TECHNICAL_RAW_MUTATION_DETECTED")
        verified[relative] = digest
    if verified != dict(expected_provider_raw):
        raise Clean3S3Error("raw audit differs from provider lineage", terminal_status="FAILED_TECHNICAL_RAW_LINEAGE_MISMATCH")
    return verified


def _replace_config(text: str, replacements: Mapping[str, str]) -> str:
    rows: list[str] = []
    seen: set[str] = set()
    for row in text.splitlines():
        key = row.split(":", 1)[0].strip() if ":" in row and not row.lstrip().startswith("#") else ""
        if key in replacements:
            rows.append(f"{key}: {replacements[key]}")
            seen.add(key)
        else:
            rows.append(row)
    rows.extend(f"{key}: {value}" for key, value in replacements.items() if key not in seen)
    rows[0] = "# CLEAN3 S3 one-shot AB0000 parity config; no later-stage routing."
    return "\n".join(rows) + "\n"


def build_s3_ab0000_config(imu: Path, gnss: Path, output: Path) -> str:
    parent = active_runtime_config(
        imu, gnss, output, method_id="strong_dual_yaw_EKF", run_id=RUN_ID,
    )
    return _replace_config(parent, {
        "clean1_formal_mode": "true",
        "clean_final_v23_parity_mode": "true",
        "clean3_s3_ab0000_parity_mode": "true",
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": CASE_ID,
        "data_mode": DATA_MODE,
        "run_id": RUN_ID,
        "run_label": RUN_ID,
        "algorithm_id": METHOD_ID,
        "ablation_variant": METHOD_ID,
        "enable_dual_yaw": "true",
        "enable_receiver_velocity": "true",
        "enable_raw_doppler": "false",
        "enable_source_aware": "false",
        "enable_go2_roll_pitch_prior": "false",
        "enable_go2_horizontal_velocity_prior": "false",
    })


def _run_checked(
    runner: CommandRunner, command: Sequence[str], cwd: Path, timeout: float, reason: str,
    stdout_path: Path, stderr_path: Path, *, raise_on_nonzero: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = runner(tuple(str(item) for item in command), cwd, timeout)
    stdout_path.write_text(completed.stdout or "", encoding="utf-8")
    stderr_path.write_text(completed.stderr or "", encoding="utf-8")
    if raise_on_nonzero and completed.returncode != 0:
        raise _TechnicalFailure(reason, f"command failed ({completed.returncode}): {' '.join(command)}")
    return completed


def _validate_solver_manifest(manifest: Mapping[str, Any], inputs: Mapping[str, Path]) -> dict[str, int]:
    expected = {
        "clean1_formal_mode": True,
        "clean_final_v23_parity_mode": True,
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": CASE_ID,
        "data_mode": DATA_MODE,
        "run_id": RUN_ID,
        "algorithm_id": METHOD_ID,
        "enable_dual_yaw_update": True,
        "enable_receiver_velocity_update": True,
        "enable_raw_doppler": False,
        "source_aware_weighting_enabled": False,
        "go2_attitude_weak_prior_enabled": False,
        "go2_horizontal_velocity_prior_enabled": False,
        "trace_used_online": False,
        "synthetic_data_used": False,
        "semisynthetic_data_used": False,
        "receiver_imu_as_body_imu": False,
        "final_v23_output_solver_input": False,
        "LegSA_output_solver_input": False,
        "per_case_tuning": False,
        "output_only_correction": False,
        "epoch_deleted_for_metric": False,
        "old_runtime_input_count": 0,
        "legacy_provider_input_count": 0,
        "legacy_row_input_count": 0,
        "legacy_aggregate_input_count": 0,
        "cov_health_status": "PASS",
        "cov_health_fail_count": 0,
        "math_port_completed": True,
        "port_role": "clean3_s3_ab0000_parity_solver",
        "phase": STAGE_ID,
        "ablation_variant": METHOD_ID,
        "yaw_scheme_C_enabled": True,
        "performance_claim": False,
        "paper_performance_claim": False,
        "proposed_factor_claim": False,
    }
    mismatches = sorted(key for key, value in expected.items() if manifest.get(key) != value)
    if mismatches:
        raise _TechnicalFailure("SOLVER_MANIFEST_CONTRACT", "solver manifest mismatch: " + ",".join(mismatches))
    actual_paths = manifest.get("actual_solver_input_paths")
    actual_roles = manifest.get("actual_solver_input_roles")
    expected_paths = {
        "propagation_imu": inputs["imu"].resolve(strict=True),
        "gnss_position_receiver_velocity_dual_yaw": inputs["gnss"].resolve(strict=True),
    }
    if not isinstance(actual_paths, Mapping) or not isinstance(actual_roles, Mapping):
        raise _TechnicalFailure("SOLVER_MANIFEST_CONTRACT", "solver input ledger is missing")
    if set(actual_paths) != set(actual_roles) or set(actual_paths) != set(expected_paths):
        raise _TechnicalFailure("SOLVER_MANIFEST_CONTRACT", "solver input role set is not AB0000-only")
    for role, expected_path in expected_paths.items():
        if Path(str(actual_paths[role])).resolve(strict=True) != expected_path:
            raise _TechnicalFailure("SOLVER_MANIFEST_CONTRACT", f"solver input path mismatch: {role}")
    counters = module_counters(manifest)
    if (
        counters["position_update_count"] <= 0
        or counters["receiver_velocity_update_count"] <= 0
        or counters["dual_yaw_attempt_count"] <= 0
        or counters["raw_doppler_update_count"] != 0
        or counters["source_aware_evaluation_count"] != 0
        or counters["source_aware_weight_changed_count"] != 0
        or counters["go2_roll_pitch_update_count"] != 0
        or counters["go2_horizontal_velocity_update_count"] != 0
        or any(counters[key] != 0 for key in ("fgo_count", "qm_count", "qa_count", "contact_fk_count"))
    ):
        raise _TechnicalFailure("SOLVER_COUNTER_CONTRACT", "AB0000 module counters failed closed")
    return counters


_SYSCALL_NAMES = (
    "openat", "openat2", "creat", "execve", "rename", "renameat", "renameat2",
    "unlink", "unlinkat", "mkdir", "mkdirat", "link", "linkat", "symlink", "symlinkat", "truncate",
    "rmdir", "chmod", "fchmodat", "chown", "lchown", "fchownat", "utime", "utimes", "utimensat",
    "mknod", "mknodat",
)
_SYSCALL_RE = re.compile(r"(?:^|\s)(" + "|".join(_SYSCALL_NAMES) + r")\((.*)\)\s+=\s+(.+)$")
_BENIGN_FILE_SYSCALLS = {"access", "faccessat", "faccessat2", "stat", "lstat", "newfstatat", "statx",
                         "readlink", "readlinkat", "getcwd"}


def _split_syscall_args(value: str) -> list[str]:
    rows, start, depth, quoted, escaped = [], 0, 0, False, False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
        elif char == "\\" and quoted:
            escaped = True
        elif char == '"':
            quoted = not quoted
        elif not quoted and char in "{[":
            depth += 1
        elif not quoted and char in "}]":
            depth -= 1
        elif not quoted and depth == 0 and char == ",":
            rows.append(value[start:index].strip())
            start = index + 1
    rows.append(value[start:].strip())
    return rows


def _decode_c_path(token: str) -> str:
    try:
        value = ast.literal_eval(token)
    except (SyntaxError, ValueError) as exc:
        raise _TechnicalFailure("SYSCALL_TRACE_PARSE", "invalid C pathname string") from exc
    if not isinstance(value, str):
        raise _TechnicalFailure("SYSCALL_TRACE_PARSE", "pathname is not a string")
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def _dirfd_base(token: str, cwd: Path) -> Path:
    annotation = re.search(r"<(/[^>]*)>", token)
    if annotation:
        return Path(annotation.group(1))
    if token.strip() == "AT_FDCWD":
        return cwd
    raise _TechnicalFailure("SYSCALL_UNRESOLVED_DIRFD", "relative pathname has unresolved dirfd")


def _path_arg(args: Sequence[str], index: int, cwd: Path, dirfd_index: int | None = None) -> Path:
    if index >= len(args) or not args[index].startswith('"'):
        raise _TechnicalFailure("SYSCALL_TRACE_PARSE", "missing pathname argument")
    candidate = Path(_decode_c_path(args[index]))
    if not candidate.is_absolute():
        candidate = (_dirfd_base(args[dirfd_index], cwd) if dirfd_index is not None else cwd) / candidate
    return candidate.resolve(strict=False)


def _syscall_events(trace: Path, cwd: Path) -> list[dict[str, Any]]:
    events = []
    for line in trace.read_text(encoding="utf-8", errors="replace").splitlines():
        if any(name + "(" in line or f"<... {name} resumed>" in line for name in _SYSCALL_NAMES) and (
            "<unfinished ...>" in line or " resumed>" in line or "..." in line and " = " not in line
        ):
            raise _TechnicalFailure("SYSCALL_TRACE_INCOMPLETE", "unfinished/resumed/truncated syscall row")
        match = _SYSCALL_RE.search(line)
        if not match:
            generic = re.search(r"(?:^|\s)([a-z][a-z0-9_]*)\(.*\)\s+=", line)
            if generic and generic.group(1) not in _BENIGN_FILE_SYSCALLS:
                raise _TechnicalFailure("SYSCALL_UNSUPPORTED", "unsupported syscall in %file trace")
            continue
        syscall, raw_args, result = match.groups()
        args = _split_syscall_args(raw_args)
        path_specs = {
            "openat": ((1, 0),), "openat2": ((1, 0),), "creat": ((0, None),),
            "execve": ((0, None),), "rename": ((0, None), (1, None)),
            "renameat": ((1, 0), (3, 2)), "renameat2": ((1, 0), (3, 2)),
            "unlink": ((0, None),), "unlinkat": ((1, 0),), "mkdir": ((0, None),),
            "mkdirat": ((1, 0),), "link": ((0, None), (1, None)),
            "linkat": ((1, 0), (3, 2)), "symlink": ((1, None),),
            "symlinkat": ((2, 1),), "truncate": ((0, None),),
            "rmdir": ((0, None),), "chmod": ((0, None),), "fchmodat": ((1, 0),),
            "chown": ((0, None),), "lchown": ((0, None),), "fchownat": ((1, 0),),
            "utime": ((0, None),), "utimes": ((0, None),), "utimensat": ((1, 0),),
            "mknod": ((0, None),), "mknodat": ((1, 0),),
        }
        paths = [_path_arg(args, index, cwd, dirfd) for index, dirfd in path_specs[syscall]]
        flags = ""
        if syscall == "openat" and len(args) > 2:
            flags = args[2]
        elif syscall == "openat2" and len(args) > 2:
            flag_match = re.search(r"(?:^|[{,]\s*)flags=([^,}]+)", args[2])
            flags = flag_match.group(1).strip() if flag_match else ""
        if syscall in ("openat", "openat2") and not any(
            flag in flags for flag in ("O_RDONLY", "O_WRONLY", "O_RDWR", "O_PATH")
        ):
            raise _TechnicalFailure("SYSCALL_OPEN_FLAGS", "open flags are not symbolically resolved")
        events.append({"syscall": syscall, "arguments": args, "flags": flags, "paths": paths,
                       "succeeded": not result.lstrip().startswith("-1")})
    return events


def _audit_solver_syscalls(
    trace: Path, *, repo: Path, clean_root: Path, raw_root: Path, stage_root: Path,
    provider_root: Path, expected_inputs: Mapping[str, Path], immutable_paths: Sequence[Path],
    solver_binary: Path,
) -> dict[str, Any]:
    events = _syscall_events(trace, repo)
    read_attempts = [event for event in events if event["syscall"] in ("openat", "openat2")
                     and ("O_RDONLY" in event["flags"] or "O_RDWR" in event["flags"])]
    opened_attempted = [event["paths"][0] for event in read_attempts]
    opened = [event["paths"][0] for event in read_attempts if event["succeeded"]]
    expected = {role: path.resolve(strict=True) for role, path in expected_inputs.items()}
    counts = {role: sum(path == expected_path for path in opened) for role, expected_path in expected.items()}
    unexpected_provider = sorted(
        str(path) for path in set(opened_attempted)
        if is_within(path, provider_root) and path not in set(expected.values())
    )
    unexpected_clean = sorted(
        str(path) for path in set(opened_attempted)
        if is_within(path, clean_root) and not is_within(path, stage_root)
        and path not in set(expected.values())
    )
    raw_opens = sorted(str(path) for path in set(opened_attempted) if is_within(path, raw_root))
    legacy_opens = sorted(str(path) for path in set(opened_attempted) if legacy_reason(path) is not None)
    trace_path = (raw_root / BY2_TRACE_RELATIVE_PATH).resolve(strict=True)
    trace_count = sum(path == trace_path for path in opened_attempted)
    immutable = {path.resolve(strict=False) for path in immutable_paths}
    writable_immutable = []
    outside_mutation = []
    execs = []
    write_flags = ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND", "O_TMPFILE")
    mutation_syscalls = {"creat", "rename", "renameat", "renameat2", "unlink", "unlinkat", "mkdir",
                         "mkdirat", "link", "linkat", "symlink", "symlinkat", "truncate", "rmdir",
                         "chmod", "fchmodat", "chown", "lchown", "fchownat", "utime", "utimes",
                         "utimensat", "mknod", "mknodat"}
    allowed_writes = {stage_root / "02_AB0000_RUNTIME" / name for name in (
        "LegSA_PORT_NAV.nav", "LegSA_PORT_STD.csv", "EVAL_NAV.csv", "KF_GINS_Navresult.nav",
        "KF_GINS_STD.txt", "KF_GINS_IMU_ERR.txt", "RUN_MANIFEST.json",
    )}
    for event in events:
        syscall, event_paths = event["syscall"], event["paths"]
        if syscall == "execve":
            execs.extend(event_paths[:1])
        if syscall in ("openat", "openat2", "creat") and event_paths:
            target = event_paths[0]
            writable = syscall == "creat" or any(flag in event["flags"] for flag in write_flags)
            if writable and target in immutable:
                writable_immutable.append(str(target))
            if writable and target not in allowed_writes:
                outside_mutation.append(str(target))
        if syscall in mutation_syscalls:
            for target in event_paths:
                if target in immutable:
                    writable_immutable.append(str(target))
                if target not in allowed_writes:
                    outside_mutation.append(str(target))
    exact_exec = execs == [solver_binary.resolve(strict=True)]
    passed = (
        all(count > 0 for count in counts.values()) and not unexpected_provider
        and not unexpected_clean and not raw_opens and not legacy_opens and trace_count == 0
        and not writable_immutable and not outside_mutation and exact_exec
    )
    ledger = {
        "schema_version": "paper_rebuild.clean3_s3_solver_read_ledger.v1",
        "actual_solver_input_open_counts": counts,
        "unexpected_provider_opens": unexpected_provider,
        "unexpected_clean_root_opens": unexpected_clean,
        "raw_root_opens": raw_opens,
        "legacy_opens": legacy_opens,
        "reference_fixposition_trace_open_count": trace_count,
        "writable_immutable_targets": sorted(set(writable_immutable)),
        "outside_stage_mutation_targets": sorted(set(outside_mutation)),
        "exec_paths": [str(path) for path in execs],
        "exact_solver_only_exec": exact_exec,
        "evaluator_invoked": False,
        "performance_metrics_read": False,
        "passed": passed,
    }
    if not passed:
        raise _TechnicalFailure("SOLVER_FILE_OPEN_AUDIT", "solver file-open audit failed")
    return ledger


def _integrity_snapshot(ledger: Mapping[str, Path]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for role, path in ledger.items():
        try:
            result[role] = {"path": str(path), "size_bytes": path.stat().st_size,
                            "sha256": sha256_file(path), "missing": False}
        except OSError as exc:
            result[role] = {"path": str(path), "missing": True, "error": str(exc)}
    return result


def _integrity_changes(before: Mapping[str, Any], after: Mapping[str, Any]) -> list[str]:
    return sorted(role for role in before if before[role] != after.get(role))


def _stream_byte_equal(left: Path, right: Path, chunk_size: int = 1024 * 1024) -> bool:
    if left.stat().st_size != right.stat().st_size:
        return False
    with left.open("rb") as a, right.open("rb") as b:
        while True:
            left_chunk, right_chunk = a.read(chunk_size), b.read(chunk_size)
            if left_chunk != right_chunk:
                return False
            if not left_chunk:
                return True


def _reject_provider_copies(runtime: Path, provider_hashes: Mapping[str, str]) -> None:
    forbidden = set(provider_hashes.values())
    copies = [str(path) for path in runtime.rglob("*") if path.is_file() and sha256_file(path) in forbidden]
    if copies:
        raise _TechnicalFailure("PROVIDER_COPY_DETECTED", "runtime contains provider-byte copies: " + ",".join(copies))


def _terminal_report_path(stage: Path) -> Path:
    return stage / "04_REPORT" / "CLEAN3_S3_AB0000_PARITY_REPORT.json"


def _audit_preflight_trace(
    trace: Path, *, cwd: Path, harness_binary: Path, accepting_config: Path,
    negative_config: Path, sentinel_root: Path, artifact_hashes: Mapping[str, str],
) -> dict[str, Any]:
    events = _syscall_events(trace, cwd)
    exec_paths = [event["paths"][0] for event in events if event["syscall"] == "execve"]
    read_events = [event for event in events if event["syscall"] in ("openat", "openat2")
                   and any(flag in event["flags"] for flag in ("O_RDONLY", "O_RDWR"))]
    read_attempts = [event["paths"][0] for event in read_events]
    write_flags = ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND", "O_TMPFILE")
    mutation_calls = {"creat", "rename", "renameat", "renameat2", "unlink", "unlinkat", "mkdir",
                      "mkdirat", "link", "linkat", "symlink", "symlinkat", "truncate", "rmdir",
                      "chmod", "fchmodat", "chown", "lchown", "fchownat", "utime", "utimes",
                      "utimensat", "mknod", "mknodat"}
    writes: list[Path] = []
    for event in events:
        if (event["syscall"] in ("openat", "openat2") and
                any(flag in event["flags"] for flag in write_flags)):
            writes.extend(event["paths"][:1])
        elif event["syscall"] in mutation_calls:
            writes.extend(event["paths"])
    raw = sorted({str(path) for path in read_attempts if is_within(path, sentinel_root / "raw")})
    provider = sorted({str(path) for path in read_attempts if is_within(path, sentinel_root / "provider")})
    reference = sorted({str(path) for path in read_attempts if is_within(path, sentinel_root / "reference")})
    legacy = sorted({str(path) for path in read_attempts if is_within(path, sentinel_root / "legacy")
                     or legacy_reason(path) is not None})
    accepting = accepting_config.resolve(strict=True)
    forbidden = set(raw + provider + reference + legacy)
    unexpected_reads = sorted({str(path) for path in read_attempts
                               if str(path) not in forbidden and path != accepting
                               and (is_within(path, sentinel_root.parent) or is_within(path, cwd))})
    classifications = {}
    for path in read_attempts:
        rendered = str(path)
        classifications[rendered] = (
            "accepting_config" if path == accepting else
            "forbidden_raw" if rendered in raw else
            "forbidden_provider" if rendered in provider else
            "forbidden_reference_trace" if rendered in reference else
            "forbidden_legacy" if rendered in legacy else
            "unexpected_scoped_read" if rendered in unexpected_reads else "system_dependency")
    config_open_count = sum(path == accepting and event["succeeded"]
                            for path, event in zip(read_attempts, read_events))
    binary = harness_binary.resolve(strict=True)
    exact_subject = exec_paths == [binary]
    ledger = {
        "schema_version": PREFLIGHT_LEDGER_SCHEMA,
        "trace_subject": "ZERO_DATA_LOADER_HARNESS",
        "exec_paths": [str(path) for path in exec_paths],
        "expected_exec_path": str(binary), "exact_exec_subject": exact_subject,
        "read_attempt_paths": [str(path) for path in read_attempts],
        "write_attempt_paths": [str(path) for path in writes],
        "accepting_config_open_count": config_open_count,
        "negative_config_open_count": sum(path == negative_config.resolve(strict=True) for path in read_attempts),
        "raw_paths": raw, "provider_paths": provider, "reference_trace_paths": reference,
        "legacy_paths": legacy, "unexpected_write_paths": sorted({str(path) for path in writes}),
        "unexpected_read_paths": unexpected_reads, "path_classifications": classifications,
        "classification_roots": {"raw": str(sentinel_root / "raw"),
            "provider": str(sentinel_root / "provider"), "reference": str(sentinel_root / "reference"),
            "legacy": str(sentinel_root / "legacy")},
        "raw_open_count": len(raw), "provider_open_count": len(provider),
        "reference_trace_open_count": len(reference), "legacy_open_count": len(legacy),
        "unexpected_write_count": len(set(writes)),
        "unexpected_read_count": len(unexpected_reads),
        "bound_artifact_sha256": dict(artifact_hashes),
        "formal_solver_executed": False,
    }
    ledger["passed"] = (exact_subject and config_open_count == 1 and
                         ledger["negative_config_open_count"] == 0 and
                         all(ledger[key] == 0 for key in ("raw_open_count", "provider_open_count",
                             "reference_trace_open_count", "legacy_open_count", "unexpected_write_count")))
    ledger["passed"] = ledger["passed"] and ledger["unexpected_read_count"] == 0
    if not ledger["passed"]:
        raise _TechnicalFailure("PREFLIGHT_FILE_OPEN_AUDIT", "zero-data loader trace audit failed")
    return ledger


@contextlib.contextmanager
def _preflight_namespace_lock(clean_root: Path):
    clean = clean_root.resolve(strict=True)
    if clean != clean_root.absolute() or clean.is_symlink() or not clean.is_dir():
        raise Clean3S3Error("unsafe clean root", terminal_status="FAILED_TECHNICAL_PREFLIGHT_NAMESPACE")
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fds: list[int] = []
    try:
        current = os.open(clean, directory_flags); fds.append(current)
        for component in ("00_GOVERNANCE_PREFLIGHT", STAGE_ID):
            try:
                os.mkdir(component, mode=0o755, dir_fd=current)
            except FileExistsError:
                pass
            child = os.open(component, directory_flags, dir_fd=current)
            if not stat.S_ISDIR(os.fstat(child).st_mode):
                raise OSError("namespace component is not a directory")
            fds.append(child); current = child
        lock_fd = os.open(".namespace.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600, dir_fd=current)
        fds.append(lock_fd)
        lock_stat = os.fstat(lock_fd)
        if not stat.S_ISREG(lock_stat.st_mode) or lock_stat.st_nlink != 1:
            raise OSError("namespace lock is not a single-linked regular file")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        namespace = clean / PREFLIGHT_RELATIVE
        path_stat = os.stat(namespace, follow_symlinks=False)
        if (path_stat.st_dev, path_stat.st_ino) != (os.fstat(current).st_dev, os.fstat(current).st_ino):
            raise OSError("namespace parent identity changed")
        yield namespace
        path_stat = os.stat(namespace, follow_symlinks=False)
        if (path_stat.st_dev, path_stat.st_ino) != (os.fstat(current).st_dev, os.fstat(current).st_ino):
            raise OSError("namespace parent identity changed")
    except OSError as exc:
        raise Clean3S3Error("unsafe preflight namespace",
                            terminal_status="FAILED_TECHNICAL_PREFLIGHT_NAMESPACE") from exc
    finally:
        for fd in reversed(fds):
            try: os.close(fd)
            except OSError: pass


def _scan_preflight_attempts(namespace: Path) -> list[Path]:
    attempts: list[tuple[int, Path]] = []
    for entry in namespace.iterdir():
        if entry.name == ".namespace.lock":
            if entry.is_symlink() or not entry.is_file():
                raise Clean3S3Error("unsafe namespace lock", terminal_status="FAILED_TECHNICAL_PREFLIGHT_NAMESPACE")
            continue
        match = re.fullmatch(r"ATTEMPT_([0-9]{6})", entry.name)
        if not match or entry.is_symlink() or not entry.is_dir():
            raise Clean3S3Error("unexpected preflight namespace entry",
                                terminal_status="FAILED_TECHNICAL_PREFLIGHT_NAMESPACE")
        ordinal = int(match.group(1), 10)
        if ordinal < 1 or entry.name != f"ATTEMPT_{ordinal:06d}":
            raise Clean3S3Error("noncanonical preflight ordinal",
                                terminal_status="FAILED_TECHNICAL_PREFLIGHT_NAMESPACE")
        attempts.append((ordinal, entry))
    attempts.sort()
    if [ordinal for ordinal, _ in attempts] != list(range(1, len(attempts) + 1)):
        raise Clean3S3Error("preflight attempt ordinals are not contiguous",
                            terminal_status="FAILED_TECHNICAL_PREFLIGHT_NAMESPACE")
    return [path for _, path in attempts]


def _attempt_terminal(attempt: Path) -> dict[str, Any] | None:
    path = attempt / "TERMINAL.json"
    if not path.exists():
        return None
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
        raise Clean3S3Error("unsafe preflight terminal", terminal_status="FAILED_TECHNICAL_PREFLIGHT_NAMESPACE")
    terminal = _load_json(path)
    if (terminal.get("schema_version") != PREFLIGHT_TERMINAL_SCHEMA or
            terminal.get("attempt_id") != attempt.name or
            terminal.get("attempt_ordinal") != int(attempt.name[-6:]) or
            terminal.get("terminal_status") not in ("PREFLIGHT_OK", "PREFLIGHT_FAILED")):
        raise Clean3S3Error("invalid preflight terminal", terminal_status="FAILED_TECHNICAL_PREFLIGHT_CONTRACT")
    claim = attempt / "ATTEMPT_CLAIM.json"
    report = attempt / "04_REPORT" / ("CLEAN3R3_GOVERNANCE_PREFLIGHT_REPORT.json"
        if terminal["terminal_status"] == "PREFLIGHT_OK" else "CLEAN3R3_GOVERNANCE_PREFLIGHT_FAILURE.json")
    if (claim.is_symlink() or report.is_symlink() or not claim.is_file() or not report.is_file()
            or not stat.S_ISREG(claim.lstat().st_mode) or not stat.S_ISREG(report.lstat().st_mode)
            or terminal.get("claim_sha256") != sha256_file(claim)
            or terminal.get("report_sha256") != sha256_file(report)):
        raise Clean3S3Error("preflight terminal hash mismatch",
                            terminal_status="FAILED_TECHNICAL_PREFLIGHT_CONTRACT")
    ordinal = int(attempt.name[-6:])
    predecessor = f"ATTEMPT_{ordinal - 1:06d}" if ordinal > 1 else None
    claim_payload = _load_json(claim)
    expected_claim = {"schema_version": PREFLIGHT_CLAIM_SCHEMA, "attempt_id": attempt.name,
        "attempt_ordinal": ordinal, "execution_head": claim_payload.get("execution_head"),
        "stage_id": STAGE_ID, "predecessor_attempt_id": predecessor,
        "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER", "formal_solver_executed": False,
        "claimed_before_work": True}
    if set(claim_payload) != set(expected_claim) or claim_payload != expected_claim:
        raise Clean3S3Error("invalid preflight claim", terminal_status="FAILED_TECHNICAL_PREFLIGHT_CONTRACT")
    if terminal["terminal_status"] == "PREFLIGHT_FAILED":
        failure = _load_json(report)
        expected_failure = {"schema_version": PREFLIGHT_FAILURE_SCHEMA, "stage_id": STAGE_ID,
            "attempt_id": attempt.name, "attempt_ordinal": ordinal,
            "execution_head": claim_payload["execution_head"], "predecessor_attempt_id": predecessor,
            "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER", "formal_solver_executed": False,
            "terminal_status": "PREFLIGHT_FAILED", "passed": False,
            "failure_reason": failure.get("failure_reason"), "claim_sha256": sha256_file(claim)}
        if (not isinstance(failure.get("failure_reason"), str) or not failure["failure_reason"] or
                set(failure) != set(expected_failure) or failure != expected_failure):
            raise Clean3S3Error("invalid preflight failure report",
                                terminal_status="FAILED_TECHNICAL_PREFLIGHT_CONTRACT")
    return terminal


def _guard_preflight_attempt(root: Path, git_identity: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute and verify the sealed zero-data loader proof from its raw trace."""

    expected_top = {"ATTEMPT_CLAIM.json", "TERMINAL.json", "01_BUILD", "02_HARNESS", "03_SEAL", "04_REPORT"}
    if set(path.name for path in root.iterdir()) != expected_top:
        raise Clean3S3Error("unexpected preflight attempt artifact",
                            terminal_status="FAILED_TECHNICAL_PREFLIGHT_NAMESPACE")
    for name in ("01_BUILD", "02_HARNESS", "03_SEAL", "04_REPORT"):
        path = root / name
        if path.is_symlink() or not path.is_dir():
            raise Clean3S3Error("unsafe preflight attempt directory",
                                terminal_status="FAILED_TECHNICAL_PREFLIGHT_NAMESPACE")

    report_path = root / "04_REPORT/CLEAN3R3_GOVERNANCE_PREFLIGHT_REPORT.json"
    ledger_path = root / "03_SEAL/ZERO_DATA_LOADER_READ_LEDGER.json"
    seal_path = root / "03_SEAL/CLEAN3R3_GOVERNANCE_PREFLIGHT_SEAL.json"
    trace_path = root / "02_HARNESS/logs/SOLVER_FILE_OPEN_TRACE.raw"
    for path in (report_path, ledger_path, seal_path, trace_path):
        if not path.is_file() or path.is_symlink():
            raise Clean3S3Error("sealed governance preflight is missing",
                                terminal_status="FAILED_TECHNICAL_PREFLIGHT_MISSING")
    report, ledger, seal = _load_json(report_path), _load_json(ledger_path), _load_json(seal_path)
    required = {
        "schema_version": PREFLIGHT_REPORT_SCHEMA,
        "terminal_status": "PREFLIGHT_OK", "stage_id": STAGE_ID,
        "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER",
        "trace_subject": "ZERO_DATA_LOADER_HARNESS", "formal_solver_executed": False,
        "raw_open_count": 0, "provider_open_count": 0, "reference_trace_open_count": 0,
        "legacy_open_count": 0, "unexpected_write_count": 0, "unexpected_read_count": 0,
        "g_c2": "REPORTING_ONLY", "g_c3": "HARD_UNCHANGED",
        "execution_head": git_identity["execution_head"],
    }
    if any(report.get(key) != value for key, value in required.items()):
        raise Clean3S3Error("governance preflight contract mismatch",
                            terminal_status="FAILED_TECHNICAL_PREFLIGHT_CONTRACT")
    count_fields = ("raw_open_count", "provider_open_count", "reference_trace_open_count",
                    "legacy_open_count", "unexpected_write_count", "unexpected_read_count")
    ledger_required = {
        "schema_version": PREFLIGHT_LEDGER_SCHEMA, "trace_subject": "ZERO_DATA_LOADER_HARNESS",
        "exact_exec_subject": True, "accepting_config_open_count": 1,
        "negative_config_open_count": 0, "formal_solver_executed": False, "passed": True,
    }
    list_fields = ("exec_paths", "read_attempt_paths", "write_attempt_paths", "raw_paths",
                   "provider_paths", "reference_trace_paths", "legacy_paths", "unexpected_write_paths",
                   "unexpected_read_paths")
    artifacts = ("harness_binary", "harness_source", "accepting_config", "negative_config")
    bound = ledger.get("bound_artifact_sha256")
    artifact_paths = {
        "harness_binary": root / "01_BUILD/zero_data_loader",
        "harness_source": root / "01_BUILD/zero_data_loader.cpp",
        "accepting_config": root / "02_HARNESS/configs/CLEAN3R3_ZERO_DATA.yaml",
        "negative_config": root / "02_HARNESS/configs/CANONICAL_T8_REJECT.yaml",
    }
    actual_artifacts = ({key: sha256_file(path) for key, path in artifact_paths.items()}
                        if all(path.is_file() and not path.is_symlink() for path in artifact_paths.values()) else {})
    expected_binary = artifact_paths["harness_binary"].resolve(strict=False)
    try:
        recomputed = _audit_preflight_trace(
            trace_path, cwd=root, harness_binary=artifact_paths["harness_binary"],
            accepting_config=artifact_paths["accepting_config"],
            negative_config=artifact_paths["negative_config"],
            sentinel_root=root / "NONEXISTENT_DO_NOT_OPEN", artifact_hashes=actual_artifacts,
        )
    except (OSError, _TechnicalFailure) as exc:
        raise Clean3S3Error("raw governance trace cannot reproduce the sealed ledger",
                            terminal_status="FAILED_TECHNICAL_PREFLIGHT_TRACE_REPLAY") from exc
    derived_report_fields = set(PREFLIGHT_LEDGER_FIELDS) - {"schema_version", "passed"}
    consistent = (
        set(ledger) == PREFLIGHT_LEDGER_FIELDS
        and ledger.get("schema_version") == PREFLIGHT_LEDGER_SCHEMA
        and all(ledger.get(key) == value for key, value in ledger_required.items())
        and all(isinstance(ledger.get(key), list) for key in list_fields)
        and isinstance(bound, Mapping) and set(bound) == set(artifacts)
        and all(isinstance(bound[key], str) and len(bound[key]) == 64 for key in artifacts)
        and dict(bound) == actual_artifacts
        and ledger == recomputed
        and ledger.get("expected_exec_path") == str(expected_binary)
        and ledger.get("exec_paths") == [str(expected_binary)]
        and all(ledger.get(key) == report.get(key) == 0 for key in count_fields)
        and len(ledger["exec_paths"]) == 1
        and ledger["exec_paths"][0] == ledger.get("expected_exec_path")
        and len(ledger["raw_paths"]) == ledger["raw_open_count"]
        and len(ledger["provider_paths"]) == ledger["provider_open_count"]
        and len(ledger["reference_trace_paths"]) == ledger["reference_trace_open_count"]
        and len(ledger["legacy_paths"]) == ledger["legacy_open_count"]
        and len(ledger["unexpected_write_paths"]) == ledger["unexpected_write_count"]
        and len(ledger["unexpected_read_paths"]) == ledger["unexpected_read_count"]
        and isinstance(ledger.get("path_classifications"), Mapping)
        and set(ledger["path_classifications"]) == set(ledger["read_attempt_paths"])
        and isinstance(ledger.get("classification_roots"), Mapping)
        and set(ledger["classification_roots"]) == {"raw", "provider", "reference", "legacy"}
        and report.get("bound_artifact_sha256") == dict(bound)
        and all(report.get(key) == recomputed.get(key) for key in derived_report_fields)
    )
    hashes = seal.get("sha256")
    expected = {
        "report": sha256_file(report_path), "ledger": sha256_file(ledger_path),
        "raw_trace": sha256_file(trace_path),
    }
    if (not consistent or seal.get("schema_version") != PREFLIGHT_SEAL_SCHEMA or
            seal.get("sealed") is not True or hashes != expected or
            seal.get("bound_artifact_sha256") != dict(bound)):
        raise Clean3S3Error("governance preflight seal mismatch",
                            terminal_status="FAILED_TECHNICAL_PREFLIGHT_SEAL")
    claim_path = root / "ATTEMPT_CLAIM.json"
    if not claim_path.is_file() or claim_path.is_symlink():
        raise Clean3S3Error("preflight claim missing", terminal_status="FAILED_TECHNICAL_PREFLIGHT_CONTRACT")
    claim = _load_json(claim_path)
    ordinal = int(root.name[-6:])
    if (claim.get("schema_version") != PREFLIGHT_CLAIM_SCHEMA or claim.get("attempt_id") != root.name or
            claim.get("attempt_ordinal") != ordinal or claim.get("execution_head") != git_identity["execution_head"]):
        raise Clean3S3Error("preflight claim mismatch", terminal_status="FAILED_TECHNICAL_PREFLIGHT_CONTRACT")
    return {"root": str(root), "attempt_id": root.name, "attempt_ordinal": ordinal,
            "claim_sha256": sha256_file(claim_path), "terminal_sha256": sha256_file(root / "TERMINAL.json"),
            "report_sha256": expected["report"], "seal_sha256": sha256_file(seal_path),
            "trace_sha256": expected["raw_trace"], "proof_kind": required["proof_kind"]}


def _select_governance_preflight_locked(namespace: Path, git_identity: Mapping[str, Any]) -> dict[str, Any]:
    attempts = _scan_preflight_attempts(namespace)
    if not attempts:
        raise Clean3S3Error("no governance preflight attempt", terminal_status="FAILED_TECHNICAL_PREFLIGHT_MISSING")
    latest = attempts[-1]
    terminal = _attempt_terminal(latest)
    if terminal is None:
        raise Clean3S3Error("latest governance preflight is incomplete",
                            terminal_status="FAILED_TECHNICAL_PREFLIGHT_INCOMPLETE")
    if terminal["terminal_status"] != "PREFLIGHT_OK":
        raise Clean3S3Error("latest governance preflight failed",
                            terminal_status="FAILED_TECHNICAL_PREFLIGHT_LATEST_FAILED")
    return _guard_preflight_attempt(latest, git_identity)


def _governance_preflight_guard(clean_root: Path, git_identity: Mapping[str, Any]) -> dict[str, Any]:
    """Select and replay the latest immutable completed governance attempt."""
    with _preflight_namespace_lock(clean_root) as namespace:
        return _select_governance_preflight_locked(namespace, git_identity)


def _locked_preflight(function):
    def wrapper(repo_root: Path, clean_root: Path, **kwargs):
        repo, clean = repo_root.resolve(strict=True), clean_root.resolve(strict=True)
        git_identity = _guard_git(repo)
        with _preflight_namespace_lock(clean) as namespace:
            formal_stage = clean / "stages" / STAGE_ID
            if formal_stage.exists() or formal_stage.is_symlink():
                raise Clean3S3Error("formal stage already claimed; preflight is closed",
                                    terminal_status="FAILED_TECHNICAL_PREFLIGHT_AFTER_FORMAL_CLAIM")
            attempts = _scan_preflight_attempts(namespace)
            if attempts and _attempt_terminal(attempts[-1]) is None:
                raise Clean3S3Error("latest preflight is incomplete",
                                    terminal_status="FAILED_TECHNICAL_PREFLIGHT_INCOMPLETE")
            ordinal = len(attempts) + 1
            root = namespace / f"ATTEMPT_{ordinal:06d}"
            root.mkdir()
            for relative in ("01_BUILD", "02_HARNESS", "03_SEAL", "04_REPORT"):
                (root / relative).mkdir()
            claim = {"schema_version": PREFLIGHT_CLAIM_SCHEMA, "attempt_id": root.name,
                     "attempt_ordinal": ordinal, "execution_head": git_identity["execution_head"],
                     "stage_id": STAGE_ID, "predecessor_attempt_id": attempts[-1].name if attempts else None,
                     "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER", "formal_solver_executed": False,
                     "claimed_before_work": True}
            claim_path = write_json_atomic(root / "ATTEMPT_CLAIM.json", claim)
            try:
                report = function(repo, clean, _attempt_root=root, _git_identity=git_identity, **kwargs)
            except Exception as exc:
                failure = {"schema_version": PREFLIGHT_FAILURE_SCHEMA, "stage_id": STAGE_ID,
                           "attempt_id": root.name, "attempt_ordinal": ordinal,
                           "execution_head": git_identity["execution_head"],
                           "predecessor_attempt_id": attempts[-1].name if attempts else None,
                           "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER", "formal_solver_executed": False,
                           "terminal_status": "PREFLIGHT_FAILED", "passed": False,
                           "failure_reason": str(exc), "claim_sha256": sha256_file(claim_path)}
                failure_path = write_json_atomic(root / "04_REPORT/CLEAN3R3_GOVERNANCE_PREFLIGHT_FAILURE.json", failure)
                write_json_atomic(root / "TERMINAL.json", {
                    "schema_version": PREFLIGHT_TERMINAL_SCHEMA, "attempt_id": root.name,
                    "attempt_ordinal": ordinal, "terminal_status": "PREFLIGHT_FAILED",
                    "report_sha256": sha256_file(failure_path), "claim_sha256": sha256_file(claim_path)})
                raise
            report_path = root / "04_REPORT/CLEAN3R3_GOVERNANCE_PREFLIGHT_REPORT.json"
            write_json_atomic(root / "TERMINAL.json", {
                "schema_version": PREFLIGHT_TERMINAL_SCHEMA, "attempt_id": root.name,
                "attempt_ordinal": ordinal, "terminal_status": "PREFLIGHT_OK",
                "report_sha256": sha256_file(report_path), "claim_sha256": sha256_file(claim_path)})
            return report
    return wrapper


@_locked_preflight
def run_governance_preflight(
    repo_root: Path, clean_root: Path, *, timeout_seconds: int = 120,
    command_runner: CommandRunner = _default_command_runner,
    which: Callable[[str], str | None] = shutil.which,
    _attempt_root: Path | None = None, _git_identity: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build and trace only a zero-data loader harness; never invoke the solver."""

    repo, clean = repo_root, clean_root
    assert _attempt_root is not None and _git_identity is not None
    git_identity = dict(_git_identity)
    strace = which("strace")
    if not strace:
        raise Clean3S3Error("strace is required for governance preflight",
                            terminal_status="FAILED_TECHNICAL_STRACE_UNAVAILABLE")
    root = _attempt_root
    build, harness_root, seal_root, report_root = (
        root / "01_BUILD", root / "02_HARNESS", root / "03_SEAL", root / "04_REPORT")
    (harness_root / "configs").mkdir(); (harness_root / "logs").mkdir()
    runtime_source = (repo / RUNTIME_COUNTER_PATH).read_text(encoding="utf-8")
    formal = runtime_source.split("if (options.clean1_formal_mode)", 1)[1].split("} else", 1)[0]
    if "options.port_role" in formal:
        raise Clean3S3Error("T9 static formal port_role assignment remains",
                            terminal_status="FAILED_TECHNICAL_T9_STATIC_ROLE_ASSIGNMENT")
    source = build / "zero_data_loader.cpp"
    source.write_text(
        '#include <exception>\n#include <iostream>\n#include "legsa_v23_port_core/config/port_config_loader.hpp"\n'
        'int main(int argc,char** argv){try{auto o=legsa_v23_port_core::PortConfigLoader::loadYamlLike(argv[1]);'
        'std::cout<<o.stage_id<<"\\n"<<o.port_role<<"\\n"<<o.phase<<"\\n"<<o.run_label;return 0;}'
        'catch(const std::exception& e){std::cerr<<e.what();return 2;}}\n', encoding="utf-8")
    binary = build / "zero_data_loader"
    compile_command = (
        "g++", "-std=c++17", "-I", str(repo / "cpp/legsa_v23_port_core/include"),
        str(repo / "cpp/legsa_v23_port_core/src/common/types.cpp"),
        str(repo / "cpp/legsa_v23_port_core/src/source_aware/source_aware_policy.cpp"),
        str(repo / LOADER_EXTENSION_PATH), str(source), "-o", str(binary),
    )
    _run_checked(command_runner, compile_command, repo, timeout_seconds, "PREFLIGHT_COMPILE",
                 harness_root / "logs/compile_stdout.txt", harness_root / "logs/compile_stderr.txt")
    sentinel = root / "NONEXISTENT_DO_NOT_OPEN"
    config = harness_root / "configs/CLEAN3R3_ZERO_DATA.yaml"
    config.write_text(build_s3_ab0000_config(sentinel / "provider/imu", sentinel / "provider/gnss",
                                             sentinel / "output"),
                      encoding="utf-8")
    canonical = harness_root / "configs/CANONICAL_T8_REJECT.yaml"
    canonical.write_text(_replace_config(config.read_text(encoding="utf-8"), {
        "stage_id": "CLEAN2R2B_BY2_CANONICAL_541_CASE_MATRIX",
        "protocol_id": "CANONICAL541_BY2_CONTROLLED_DEGRADATION", "case_id": "C00_clean_normal",
    }), encoding="utf-8")
    artifact_hashes = {
        "harness_binary": sha256_file(binary), "harness_source": sha256_file(source),
        "accepting_config": sha256_file(config), "negative_config": sha256_file(canonical),
    }
    trace = harness_root / "logs/SOLVER_FILE_OPEN_TRACE.raw"
    traced = _run_checked(command_runner,
        (str(strace), "-f", "-qq", "-yy", "-s", "4096", "-e", "trace=%file", "-o", str(trace),
         str(binary), str(config)), repo, timeout_seconds, "PREFLIGHT_HARNESS",
        harness_root / "logs/harness_stdout.txt", harness_root / "logs/harness_stderr.txt")
    expected_stdout = "\n".join((STAGE_ID, "clean3_s3_ab0000_parity_solver", STAGE_ID, RUN_ID))
    if traced.stdout.strip() != expected_stdout:
        raise Clean3S3Error("T5-T7 loader identity mismatch",
                            terminal_status="FAILED_TECHNICAL_PREFLIGHT_IDENTITY")
    rejected = command_runner((str(binary), str(canonical)), repo, timeout_seconds)
    if rejected.returncode == 0 or "FAIL_CLEAN1_METHOD_CONTRACT_MISMATCH" not in rejected.stderr:
        raise Clean3S3Error("T8 Canonical tuple was not rejected",
                            terminal_status="FAILED_TECHNICAL_PREFLIGHT_T8")
    try:
        ledger = _audit_preflight_trace(
            trace, cwd=root, harness_binary=binary, accepting_config=config,
            negative_config=canonical, sentinel_root=sentinel, artifact_hashes=artifact_hashes,
        )
    except _TechnicalFailure as exc:
        raise Clean3S3Error(str(exc), terminal_status="FAILED_TECHNICAL_PREFLIGHT_FILE_OPEN_AUDIT") from exc
    ledger_path = write_json_atomic(seal_root / "ZERO_DATA_LOADER_READ_LEDGER.json", ledger)
    report = {"schema_version": PREFLIGHT_REPORT_SCHEMA,
              "stage_id": STAGE_ID, "execution_head": git_identity["execution_head"],
              "attempt_id": root.name, "attempt_ordinal": int(root.name[-6:]),
              "terminal_status": "PREFLIGHT_OK", "proof_kind": "STATIC_PLUS_ZERO_DATA_LOADER",
              "trace_subject": "ZERO_DATA_LOADER_HARNESS", "formal_solver_executed": False,
              **{key: ledger[key] for key in ledger if key not in ("passed", "schema_version")},
              "g_c2": "REPORTING_ONLY", "g_c3": "HARD_UNCHANGED"}
    report_path = write_json_atomic(report_root / "CLEAN3R3_GOVERNANCE_PREFLIGHT_REPORT.json", report)
    write_json_atomic(seal_root / "CLEAN3R3_GOVERNANCE_PREFLIGHT_SEAL.json",
                      {"schema_version": PREFLIGHT_SEAL_SCHEMA, "sealed": True,
                       "bound_artifact_sha256": artifact_hashes,
                       "sha256": {"report": sha256_file(report_path),
                       "ledger": sha256_file(ledger_path), "raw_trace": sha256_file(trace)}})
    return report


def run_s3_ab0000_parity(
    inputs: S3Inputs,
    *,
    command_runner: CommandRunner = _default_command_runner,
    which: Callable[[str], str | None] = shutil.which,
) -> dict[str, Any]:
    """Run exactly one AB0000 parity attempt and stop at S3."""

    if inputs.jobs < 1 or inputs.timeout_seconds < 1:
        raise Clean3S3Error("jobs/timeout must be positive", terminal_status="FAILED_TECHNICAL_ARGUMENT")
    try:
        repo = inputs.repo_root.resolve(strict=True)
        git_identity = _guard_git(repo)
        clean_root = inputs.clean_root.resolve(strict=True)
        initial_preflight = _governance_preflight_guard(clean_root, git_identity)
        with _preflight_namespace_lock(clean_root) as namespace:
            preflight = _select_governance_preflight_locked(namespace, git_identity)
            if preflight != initial_preflight:
                raise Clean3S3Error("selected preflight changed before formal claim",
                                    terminal_status="FAILED_TECHNICAL_PREFLIGHT_SELECTION_RACE")
            paths = _exact_paths(inputs)
            paths["stage_root"].mkdir(parents=False)
            write_json_atomic(paths["stage_root"] / "ATTEMPT_CLAIM.json", {
                "stage_id": STAGE_ID, "execution_head": git_identity["execution_head"],
                "attempt_ordinal": 1, "maximum_solver_executions": 1,
                "retry_count": 0, "retry_allowed": False, "claimed_before_configure": True,
                "selected_preflight": preflight,
            })
        inherited = _manifest_and_provider_guard(paths)
        anchor_hashes = {
            "KF_GINS_Navresult.nav": sha256_file(paths["anchor_nav"]),
            "KF_GINS_STD.txt": sha256_file(paths["anchor_std"]),
        }
        if anchor_hashes != EXPECTED_ANCHOR_HASHES:
            raise Clean3S3Error("frozen parity anchor hash mismatch", terminal_status="FAILED_TECHNICAL_ANCHOR_HASH_MISMATCH")
        pre_raw = _raw_guard(paths, inherited["raw_source_hashes"])
        provider_pre = {
            role: sha256_file(path) for role, path in inherited["provider_paths"].items()
        }
    except Clean3S3Error:
        raise
    except Exception as exc:
        reason = exc.reason if isinstance(exc, _TechnicalFailure) else type(exc).__name__.upper()
        terminal = "FAILED_TECHNICAL_" + "".join(ch if ch.isalnum() else "_" for ch in reason.upper()).strip("_")
        raise Clean3S3Error(str(exc), terminal_status=terminal) from exc
    immutable_paths = {
        **{f"manifest:{role}": paths[role] for role in EXPECTED_MANIFEST_HASHES},
        "raw_lock:full": paths["full_raw_lock"], "raw_lock:by2": paths["by2_raw_lock"],
        **{f"provider:{role}": path for role, path in inherited["provider_paths"].items()},
        **{f"raw:{relative}": paths["raw_root"] / relative for relative in pre_raw},
        "anchor:nav": paths["anchor_nav"], "anchor:std": paths["anchor_std"],
    }
    integrity_pre = _integrity_snapshot(immutable_paths)

    stage = paths["stage_root"]
    report_path = _terminal_report_path(stage)
    build = stage / "01_BUILD"
    runtime = stage / "02_AB0000_RUNTIME"
    seal_root = stage / "03_SEAL"
    runtime.mkdir()
    (runtime / "logs").mkdir()
    seal_root.mkdir()
    started = time.monotonic()
    base_report: dict[str, Any] = {
        "schema_version": "paper_rebuild.clean3_s3_ab0000_parity.v1",
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "case_id": CASE_ID,
        "run_id": RUN_ID,
        "algorithm_id": METHOD_ID,
        "data_mode": DATA_MODE,
        "parent_provider_stage_id": PARENT_PROVIDER_STAGE_ID,
        "parent_provider_protocol_id": PARENT_PROVIDER_PROTOCOL_ID,
        "parent_parity_stage_id": PARENT_PARITY_STAGE_ID,
        "parent_parity_protocol_id": PARENT_PARITY_PROTOCOL_ID,
        **git_identity,
        "inherited_manifest_hashes": inherited["manifest_hashes"],
        "provider_hashes_pre": provider_pre,
        "raw_hashes_pre": pre_raw,
        "immutable_integrity_pre": integrity_pre,
        "raw_integrity_audit_includes_trace_hash": BY2_TRACE_RELATIVE_PATH in pre_raw,
        "profile_count": 1,
        "profiles": [METHOD_ID],
        "evaluator_invoked": False,
        "performance_metrics_read": False,
        "trace_used_online": False,
        "auto_s4_started": False,
        "retry_count": 0,
        "ready_for_paper_claims": False,
        "governance_preflight": preflight,
    }
    attempt_started = False
    try:
        attempt_started = True
        configure = _run_checked(
            command_runner,
            ("cmake", "-S", str(paths["repo"] / "cpp"), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"),
            paths["repo"], inputs.timeout_seconds, "CMAKE_CONFIGURE",
            runtime / "logs/cmake_configure_stdout.txt", runtime / "logs/cmake_configure_stderr.txt",
        )
        build_result = _run_checked(
            command_runner,
            ("cmake", "--build", str(build), "--target", "legsa_v23_port_core_demo", "-j", str(inputs.jobs)),
            paths["repo"], inputs.timeout_seconds, "CMAKE_BUILD",
            runtime / "logs/cmake_build_stdout.txt", runtime / "logs/cmake_build_stderr.txt",
        )
        binary = (build / "legsa_v23_port_core_demo").resolve(strict=True)
        binary_hash_pre = sha256_file(binary)
        config = runtime / "CLEAN3_S3_AB0000_RUNTIME_CONFIG.yaml"
        config_text = build_s3_ab0000_config(
            inherited["provider_paths"]["imu"], inherited["provider_paths"]["gnss"], runtime,
        )
        config.write_text(config_text, encoding="utf-8")
        config_hash = sha256_file(config)
        strace_binary = which("strace")
        if not strace_binary:
            raise _TechnicalFailure("STRACE_UNAVAILABLE", "strace is required for the S3 solver read audit")
        trace = runtime / "logs" / "SOLVER_FILE_OPEN_TRACE.raw"
        solver_command = (
            str(strace_binary), "-f", "-qq", "-yy", "-s", "4096", "-e",
            "trace=%file",
            "-o", str(trace), str(binary), "--config", str(config), "--output-dir", str(runtime),
        )
        write_json_atomic(runtime / "SOLVER_LAUNCH_CLAIM.json", {
            "stage_id": STAGE_ID, "execution_head": git_identity["execution_head"],
            "solver_execution_ordinal": 1, "maximum_solver_executions": 1,
            "retry_allowed": False, "solver_executable_sha256": binary_hash_pre,
            "runtime_config_sha256": config_hash,
            "selected_preflight": preflight,
        })
        solver = _run_checked(
            command_runner, solver_command, paths["repo"], inputs.timeout_seconds, "SOLVER_EXECUTION",
            runtime / "logs/solver_stdout.txt", runtime / "logs/solver_stderr.txt",
            raise_on_nonzero=False,
        )
        binary_hash_post = sha256_file(binary)
        if binary_hash_post != binary_hash_pre:
            raise _TechnicalFailure("EXECUTABLE_MUTATION", "fresh solver executable changed during execution")
        if not trace.is_file():
            raise _TechnicalFailure("SOLVER_TRACE_MISSING", "solver syscall trace is missing")
        read_ledger = _audit_solver_syscalls(
            trace,
            repo=paths["repo"], clean_root=paths["clean_root"], raw_root=paths["raw_root"],
            stage_root=stage, provider_root=inherited["provider_root"],
            expected_inputs={
                "propagation_imu": inherited["provider_paths"]["imu"],
                "gnss_position_receiver_velocity_dual_yaw": inherited["provider_paths"]["gnss"],
            },
            immutable_paths=list(immutable_paths.values()), solver_binary=binary,
        )
        if solver.returncode != 0:
            raise _TechnicalFailure("SOLVER_EXECUTION", f"solver command failed ({solver.returncode})")
        required = {
            "nav": runtime / "KF_GINS_Navresult.nav",
            "std": runtime / "KF_GINS_STD.txt",
            "solver_manifest": runtime / "RUN_MANIFEST.json",
            "file_open_trace": trace,
        }
        missing = [role for role, path in required.items() if not path.is_file()]
        if missing:
            raise _TechnicalFailure("OUTPUT_INCOMPLETE", "missing solver outputs: " + ",".join(missing))
        solver_manifest = _load_json(required["solver_manifest"])
        counters = _validate_solver_manifest(solver_manifest, inherited["provider_paths"])
        read_ledger_path = write_json_atomic(runtime / "CLEAN3_S3_SOLVER_READ_LEDGER.json", read_ledger)
        _reject_provider_copies(runtime, provider_pre)
        integrity_post = _integrity_snapshot(immutable_paths)
        changes = _integrity_changes(integrity_pre, integrity_post)
        if changes:
            raise _TechnicalFailure("IMMUTABLE_MUTATION_DETECTED", "immutable inputs changed: " + ",".join(changes))
        post_raw = _raw_guard(paths, inherited["raw_source_hashes"])
        provider_post = {
            role: sha256_file(path) for role, path in inherited["provider_paths"].items()
        }
        if post_raw != pre_raw:
            raise _TechnicalFailure("RAW_MUTATION_DETECTED", "BY2 raw bytes changed during S3")
        if provider_post != provider_pre:
            raise _TechnicalFailure("PROVIDER_MUTATION_DETECTED", "provider bytes changed during S3")
        head_after = _guard_git(paths["repo"])
        if head_after != git_identity:
            raise _TechnicalFailure("CODE_STATE_CHANGED", "Git/C++ identity changed during S3")
        output_hashes = {
            "KF_GINS_Navresult.nav": sha256_file(required["nav"]),
            "KF_GINS_STD.txt": sha256_file(required["std"]),
        }
        seal = {
            "schema_version": "paper_rebuild.clean3_s3_output_seal.v1",
            "sealed_before_parity_comparison": True,
            "output_hashes": output_hashes,
            "solver_executable_sha256": binary_hash_post,
            "solver_manifest_sha256": sha256_file(required["solver_manifest"]),
            "runtime_config_sha256": config_hash,
            "file_open_trace_sha256": sha256_file(trace),
            "file_open_ledger_sha256": sha256_file(read_ledger_path),
            "solver_executable_sha256_pre": binary_hash_pre,
            "solver_executable_sha256_post": binary_hash_post,
        }
        seal_path = write_json_atomic(seal_root / "CLEAN3_S3_OUTPUT_SEAL.json", seal)
        byte_comparison = {
            "KF_GINS_Navresult.nav": {
                "output_size": required["nav"].stat().st_size, "anchor_size": paths["anchor_nav"].stat().st_size,
                "output_sha256": output_hashes["KF_GINS_Navresult.nav"],
                "anchor_sha256": anchor_hashes["KF_GINS_Navresult.nav"],
                "byte_equal": _stream_byte_equal(required["nav"], paths["anchor_nav"]),
            },
            "KF_GINS_STD.txt": {
                "output_size": required["std"].stat().st_size, "anchor_size": paths["anchor_std"].stat().st_size,
                "output_sha256": output_hashes["KF_GINS_STD.txt"],
                "anchor_sha256": anchor_hashes["KF_GINS_STD.txt"],
                "byte_equal": _stream_byte_equal(required["std"], paths["anchor_std"]),
            },
        }
        anchor_hashes_after_seal = {
            "KF_GINS_Navresult.nav": sha256_file(paths["anchor_nav"]),
            "KF_GINS_STD.txt": sha256_file(paths["anchor_std"]),
        }
        if anchor_hashes_after_seal != anchor_hashes:
            raise _TechnicalFailure("ANCHOR_MUTATION_DETECTED", "parity anchor changed after output seal")
        parity = {
            name: byte_comparison[name]["byte_equal"] and output_hashes[name] == EXPECTED_ANCHOR_HASHES[name]
            for name in EXPECTED_ANCHOR_HASHES
        }
        terminal = PASS_TERMINAL if all(parity.values()) else MISMATCH_TERMINAL
        outer_manifest = {
            "schema_version": "paper_rebuild.clean3_s3_run_manifest.v1",
            "stage_id": STAGE_ID,
            "protocol_id": PROTOCOL_ID,
            "parent_contract": {
                "stage_id": PARENT_PROVIDER_STAGE_ID,
                "protocol_id": PARENT_PROVIDER_PROTOCOL_ID,
            },
            "run_id": RUN_ID,
            "algorithm_id": METHOD_ID,
            "data_mode": DATA_MODE,
            "code_commit": git_identity["execution_head"],
            "code_worktree_dirty_at_run": False,
            "repair_implementation_commit": REPAIR_IMPLEMENTATION_COMMIT,
            "amendment_parent_head": AMENDMENT_PARENT_HEAD,
            "prior_reviewed_cpp_tree": PRIOR_REVIEWED_CPP_TREE,
            "final_execution_cpp_tree": git_identity["final_execution_cpp_tree"],
            "config_hash": config_hash,
            "solver_executable_sha256": binary_hash_post,
            "solver_manifest_hash": sha256_file(required["solver_manifest"]),
            "provider_hashes": provider_post,
            "raw_source_hashes": post_raw,
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
            "cov_health_status": "PASS",
            "cov_health_fail_count": 0,
            "module_counters": counters,
            "solver_read_ledger": read_ledger,
            "output_seal_sha256": sha256_file(seal_path),
            "terminal_status": terminal,
            "governance_preflight": preflight,
        }
        outer_path = write_json_atomic(runtime / "CLEAN3_S3_RUN_MANIFEST.json", outer_manifest)
        report = {
            **base_report,
            "runtime_config_sha256": config_hash,
            "solver_manifest_sha256": sha256_file(required["solver_manifest"]),
            "outer_manifest_sha256": sha256_file(outer_path),
            "output_seal_sha256": sha256_file(seal_path),
            "output_hashes": output_hashes,
            "byte_comparison": byte_comparison,
            "anchor_hashes_after_seal": anchor_hashes_after_seal,
            "immutable_integrity_post": integrity_post,
            "expected_anchor_hashes": EXPECTED_ANCHOR_HASHES,
            "byte_parity": parity,
            "provider_hashes_post": provider_post,
            "raw_hashes_post": post_raw,
            "raw_mutation_count": 0,
            "provider_mutation_count": 0,
            "solver_read_ledger": read_ledger,
            "cov_health_status": "PASS",
            "cov_health_fail_count": 0,
            "elapsed_seconds": time.monotonic() - started,
            "terminal_status": terminal,
            "passed": terminal == PASS_TERMINAL,
        }
        write_json_atomic(report_path, report)
        if terminal != PASS_TERMINAL:
            raise Clean3S3Error(
                "AB0000 NAV/STD byte parity mismatch", terminal_status=terminal, report_path=report_path,
            )
        return report
    except Clean3S3Error as exc:
        if exc.terminal_status == MISMATCH_TERMINAL and exc.report_path == report_path:
            raise
        integrity_post = _integrity_snapshot(immutable_paths) if attempt_started else integrity_pre
        changes = _integrity_changes(integrity_pre, integrity_post)
        terminal = "FAILED_TECHNICAL_IMMUTABLE_MUTATION_DETECTED" if changes else exc.terminal_status
        failure_report = {
            **base_report,
            "elapsed_seconds": time.monotonic() - started,
            "terminal_status": terminal,
            "passed": False,
            "failure_reason": str(exc),
            "immutable_integrity_post": integrity_post,
            "immutable_changed_roles": changes,
        }
        write_json_atomic(report_path, failure_report)
        raise Clean3S3Error(
            str(exc), terminal_status=terminal, report_path=report_path,
        ) from exc
    except Exception as exc:
        reason = exc.reason if isinstance(exc, _TechnicalFailure) else type(exc).__name__.upper()
        terminal = "FAILED_TECHNICAL_" + "".join(ch if ch.isalnum() else "_" for ch in reason.upper()).strip("_")
        integrity_post = _integrity_snapshot(immutable_paths) if attempt_started else integrity_pre
        changes = _integrity_changes(integrity_pre, integrity_post)
        if changes:
            terminal = "FAILED_TECHNICAL_IMMUTABLE_MUTATION_DETECTED"
        failure_report = {
            **base_report,
            "elapsed_seconds": time.monotonic() - started,
            "terminal_status": terminal,
            "passed": False,
            "failure_reason": str(exc),
            "immutable_integrity_post": integrity_post,
            "immutable_changed_roles": changes,
        }
        write_json_atomic(report_path, failure_report)
        raise Clean3S3Error(str(exc), terminal_status=terminal, report_path=report_path) from exc


def s3_cli_payload(report: Mapping[str, Any]) -> dict[str, Any]:
    """Return the intentionally small CLI result without starting another gate."""

    return {
        "stage_id": report["stage_id"],
        "protocol_id": report["protocol_id"],
        "profile_count": report["profile_count"],
        "terminal_status": report["terminal_status"],
        "auto_s4_started": False,
        "ready_for_paper_claims": False,
    }
