"""Pinned-source verification, runtime mirrors, and file-access guards."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePath
from typing import Any, Iterable, Mapping, Sequence

from .constants import (
    FORBIDDEN_ROLE_TOKENS,
    OFFICIAL_COMMIT,
    OFFICIAL_NAMED_HASHES,
    OFFICIAL_NAMED_SIZES,
    OFFICIAL_REPOSITORY,
    OFFICIAL_TREE,
)


class SourceIdentityError(RuntimeError):
    """The external source or a runtime source mirror is not exact."""


class ForbiddenInputError(RuntimeError):
    """A path or role crosses the LC02 native-input boundary."""


def sha256_file(path: str | Path, *, limit: int | None = None) -> str:
    source = Path(path)
    digest = hashlib.sha256()
    remaining = limit
    with source.open("rb") as handle:
        while True:
            size = 4 * 1024 * 1024 if remaining is None else min(4 * 1024 * 1024, remaining)
            if size <= 0:
                break
            chunk = handle.read(size)
            if not chunk:
                break
            digest.update(chunk)
            if remaining is not None:
                remaining -= len(chunk)
    if remaining is not None and remaining != 0:
        raise SourceIdentityError(f"file shorter than declared prefix: {source}")
    return digest.hexdigest()


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=check,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SourceIdentityError(f"git {' '.join(args)} failed for {root}: {exc}") from exc


def _tracked_clean(root: Path) -> tuple[bool, list[str]]:
    # Generated ignored files do not alter the official tracked source.  The
    # runtime never writes into this checkout, but the gate is deliberately
    # expressed in tracked-source terms.
    result = _git(root, "status", "--porcelain=v1", "--untracked-files=no")
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    return not lines, lines


def verify_source_identity(root: str | Path) -> dict[str, Any]:
    """Verify commit, whole-tree OID, detached state, cleanliness, and hashes."""

    source = Path(root).expanduser().resolve(strict=True)
    if not (source / ".git").exists():
        raise SourceIdentityError(f"official checkout is not a Git worktree: {source}")
    commit = _git(source, "rev-parse", "HEAD").stdout.strip()
    tree = _git(source, "rev-parse", "HEAD^{tree}").stdout.strip()
    symbolic = _git(source, "symbolic-ref", "-q", "HEAD", check=False)
    detached = symbolic.returncode != 0
    tracked_clean, tracked_changes = _tracked_clean(source)
    remote_lines = _git(source, "remote", "get-url", "--all", "origin").stdout.splitlines()
    origin_urls = tuple(line.strip() for line in remote_lines if line.strip())

    named: dict[str, dict[str, Any]] = {}
    issues: list[str] = []
    for relative, expected_hash in OFFICIAL_NAMED_HASHES.items():
        path = source / relative
        if not path.is_file():
            named[relative] = {"exists": False, "expected_sha256": expected_hash}
            issues.append(f"missing:{relative}")
            continue
        actual_hash = sha256_file(path)
        actual_size = path.stat().st_size
        expected_size = OFFICIAL_NAMED_SIZES.get(relative)
        ok = actual_hash == expected_hash and (
            expected_size is None or actual_size == expected_size
        )
        named[relative] = {
            "exists": True,
            "bytes": actual_size,
            "expected_bytes": expected_size,
            "sha256": actual_hash,
            "expected_sha256": expected_hash,
            "pass": ok,
        }
        if not ok:
            issues.append(f"named_identity:{relative}")

    if commit != OFFICIAL_COMMIT:
        issues.append("commit")
    if tree != OFFICIAL_TREE:
        issues.append("tree")
    if not detached:
        issues.append("not_detached")
    if not tracked_clean:
        issues.append("tracked_dirty")
    normalized_origins = {url.removesuffix(".git") for url in origin_urls}
    if OFFICIAL_REPOSITORY.removesuffix(".git") not in normalized_origins:
        issues.append("origin")

    payload = {
        "schema_version": "ginav2021.source_lock.v1",
        "official_repository": OFFICIAL_REPOSITORY,
        "checkout": str(source),
        "commit": commit,
        "expected_commit": OFFICIAL_COMMIT,
        "tree_oid": tree,
        "expected_tree_oid": OFFICIAL_TREE,
        "detached_head": detached,
        "tracked_source_clean": tracked_clean,
        "tracked_changes": tracked_changes,
        "origin_urls": list(origin_urls),
        "named_files": named,
        "source_identity_pass": not issues,
        "issues": issues,
    }
    if issues:
        raise SourceIdentityError("official source identity mismatch: " + ",".join(issues))
    return payload


def materialize_official_checkout(destination: str | Path) -> dict[str, Any]:
    """Create the one authorized detached external checkout if it is absent."""

    target = Path(destination).expanduser().resolve(strict=False)
    if target.exists():
        return verify_source_identity(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            ["git", "clone", "--no-checkout", OFFICIAL_REPOSITORY, str(target)],
            check=True,
            timeout=300,
        )
        subprocess.run(
            ["git", "-C", str(target), "switch", "--detach", OFFICIAL_COMMIT],
            check=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SourceIdentityError(f"cannot materialize official checkout: {exc}") from exc
    return verify_source_identity(target)


RUNTIME_MIRROR_EXCLUDED_PREFIXES = ("data/", "result/")


def _tracked_files(root: Path) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
        timeout=60,
    )
    return tuple(
        item.decode("utf-8", errors="strict")
        for item in result.stdout.split(b"\0")
        if item
    )


def materialize_runtime_source_mirror(
    official_root: str | Path,
    mirror_root: str | Path,
) -> dict[str, Any]:
    """Copy exact tracked code without opening old tracked result payloads.

    The controlling whole-tree identity is proven on ``official_root`` first.
    ``data/`` and ``result/`` are deliberately not copied: the former is
    supplied source-explicitly and the latter contains denied historical
    runtime output.  An empty result directory is created for initoutfile.
    """

    source = Path(official_root).expanduser().resolve(strict=True)
    identity = verify_source_identity(source)
    destination = Path(mirror_root).expanduser().resolve(strict=False)
    if destination.exists():
        raise SourceIdentityError(f"runtime mirror already exists: {destination}")
    destination.mkdir(parents=True, exist_ok=False)

    copied: dict[str, str] = {}
    excluded: list[str] = []
    for relative in _tracked_files(source):
        if relative.startswith(RUNTIME_MIRROR_EXCLUDED_PREFIXES):
            excluded.append(relative)
            continue
        src = source / relative
        dst = destination / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_symlink():
            os.symlink(os.readlink(src), dst)
        elif src.is_file():
            shutil.copy2(src, dst)
            copied[relative] = sha256_file(dst)
        else:
            raise SourceIdentityError(f"unsupported tracked entry in source mirror: {relative}")
    (destination / "result").mkdir(exist_ok=False)

    for relative, digest in copied.items():
        if sha256_file(source / relative) != digest:
            raise SourceIdentityError(f"source mirror parity mismatch: {relative}")
    for relative, expected in OFFICIAL_NAMED_HASHES.items():
        if relative.startswith(RUNTIME_MIRROR_EXCLUDED_PREFIXES):
            continue
        if copied.get(relative) != expected:
            raise SourceIdentityError(f"named source absent or changed in mirror: {relative}")

    return {
        "schema_version": "ginav2021.runtime_source_mirror.v1",
        "controlling_commit": identity["commit"],
        "controlling_tree_oid": identity["tree_oid"],
        "mirror_root": str(destination),
        "copied_tracked_file_count": len(copied),
        "copied_file_sha256": copied,
        "excluded_tracked_paths": excluded,
        "excluded_policy": {
            "data": "source_explicit_runtime_inputs_only",
            "result": "historical_GINav_runtime_never_opened_or_copied",
        },
        "empty_result_directory_created": True,
    }


def verify_runtime_mirror(mirror_root: str | Path, manifest: Mapping[str, Any]) -> None:
    root = Path(mirror_root).resolve(strict=True)
    copied = manifest.get("copied_file_sha256")
    if not isinstance(copied, Mapping) or not copied:
        raise SourceIdentityError("runtime mirror manifest has no copied-file registry")
    for relative, expected in copied.items():
        path = root / str(relative)
        if not path.is_file() or sha256_file(path) != expected:
            raise SourceIdentityError(f"runtime mirror changed: {relative}")


def _normalized_path_text(path: str | Path) -> str:
    return str(path).replace("\\", "/").casefold()


def forbidden_path_hits(path: str | Path) -> tuple[str, ...]:
    text = _normalized_path_text(path)
    return tuple(token for token in FORBIDDEN_ROLE_TOKENS if token.casefold() in text)


def assert_role_name_allowed(role: str) -> None:
    hits = forbidden_path_hits(role)
    if hits:
        raise ForbiddenInputError(f"forbidden input role {role!r}: {','.join(hits)}")


def assert_gnss1_only_path(path: str | Path) -> None:
    text = _normalized_path_text(path)
    name = PurePath(text).name
    if "gnss1" not in name or "gnss2" in text:
        raise ForbiddenInputError(f"GNSS adapter is not GNSS1-only: {path}")


@dataclass
class AccessLedger:
    """Explicit application-level path ledger for adapters and MATLAB logs."""

    records: list[dict[str, Any]] = field(default_factory=list)
    authorized_runtime_reads: set[str] = field(default_factory=set)

    def authorize_runtime_read(self, path: str | Path) -> None:
        hits = forbidden_path_hits(path)
        if hits:
            raise ForbiddenInputError(
                f"cannot authorize forbidden runtime input {path}: {','.join(hits)}"
            )
        self.authorized_runtime_reads.add(_normalized_path_text(path))

    def record(self, path: str | Path, *, role: str, operation: str = "read") -> None:
        assert_role_name_allowed(role)
        hits = forbidden_path_hits(path)
        if hits:
            raise ForbiddenInputError(
                f"forbidden path for {role}: {path} ({','.join(hits)})"
            )
        self.records.append(
            {"sequence": len(self.records) + 1, "operation": operation,
             "role": role, "path": str(Path(path).resolve(strict=False))}
        )

    def import_matlab_fopen_log(self, path: str | Path) -> None:
        source = Path(path)
        if not source.is_file():
            raise ForbiddenInputError(f"MATLAB fopen ledger is missing: {source}")
        for line_number, raw in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            if not raw.strip():
                continue
            parts = raw.split("\t", 2)
            if len(parts) != 3:
                raise ForbiddenInputError(
                    f"malformed MATLAB fopen ledger row {line_number}"
                )
            _, mode, opened = parts
            hits = forbidden_path_hits(opened)
            unauthorized_read = (
                mode.casefold().startswith("r")
                and _normalized_path_text(opened) not in self.authorized_runtime_reads
            )
            self.records.append(
                {
                    "sequence": len(self.records) + 1,
                    "operation": "matlab_fopen",
                    "role": "official_matlab_runtime",
                    "path": opened,
                    "mode": mode,
                    "source_line": line_number,
                    "forbidden_hits": list(hits),
                    "authorized_runtime_read": not unauthorized_read,
                }
            )
            if hits:
                raise ForbiddenInputError(
                    f"MATLAB opened forbidden path {opened}: {','.join(hits)}"
                )
            if unauthorized_read:
                raise ForbiddenInputError(
                    f"MATLAB opened undeclared read path {opened}"
                )

    def audit(self) -> dict[str, Any]:
        bad = [row for row in self.records if row.get("forbidden_hits")]
        unauthorized = [
            row for row in self.records
            if row.get("authorized_runtime_read") is False
        ]
        return {
            "schema_version": "ginav2021.file_access_audit.v1",
            "open_record_count": len(self.records),
            "forbidden_open_count": len(bad),
            "forbidden_records": bad,
            "unauthorized_runtime_read_count": len(unauthorized),
            "unauthorized_runtime_read_records": unauthorized,
            "authorized_runtime_read_paths": sorted(self.authorized_runtime_reads),
            "records": self.records,
            "trace_open_count": sum("trace" in forbidden_path_hits(row["path"]) for row in self.records),
            "reference_open_count": sum("reference" in forbidden_path_hits(row["path"]) for row in self.records),
            "gnss2_open_count": sum("gnss2" in forbidden_path_hits(row["path"]) for row in self.records),
            "other_method_open_count": sum(
                bool(set(forbidden_path_hits(row["path"])) & {
                    "lc01", "hartley", "ext01", "ext02", "ext03", "ext04",
                    "canonical-541", "canonical541", "legsa_output",
                })
                for row in self.records
            ),
            "pass": not bad and not unauthorized,
        }


@dataclass
class CoreCleanlinessGuard:
    """Snapshot official checkout and runtime mirror around one official run."""

    run_id: str
    official_root: Path
    mirror_root: Path
    mirror_manifest: Mapping[str, Any]
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None

    def __enter__(self) -> "CoreCleanlinessGuard":
        self.before = verify_source_identity(self.official_root)
        verify_runtime_mirror(self.mirror_root, self.mirror_manifest)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        self.after = verify_source_identity(self.official_root)
        verify_runtime_mirror(self.mirror_root, self.mirror_manifest)
        return False

    def report(self) -> dict[str, Any]:
        if self.before is None or self.after is None:
            raise SourceIdentityError("cleanliness guard did not complete")
        return {
            "schema_version": "ginav2021.core_cleanliness_before_after.v1",
            "run_id": self.run_id,
            "before": self.before,
            "after": self.after,
            "commit_unchanged": self.before["commit"] == self.after["commit"] == OFFICIAL_COMMIT,
            "tree_unchanged": self.before["tree_oid"] == self.after["tree_oid"] == OFFICIAL_TREE,
            "tracked_source_clean_before": self.before["tracked_source_clean"],
            "tracked_source_clean_after": self.after["tracked_source_clean"],
            "source_patch_count": 0,
            "pass": True,
        }


def write_json(path: str | Path, payload: Mapping[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, destination)
    return destination
