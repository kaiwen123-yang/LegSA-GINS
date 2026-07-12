#!/usr/bin/env python3
"""Recover an exact final_v23 tag tree from the authorized archive.

This command is deliberately limited to static Git provenance.  It extracts an
isolated object database, verifies the named tag with the system ``git``, and
materializes a narrow source/build allowlist.  It never executes archived code,
builds a solver, reads runtime results, or uses the archive working-tree HEAD.

All machine-local paths are required CLI arguments.  The recovery tree is
published by one same-filesystem rename only after the archive post-read hash
and stat checks pass.
"""

from __future__ import annotations

import argparse
import configparser
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import uuid
import zipfile
import zlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Mapping, Sequence


SCHEMA_VERSION = "clean1r2.final_v23_tag_source_recovery.v1"
DEFAULT_TAG_NAME = "final-v23-freeze"
DEFAULT_ARCHIVE_REPO_PREFIX = "KF-GINS"
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
HEX64_RE = re.compile(r"^[0-9a-f]{64}$")

REQUIRED_TAG_PATHS = (
    "CMakeLists.txt",
    "scripts/run_final_mainline.py",
    "docs/final_mainline_config.md",
    "config/kf-gins.yaml",
)

REQUIRED_SOLVER_WRITER_PATHS = (
    "CMakeLists.txt",
    "config/kf-gins.yaml",
    "src/kf_gins.cpp",
    "src/common/earth.h",
    "src/common/rotation.h",
    "src/common/types.h",
    "src/fileio/filebase.h",
    "src/fileio/fileloader.cc",
    "src/fileio/fileloader.h",
    "src/fileio/filesaver.cc",
    "src/fileio/filesaver.h",
    "src/kf-gins/gi_engine.cpp",
    "src/kf-gins/gi_engine.h",
    "src/kf-gins/insmech.cpp",
    "src/kf-gins/insmech.h",
    "src/kf-gins/kf_gins_types.h",
)

ANCILLARY_ROLE_PATHS: Mapping[str, str] = {
    "bin/process_data.py": "input_builder",
    "bin/evaluate_nav_trace_kfgins_v2.py": "evaluator",
    "scripts/run_final_mainline.py": "runtime_runner",
    "docs/final_mainline_config.md": "runtime_config_note",
}

EXPECTED_MISSING_TAG_ANCILLARY_PATHS = frozenset(
    {
        "bin/process_data.py",
        "bin/evaluate_nav_trace_kfgins_v2.py",
    }
)

DEPENDENCY_ALIASES: Mapping[str, frozenset[str]] = {
    "eigen": frozenset({"eigen", "eigen3", "eigen-3.3.9"}),
    "yaml_cpp": frozenset({"yaml-cpp", "yaml-cpp-0.7.0"}),
    "abseil": frozenset({"abseil", "abseil-cpp", "abseil-cpp-20220623.1"}),
}

DOC_MARKERS = ("final_v23", "final-v23", "final_mainline", "final-mainline")


class RecoveryError(RuntimeError):
    """Fail-closed recovery error."""


@dataclass(frozen=True)
class ArchiveSnapshot:
    device: int
    inode: int
    mode: int
    size: int
    mtime_ns: int
    sha256: str


@dataclass(frozen=True)
class TreeEntry:
    mode: str
    object_type: str
    object_id: str
    size: int | None
    path: str


@dataclass(frozen=True)
class SourceSelection:
    entry: TreeEntry
    logical_role: str
    selection_reason: str
    dependency_root: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_posix_relative(value: str, *, role: str) -> str:
    """Return a strict relative POSIX path or raise."""

    if not value or "\x00" in value or "\\" in value:
        raise RecoveryError(f"unsafe {role}: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise RecoveryError(f"unsafe {role}: {value!r}")
    normalized = path.as_posix()
    if normalized != value.rstrip("/"):
        raise RecoveryError(f"non-canonical {role}: {value!r}")
    return normalized


def zipinfo_kind(info: zipfile.ZipInfo) -> str:
    """Classify a ZIP member without following or creating links."""

    unix_mode = (info.external_attr >> 16) & 0xFFFF
    if info.create_system == 3 and unix_mode:
        file_type = stat.S_IFMT(unix_mode)
        if file_type == stat.S_IFLNK:
            return "symlink"
        if file_type == stat.S_IFDIR:
            return "directory"
        if file_type == stat.S_IFREG:
            return "file"
        if file_type != 0:
            return "special"
    return "directory" if info.is_dir() else "file"


def selected_git_database_member(name: str, repo_prefix: str) -> bool:
    """Whether a canonical archive member is needed by isolated Git."""

    base = f"{repo_prefix}/.git/"
    if not name.startswith(base):
        return False
    relative = name[len(base) :].rstrip("/")
    if not relative:
        return False
    return (
        relative.startswith("objects/")
        or relative.startswith("refs/")
        or relative in {"config", "HEAD", "packed-refs", "shallow"}
    )


def safe_lstat_directory_chain(path: Path, *, create: bool) -> None:
    """Validate every path component with lstat, optionally creating it."""

    absolute = Path(os.path.abspath(os.fspath(path)))
    if not absolute.is_absolute():  # pragma: no cover - os.path.abspath guarantees this
        raise RecoveryError(f"directory must be absolute: {path}")
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            if not create:
                raise RecoveryError(f"missing directory component: {current}")
            os.mkdir(current, 0o755)
            metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode):
            raise RecoveryError(f"symlink directory component denied: {current}")
        if not stat.S_ISDIR(metadata.st_mode):
            raise RecoveryError(f"non-directory path component: {current}")


def safe_destination(root: Path, relative: str) -> Path:
    normalized = normalize_posix_relative(relative, role="destination")
    destination = root.joinpath(*PurePosixPath(normalized).parts)
    root_text = os.path.abspath(os.fspath(root))
    destination_text = os.path.abspath(os.fspath(destination))
    if os.path.commonpath([root_text, destination_text]) != root_text:
        raise RecoveryError(f"destination escaped recovery root: {relative}")
    return Path(destination_text)


