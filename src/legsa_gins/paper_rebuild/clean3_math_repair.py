"""One-shot CLEAN3 S3 AB0000 byte-parity orchestration.

This module intentionally exposes one operation only.  It does not import an
evaluator, generate providers, read performance metrics, or route to CLEAN2
execution entrypoints.
"""

from __future__ import annotations

import json
import ast
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


STAGE_ID = "CLEAN3_MATH_REPAIR_RP_JACOBIAN_RD_LEVERARM_SA_CLEAN_SILENCE"
PROTOCOL_ID = "CLEAN3_S3_AB0000_PARITY"
CASE_ID = "CLEAN1_BY2_CLEAN_NORMAL"
RUN_ID = "CLEAN3_S3_AB0000"
METHOD_ID = "AB0000"
DATA_MODE = "real_clean"

REPAIR_IMPLEMENTATION_COMMIT = "0d8cc2bdccfd89b236ab4badeef9db5344dcf4d3"
PRE_PARITY_CONTEXT_COMMIT = "b451110267e71725d1d5259f6a37ab696197ed9a"
PRIOR_REVIEWED_CPP_TREE = "a3716d22acf95fb1e6028ae82acb2ae73e138bfc"
LOADER_EXTENSION_PATH = "cpp/legsa_v23_port_core/src/config/port_config_loader.cpp"
FREEZE_PATH = "docs/paper_rebuild/CLEAN3_S3_EXECUTION_FREEZE.json"
FROZEN_CODE_PATHS = (
    LOADER_EXTENSION_PATH,
    "src/legsa_gins/paper_rebuild/clean3_math_repair.py",
    "scripts/paper_rebuild/run_clean3_math_repair.py",
    "tests/paper_rebuild/test_clean3_s3_parity_runner.py",
)

PARENT_PROVIDER_STAGE_ID = "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION_REBUILD"
PARENT_PROVIDER_PROTOCOL_ID = "CLEAN2R2A_BY2_CLEAN_MODULE_ABLATION"
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
        "schema_version": "paper_rebuild.clean3_s3_execution_freeze.v1",
        "stage_id": STAGE_ID,
        "protocol_id": PROTOCOL_ID,
        "repair_implementation_commit": REPAIR_IMPLEMENTATION_COMMIT,
        "pre_parity_context_commit": PRE_PARITY_CONTEXT_COMMIT,
    }
    if any(freeze.get(key) != value for key, value in required.items()):
        raise Clean3S3Error("execution freeze lineage mismatch", terminal_status="FAILED_TECHNICAL_FREEZE_CONTRACT")
    runner_freeze = freeze.get("runner_freeze_commit")
    if (not isinstance(runner_freeze, str) or len(runner_freeze) != 40
            or any(ch not in "0123456789abcdef" for ch in runner_freeze)):
        raise Clean3S3Error("execution freeze commit is invalid", terminal_status="FAILED_TECHNICAL_FREEZE_CONTRACT")
    if _git(repo, "rev-parse", f"{head}^").stdout.strip() != runner_freeze:
        raise Clean3S3Error("execution HEAD is not exactly one authorization commit after runner freeze",
                            terminal_status="FAILED_TECHNICAL_FREEZE_LINEAGE")
    changed = tuple(_git(repo, "diff", "--name-only", f"{runner_freeze}..{head}").stdout.splitlines())
    if changed != (FREEZE_PATH,):
        raise Clean3S3Error("authorization commit changed files other than the freeze JSON",
                            terminal_status="FAILED_TECHNICAL_FREEZE_SCOPE_DRIFT")
    if _git(repo, "ls-files", "--error-unmatch", FREEZE_PATH, check=False).returncode != 0:
        raise Clean3S3Error("execution freeze is not tracked", terminal_status="FAILED_TECHNICAL_FREEZE_UNTRACKED")
    for ancestor in (runner_freeze, REPAIR_IMPLEMENTATION_COMMIT, PRE_PARITY_CONTEXT_COMMIT):
        if _git(repo, "merge-base", "--is-ancestor", ancestor, head, check=False).returncode != 0:
            raise Clean3S3Error(
                f"HEAD does not descend from required context {ancestor}",
                terminal_status="FAILED_TECHNICAL_WRONG_CODE_LINEAGE",
            )
    cpp_tree = _git(repo, "rev-parse", f"{head}:cpp").stdout.strip()
    if freeze.get("final_cpp_tree") != cpp_tree:
        raise Clean3S3Error("frozen C++ tree mismatch", terminal_status="FAILED_TECHNICAL_CPP_TREE_DRIFT")
    frozen_hashes = freeze.get("tracked_file_sha256")
    if not isinstance(frozen_hashes, Mapping) or set(frozen_hashes) != set(FROZEN_CODE_PATHS):
        raise Clean3S3Error("frozen tracked-file ledger is incomplete", terminal_status="FAILED_TECHNICAL_FREEZE_CONTRACT")
    actual_hashes = {relative: sha256_file(repo / relative) for relative in FROZEN_CODE_PATHS}
    if actual_hashes != frozen_hashes:
        raise Clean3S3Error("tracked runner bytes differ from execution freeze",
                            terminal_status="FAILED_TECHNICAL_RUNNER_BYTE_DRIFT")
    changed_cpp = tuple(
        row for row in _git(
            repo, "diff", "--name-only", f"{PRE_PARITY_CONTEXT_COMMIT}..{head}", "--", "cpp",
        ).stdout.splitlines() if row
    )
    if changed_cpp != (LOADER_EXTENSION_PATH,):
        raise Clean3S3Error(
            "C++ diff from pre-parity context is not the exact loader-only extension",
            terminal_status="FAILED_TECHNICAL_CPP_SCOPE_DRIFT",
        )
    prior_tree = _git(repo, "rev-parse", f"{REPAIR_IMPLEMENTATION_COMMIT}:cpp").stdout.strip()
    if prior_tree != PRIOR_REVIEWED_CPP_TREE:
        raise Clean3S3Error(
            "reviewed S2 C++ tree identity drifted",
            terminal_status="FAILED_TECHNICAL_REVIEWED_CPP_TREE_MISMATCH",
        )
    return {
        "execution_head": head,
        "runner_freeze_commit": runner_freeze,
        "execution_freeze_sha256": sha256_file(freeze_path),
        "frozen_tracked_file_sha256": dict(frozen_hashes),
        "repair_implementation_commit": REPAIR_IMPLEMENTATION_COMMIT,
        "pre_parity_context_commit": PRE_PARITY_CONTEXT_COMMIT,
        "prior_reviewed_cpp_tree": PRIOR_REVIEWED_CPP_TREE,
        "final_execution_cpp_tree": cpp_tree,
        "cpp_diff_from_pre_parity_context": list(changed_cpp),
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
        clean.get("stage_id") != PARENT_PROVIDER_STAGE_ID
        or clean.get("protocol_id") != PARENT_PROVIDER_PROTOCOL_ID
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
        paths = _exact_paths(inputs)
        git_identity = _guard_git(paths["repo"])
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
    stage.mkdir(parents=False)
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
            "pre_parity_context_commit": PRE_PARITY_CONTEXT_COMMIT,
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
