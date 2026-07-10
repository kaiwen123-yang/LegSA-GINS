"""Hashing and fail-closed manifest contracts for clean paper rebuild runs."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping


REQUIRED_RUN_FIELDS = (
    "schema_version",
    "run_id",
    "algorithm_id",
    "case_id",
    "data_mode",
    "raw_source_hashes",
    "provider_hashes",
    "synthetic_data_used",
    "semisynthetic_data_used",
    "trace_used_online",
    "receiver_imu_as_body_imu",
    "final_v23_output_solver_input",
    "LegSA_output_solver_input",
    "per_case_tuning",
    "output_only_correction",
    "epoch_deleted_for_metric",
    "old_runtime_input_count",
    "code_commit",
    "code_worktree_dirty_at_run",
    "config_hash",
    "provider_generator_commit",
    "provider_generation_config_hash",
    "local_path_config_hash",
    "terminal_status",
)

FORBIDDEN_TRUE_FIELDS = (
    "synthetic_data_used",
    "semisynthetic_data_used",
    "trace_used_online",
    "receiver_imu_as_body_imu",
    "final_v23_output_solver_input",
    "LegSA_output_solver_input",
    "per_case_tuning",
    "output_only_correction",
    "epoch_deleted_for_metric",
)


class ManifestContractError(ValueError):
    """Raised when lineage or safety fields are missing or inconsistent."""


def git_code_state(code_root: str | Path) -> tuple[str, bool]:
    """Return the exact Git commit and whether tracked/untracked content is dirty."""

    root = Path(code_root)
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
                timeout=15,
            ).stdout.strip()
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ManifestContractError(f"Cannot resolve clean Git code state: {exc}") from exc
    if not commit:
        raise ManifestContractError("Git code commit is empty")
    return commit, dirty


def sha256_file(path: str | Path, *, chunk_size: int = 4 * 1024 * 1024) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    with source.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def write_json_atomic(path: str | Path, payload: Mapping[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".", dir=destination.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, destination)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return destination


def read_hash_lock(path: str | Path) -> dict[str, dict[str, str]]:
    source = Path(path)
    if not source.is_file():
        raise ManifestContractError(f"Raw hash lock is missing: {source}")
    rows: dict[str, dict[str, str]] = {}
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"relative_path", "size_bytes", "sha256"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ManifestContractError("Raw hash lock schema is incomplete")
        for row in reader:
            relative = str(row.get("relative_path") or "").strip().replace("\\", "/")
            if not relative or relative.startswith("/") or ".." in Path(relative).parts:
                raise ManifestContractError(f"Unsafe raw hash-lock relative path: {relative!r}")
            if relative in rows:
                raise ManifestContractError(f"Duplicate raw hash-lock row: {relative}")
            rows[relative] = {key: str(value or "") for key, value in row.items()}
    if not rows:
        raise ManifestContractError("Raw hash lock is empty")
    return rows


def verify_raw_sources(
    raw_root: str | Path,
    relative_paths: Iterable[str],
    hash_lock: Mapping[str, Mapping[str, str]],
) -> dict[str, str]:
    """Verify source bytes against the immutable raw lock."""

    root = Path(raw_root).resolve(strict=True)
    verified: dict[str, str] = {}
    for relative_raw in relative_paths:
        relative = str(relative_raw).replace("\\", "/")
        if relative.startswith("/") or ".." in Path(relative).parts:
            raise ManifestContractError(f"Unsafe raw source relative path: {relative}")
        row = hash_lock.get(relative)
        if not row:
            raise ManifestContractError(f"Raw source is absent from hash lock: {relative}")
        source = (root / relative).resolve(strict=True)
        if root not in source.parents:
            raise ManifestContractError(f"Raw source escapes raw root: {relative}")
        expected_size = int(str(row.get("size_bytes") or "-1"))
        if source.stat().st_size != expected_size:
            raise ManifestContractError(f"Raw source size changed since hash lock: {relative}")
        actual = sha256_file(source)
        expected = str(row.get("sha256") or "")
        if actual != expected:
            raise ManifestContractError(f"Raw source hash changed since hash lock: {relative}")
        verified[relative] = actual
    return verified


def validate_run_manifest(
    manifest: Mapping[str, Any],
    *,
    require_pass: bool = False,
) -> list[str]:
    """Return all contract violations; an empty list means pass."""

    issues: list[str] = []
    for field in REQUIRED_RUN_FIELDS:
        if field not in manifest:
            issues.append(f"missing_field:{field}")
    if manifest.get("data_mode") != "real_by2_raw":
        issues.append("data_mode_must_be_real_by2_raw")
    for field in FORBIDDEN_TRUE_FIELDS:
        if manifest.get(field) is not False:
            issues.append(f"forbidden_flag_not_false:{field}")
    if manifest.get("old_runtime_input_count") != 0:
        issues.append("old_runtime_input_count_must_be_zero")
    if manifest.get("code_worktree_dirty_at_run") is not False:
        issues.append("code_worktree_dirty_at_run_must_be_false")
    for field in ("raw_source_hashes", "provider_hashes"):
        value = manifest.get(field)
        if not isinstance(value, Mapping) or not value:
            issues.append(f"{field}_must_be_nonempty_mapping")
        elif any(not isinstance(key, str) or not isinstance(item, str) or len(item) != 64 for key, item in value.items()):
            issues.append(f"{field}_contains_invalid_sha256")
    for field in (
        "code_commit",
        "config_hash",
        "provider_generator_commit",
        "provider_generation_config_hash",
        "local_path_config_hash",
    ):
        value = manifest.get(field)
        if not isinstance(value, str) or not value:
            issues.append(f"{field}_must_be_nonempty")
    for field in ("config_hash", "provider_generation_config_hash", "local_path_config_hash"):
        value = manifest.get(field)
        if isinstance(value, str) and len(value) != 64:
            issues.append(f"{field}_must_be_sha256")
    if require_pass and str(manifest.get("terminal_status") or "").upper() != "PASS":
        issues.append("terminal_status_not_pass")
    return issues


def assert_run_manifest(manifest: Mapping[str, Any], *, require_pass: bool = False) -> None:
    issues = validate_run_manifest(manifest, require_pass=require_pass)
    if issues:
        raise ManifestContractError(";".join(issues))