def ensure_safe_parent(root: Path, destination: Path) -> None:
    root_abs = Path(os.path.abspath(os.fspath(root)))
    parent_abs = Path(os.path.abspath(os.fspath(destination.parent)))
    if os.path.commonpath([os.fspath(root_abs), os.fspath(parent_abs)]) != os.fspath(root_abs):
        raise RecoveryError(f"parent escaped recovery root: {destination}")
    current = root_abs
    relative_parts = parent_abs.relative_to(root_abs).parts
    safe_lstat_directory_chain(root_abs, create=False)
    for part in relative_parts:
        current = current / part
        try:
            metadata = os.lstat(current)
        except FileNotFoundError:
            os.mkdir(current, 0o755)
            metadata = os.lstat(current)
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise RecoveryError(f"unsafe destination parent: {current}")


def atomic_write_bytes(root: Path, relative: str, data: bytes, mode: int = 0o644) -> Path:
    destination = safe_destination(root, relative)
    ensure_safe_parent(root, destination)
    try:
        os.lstat(destination)
    except FileNotFoundError:
        pass
    else:
        raise RecoveryError(f"refusing to overwrite recovery output: {destination}")
    temporary = destination.parent / f".{destination.name}.tmp-{uuid.uuid4().hex}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, mode)
    try:
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode, follow_symlinks=False)
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return destination


def write_json(root: Path, relative: str, payload: object) -> None:
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    atomic_write_bytes(root, relative, data)


def write_csv(root: Path, relative: str, fieldnames: Sequence[str], rows: Sequence[Mapping[str, object]]) -> None:
    destination = safe_destination(root, relative)
    ensure_safe_parent(root, destination)
    try:
        os.lstat(destination)
    except FileNotFoundError:
        pass
    else:
        raise RecoveryError(f"refusing to overwrite recovery output: {destination}")
    temporary = destination.parent / f".{destination.name}.tmp-{uuid.uuid4().hex}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o644)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="", closefd=True) as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def quarantine_failed_stage(stage: Path, intended_target: Path, error: BaseException) -> Path | None:
    """Mark an unpublished attempt as non-evidence and move it out of staging."""

    try:
        metadata = os.lstat(stage)
    except FileNotFoundError:
        return None
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
        raise RecoveryError(f"cannot quarantine unsafe staging root: {stage}")
    marker = {
        "schema_version": SCHEMA_VERSION,
        "evidence_eligible": False,
        "disposition": "QUARANTINED_FAILED_UNPUBLISHED_ATTEMPT",
        "intended_target": os.fspath(intended_target),
        "error_type": type(error).__name__,
        "error": str(error),
        "quarantined_at_utc": utc_now(),
    }
    write_json(stage, "NON_EVIDENCE_FAILED_ATTEMPT.json", marker)
    quarantine = intended_target.parent / (
        f"{intended_target.name}.FAILED_NON_EVIDENCE-{uuid.uuid4().hex}"
    )
    os.replace(stage, quarantine)
    return quarantine


def failed_quarantine_roots(target: Path) -> list[Path]:
    """List marked sibling quarantines without following symlinks."""

    prefix = f"{target.name}.FAILED_NON_EVIDENCE-"
    rows: list[Path] = []
    with os.scandir(target.parent) as entries:
        for entry in entries:
            if not entry.name.startswith(prefix) or not entry.is_dir(follow_symlinks=False):
                continue
            marker = Path(entry.path) / "NON_EVIDENCE_FAILED_ATTEMPT.json"
            try:
                marker_metadata = os.lstat(marker)
            except FileNotFoundError:
                continue
            if stat.S_ISREG(marker_metadata.st_mode) and not stat.S_ISLNK(marker_metadata.st_mode):
                rows.append(Path(entry.path))
    return sorted(rows, key=os.fspath)


def hash_fd(descriptor: int) -> str:
    digest = hashlib.sha256()
    os.lseek(descriptor, 0, os.SEEK_SET)
    while True:
        chunk = os.read(descriptor, 8 * 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    os.lseek(descriptor, 0, os.SEEK_SET)
    return digest.hexdigest()


def snapshot_fd(descriptor: int, digest: str) -> ArchiveSnapshot:
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode):
        raise RecoveryError("archive descriptor is not a regular file")
    return ArchiveSnapshot(
        device=metadata.st_dev,
        inode=metadata.st_ino,
        mode=stat.S_IMODE(metadata.st_mode),
        size=metadata.st_size,
        mtime_ns=metadata.st_mtime_ns,
        sha256=digest,
    )


def validate_archive_path_snapshot(path: Path, expected: ArchiveSnapshot) -> None:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise RecoveryError("archive pathname became a symlink or non-regular file")
    identity = (metadata.st_dev, metadata.st_ino, stat.S_IMODE(metadata.st_mode), metadata.st_size, metadata.st_mtime_ns)
    expected_identity = (
        expected.device,
        expected.inode,
        expected.mode,
        expected.size,
        expected.mtime_ns,
    )
    if identity != expected_identity:
        raise RecoveryError("archive path stat changed during recovery")


def extract_zip_file(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    root: Path,
    relative: str,
) -> dict[str, object]:
    if info.flag_bits & 0x1:
        raise RecoveryError(f"encrypted ZIP member denied: {info.filename}")
    if zipinfo_kind(info) != "file":
        raise RecoveryError(f"non-regular ZIP member denied: {info.filename}")
    destination = safe_destination(root, relative)
    ensure_safe_parent(root, destination)
    try:
        os.lstat(destination)
    except FileNotFoundError:
        pass
    else:
        raise RecoveryError(f"duplicate extraction destination: {destination}")
    temporary = destination.parent / f".{destination.name}.tmp-{uuid.uuid4().hex}"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o600)
    digest = hashlib.sha256()
    crc = 0
    size = 0
    try:
        with archive.open(info, "r") as source, os.fdopen(descriptor, "wb", closefd=True) as output:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                digest.update(chunk)
                crc = zlib.crc32(chunk, crc)
                size += len(chunk)
            output.flush()
            os.fsync(output.fileno())
        if size != info.file_size:
            raise RecoveryError(f"ZIP size mismatch for {info.filename}: {size} != {info.file_size}")
        if (crc & 0xFFFFFFFF) != info.CRC:
            raise RecoveryError(f"ZIP CRC mismatch for {info.filename}")
        os.chmod(temporary, 0o644, follow_symlinks=False)
        os.replace(temporary, destination)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return {
        "archive_member": info.filename,
        "destination_relative": relative,
        "member_size": info.file_size,
        "compressed_size": info.compress_size,
        "crc32": f"{info.CRC:08x}",
        "crc32_verified": True,
        "sha256": digest.hexdigest(),
        "encrypted": False,
        "member_kind": "file",
    }


