"""Bounded, one-shot BY2 raw checkpoints for the canonical 541-case stage.

This module deliberately audits only the 22 BY2 rows named by the immutable
``RAW_FILE_HASH_LOCK.csv``.  It never walks the raw tree and it never exposes
the evaluation trace as a provider or solver input.  Each checkpoint is
published as an immutable CSV/JSON pair after the complete audit has finished.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping

from legsa_gins.paper_rebuild.evidence import (
    BY2_RAW_RELATIVE_PATHS,
    BY2_TRACE_RELATIVE_PATH,
)
from legsa_gins.paper_rebuild.manifest import read_hash_lock, sha256_file


RAW_CHECKPOINT_PHASES = (
    "PRE_CODE_FREEZE",
    "PRE_PROVIDER",
    "POST_PROVIDER",
    "POST_RUN",
)
TRACE_AUDIT_ROLE = "outer_raw_integrity_hash_audit_only"
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_CSV_FIELDS = (
    "audit_phase",
    "relative_path",
    "dataset",
    "lock_role",
    "source_role",
    "expected_size_bytes",
    "actual_size_bytes",
    "expected_sha256",
    "actual_sha256",
    "exists",
    "regular_file",
    "realpath_confined",
    "no_symlink_components",
    "status",
    "reason",
)


class RawCheckpointError(RuntimeError):
    """Raised when a raw checkpoint cannot be proven or published safely."""

    def __init__(self, message: str, *, summary: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.summary = dict(summary or {})


def _absolute_lexical(path: str | Path) -> Path:
    """Return an absolute path without resolving a possibly unsafe symlink."""

    return Path(os.path.abspath(os.fspath(path)))


def _assert_no_symlink_components(path: str | Path, *, kind: str) -> Path:
    """Resolve *path* only after every existing component passed ``lstat``."""

    absolute = _absolute_lexical(path)
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError as exc:
            raise RawCheckpointError(f"{kind} is missing: {absolute}") from exc
        if stat.S_ISLNK(mode):
            raise RawCheckpointError(f"{kind} has a symlink component: {current}")
    return absolute.resolve(strict=True)


def _candidate_state(root: Path, relative: str) -> tuple[Path | None, str]:
    """Return a no-symlink candidate or a bounded failure reason."""

    current = root
    for part in Path(relative).parts:
        current /= part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            return None, "missing"
        if stat.S_ISLNK(mode):
            return None, "symlink_component"
    resolved = current.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError:
        return None, "realpath_escape"
    if not stat.S_ISREG(os.lstat(current).st_mode):
        return None, "not_regular_file"
    return resolved, ""


def _source_role(relative: str) -> str:
    # trace 只能在此处读取其外层文件哈希，绝不能成为 provider/solver 输入。
    if relative == BY2_TRACE_RELATIVE_PATH:
        return TRACE_AUDIT_ROLE
    if relative.endswith("/by2.txt"):
        return "go2_body_source_not_truth"
    if Path(relative).name.startswith("imu-"):
        return "receiver_imu_hash_audit_not_body_propagation"
    return "hash_locked_by2_raw_source"


def _validate_lock(
    lock_path: Path,
    *,
    expected_lock_sha256: str,
    expected_full_lock_rows: int,
) -> tuple[dict[str, dict[str, str]], str, int]:
    if not _SHA256_RE.fullmatch(expected_lock_sha256):
        raise RawCheckpointError("expected RAW_FILE_HASH_LOCK SHA256 is invalid")
    actual_lock_sha256 = sha256_file(lock_path)
    if actual_lock_sha256 != expected_lock_sha256:
        raise RawCheckpointError("RAW_FILE_HASH_LOCK SHA256 mismatch")
    try:
        lock = read_hash_lock(lock_path)
    except (OSError, ValueError) as exc:
        raise RawCheckpointError(f"RAW_FILE_HASH_LOCK cannot be parsed: {exc}") from exc
    if len(lock) != expected_full_lock_rows:
        raise RawCheckpointError(
            f"RAW_FILE_HASH_LOCK row count mismatch: {len(lock)} != {expected_full_lock_rows}"
        )
    by2 = {relative: row for relative, row in lock.items() if row.get("dataset") == "BY2"}
    expected_paths = set(BY2_RAW_RELATIVE_PATHS)
    if set(by2) != expected_paths or len(by2) != 22:
        missing = sorted(expected_paths - set(by2))
        extra = sorted(set(by2) - expected_paths)
        raise RawCheckpointError(
            f"RAW_FILE_HASH_LOCK BY2 path set is not exact; missing={missing}; extra={extra}"
        )
    for relative in BY2_RAW_RELATIVE_PATHS:
        row = by2[relative]
        try:
            size = int(row.get("size_bytes", ""))
        except ValueError as exc:
            raise RawCheckpointError(f"invalid locked size for {relative}") from exc
        if size < 0 or not _SHA256_RE.fullmatch(str(row.get("sha256", ""))):
            raise RawCheckpointError(f"invalid locked size/SHA256 for {relative}")
        if str(row.get("immutable", "")).strip().lower() not in {"true", "1", "yes"}:
            raise RawCheckpointError(f"BY2 raw lock row is not immutable: {relative}")
    return by2, actual_lock_sha256, len(lock)


def _audit_rows(root: Path, by2_lock: Mapping[str, Mapping[str, str]], phase: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    verified_hashes: dict[str, str] = {}
    counts = {"missing": 0, "mismatch": 0, "symlink_escape": 0}
    for relative in BY2_RAW_RELATIVE_PATHS:
        locked = by2_lock[relative]
        candidate, failure = _candidate_state(root, relative)
        expected_size = int(locked["size_bytes"])
        expected_sha = str(locked["sha256"])
        row: dict[str, Any] = {
            "audit_phase": phase,
            "relative_path": relative,
            "dataset": "BY2",
            "lock_role": str(locked.get("role", "")),
            "source_role": _source_role(relative),
            "expected_size_bytes": expected_size,
            "actual_size_bytes": "",
            "expected_sha256": expected_sha,
            "actual_sha256": "",
            "exists": failure != "missing",
            "regular_file": False,
            "realpath_confined": failure not in {"realpath_escape", "symlink_component"},
            "no_symlink_components": failure != "symlink_component",
            "status": "FAIL",
            "reason": failure,
        }
        if failure:
            if failure == "missing":
                counts["missing"] += 1
            elif failure in {"realpath_escape", "symlink_component"}:
                counts["symlink_escape"] += 1
            else:
                counts["mismatch"] += 1
            rows.append(row)
            continue

        assert candidate is not None
        row["regular_file"] = True
        actual_size = candidate.stat().st_size
        actual_sha = sha256_file(candidate)
        row["actual_size_bytes"] = actual_size
        row["actual_sha256"] = actual_sha
        if actual_size != expected_size or actual_sha != expected_sha:
            counts["mismatch"] += 1
            row["reason"] = "size_or_sha256_mismatch"
        else:
            row["status"] = "PASS"
            row["reason"] = ""
            verified_hashes[relative] = actual_sha
        rows.append(row)

    verified = sum(row["status"] == "PASS" for row in rows)
    passed = verified == 22 and not any(counts.values())
    summary: dict[str, Any] = {
        "schema_version": "paper_rebuild.canonical541.raw_checkpoint.v1",
        "audit_phase": phase,
        "expected": 22,
        "verified": verified,
        **counts,
        "raw_mutation": counts["mismatch"],
        "trace_read_role": TRACE_AUDIT_ROLE,
        "trace_provider_or_solver_input": False,
        "trace_used_online": False,
        "trace_open_count_online": 0,
        "old_provider_solver_input": False,
        "directory_discovery_used": False,
        "verified_hashes": verified_hashes,
        "passed": passed,
    }
    return rows, summary


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=_CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def write_raw_checkpoint(
    *,
    raw_root: str | Path,
    hash_lock_path: str | Path,
    expected_lock_sha256: str,
    output_root: str | Path,
    phase: str,
    expected_full_lock_rows: int = 9980,
) -> dict[str, Any]:
    """Verify and atomically publish one immutable canonical541 raw checkpoint.

    A failed content audit is also published (for provenance) and then raises
    :class:`RawCheckpointError`.  Structural failures, such as an unsafe lock
    or output path, publish nothing.
    """

    if phase not in RAW_CHECKPOINT_PHASES:
        raise RawCheckpointError(f"unsupported raw checkpoint phase: {phase!r}")
    root = _assert_no_symlink_components(raw_root, kind="raw root")
    if not root.is_dir():
        raise RawCheckpointError(f"raw root is not a directory: {root}")
    lock_path = _assert_no_symlink_components(hash_lock_path, kind="raw hash lock")
    if not lock_path.is_file():
        raise RawCheckpointError(f"raw hash lock is not a regular file: {lock_path}")
    destination_root = _assert_no_symlink_components(output_root, kind="checkpoint output root")
    if not destination_root.is_dir():
        raise RawCheckpointError(f"checkpoint output root is not a directory: {destination_root}")

    by2_lock, lock_sha, full_lock_rows = _validate_lock(
        lock_path,
        expected_lock_sha256=expected_lock_sha256,
        expected_full_lock_rows=expected_full_lock_rows,
    )
    rows, summary = _audit_rows(root, by2_lock, phase)
    summary.update({
        "raw_hash_lock_sha256": lock_sha,
        "full_lock_rows": full_lock_rows,
        "by2_lock_rows": len(by2_lock),
    })

    stem = f"CANONICAL541_RAW_22_{phase}"
    csv_target = destination_root / f"{stem}.csv"
    json_target = destination_root / f"{stem}.json"
    if csv_target.exists() or json_target.exists():
        raise RawCheckpointError(f"raw checkpoint is immutable and already exists: {stem}")

    staging = Path(tempfile.mkdtemp(prefix=f".{stem}.", dir=destination_root))
    published_csv = False
    published_json = False
    try:
        staged_csv = staging / csv_target.name
        staged_json = staging / json_target.name
        _write_csv(staged_csv, rows)
        summary["checkpoint_csv_sha256"] = sha256_file(staged_csv)
        summary["checkpoint_pair_complete"] = True
        _write_json(staged_json, summary)
        # 两个目标在发布前都已完整写入并 fsync；第二步失败时回滚第一步。
        os.replace(staged_csv, csv_target)
        published_csv = True
        os.replace(staged_json, json_target)
        published_json = True
        directory_fd = os.open(destination_root, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except Exception:
        if published_json and json_target.exists():
            json_target.unlink()
        if published_csv and csv_target.exists():
            csv_target.unlink()
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    summary["checkpoint_csv_path"] = csv_target.as_posix()
    summary["checkpoint_json_path"] = json_target.as_posix()
    if not summary["passed"]:
        raise RawCheckpointError(f"BY2 raw checkpoint failed: {phase}", summary=summary)
    return summary


def ensure_raw_checkpoint(
    *,
    raw_root: str | Path,
    hash_lock_path: str | Path,
    expected_lock_sha256: str,
    output_root: str | Path,
    phase: str,
    expected_full_lock_rows: int = 9980,
) -> dict[str, Any]:
    """Create a checkpoint once, or strictly revalidate its immutable pair.

    Resume must never overwrite a checkpoint.  When the pair already exists,
    this function re-hashes the same exact 22 raw files and requires the stored
    CSV bytes and JSON binding to match the fresh audit exactly.
    """

    destination = Path(output_root)
    stem = f"CANONICAL541_RAW_22_{phase}"
    csv_path = destination / f"{stem}.csv"
    json_path = destination / f"{stem}.json"
    if not csv_path.exists() and not json_path.exists():
        return write_raw_checkpoint(
            raw_root=raw_root,
            hash_lock_path=hash_lock_path,
            expected_lock_sha256=expected_lock_sha256,
            output_root=output_root,
            phase=phase,
            expected_full_lock_rows=expected_full_lock_rows,
        )
    if not csv_path.is_file() or not json_path.is_file() or csv_path.is_symlink() or json_path.is_symlink():
        raise RawCheckpointError(f"raw checkpoint pair is partial or unsafe: {stem}")

    root = _assert_no_symlink_components(raw_root, kind="raw root")
    lock_path = _assert_no_symlink_components(hash_lock_path, kind="raw hash lock")
    by2_lock, lock_sha, full_lock_rows = _validate_lock(
        lock_path,
        expected_lock_sha256=expected_lock_sha256,
        expected_full_lock_rows=expected_full_lock_rows,
    )
    rows, current = _audit_rows(root, by2_lock, phase)
    if not current["passed"]:
        raise RawCheckpointError(f"BY2 raw checkpoint revalidation failed: {phase}", summary=current)

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=_CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    expected_csv = buffer.getvalue().encode("utf-8")
    if csv_path.read_bytes() != expected_csv:
        raise RawCheckpointError(f"stored raw checkpoint CSV drift: {stem}")
    try:
        stored = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RawCheckpointError(f"stored raw checkpoint JSON is invalid: {stem}") from exc
    required = {
        "audit_phase": phase,
        "expected": 22,
        "verified": 22,
        "missing": 0,
        "mismatch": 0,
        "symlink_escape": 0,
        "raw_mutation": 0,
        "raw_hash_lock_sha256": lock_sha,
        "full_lock_rows": full_lock_rows,
        "by2_lock_rows": 22,
        "checkpoint_csv_sha256": sha256_file(csv_path),
        "checkpoint_pair_complete": True,
        "trace_used_online": False,
        "old_provider_solver_input": False,
        "passed": True,
    }
    mismatch = {key: (stored.get(key), value) for key, value in required.items()
                if stored.get(key) != value}
    if mismatch or stored.get("verified_hashes") != current["verified_hashes"]:
        raise RawCheckpointError(f"stored raw checkpoint JSON binding drift: {stem}; {mismatch}")
    return {**stored, "resume_revalidated": True}