def read_zip_member_hash(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> tuple[str, int, str]:
    if info.flag_bits & 0x1 or zipinfo_kind(info) != "file":
        raise RecoveryError(f"cannot hash unsafe ZIP member: {info.filename}")
    digest = hashlib.sha256()
    crc = 0
    size = 0
    with archive.open(info, "r") as source:
        while True:
            chunk = source.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            crc = zlib.crc32(chunk, crc)
            size += len(chunk)
    if size != info.file_size or (crc & 0xFFFFFFFF) != info.CRC:
        raise RecoveryError(f"hash read failed CRC/size for {info.filename}")
    return digest.hexdigest(), size, f"{info.CRC:08x}"


def validate_archive_git_config(config_path: Path) -> dict[str, object]:
    data = config_path.read_bytes()
    if b"\x00" in data:
        raise RecoveryError("archive Git config contains NUL")
    text = data.decode("utf-8", errors="strict")
    lowered = text.lower()
    denied_tokens = (
        "[include]",
        "[includeif ",
        "hookspath",
        "fsmonitor",
        "alternaterefscommand",
        "worktree =",
        "skiplist",
        "[fsck]",
        "[extensions]",
    )
    hits = [token for token in denied_tokens if token in lowered]
    if hits:
        raise RecoveryError(f"archive Git config contains denied behavior: {hits}")
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.read_string(text)
    repository_format = parser.get("core", "repositoryformatversion", fallback="")
    if repository_format != "0":
        raise RecoveryError(f"unsupported Git repository format: {repository_format!r}")
    return {
        "sha256": sha256_bytes(data),
        "repository_format_version": repository_format,
        "sections": parser.sections(),
        "denied_behavior_hits": [],
    }


def isolated_git_command(git_dir: Path, args: Sequence[str]) -> list[str]:
    return [
        "git",
        "--no-replace-objects",
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        f"--git-dir={git_dir}",
        *args,
    ]


def isolated_git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "LANG": "C",
            "LC_ALL": "C",
        }
    )
    environment.pop("GIT_WORK_TREE", None)
    environment.pop("GIT_COMMON_DIR", None)
    environment.pop("GIT_OBJECT_DIRECTORY", None)
    environment.pop("GIT_ALTERNATE_OBJECT_DIRECTORIES", None)
    return environment


def run_git(
    git_dir: Path,
    args: Sequence[str],
    *,
    text_mode: bool = True,
) -> tuple[str | bytes, str | bytes, dict[str, object]]:
    command = isolated_git_command(git_dir, args)
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text_mode,
        env=isolated_git_environment(),
    )
    audit = {
        "argv": command,
        "returncode": result.returncode,
        "stdout_sha256": sha256_bytes(
            result.stdout.encode("utf-8") if isinstance(result.stdout, str) else result.stdout
        ),
        "stderr_sha256": sha256_bytes(
            result.stderr.encode("utf-8") if isinstance(result.stderr, str) else result.stderr
        ),
    }
    if result.returncode != 0:
        stderr = result.stderr if isinstance(result.stderr, str) else result.stderr.decode("utf-8", "replace")
        raise RecoveryError(f"isolated Git command failed ({args!r}): {stderr.strip()}")
    return result.stdout, result.stderr, audit


def classify_fsck_output(stdout: str, stderr: str) -> dict[str, object]:
    lines = [line.strip() for line in (stdout + "\n" + stderr).splitlines() if line.strip()]
    dangling = [line for line in lines if line.startswith("dangling ")]
    unexpected = [line for line in lines if not line.startswith("dangling ")]
    return {
        "line_count": len(lines),
        "dangling_count": len(dangling),
        "dangling": dangling,
        "unexpected": unexpected,
        "authoritative_pass": not unexpected,
    }


def parse_ls_tree_z(payload: bytes) -> list[TreeEntry]:
    entries: list[TreeEntry] = []
    for record in payload.split(b"\x00"):
        if not record:
            continue
        try:
            header, raw_path = record.split(b"\t", 1)
            mode, object_type, object_id, raw_size = header.decode("ascii").split()
            path = raw_path.decode("utf-8", errors="strict")
        except (ValueError, UnicodeDecodeError) as error:
            raise RecoveryError("malformed git ls-tree record") from error
        normalized = normalize_posix_relative(path, role="tag tree path")
        if object_type not in {"blob", "commit"}:
            raise RecoveryError(f"unexpected recursive tree object type: {object_type}")
        if not HEX40_RE.fullmatch(object_id):
            raise RecoveryError(f"invalid Git object id: {object_id}")
        size = None if raw_size == "-" else int(raw_size)
        entries.append(TreeEntry(mode, object_type, object_id, size, normalized))
    if len({entry.path for entry in entries}) != len(entries):
        raise RecoveryError("duplicate paths in tag tree")
    return entries


def dependency_roots(entries: Sequence[TreeEntry]) -> dict[str, str]:
    roots_by_name: dict[str, set[str]] = {name: set() for name in DEPENDENCY_ALIASES}
    for entry in entries:
        parts = PurePosixPath(entry.path).parts
        if len(parts) < 3 or parts[0] != "ThirdParty":
            continue
        component = parts[1].lower()
        for name, aliases in DEPENDENCY_ALIASES.items():
            if component in aliases:
                roots_by_name[name].add(f"ThirdParty/{parts[1]}")
    resolved: dict[str, str] = {}
    for name, candidates in roots_by_name.items():
        if len(candidates) != 1:
            raise RecoveryError(
                f"dependency root identity is not unique for {name}: {sorted(candidates)}"
            )
        resolved[name] = next(iter(candidates))
    return resolved


def select_source_entries(entries: Sequence[TreeEntry]) -> tuple[list[SourceSelection], dict[str, str]]:
    roots = dependency_roots(entries)
    selected: list[SourceSelection] = []
    for entry in entries:
        path = entry.path
        role = ""
        reason = ""
        dependency = ""
        if path == "CMakeLists.txt":
            role, reason = "top_level_build_spec", "exact top-level CMake allowlist"
        elif path.startswith("src/"):
            role, reason = "solver_source", "exact tag src/** allowlist"
        elif path == "bin/process_data.py":
            role, reason = "input_builder", "exact final_v23 builder allowlist"
        elif path == "bin/evaluate_nav_trace_kfgins_v2.py":
            role, reason = "evaluator", "exact final_v23 evaluator allowlist"
        elif path == "scripts/run_final_mainline.py":
            role, reason = "runtime_runner", "exact final_v23 runner allowlist"
        elif path == "config/kf-gins.yaml":
            role, reason = "runtime_config", "canonical final_v23 config allowlist"
        elif path.startswith("docs/") and any(marker in path.lower() for marker in DOC_MARKERS):
            role, reason = "final_v23_documentation", "final_v23/final_mainline doc allowlist"
        else:
            for dependency_name, root in roots.items():
                if path.startswith(f"{root}/"):
                    role = "build_dependency"
                    reason = f"canonical {dependency_name} dependency allowlist"
                    dependency = root
                    break
        if not role:
            continue
        if entry.object_type != "blob" or entry.mode not in {"100644", "100755"}:
            raise RecoveryError(
                f"selected tag source is not a regular blob: {entry.path} "
                f"({entry.mode} {entry.object_type})"
            )
        selected.append(SourceSelection(entry, role, reason, dependency))
    selected.sort(key=lambda item: item.entry.path)
    paths = {item.entry.path for item in selected}
    missing = [path for path in REQUIRED_TAG_PATHS if path not in paths]
    if missing:
        raise RecoveryError(f"required exact tag paths are missing: {missing}")
    missing_solver_writer = [path for path in REQUIRED_SOLVER_WRITER_PATHS if path not in paths]
    if missing_solver_writer:
        raise RecoveryError(
            f"required solver/writer tag paths are missing: {missing_solver_writer}"
        )
    return selected, roots


def source_completeness(selected: Sequence[SourceSelection], roots: Mapping[str, str]) -> dict[str, object]:
    paths = {item.entry.path for item in selected}
    basenames = {PurePosixPath(path).name.lower() for path in paths if path.startswith("src/")}
    categories = {
        "top_cmake": "CMakeLists.txt" in paths,
        "main": "src/kf_gins.cpp" in paths,
        "file_loader": any(name.startswith("fileloader") for name in basenames),
        "file_base": any(name.startswith("filebase") for name in basenames),
        "file_saver": any(name.startswith("filesaver") or name.startswith("file_saver") for name in basenames),
        "earth": any(name.startswith("earth") for name in basenames),
        "rotation": any(name.startswith("rotation") for name in basenames),
        "types": any("types" in name for name in basenames),
        "gi_engine": any(name.startswith("gi_engine") for name in basenames),
        "insmech": any(name.startswith("insmech") for name in basenames),
        "eigen_dependency": "eigen" in roots,
        "yaml_cpp_dependency": "yaml_cpp" in roots,
        "abseil_dependency": "abseil" in roots,
    }
    return {
        "static_build_source_closure": all(categories.values()),
        "categories": categories,
        "dependency_roots": dict(roots),
        "build_executed": False,
        "claim_ceiling": "static source/build dependency closure only; build not executed",
    }


def materialize_blobs(
    git_dir: Path,
    source_root: Path,
    selected: Sequence[SourceSelection],
) -> list[dict[str, object]]:
    command = isolated_git_command(git_dir, ["cat-file", "--batch"])
    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=isolated_git_environment(),
    )
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    rows: list[dict[str, object]] = []
    try:
        for selection in selected:
            entry = selection.entry
            process.stdin.write((entry.object_id + "\n").encode("ascii"))
            process.stdin.flush()
            header = process.stdout.readline().decode("ascii", errors="strict").rstrip("\n")
            parts = header.split(" ")
            if len(parts) != 3:
                raise RecoveryError(f"malformed cat-file batch header: {header!r}")
            object_id, object_type, raw_size = parts
            size = int(raw_size)
            if object_id != entry.object_id or object_type != "blob" or size != entry.size:
                raise RecoveryError(f"cat-file identity mismatch for {entry.path}: {header}")
            destination = safe_destination(source_root, entry.path)
            ensure_safe_parent(source_root, destination)
            try:
                os.lstat(destination)
            except FileNotFoundError:
                pass
            else:
                raise RecoveryError(f"duplicate tag materialization destination: {destination}")
            temporary = destination.parent / f".{destination.name}.tmp-{uuid.uuid4().hex}"
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            descriptor = os.open(temporary, flags, 0o600)
            digest = hashlib.sha256()
            remaining = size
            try:
                with os.fdopen(descriptor, "wb", closefd=True) as output:
                    while remaining:
                        chunk = process.stdout.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise RecoveryError(f"truncated cat-file blob: {entry.path}")
                        output.write(chunk)
                        digest.update(chunk)
                        remaining -= len(chunk)
                    delimiter = process.stdout.read(1)
                    if delimiter != b"\n":
                        raise RecoveryError(f"missing cat-file delimiter: {entry.path}")
                    output.flush()
                    os.fsync(output.fileno())
                file_mode = 0o755 if entry.mode == "100755" else 0o644
                os.chmod(temporary, file_mode, follow_symlinks=False)
                os.replace(temporary, destination)
            except BaseException:
                try:
                    os.unlink(temporary)
                except FileNotFoundError:
                    pass
                raise
            rows.append(
                {
                    "path": entry.path,
                    "git_mode": entry.mode,
                    "git_type": entry.object_type,
                    "git_object_id": entry.object_id,
                    "size": size,
                    "sha256": digest.hexdigest(),
                    "logical_role": selection.logical_role,
                    "selection_reason": selection.selection_reason,
                    "dependency_root": selection.dependency_root,
                    "materialized_relative": f"tag_source/{entry.path}",
                }
            )
        process.stdin.close()
        returncode = process.wait(timeout=60)
        stderr = process.stderr.read().decode("utf-8", errors="replace")
        if returncode != 0:
            raise RecoveryError(f"cat-file --batch failed: {stderr.strip()}")
        if stderr.strip():
            raise RecoveryError(f"cat-file --batch emitted stderr: {stderr.strip()}")
    except BaseException:
        process.kill()
        process.wait()
        raise
    return rows


def working_tree_conflicts(
    archive: zipfile.ZipFile,
    info_by_name: Mapping[str, list[zipfile.ZipInfo]],
    repo_prefix: str,
    tag_commit: str,
    source_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for source in source_rows:
        path = str(source["path"])
        member = f"{repo_prefix}/{path}"
        candidates = info_by_name.get(member, [])
        archive_sha = ""
        archive_size: int | str = ""
        archive_crc = ""
        if not candidates:
            status = "MISSING_FROM_ARCHIVE_WORKING_TREE"
        elif len(candidates) != 1:
            status = "DUPLICATE_ARCHIVE_WORKING_TREE_MEMBER"
        elif zipinfo_kind(candidates[0]) != "file" or candidates[0].flag_bits & 0x1:
            status = "UNSAFE_ARCHIVE_WORKING_TREE_MEMBER"
        else:
            archive_sha, archive_size, archive_crc = read_zip_member_hash(archive, candidates[0])
            status = "HASH_MATCH" if archive_sha == source["sha256"] else "HASH_DIFFERENT"
        rows.append(
            {
                "path": path,
                "tag_commit": tag_commit,
                "tag_blob_object_id": source["git_object_id"],
                "tag_sha256": source["sha256"],
                "tag_size": source["size"],
                "archive_working_tree_member": member,
                "archive_working_tree_candidate_count": len(candidates),
                "archive_working_tree_sha256": archive_sha,
                "archive_working_tree_size": archive_size,
                "archive_working_tree_crc32": archive_crc,
                "comparison_status": status,
                "comparison_basis": "sha256_content_only",
                "mtime_used": False,
                "metric_used": False,
            }
        )
    return rows


def ancillary_role_audit(
    archive: zipfile.ZipFile,
    info_by_name: Mapping[str, list[zipfile.ZipInfo]],
    repo_prefix: str,
    entries: Sequence[TreeEntry],
    source_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Record tag presence and unique archive-static bindings for ancillary roles."""

    entry_by_path = {entry.path: entry for entry in entries}
    source_by_path = {str(row["path"]): row for row in source_rows}
    rows: list[dict[str, object]] = []
    for path, role in ANCILLARY_ROLE_PATHS.items():
        entry = entry_by_path.get(path)
        source = source_by_path.get(path)
        if (entry is None) != (source is None):
            raise RecoveryError(f"ancillary tag/source selection mismatch for {path}")
        member = f"{repo_prefix}/{path}"
        candidates = info_by_name.get(member, [])
        if len(candidates) != 1:
            raise RecoveryError(
                f"archive static ancillary member is not unique for {path}: {len(candidates)}"
            )
        info = candidates[0]
        if zipinfo_kind(info) != "file" or info.flag_bits & 0x1:
            raise RecoveryError(f"unsafe archive static ancillary member: {member}")
        archive_sha, archive_size, archive_crc = read_zip_member_hash(archive, info)
        present = entry is not None
        rows.append(
            {
                "logical_role": role,
                "logical_path": path,
                "tag_status": "PRESENT_IN_TAG" if present else "MISSING_FROM_TAG_ANCILLARY_ROLE",
                "tag_blob_object_id": "" if entry is None else entry.object_id,
                "tag_sha256": "" if source is None else source["sha256"],
                "tag_size": "" if entry is None else entry.size,
                "materialized_into_tag_source": present,
                "archive_static_member": member,
                "archive_static_candidate_count": 1,
                "archive_static_sha256": archive_sha,
                "archive_static_size": archive_size,
                "archive_static_crc32": archive_crc,
                "archive_static_binding_status": "UNIQUE_STATIC_MEMBER_REFERENCE_ONLY",
                "archive_static_materialized_into_tag_source": False,
                "archive_working_tree_head_used": False,
                "identity_basis": "tag_tree_presence_plus_unique_archive_member_content_hash",
            }
        )
    return rows


def tree_inventory_rows(entries: Sequence[TreeEntry], selected: Sequence[SourceSelection]) -> list[dict[str, object]]:
    selected_by_path = {item.entry.path: item for item in selected}
    rows: list[dict[str, object]] = []
    for entry in entries:
        selection = selected_by_path.get(entry.path)
        rows.append(
            {
                "path": entry.path,
                "mode": entry.mode,
                "object_type": entry.object_type,
                "object_id": entry.object_id,
                "size": "" if entry.size is None else entry.size,
                "selected": selection is not None,
                "logical_role": "" if selection is None else selection.logical_role,
                "selection_reason": "" if selection is None else selection.selection_reason,
            }
        )
    return rows


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--archive", required=True, type=Path)
    result.add_argument("--recovery-root", required=True, type=Path)
    result.add_argument("--log-root", required=True, type=Path)
    result.add_argument("--expected-archive-sha256", required=True)
    result.add_argument("--expected-tag-commit", required=True)
    result.add_argument("--tag-name", default=DEFAULT_TAG_NAME)
    result.add_argument("--archive-repo-prefix", default=DEFAULT_ARCHIVE_REPO_PREFIX)
    return result


def recover(args: argparse.Namespace) -> dict[str, object]:
    expected_archive_sha = args.expected_archive_sha256.lower()
    expected_commit = args.expected_tag_commit.lower()
    if not HEX64_RE.fullmatch(expected_archive_sha):
        raise RecoveryError("expected archive SHA256 must be 64 lowercase hex characters")
    if not HEX40_RE.fullmatch(expected_commit):
        raise RecoveryError("expected tag commit must be 40 lowercase hex characters")
    tag_name = normalize_posix_relative(args.tag_name, role="tag name")
    repo_prefix = normalize_posix_relative(args.archive_repo_prefix, role="archive repo prefix")

    archive_path = Path(os.path.abspath(os.fspath(args.archive)))
    recovery_root = Path(os.path.abspath(os.fspath(args.recovery_root)))
    log_root = Path(os.path.abspath(os.fspath(args.log_root)))
    if recovery_root == log_root:
        raise RecoveryError("recovery root and log root must differ")
    for target in (recovery_root, log_root):
        safe_lstat_directory_chain(target.parent, create=True)
        try:
            os.lstat(target)
        except FileNotFoundError:
            pass
        else:
            raise RecoveryError(f"target already exists; refusing overwrite: {target}")
    prior_failed_quarantines = failed_quarantine_roots(recovery_root)

    archive_metadata = os.lstat(archive_path)
    if stat.S_ISLNK(archive_metadata.st_mode) or not stat.S_ISREG(archive_metadata.st_mode):
        raise RecoveryError("archive must be a non-symlink regular file")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    archive_fd = os.open(archive_path, flags)

    stage_root = recovery_root.parent / f".{recovery_root.name}.stage-{uuid.uuid4().hex}"
    log_stage = log_root.parent / f".{log_root.name}.stage-{uuid.uuid4().hex}"
    command_audit: list[dict[str, object]] = []
    started_at = utc_now()
    try:
        os.mkdir(stage_root, 0o755)
        os.mkdir(log_stage, 0o755)
        safe_lstat_directory_chain(stage_root, create=False)
        safe_lstat_directory_chain(log_stage, create=False)
        git_dir = stage_root / "isolated_repo" / ".git"
        source_root = stage_root / "tag_source"
        safe_lstat_directory_chain(git_dir, create=True)
        safe_lstat_directory_chain(source_root, create=True)

        pre_sha = hash_fd(archive_fd)
        pre_snapshot = snapshot_fd(archive_fd, pre_sha)
        validate_archive_path_snapshot(archive_path, pre_snapshot)
        if pre_sha != expected_archive_sha:
            raise RecoveryError(
                f"archive SHA256 mismatch: expected {expected_archive_sha}, actual {pre_sha}"
            )

        with os.fdopen(os.dup(archive_fd), "rb", closefd=True) as archive_handle, zipfile.ZipFile(
            archive_handle, "r"
        ) as archive:
            info_by_name: dict[str, list[zipfile.ZipInfo]] = {}
            for info in archive.infolist():
                info_by_name.setdefault(info.filename, []).append(info)

            selected_infos: list[zipfile.ZipInfo] = []
            for info in archive.infolist():
                raw_name = info.filename.rstrip("/")
                if not selected_git_database_member(raw_name, repo_prefix):
                    continue
                normalize_posix_relative(raw_name, role="selected Git archive member")
                if len(info_by_name[info.filename]) != 1:
                    raise RecoveryError(f"duplicate selected Git ZIP member: {info.filename}")
                kind = zipinfo_kind(info)
                if kind in {"symlink", "special"}:
                    raise RecoveryError(f"unsafe selected Git ZIP member: {info.filename} ({kind})")
                if kind == "file":
                    selected_infos.append(info)

            tag_ref_member = f"{repo_prefix}/.git/refs/tags/{tag_name}"
            if len(info_by_name.get(tag_ref_member, [])) != 1:
                raise RecoveryError(f"tag ref member identity is not unique: {tag_ref_member}")

            extraction_rows: list[dict[str, object]] = []
            git_prefix = f"{repo_prefix}/.git/"
            for info in sorted(selected_infos, key=lambda item: item.filename):
                relative = info.filename[len(git_prefix) :]
                extraction_rows.append(extract_zip_file(archive, info, git_dir, relative))

            config_audit = validate_archive_git_config(git_dir / "config")
            alternates = git_dir / "objects" / "info" / "alternates"
            if alternates.exists() and alternates.read_bytes().strip():
                raise RecoveryError("external Git object alternates are denied")

            tag_ref_text = (git_dir / "refs" / "tags" / tag_name).read_text(
                encoding="ascii", errors="strict"
            ).strip()
            if not HEX40_RE.fullmatch(tag_ref_text):
                raise RecoveryError(f"tag ref does not contain one SHA-1 object id: {tag_ref_text!r}")

            git_version = subprocess.run(
                ["git", "--version"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=isolated_git_environment(),
            ).stdout.strip()

            rev_output, rev_error, audit = run_git(
                git_dir, ["rev-parse", "--verify", f"refs/tags/{tag_name}^{{commit}}"]
            )
            command_audit.append(audit)
            resolved_commit = str(rev_output).strip()
            if resolved_commit != expected_commit or tag_ref_text != expected_commit:
                raise RecoveryError(
                    f"tag identity mismatch: ref={tag_ref_text}, peeled={resolved_commit}, "
                    f"expected={expected_commit}"
                )

            object_type, _, audit = run_git(git_dir, ["cat-file", "-t", expected_commit])
            command_audit.append(audit)
            if str(object_type).strip() != "commit":
                raise RecoveryError(f"expected tag target is not a commit: {object_type!r}")

            commit_payload, _, audit = run_git(git_dir, ["cat-file", "-p", expected_commit])
            command_audit.append(audit)

            fsck_stdout, fsck_stderr, audit = run_git(
                git_dir, ["fsck", "--full", "--no-reflogs"]
            )
            command_audit.append(audit)
            fsck = classify_fsck_output(str(fsck_stdout), str(fsck_stderr))
            if not fsck["authoritative_pass"]:
                raise RecoveryError(f"git fsck emitted non-dangling diagnostics: {fsck['unexpected']}")

            tree_payload, tree_stderr, audit = run_git(
                git_dir,
                ["ls-tree", "-r", "-l", "-z", "--full-tree", f"{expected_commit}^{{tree}}"],
                text_mode=False,
            )
            command_audit.append(audit)
            if bytes(tree_stderr):
                raise RecoveryError("git ls-tree emitted stderr")
            entries = parse_ls_tree_z(bytes(tree_payload))
            selected, roots = select_source_entries(entries)
            source_rows = materialize_blobs(git_dir, source_root, selected)
            conflicts = working_tree_conflicts(
                archive, info_by_name, repo_prefix, expected_commit, source_rows
            )
            ancillary_rows = ancillary_role_audit(
                archive, info_by_name, repo_prefix, entries, source_rows
            )

        post_sha = hash_fd(archive_fd)
        post_snapshot = snapshot_fd(archive_fd, post_sha)
        validate_archive_path_snapshot(archive_path, pre_snapshot)
        if post_snapshot != pre_snapshot:
            raise RecoveryError("archive SHA/stat changed between pre-read and post-read checks")

        completeness = source_completeness(selected, roots)
        if not completeness["static_build_source_closure"]:
            raise RecoveryError(f"tag static build-source closure is incomplete: {completeness}")

        tree_rows = tree_inventory_rows(entries, selected)
        core_hashes = {
            str(row["path"]): str(row["sha256"])
            for row in source_rows
            if row["path"] in REQUIRED_TAG_PATHS
            or row["path"] in REQUIRED_SOLVER_WRITER_PATHS
            or PurePosixPath(str(row["path"])).name.lower()
            in {
                "kf_gins.cpp",
                "gi_engine.cpp",
                "gi_engine.hpp",
                "insmech.cpp",
                "insmech.hpp",
                "options.hpp",
                "kf_gins_types.hpp",
            }
        }
        conflict_counts: dict[str, int] = {}
        for row in conflicts:
            status_name = str(row["comparison_status"])
            conflict_counts[status_name] = conflict_counts.get(status_name, 0) + 1
        missing_tag_ancillary = [
            str(row["logical_path"])
            for row in ancillary_rows
            if row["tag_status"] == "MISSING_FROM_TAG_ANCILLARY_ROLE"
        ]
        if set(missing_tag_ancillary) != EXPECTED_MISSING_TAG_ANCILLARY_PATHS:
            raise RecoveryError(
                "unexpected exact-tag ancillary presence/absence set: "
                f"{sorted(missing_tag_ancillary)}"
            )

        archive_invariant = {
            "pre": asdict(pre_snapshot),
            "post": asdict(post_snapshot),
            "sha256_unchanged": pre_sha == post_sha == expected_archive_sha,
            "stat_unchanged": pre_snapshot == post_snapshot,
            "archive_path_unchanged": True,
        }
        provenance = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": utc_now(),
            "archive": {
                "path": os.fspath(archive_path),
                "repo_prefix": repo_prefix,
                "expected_sha256": expected_archive_sha,
                "invariant": archive_invariant,
            },
            "git": {
                "system_git_version": git_version,
                "tag_name": tag_name,
                "archive_tag_ref_member": tag_ref_member,
                "tag_ref_object_id": tag_ref_text,
                "peeled_commit": resolved_commit,
                "commit_object_type": "commit",
                "commit_payload_sha256": sha256_bytes(str(commit_payload).encode("utf-8")),
                "archive_working_tree_head_used": False,
                "object_database_member_count": sum(
                    1 for row in extraction_rows if "/objects/" in str(row["archive_member"])
                ),
                "extracted_git_member_count": len(extraction_rows),
                "config_audit": config_audit,
                "fsck": fsck,
            },
            "tag_tree": {
                "entry_count": len(entries),
                "selected_source_count": len(source_rows),
                "dependency_roots": roots,
                "static_build_source_closure": completeness,
                "core_hashes": core_hashes,
                "ancillary_role_audit": {
                    "row_count": len(ancillary_rows),
                    "missing_from_tag_count": len(missing_tag_ancillary),
                    "missing_from_tag_paths": missing_tag_ancillary,
                    "all_archive_static_bindings_unique": all(
                        row["archive_static_candidate_count"] == 1 for row in ancillary_rows
                    ),
                    "missing_roles_materialized_into_tag_source": False,
                },
            },
            "working_tree_comparison": {
                "basis": "sha256_content_only",
                "mtime_used": False,
                "metric_used": False,
                "status_counts": conflict_counts,
            },
            "execution_boundary": {
                "archived_binary_executed": False,
                "archived_source_executed": False,
                "solver_built": False,
                "solver_run": False,
                "trace_read": False,
                "performance_result_read": False,
                "prior_failed_attempt_quarantines_excluded": True,
                "prior_failed_attempt_quarantine_count": len(prior_failed_quarantines),
                "prior_failed_attempt_quarantines": [
                    os.fspath(path) for path in prior_failed_quarantines
                ],
            },
        }
        terminal = {
            "schema_version": SCHEMA_VERSION,
            "terminal_decision": "APPROVED_EXACT_FINAL_V23_SOLVER_TAG_SOURCE_RECOVERY",
            "stage_id": "CLEAN1R2_FINAL_V23_ARCHIVE_PARITY_AND_FOUR_METHOD_REEXECUTION",
            "tag_name": tag_name,
            "tag_commit": resolved_commit,
            "archive_sha256": expected_archive_sha,
            "gates": {
                "archive_pre_post_sha_stat_unchanged": True,
                "tag_ref_unique": True,
                "tag_commit_exact": True,
                "git_fsck_full_no_reflogs_pass": True,
                "fsck_non_dangling_diagnostic_count": 0,
                "selected_source_regular_blob_only": True,
                "required_tag_paths_present": True,
                "required_solver_writer_paths_present": True,
                "dependency_roots_unique": True,
                "static_build_source_closure": True,
                "archive_static_ancillary_bindings_unique": True,
                "missing_tag_ancillary_roles_recorded": True,
                "missing_tag_ancillary_role_count": len(missing_tag_ancillary),
                "failed_attempt_quarantines_excluded": True,
                "archive_working_tree_head_used": False,
                "solver_or_binary_executed": False,
            },
            "missing_from_tag_ancillary_roles": missing_tag_ancillary,
            "blockers": [],
            "claim_ceiling": (
                "exact static solver tag source and build-dependency recovery; missing ancillary "
                "roles remain separately bound archive-static references; build/run parity not assessed"
            ),
        }

        extraction_fields = [
            "archive_member",
            "destination_relative",
            "member_size",
            "compressed_size",
            "crc32",
            "crc32_verified",
            "sha256",
            "encrypted",
            "member_kind",
        ]
        tree_fields = [
            "path",
            "mode",
            "object_type",
            "object_id",
            "size",
            "selected",
            "logical_role",
            "selection_reason",
        ]
        source_fields = [
            "path",
            "git_mode",
            "git_type",
            "git_object_id",
            "size",
            "sha256",
            "logical_role",
            "selection_reason",
            "dependency_root",
            "materialized_relative",
        ]
        conflict_fields = [
            "path",
            "tag_commit",
            "tag_blob_object_id",
            "tag_sha256",
            "tag_size",
            "archive_working_tree_member",
            "archive_working_tree_candidate_count",
            "archive_working_tree_sha256",
            "archive_working_tree_size",
            "archive_working_tree_crc32",
            "comparison_status",
            "comparison_basis",
            "mtime_used",
            "metric_used",
        ]
        ancillary_fields = [
            "logical_role",
            "logical_path",
            "tag_status",
            "tag_blob_object_id",
            "tag_sha256",
            "tag_size",
            "materialized_into_tag_source",
            "archive_static_member",
            "archive_static_candidate_count",
            "archive_static_sha256",
            "archive_static_size",
            "archive_static_crc32",
            "archive_static_binding_status",
            "archive_static_materialized_into_tag_source",
            "archive_working_tree_head_used",
            "identity_basis",
        ]

        write_csv(stage_root, "TAG_GIT_DATABASE_EXTRACTION_MANIFEST.csv", extraction_fields, extraction_rows)
        write_json(
            stage_root,
            "TAG_GIT_DATABASE_EXTRACTION_MANIFEST.json",
            {"schema_version": SCHEMA_VERSION, "rows": extraction_rows},
        )
        write_csv(stage_root, "TAG_TREE_INVENTORY.csv", tree_fields, tree_rows)
        write_json(
            stage_root,
            "TAG_TREE_INVENTORY.json",
            {"schema_version": SCHEMA_VERSION, "tag_commit": resolved_commit, "rows": tree_rows},
        )
        write_csv(stage_root, "TAG_SOURCE_MANIFEST.csv", source_fields, source_rows)
        write_json(
            stage_root,
            "TAG_SOURCE_MANIFEST.json",
            {"schema_version": SCHEMA_VERSION, "tag_commit": resolved_commit, "rows": source_rows},
        )
        write_csv(stage_root, "WORKING_TREE_VS_TAG_CONFLICT_MAP.csv", conflict_fields, conflicts)
        write_json(
            stage_root,
            "WORKING_TREE_VS_TAG_CONFLICT_MAP.json",
            {"schema_version": SCHEMA_VERSION, "tag_commit": resolved_commit, "rows": conflicts},
        )
        write_csv(stage_root, "TAG_ANCILLARY_ROLE_MAP.csv", ancillary_fields, ancillary_rows)
        write_json(
            stage_root,
            "TAG_ANCILLARY_ROLE_MAP.json",
            {"schema_version": SCHEMA_VERSION, "tag_commit": resolved_commit, "rows": ancillary_rows},
        )
        write_json(stage_root, "TAG_PROVENANCE.json", provenance)
        write_json(stage_root, "FINAL_V23_TAG_SOURCE_RECOVERY_MANIFEST.json", terminal)

        log_payloads = {
            "ARCHIVE_PRE_POST_INVARIANT.json": archive_invariant,
            "GIT_COMMAND_AUDIT.json": {
                "schema_version": SCHEMA_VERSION,
                "commands": command_audit,
            },
            "GIT_FSCK_FULL_NO_REFLOGS.json": fsck,
            "TAG_PROVENANCE.json": provenance,
            "FINAL_V23_TAG_SOURCE_RECOVERY_MANIFEST.json": terminal,
        }
        for name, payload in log_payloads.items():
            write_json(log_stage, name, payload)

        safe_lstat_directory_chain(stage_root, create=False)
        safe_lstat_directory_chain(log_stage, create=False)
        os.replace(stage_root, recovery_root)
        safe_lstat_directory_chain(recovery_root, create=False)
        os.replace(log_stage, log_root)
        safe_lstat_directory_chain(log_root, create=False)

        result = dict(terminal)
        result.update(
            {
                "recovery_root": os.fspath(recovery_root),
                "log_root": os.fspath(log_root),
                "tree_entry_count": len(entries),
                "selected_source_count": len(source_rows),
                "core_hashes": core_hashes,
                "started_at_utc": started_at,
                "completed_at_utc": utc_now(),
            }
        )
        return result
    except BaseException as error:
        quarantine_errors: list[str] = []
        for unpublished_stage, intended_target in (
            (stage_root, recovery_root),
            (log_stage, log_root),
        ):
            try:
                quarantine_failed_stage(unpublished_stage, intended_target, error)
            except BaseException as quarantine_error:  # preserve the primary deterministic error
                quarantine_errors.append(str(quarantine_error))
        if quarantine_errors:
            raise RecoveryError(
                f"{error}; failed-attempt quarantine errors: {quarantine_errors}"
            ) from error
        raise
    finally:
        os.close(archive_fd)


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = recover(args)
    except (RecoveryError, OSError, zipfile.BadZipFile, subprocess.SubprocessError) as error:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA_VERSION,
                    "terminal_decision": "BLOCKED_FINAL_V23_TAG_SOURCE_RECOVERY",
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
