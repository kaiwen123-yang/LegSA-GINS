"""Exact-file, journaled storage retirement. No scientific executables are called.

Inventory is metadata-only except retained metadata and hashes of eligible files.
The immutable plan is separate from the move/unlink journal. Physical phases are
explicit CLI commands for the supervisor; inventory never moves or deletes files.
"""
from __future__ import annotations

import argparse
import base64
import csv
import ctypes
import fnmatch
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from collections import deque
from contextlib import contextmanager
from datetime import datetime, timezone
from dataclasses import dataclass
from functools import wraps

import yaml


class PurgeError(RuntimeError):
    """An exact-manifest or safety gate failed; preserve current state."""


HEX = re.compile(r"[0-9a-f]{64}\Z")
STAMP = re.compile(r"[0-9]{8}T[0-9]{6}Z\Z")
VERSION = "clean6.storage_purge.v1"
CHUNK = 4 * 1024 * 1024
PLAN_COLUMNS = ["original_relative_path", "size_bytes", "sha256", "family", "file_class",
                "quarantine_relative_path", "hash_evidence", "seal_provenance"]
INVENTORY_COLUMNS = ["original_relative_path", "group", "file_type", "size_bytes", "nlink",
                     "classification", "reason", "family", "file_class", "device", "inode",
                     "mtime_ns", "metadata_source", "identity_status"]
C5_CHECKS = {"repository_record_tests", "decision_readability", "aggregate_readability",
             "three_sequence_CAL_readability"}


@dataclass(frozen=True)
class NativeKeepMetadata:
    """Only independently retained regular files may lack Linux identity metadata."""
    st_size: int
    attributes: int
    st_mode: int = stat.S_IFREG
    st_nlink: None = None
    st_dev: None = None
    st_ino: None = None
    st_mtime_ns: None = None


def _fail(message):
    raise PurgeError(message)


def _json_bytes(obj):
    return (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()


def _digest(data):
    return hashlib.sha256(data).hexdigest()


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _relative(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        _fail(f"invalid relative path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(p in {"", ".", ".."} for p in value.split("/")):
        _fail(f"noncanonical relative path: {value!r}")
    return value


def _under(relative, directory):
    return relative == directory or relative.startswith(directory + "/")


def _absolute_without_links(path, *, missing=False):
    """Reject symlinks in every existing path component without resolving them."""
    if ".." in Path(path).parts:
        _fail(f"parent traversal in absolute path: {path}")
    path = Path(os.path.abspath(path))
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor /= part
        try:
            s = cursor.lstat()
        except FileNotFoundError:
            if missing:
                continue
            raise
        if stat.S_ISLNK(s.st_mode):
            _fail(f"symlink path component: {cursor}")
    return path


@contextmanager
def _parent_fd(path, *, create=False):
    """Open each parent with O_NOFOLLOW; mutations operate relative to pinned FDs."""
    path = Path(os.path.abspath(path))
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:-1]:
            if create:
                try:
                    os.mkdir(part, dir_fd=fd)
                    os.fsync(fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        yield fd, path.name
    finally:
        os.close(fd)


def _stat(path):
    with _parent_fd(path) as (fd, name):
        return os.stat(name, dir_fd=fd, follow_symlinks=False)


def _exists(path):
    try:
        _stat(path)
        return True
    except FileNotFoundError:
        return False


def _same_stat(a, b):
    return (a.st_dev, a.st_ino, a.st_size, a.st_mtime_ns, a.st_nlink) == (
        b.st_dev, b.st_ino, b.st_size, b.st_mtime_ns, b.st_nlink)


def _regular_single(s, path):
    if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1:
        _fail(f"not a singly linked regular file: {path}")


def _forbid_raw_content(path):
    path = Path(path)
    if ("raw" in [p.lower() for p in path.parts] or path.name.lower().startswith("trace_")
            or path.suffix.lower() in {".bag", ".fpl"}):
        _fail(f"raw/reference payload content access forbidden: {path}")


def hash_file(path, *, expected_size=None):
    """Streaming hash with descriptor identity and before/after change checks."""
    _forbid_raw_content(path)
    with _parent_fd(path) as (parent, name):
        _regular_single(os.stat(name, dir_fd=parent, follow_symlinks=False), path)
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(fd)
            _regular_single(before, path)
            if expected_size is not None and before.st_size != expected_size:
                _fail(f"size changed: {path}")
            digest = hashlib.sha256()
            while True:
                chunk = os.read(fd, CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
            after = os.fstat(fd)
            named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            if not _same_stat(before, after) or not _same_stat(after, named):
                _fail(f"file changed while hashing: {path}")
            return digest.hexdigest(), before
        finally:
            os.close(fd)


def _read(path):
    _forbid_raw_content(path)
    with _parent_fd(path) as (parent, name):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                _fail(f"metadata is not a regular file: {path}")
            data = stream.read()
            after = os.fstat(stream.fileno())
            if not _same_stat(before, after):
                _fail(f"metadata changed while reading: {path}")
            return data


def _load(path):
    return json.loads(_read(path))


def _write_new(path, data):
    with _parent_fd(path, create=True) as (parent, name):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                     dir_fd=parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.fsync(parent)


def _write_or_verify(path, obj):
    data = _json_bytes(obj)
    if _exists(path):
        if _read(path) != data:
            _fail(f"existing receipt differs: {path}")
    else:
        _write_new(path, data)


def _csv_bytes(rows, columns):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, sort_keys=True) if isinstance(v, (dict, list)) else v
                         for k, v in row.items()})
    return stream.getvalue().encode()


def _serialized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._operation_lock():
            return method(self, *args, **kwargs)
    return wrapped


class StoragePurge:
    def __init__(self, clean_root, code_root, policy, closure, audit_root):
        self.clean = _absolute_without_links(clean_root)
        self.code = _absolute_without_links(code_root)
        self.audit = _absolute_without_links(audit_root, missing=True)
        if not self.clean.is_dir() or not self.code.is_dir():
            _fail("clean/code root must be existing directories")
        if self.audit.parent != self.clean / "storage_purge" or not STAMP.fullmatch(self.audit.name):
            _fail("audit root must be <CLEAN_ROOT>/storage_purge/YYYYmmddTHHMMSSZ")
        self.timestamp = self.audit.name
        self.quarantine = self.clean / "_PURGE_PENDING" / self.timestamp
        _absolute_without_links(self.quarantine, missing=True)
        self.policy_bytes = _read(policy)
        self.policy = yaml.safe_load(self.policy_bytes)
        if self.policy.get("schema_version") != "clean6.storage_purge_policy.v1":
            _fail("unsupported storage policy")
        if self.policy.get("precedence") != ["KEEP", "BULK_DELETABLE", "UNKNOWN"]:
            _fail("KEEP precedence is mandatory")
        self.closure_bytes = _read(closure)
        self.closure = json.loads(self.closure_bytes)
        if self.closure.get("schema_version") != "clean6.storage_reference_closure.v1":
            _fail("unsupported reference closure")
        for field in ("keep_files", "keep_dirs", "protected_dir_entries", "superseded_attempt_dirs",
                      "clean4_nonfinal_attempt_dirs"):
            for relative in self.closure.get(field, []):
                _relative(relative)
        self.keep_files = set(self.closure.get("keep_files", []))
        self.keep_dirs = tuple(self.closure.get("keep_dirs", []))
        self.embedded_git_roots = set()
        self.inventory_walking = False
        self.base_binding = {"policy_sha256": _digest(self.policy_bytes),
                             "closure_sha256": _digest(self.closure_bytes)}

    @contextmanager
    def _operation_lock(self):
        with _parent_fd(self.audit / "OPERATION_LOCK") as (parent, name):
            fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            try:
                _regular_single(os.fstat(fd), "operation lock")
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    _fail("another gate/move/purge phase holds the operation lock")
                yield
            finally:
                os.close(fd)

    def alias(self, value):
        for prefix in ("<HOME>/", "<USER_HOME>/"):
            if value.startswith(prefix):
                return Path.home() / _relative(value[len(prefix):])
        if value.startswith("<CLEAN_ROOT>/"):
            return self.clean / _relative(value[len("<CLEAN_ROOT>/"):])
        if value.startswith("<CODE_ROOT>/"):
            return self.code / _relative(value[len("<CODE_ROOT>/"):])
        if Path(value).is_absolute():
            return _absolute_without_links(value)
        return self.clean / _relative(value)

    def portable(self, path):
        path = Path(path)
        for root, alias in [(self.clean, "<CLEAN_ROOT>"), (self.code, "<CODE_ROOT>"), (Path.home(), "<HOME>")]:
            try:
                return alias + "/" + path.relative_to(root).as_posix()
            except ValueError:
                pass
        return "<EXTERNAL>/" + path.name

    def _family(self, relative):
        parts = PurePosixPath(relative).parts
        if len(parts) < 4 or parts[0] != "stages":
            return ""
        families = self.policy["bulk_deletable"]["families"]
        f = families["canonical541_v1"]
        if parts[1:3] == (f["stage"], f["attempt"]) and parts[3] in f["directories"]:
            return "canonical541_v1"
        f = families["clean5_sequences_v1_v2"]
        if parts[1] in f["stages"] and any(fnmatch.fnmatchcase(parts[2], p)
                                                   for p in f["directory_patterns"]):
            return "clean5_sequences_v1_v2"
        f = families["clean5_parity_ladder_and_p05"]
        if parts[1] == f["stage"]:
            tail = "/".join(parts[2:])
            for parent in f["parent_paths"]:
                for directory in f["directories"]:
                    prefix = directory if parent == "." else parent + "/" + directory
                    if tail.startswith(prefix + "/"):
                        return "clean5_parity_ladder_and_p05"
        f = families["clean5_p07"]
        if (parts[1] == f["stage"] and parts[2] in f["directories"]
                and any(chain in parts[3:-1] for chain in f["chains"])):
            return "clean5_p07"
        f = families["superseded_attempts"]
        for directory in self.closure.get("superseded_attempt_dirs", []):
            dparts = PurePosixPath(directory).parts
            if (len(dparts) >= 3 and dparts[0] == "stages"
                    and any(dparts[1].startswith(p) for p in f["stage_prefixes"])
                    and fnmatch.fnmatchcase(dparts[-1], f["attempt_component_pattern"])
                    and _under(relative, directory)):
                return "superseded_attempts"
        f = families["clean4_nonfinal_attempts"]
        for directory in self.closure.get("clean4_nonfinal_attempt_dirs", []):
            if parts[1] == f["stage"] and _under(relative, directory):
                return "clean4_nonfinal_attempts"
        return ""

    def classify(self, relative, s):
        _relative(relative)
        parts = PurePosixPath(relative).parts
        name = parts[-1]
        if isinstance(s, NativeKeepMetadata):
            if (type(s.st_size) is not int or s.st_size < 0 or type(s.attributes) is not int
                    or s.attributes < 0 or s.attributes & (16 | 1024)
                    or s.st_mode != stat.S_IFREG or any(value is not None for value in
                        (s.st_nlink, s.st_dev, s.st_ino, s.st_mtime_ns))):
                _fail("invalid native KEEP metadata")
            independent_reason = self._independent_keep(name, s.st_size)
            if not independent_reason:
                _fail("native identity-free metadata cannot classify a candidate or UNKNOWN file")
            return "KEEP", independent_reason, "", ""
        keep = self.policy["keep"]
        bulk = self.policy["bulk_deletable"]
        file_class = ""
        if name in bulk["exact_filenames"]:
            file_class = "exact_bulk_filename"
        elif name in bulk["staging_copies"]:
            file_class = "staging_copy"
        elif any(fnmatch.fnmatchcase(name, p) for p in bulk["strace_patterns"]):
            file_class = "strace"
        elif name in bulk["solver_logs"]["filenames"] and self._solver_directory(parts):
            file_class = "solver_log"
        elif name in bulk["evaluator_logs"]["filenames"] and self._evaluation_directory(parts):
            file_class = "evaluator_log"
        elif any(any(fnmatch.fnmatchcase(p, pattern)
                     for pattern in bulk["temporary_directories"]["component_patterns"])
                 for p in parts[:-1]):
            file_class = "temporary_regular_file"
        reason = ""
        if not stat.S_ISREG(s.st_mode):
            reason = "symlink_directory_or_special_never_follow"
        elif s.st_nlink > 1:
            reason = "multiply_linked"
        elif relative in self.keep_files or any(_under(relative, d) for d in self.keep_dirs):
            reason = "reference_closure"
        elif self._embedded_git(relative):
            reason = "embedded_git_worktree"
        elif any("PROVIDER" in p.upper() for p in parts[:-1]):
            reason = "provider_directory"
        elif any(p == "01_RAW_HASH_LOCK" for p in parts) or relative.startswith("data/raw/"):
            reason = "raw_or_hash_lock"
        elif len(parts) > 1 and parts[1] == "CLEAN5_CALIBRATED_SENSOR_MODEL":
            reason = "complete_CAL_subtree"
        elif not file_class and any(any(term.upper() in p.upper() for term in keep["nonbulk_subtree_name_contains"])
                 for p in parts[:-1]):
            reason = "nonbulk_subtree"
        elif any(fnmatch.fnmatchcase(name, pattern) for pattern in keep["filename_patterns"]):
            reason = "record_filename"
        elif any(fnmatch.fnmatchcase(name, pattern) for pattern in keep["run_records"]["filenames"]):
            reason = "run_record"
        elif name.lower().endswith((".json", ".csv")) and s.st_size <= keep["run_records"]["small_json_csv_max_bytes"]:
            reason = "small_json_csv"
        elif (name.lower().endswith((".imu", ".gnss")) or any(term in name.lower() for term in
              ("provider", "input", "raw_doppler", "go2", "imu", "gnss", "dual_yaw", "source_quality"))) \
                and name not in bulk["staging_copies"] + bulk["exact_filenames"]:
            reason = "ambiguous_input_or_provider"
        if reason:
            return "KEEP", reason, "", ""
        family = self._family(relative)
        if file_class and family:
            return "BULK_DELETABLE", "approved_class_and_family", family, file_class
        return "UNKNOWN", "family_or_class_not_approved", family, file_class

    def _independent_keep(self, name, size):
        keep = self.policy["keep"]
        if any(fnmatch.fnmatchcase(name, pattern) for pattern in keep["filename_patterns"]):
            return "record_filename"
        if name.lower().endswith((".json", ".csv")) and size <= keep["run_records"]["small_json_csv_max_bytes"]:
            return "small_json_csv"
        return ""

    def _embedded_git(self, relative):
        if any(_under(relative, root) for root in self.embedded_git_roots):
            return True
        if self.inventory_walking:
            return False
        parent = (self.clean / relative).parent
        while parent != self.clean.parent:
            try:
                # A .git file, directory or link is enough for conservative KEEP.
                (parent / ".git").lstat()
                return True
            except FileNotFoundError:
                pass
            parent = parent.parent
        return False

    @staticmethod
    def _solver_directory(parts):
        return (any("RUNS" in p and "EVAL" not in p for p in parts[:-2])
                and not StoragePurge._evaluation_directory(parts))

    @staticmethod
    def _evaluation_directory(parts):
        return any("EVALUATION" in p for p in parts[:-1])

    def _walk(self, root):
        """Sorted depth-first scandir, retaining directories and never following links."""
        stack = [root]
        while stack:
            directory = stack.pop()
            _absolute_without_links(directory)
            with os.scandir(directory) as entries:
                entries = sorted(entries, key=lambda entry: entry.name)
            if any(entry.name == ".git" for entry in entries):
                self.embedded_git_roots.add(directory.relative_to(self.clean).as_posix())
            subdirs = []
            for entry in entries:
                s = entry.stat(follow_symlinks=False)
                path = Path(entry.path)
                yield path, s
                if stat.S_ISDIR(s.st_mode):
                    subdirs.append(path)
            stack.extend(reversed(subdirs))

    @staticmethod
    def _directory_metadata(directory):
        """Worker reads one directory only; it never classifies or submits children."""
        with _parent_fd(directory) as (parent, name):
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=parent)
            try:
                with os.scandir(fd) as entries:
                    return sorted([(directory / entry.name, entry.stat(follow_symlinks=False))
                                   for entry in entries], key=lambda item: item[0].name)
            finally:
                os.close(fd)

    @staticmethod
    def _native_directory_listing(directory):
        """One exact directory, metadata only; no configurable Windows root mapping."""
        windows_path = subprocess.check_output(["wslpath", "-w", str(directory)], text=True,
                                               timeout=15).strip()
        if not re.match(r"^[A-Za-z]:\\", windows_path) or "\n" in windows_path or "\r" in windows_path:
            _fail("wslpath did not return one native drive directory")
        literal = windows_path.replace("'", "''")
        script = (
            "$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; "
            "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
            f"$dir=[System.IO.DirectoryInfo]::new('{literal}'); "
            "$rootAttributes=[int]$dir.Attributes; "
            "if(($rootAttributes -band 1024) -ne 0){throw 'reparse directory forbidden'}; "
            "$rows=[System.Collections.Generic.List[object]]::new(); "
            "foreach($x in $dir.EnumerateFileSystemInfos()){ $a=[int]$x.Attributes; "
            "$n=[int64]0; if(($a -band 16) -eq 0 -and ($a -band 1024) -eq 0){$n=$x.Length}; "
            "$rows.Add(@{name=$x.Name;size=$n;attributes=$a}) }; "
            "@{directory_attributes=$rootAttributes;rows=$rows} | ConvertTo-Json -Compress -Depth 4"
        )
        encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        result = subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
                                 "-EncodedCommand", encoded], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, check=True, timeout=60)
        return json.loads(result.stdout.decode("utf-8-sig"))

    def _dense_directory_metadata(self, directory):
        with _parent_fd(directory) as (parent, name):
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=parent)
            try:
                before = os.fstat(fd)
                with os.scandir(fd) as scan:
                    entries = sorted(list(scan), key=lambda entry: entry.name)
                if len(entries) < 1000:
                    return [(directory / entry.name, entry.stat(follow_symlinks=False)) for entry in entries]
                # d_type checks do not follow links; if unavailable Python safely obtains lstat.
                linux_types = {entry.name: "symlink" if entry.is_symlink() else "directory"
                               if entry.is_dir(follow_symlinks=False) else "regular"
                               if entry.is_file(follow_symlinks=False) else "special" for entry in entries}
                native = self._native_directory_listing(directory)
                attributes = native.get("directory_attributes")
                if type(attributes) is not int or not attributes & 16 or attributes & 1024:
                    _fail("native directory is not an ordinary non-reparse directory")
                rows = native.get("rows")
                if not isinstance(rows, list):
                    _fail("native directory rows must be a list")
                by_name = {}
                for row in rows:
                    if not isinstance(row, dict):
                        _fail("malformed native directory row")
                    filename, size, attributes = row.get("name"), row.get("size"), row.get("attributes")
                    if (not isinstance(filename, str) or not filename or filename in by_name
                            or "/" in filename or "\\" in filename or filename in {".", ".."}
                            or type(size) is not int or size < 0 or type(attributes) is not int or attributes < 0):
                        _fail("invalid or duplicate native metadata")
                    by_name[filename] = row
                if set(by_name) != set(linux_types):
                    _fail("native/Linux directory names mismatch")
                all_independent_keep = True
                for filename, row in by_name.items():
                    native_type = "symlink" if row["attributes"] & 1024 else "directory" if row["attributes"] & 16 else "regular"
                    if linux_types[filename] != native_type:
                        _fail("native/Linux directory types mismatch")
                    if native_type != "regular" or not self._independent_keep(filename, row["size"]):
                        all_independent_keep = False
                if not _same_stat(before, os.fstat(fd)) or not _same_stat(before, _stat(directory)):
                    _fail("directory changed during native metadata query")
                if all_independent_keep:
                    return [(directory / entry.name,
                             NativeKeepMetadata(by_name[entry.name]["size"], by_name[entry.name]["attributes"]))
                            for entry in entries]
                return [(directory / entry.name, entry.stat(follow_symlinks=False)) for entry in entries]
            finally:
                os.close(fd)

    def _walk_plan(self, root, *, workers=8, native_dense_keep=False):
        """Bounded directory parallelism; the owner observes parents before children."""
        if not 1 <= workers <= 16:
            _fail("metadata_workers must be 1..16")
        ready = deque([root])
        pending = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            while ready or pending:
                while ready and len(pending) < workers:
                    directory = ready.popleft()
                    reader = self._dense_directory_metadata if native_dense_keep else self._directory_metadata
                    pending[pool.submit(reader, directory)] = directory
                completed, _ = wait(pending, return_when=FIRST_COMPLETED)
                for future in completed:
                    directory = pending.pop(future)
                    entries = future.result()
                    # Parent retention is established before any child can be submitted.
                    if any(path.name == ".git" for path, _ in entries):
                        self.embedded_git_roots.add(directory.relative_to(self.clean).as_posix())
                    children = []
                    for path, s in entries:
                        yield path, s
                        if stat.S_ISDIR(s.st_mode):
                            children.append(path)
                    ready.extend(children)

    def _inventory_group(self, relative):
        parts = PurePosixPath(relative).parts
        groups = ["/".join(parts[:2])]
        groups.extend("/".join(parts[:index + 1]) for index, part in enumerate(parts)
                      if part.startswith(".attempt_"))
        groups.extend(directory for field in ("superseded_attempt_dirs", "clean4_nonfinal_attempt_dirs")
                      for directory in self.closure.get(field, []) if _under(relative, directory))
        return max(groups, key=lambda group: len(PurePosixPath(group).parts))

    def _seal_index(self, metadata_paths):
        """Use only unambiguous absolute/root-relative paths; hash occurrence is supplementary."""
        explicit = self.closure.get("seal_sources", [])
        sources = {str(self.alias(item["path"])): item for item in explicit}
        for path in metadata_paths:
            sources.setdefault(str(path), {"path": self.portable(path)})
        by_path, by_hash = {}, {}

        def resolved(value, spec):
            if not isinstance(value, str):
                return None
            try:
                if value.startswith(("<CLEAN_ROOT>/", "stages/")) or Path(value).is_absolute():
                    path = self.alias(value)
                elif spec.get("base"):
                    path = self.alias(spec["base"]) / _relative(value)
                else:
                    return None
                return path.relative_to(self.clean).as_posix()
            except (ValueError, PurgeError, FileNotFoundError):
                return None

        for path_string, spec in sorted(sources.items()):
            path = Path(path_string)
            try:
                rel = path.relative_to(self.clean).as_posix()
            except ValueError:
                _fail("seal sources must be under CLEAN_ROOT")
            if path.suffix.lower() not in {".json", ".csv"}:
                _fail("seal/manifest source must be JSON or CSV metadata")
            s = _stat(path)
            if self.classify(rel, s)[0] != "KEEP":
                _fail("seal evidence itself must be retained")
            data = _read(path)
            file_hash = _digest(data)
            if spec.get("sha256") and spec["sha256"] != file_hash:
                _fail(f"seal source pin mismatch: {rel}")
            provenance = {"path": self.portable(path), "sha256": file_hash}

            def occurrence(sha, pointer):
                item = dict(provenance, json_pointer=pointer)
                bucket = by_hash.setdefault(sha, [])
                if len(bucket) < 3 and item not in bucket:
                    bucket.append(item)

            def exact_path(relpath, sha, pointer):
                item = dict(provenance, json_pointer=pointer)
                bucket = by_path.setdefault(relpath, {}).setdefault(sha, [])
                if len(bucket) < 3 and item not in bucket:
                    bucket.append(item)

            if path.suffix.lower() == ".csv":
                rows = csv.DictReader(io.StringIO(data.decode("utf-8-sig")))
                for line_number, row in enumerate(rows, 2):
                    sha = row.get("sha256", "")
                    if not HEX.fullmatch(sha):
                        _fail(f"invalid CSV seal sha256 at {rel}:{line_number}")
                    if row.get("run_root") and row.get("relative_path"):
                        root = self.alias(row["run_root"])
                        pathname = str(root / _relative(row["relative_path"]))
                    else:
                        pathname = row.get("path", row.get("relative_path"))
                    relpath = resolved(pathname, spec)
                    if relpath:
                        exact_path(relpath, sha, f"csv_row:{line_number}/sha256")
                    occurrence(sha, f"csv_row:{line_number}/sha256")
                continue
            try:
                obj = json.loads(data)
            except (ValueError, UnicodeDecodeError):
                if path_string in {str(self.alias(x["path"])) for x in explicit}:
                    _fail(f"invalid explicit seal JSON: {rel}")
                continue

            def visit(value, pointer=""):
                if isinstance(value, str) and HEX.fullmatch(value):
                    occurrence(value, pointer)
                elif isinstance(value, list):
                    for index, item in enumerate(value):
                        visit(item, pointer + "/" + str(index))
                elif isinstance(value, dict):
                    sha = value.get("sha256")
                    pathname = value.get("path", value.get("relative_path", value.get("original_relative_path")))
                    pairs = [(pathname, sha, pointer + "/sha256")]
                    pairs.extend((key, val, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
                                 for key, val in value.items() if isinstance(val, str)
                                 and HEX.fullmatch(val) and ("/" in key or "." in key))
                    for pathname, sha, sha_pointer in pairs:
                        relpath = resolved(pathname, spec)
                        if relpath and isinstance(sha, str) and HEX.fullmatch(sha):
                            exact_path(relpath, sha, sha_pointer)
                    for key, item in value.items():
                        visit(item, pointer + "/" + key.replace("~", "~0").replace("/", "~1"))
            visit(obj)
        return by_path, by_hash

    def plan(self, *, hash_workers=4, metadata_workers=8, native_dense_keep=False):
        if not 1 <= hash_workers <= 8:
            _fail("hash_workers must be 1..8")
        if _exists(self.audit) or _exists(self.quarantine):
            _fail("plan requires new audit and quarantine identities")
        inventory, candidates, metadata = [], [], []
        totals = {"KEEP": 0, "BULK_DELETABLE": 0, "UNKNOWN": 0}
        self.inventory_walking = True
        for path, s in self._walk_plan(self.clean / "stages", workers=metadata_workers,
                                      native_dense_keep=native_dense_keep):
            relative = path.relative_to(self.clean).as_posix()
            classification, reason, family, file_class = self.classify(relative, s)
            group = self._inventory_group(relative)
            file_type = "regular" if stat.S_ISREG(s.st_mode) else "directory" if stat.S_ISDIR(s.st_mode) else "symlink" if stat.S_ISLNK(s.st_mode) else "special"
            row = dict(original_relative_path=relative, group=group, file_type=file_type,
                       size_bytes=s.st_size if file_type == "regular" else 0, nlink=s.st_nlink,
                       classification=classification, reason=reason, family=family, file_class=file_class,
                       device=s.st_dev, inode=s.st_ino, mtime_ns=s.st_mtime_ns,
                       metadata_source="WINDOWS_NATIVE_INDEPENDENT_KEEP" if isinstance(s, NativeKeepMetadata) else "LINUX_LSTAT",
                       identity_status="UNQUERIED" if isinstance(s, NativeKeepMetadata) else "QUERIED")
            inventory.append(row)
            totals[classification] += 1
            if classification == "BULK_DELETABLE":
                candidates.append(dict(row, device=s.st_dev, inode=s.st_ino, mtime_ns=s.st_mtime_ns))
            if (classification == "KEEP" and file_type == "regular" and s.st_size <= 1048576
                    and path.suffix.lower() == ".json"
                    and any(token in path.name.upper() for token in ("SEAL", "MANIFEST"))):
                metadata.append(path)
            if len(inventory) % 1000 == 0:
                print(f"inventory {len(inventory)} entries; candidates {len(candidates)}", flush=True)
        self.inventory_walking = False
        inventory.sort(key=lambda row: row["original_relative_path"])
        candidates.sort(key=lambda row: row["original_relative_path"])
        by_path, by_hash = self._seal_index(metadata)

        def hash_candidate(row):
            relative = row["original_relative_path"]
            known = by_path.get(relative, {})
            if len(known) > 1:
                _fail(f"conflicting sealed hashes: {relative}")
            if known:
                sha, evidence = next(iter(known)), "EXACT_PATH_SEAL_SHA256"
                provenance = known[sha]
            else:
                sha, now = hash_file(self.clean / relative, expected_size=row["size_bytes"])
                if (now.st_dev, now.st_ino, now.st_mtime_ns) != (row["device"], row["inode"], row["mtime_ns"]):
                    _fail(f"candidate changed after inventory: {relative}")
                evidence = "FRESH_STREAMING_SHA256"
                provenance = by_hash.get(sha, [])
            return dict(row, sha256=sha, hash_evidence=evidence, seal_provenance=provenance,
                        quarantine_relative_path="_PURGE_PENDING/" + self.timestamp + "/" + relative,
                        quarantine_timestamp=self.timestamp)

        planned = []
        with ThreadPoolExecutor(max_workers=hash_workers) as pool:
            for row in pool.map(hash_candidate, candidates):
                planned.append(row)
                if len(planned) % 100 == 0:
                    print(f"candidate hash evidence {len(planned)}/{len(candidates)}", flush=True)
        planned.sort(key=lambda row: row["original_relative_path"])
        plan_data = _csv_bytes(planned, PLAN_COLUMNS)
        ledger = dict(schema_version=VERSION, phase="PLANNED", quarantine_timestamp=self.timestamp,
                      **self.base_binding, plan_sha256=_digest(plan_data), entries=planned,
                      candidate_count=len(planned), candidate_bytes=sum(r["size_bytes"] for r in planned),
                      inventory_counts=totals, scientific_execution_count=0, raw_content_open_count=0,
                      native_dense_keep_enabled=bool(native_dense_keep),
                      native_independent_keep_count=sum(r["identity_status"] == "UNQUERIED" for r in inventory),
                      disk_available_bytes=os.statvfs(self.clean).f_bavail * os.statvfs(self.clean).f_frsize)
        grouped = {}
        for row in inventory:
            counts = grouped.setdefault(row["group"], dict(group=row["group"], regular_files=0,
                      logical_bytes=0, KEEP_files=0, KEEP_bytes=0, BULK_DELETABLE_files=0,
                      BULK_DELETABLE_bytes=0, UNKNOWN_files=0, UNKNOWN_bytes=0,
                      directories=0, symlinks_and_special=0))
            if row["file_type"] == "regular":
                counts["regular_files"] += 1
                counts["logical_bytes"] += row["size_bytes"]
                counts[row["classification"] + "_files"] += 1
                counts[row["classification"] + "_bytes"] += row["size_bytes"]
            elif row["file_type"] == "directory":
                counts["directories"] += 1
            else:
                counts["symlinks_and_special"] += 1
        group_columns = ["group", "regular_files", "logical_bytes", "KEEP_files", "KEEP_bytes",
                         "BULK_DELETABLE_files", "BULK_DELETABLE_bytes", "UNKNOWN_files", "UNKNOWN_bytes",
                         "directories", "symlinks_and_special"]
        _write_new(self.audit / "STORAGE_INVENTORY.csv", _csv_bytes(
            [grouped[key] for key in sorted(grouped)], group_columns))
        _write_new(self.audit / "FILE_INVENTORY.csv", _csv_bytes(inventory, INVENTORY_COLUMNS))
        _write_new(self.audit / "UNKNOWN_FILES.csv", _csv_bytes(
            [row for row in inventory if row["classification"] == "UNKNOWN"], INVENTORY_COLUMNS))
        _write_new(self.audit / "REFERENCE_CLOSURE.json", self.closure_bytes)
        _write_new(self.audit / "DELETION_PLAN.csv", plan_data)
        _write_new(self.audit / "DELETION_LEDGER.json", _json_bytes(ledger))
        print(f"PLANNED {len(planned)} exact files, {ledger['candidate_bytes']} logical bytes", flush=True)
        return ledger

    def _ledger(self):
        data = _read(self.audit / "DELETION_LEDGER.json")
        ledger = json.loads(data)
        if ledger.get("schema_version") != VERSION or ledger.get("quarantine_timestamp") != self.timestamp:
            _fail("ledger identity mismatch")
        if any(ledger.get(k) != v for k, v in self.base_binding.items()):
            _fail("policy or closure changed since plan")
        if _read(self.audit / "REFERENCE_CLOSURE.json") != self.closure_bytes:
            _fail("saved reference closure mismatch")
        if _digest(_read(self.audit / "DELETION_PLAN.csv")) != ledger.get("plan_sha256"):
            _fail("plan hash mismatch")
        entries = ledger["entries"]
        if _csv_bytes(entries, PLAN_COLUMNS) != _read(self.audit / "DELETION_PLAN.csv"):
            _fail("ledger entries do not exactly reproduce plan")
        seen = set()
        for row in entries:
            relative = _relative(row["original_relative_path"])
            expected_q = "_PURGE_PENDING/" + self.timestamp + "/" + relative
            if (not relative.startswith("stages/") or row["quarantine_relative_path"] != expected_q
                    or relative in seen or not HEX.fullmatch(row["sha256"])
                    or type(row["size_bytes"]) is not int or row["size_bytes"] < 0
                    or row["quarantine_timestamp"] != self.timestamp):
                _fail("invalid or duplicate ledger entry")
            seen.add(relative)
        if len(entries) != ledger["candidate_count"] or sum(r["size_bytes"] for r in entries) != ledger["candidate_bytes"]:
            _fail("ledger count/size mismatch")
        return ledger, dict(self.base_binding, plan_sha256=ledger["plan_sha256"], ledger_sha256=_digest(data))

    def _references(self, removed):
        records = []
        if self.closure.get("unresolved_required_paths"):
            _fail("C2 closure contains unresolved required record references")
        for path, expected in self.closure.get("source_documents_sha256", {}).items():
            actual = _digest(_read(self.code / _relative(path)))
            if actual != expected:
                _fail(f"closure source document changed: {path}")
        for alias, expected in self.closure.get("frozen_source_sha256", {}).items():
            actual = _digest(_read(self.alias(alias)))
            if actual != expected:
                _fail(f"frozen closure source changed: {alias}")
        required = list(self.closure.get("required_paths", []))
        required.extend({"path": "<CLEAN_ROOT>/" + p, "kind": "file"} for p in self.keep_files)
        required.extend({"path": "<CLEAN_ROOT>/" + p, "kind": "directory"}
                        for p in (*self.keep_dirs, *self.closure.get("protected_dir_entries", [])))
        for item in required:
            path = self.alias(item["path"])
            _absolute_without_links(path)
            s = _stat(path)
            kind = item.get("kind", "file")
            if kind not in {"file", "directory"}:
                _fail("unknown reference kind")
            if not (stat.S_ISREG(s.st_mode) if kind == "file" else stat.S_ISDIR(s.st_mode)):
                _fail(f"required reference has wrong type: {item['path']}")
            try:
                rel = path.relative_to(self.clean).as_posix()
            except ValueError:
                rel = None
            if rel in removed:
                _fail(f"required reference selected for removal: {item['path']}")
            records.append({"path": item["path"], "kind": kind, "exists_after_simulated_removal": True,
                            "payload_hash_not_recomputed": True})
        return records

    @_serialized
    def gate(self):
        ledger, binding = self._ledger()
        if _exists(self.audit / "JOURNAL.jsonl"):
            _fail("pre-move gates cannot be recreated after physical operations")
        for row in ledger["entries"]:
            path = self.clean / row["original_relative_path"]
            s = _stat(path)
            _regular_single(s, path)
            result = self.classify(row["original_relative_path"], s)
            if result[0] != "BULK_DELETABLE" or result[2:] != (row["family"], row["file_class"]):
                _fail(f"C1 no longer eligible: {path}")
            if (s.st_size, s.st_dev, s.st_ino, s.st_mtime_ns) != (
                    row["size_bytes"], row["device"], row["inode"], row["mtime_ns"]):
                _fail(f"C3 source metadata changed: {path}")
            if _exists(self.clean / row["quarantine_relative_path"]):
                _fail("quarantine destination collision")
        references = self._references({r["original_relative_path"] for r in ledger["entries"]})
        for alias, expected in {p["path"]: p["sha256"] for row in ledger["entries"]
                                 for p in row["seal_provenance"]}.items():
            if _digest(_read(self.alias(alias))) != expected:
                _fail(f"seal provenance metadata changed: {alias}")
        result = dict(binding, gates={"C1": "PASS", "C2": "PASS", "C3": "PASS"},
                      keep_match_count=0, outside_stages_count=0, invalidclassfamily_count=0,
                      candidate_count=len(ledger["entries"]), references=references,
                      c3_note="immutable plan contains SHA256, size and quarantine timestamp; C4 rehashes payload")
        _write_or_verify(self.audit / "GATE_PRE_MOVE.json", result)
        return result

    def _receipt(self, name, binding, gates):
        obj = _load(self.audit / name)
        if any(obj.get(k) != v for k, v in binding.items()):
            _fail(f"receipt binding mismatch: {name}")
        if any(obj.get("gates", {}).get(gate) != "PASS" for gate in gates):
            _fail(f"required gates not PASS: {name}")
        return obj

    def _journal(self, binding):
        path = self.audit / "JOURNAL.jsonl"
        events = []
        previous = "0" * 64
        if _exists(path):
            data = _read(path)
            if data and not data.endswith(b"\n"):
                _fail("torn journal tail; preserve quarantine for supervised recovery")
            for line in data.splitlines():
                event = json.loads(line)
                sha = event.pop("event_sha256")
                if (event.get("previous_sha256") != previous or event.get("sequence") != len(events) + 1
                        or event.get("binding") != binding or _digest(_json_bytes(event)) != sha):
                    _fail("journal chain or plan binding mismatch")
                event["event_sha256"] = sha
                events.append(event)
                previous = sha
        return events

    @staticmethod
    def _event_actions(ledger, events):
        registered = {r["original_relative_path"]: r for r in ledger["entries"]}
        actions = {}
        for event in events:
            relative = event["original_relative_path"]
            row = registered.get(relative)
            if row is None or any(event[k] != row[k] for k in ["sha256", "size_bytes"]):
                _fail("journal item does not match exact ledger")
            action = event["action"]
            prior = actions.setdefault(relative, set())
            if action not in {"MOVE_PREPARED", "MOVED_HASH_VERIFIED", "PURGE_PREPARED", "PURGED"}:
                _fail("unknown journal action")
            required = {"MOVED_HASH_VERIFIED": "MOVE_PREPARED", "PURGE_PREPARED": "MOVED_HASH_VERIFIED",
                        "PURGED": "PURGE_PREPARED"}.get(action)
            if required and required not in prior:
                _fail("journal action lacks durable predecessor")
            prior.add(action)
        return actions

    def _append(self, events, binding, action, row, **extra):
        event = dict(sequence=len(events) + 1, previous_sha256=events[-1]["event_sha256"] if events else "0" * 64,
                     binding=binding, action=action, time_utc=_utc(),
                     original_relative_path=row["original_relative_path"], sha256=row["sha256"],
                     size_bytes=row["size_bytes"], **extra)
        event["event_sha256"] = _digest(_json_bytes(event))
        with _parent_fd(self.audit / "JOURNAL.jsonl") as (parent, name):
            fd = os.open(name, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            _regular_single(os.fstat(fd), "journal")
            with os.fdopen(fd, "ab") as stream:
                stream.write(json.dumps(event, sort_keys=True).encode() + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(parent)
        events.append(event)

    def _exact_quarantine(self, ledger, absent=()):
        expected = {r["quarantine_relative_path"] for r in ledger["entries"]
                    if r["original_relative_path"] not in absent}
        all_dirs = set()
        for relative in (r["quarantine_relative_path"] for r in ledger["entries"]):
            p = PurePosixPath(relative).parent
            while p.as_posix() != "_PURGE_PENDING/" + self.timestamp:
                all_dirs.add(p.as_posix())
                p = p.parent
        found = set()
        if _exists(self.quarantine):
            for path, s in self._walk(self.quarantine):
                relative = path.relative_to(self.clean).as_posix()
                if stat.S_ISDIR(s.st_mode):
                    if relative not in all_dirs:
                        _fail(f"unexpected quarantine directory: {relative}")
                elif stat.S_ISREG(s.st_mode) and s.st_nlink == 1:
                    found.add(relative)
                else:
                    _fail(f"unexpected quarantine symlink/special/hardlink: {relative}")
        if found != expected:
            _fail(f"quarantine exact set mismatch: missing={len(expected-found)}, extra={len(found-expected)}")

    @staticmethod
    def _rename_noreplace(source, destination):
        libc = ctypes.CDLL(None, use_errno=True)
        rename = getattr(libc, "renameat2", None)
        if rename is None:
            _fail("renameat2(RENAME_NOREPLACE) unavailable; no copy/overwrite fallback")
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        with _parent_fd(source) as (src, srcname), _parent_fd(destination, create=True) as (dst, dstname):
            if os.fstat(src).st_dev != os.fstat(dst).st_dev:
                _fail("cross-filesystem rename forbidden")
            if rename(src, os.fsencode(srcname), dst, os.fsencode(dstname), 1) != 0:
                number = ctypes.get_errno()
                raise OSError(number, os.strerror(number), str(destination))
            os.fsync(src)
            os.fsync(dst)

    @_serialized
    def quarantine_files(self):
        ledger, binding = self._ledger()
        self._receipt("GATE_PRE_MOVE.json", binding, ["C1", "C2", "C3"])
        self._references({r["original_relative_path"] for r in ledger["entries"]})
        events = self._journal(binding)
        actions_by_path = self._event_actions(ledger, events)
        if any(e["action"].startswith("PURGE") for e in events):
            _fail("quarantine phase cannot run after purge started")
        for i, row in enumerate(ledger["entries"], 1):
            relative = row["original_relative_path"]
            source, destination = self.clean / relative, self.clean / row["quarantine_relative_path"]
            actions = actions_by_path.get(relative, set())
            if _exists(destination):
                if _exists(source) or "MOVE_PREPARED" not in actions:
                    _fail(f"destination collision or unjournaled move: {relative}")
                digest, _ = hash_file(destination, expected_size=row["size_bytes"])
                if digest != row["sha256"]:
                    _fail(f"quarantined hash mismatch: {relative}")
                if "MOVED_HASH_VERIFIED" not in actions:
                    self._append(events, binding, "MOVED_HASH_VERIFIED", row, recovered_after_prepare=True)
                continue
            if "MOVED_HASH_VERIFIED" in actions:
                _fail(f"journaled quarantine file is missing: {relative}")
            s = _stat(source)
            if self.classify(relative, s)[0] != "BULK_DELETABLE":
                _fail(f"KEEP or unknown file at move checkpoint: {relative}")
            digest, before = hash_file(source, expected_size=row["size_bytes"])
            if digest != row["sha256"]:
                _fail(f"source hash mismatch before move: {relative}")
            if (before.st_dev, before.st_ino, before.st_mtime_ns) != (row["device"], row["inode"], row["mtime_ns"]):
                _fail(f"source metadata changed before move: {relative}")
            with _parent_fd(destination, create=True) as (parent, _):
                if os.fstat(parent).st_dev != before.st_dev:
                    _fail("cross-filesystem quarantine forbidden")
            self._append(events, binding, "MOVE_PREPARED", row)
            if not _same_stat(_stat(source), before):
                _fail(f"source changed immediately before rename: {relative}")
            self._rename_noreplace(source, destination)
            digest, _ = hash_file(destination, expected_size=row["size_bytes"])
            if digest != row["sha256"] or _exists(source):
                _fail(f"post-rename hash/location mismatch: {relative}")
            self._append(events, binding, "MOVED_HASH_VERIFIED", row)
            if i % 100 == 0:
                print(f"quarantined {i}/{len(ledger['entries'])} verified files", flush=True)
        self._exact_quarantine(ledger)
        result = dict(binding, gates={"C4": "PASS"}, verified_files=len(ledger["entries"]),
                      exact_quarantine_set=True)
        _write_or_verify(self.audit / "GATE_QUARANTINE.json", result)
        return result

    @_serialized
    def purge(self, c5_receipt):
        ledger, binding = self._ledger()
        self._receipt("GATE_PRE_MOVE.json", binding, ["C1", "C2", "C3"])
        self._receipt("GATE_QUARANTINE.json", binding, ["C4"])
        c5 = _load(c5_receipt)
        if (any(c5.get(k) != v for k, v in binding.items()) or c5.get("gates", {}).get("C5") != "PASS"
                or not C5_CHECKS <= c5.get("checks", {}).keys()
                or any(value != "PASS" for value in c5["checks"].values())):
            _fail("C5 independent checks or plan/ledger binding not PASS")
        self._references({r["original_relative_path"] for r in ledger["entries"]})
        events = self._journal(binding)
        actions = self._event_actions(ledger, events)
        if any("MOVED_HASH_VERIFIED" not in actions.get(r["original_relative_path"], set())
               for r in ledger["entries"]):
            _fail("purge requires every item durably hash-verified after move")
        removed = {e["original_relative_path"] for e in events if e["action"] == "PURGED"}
        prepared = {e["original_relative_path"] for e in events if e["action"] == "PURGE_PREPARED"}
        # A crash after unlink but before its checkpoint is recovered only with a durable intent.
        for row in ledger["entries"]:
            relative = row["original_relative_path"]
            if relative in prepared and relative not in removed and not _exists(self.clean / row["quarantine_relative_path"]):
                if _exists(self.clean / relative):
                    _fail("original path reappeared during purge recovery")
                self._append(events, binding, "PURGED", row, recovered_after_prepare=True)
                removed.add(relative)
        self._exact_quarantine(ledger, removed)
        for i, row in enumerate(ledger["entries"], 1):
            relative = row["original_relative_path"]
            if relative in removed:
                continue
            path = self.clean / row["quarantine_relative_path"]
            if _exists(self.clean / relative):
                _fail(f"original path reappeared: {relative}")
            digest, before = hash_file(path, expected_size=row["size_bytes"])
            if digest != row["sha256"]:
                _fail(f"quarantine hash changed before unlink: {relative}")
            self._append(events, binding, "PURGE_PREPARED", row)
            with _parent_fd(path) as (parent, name):
                if not _same_stat(os.stat(name, dir_fd=parent, follow_symlinks=False), before):
                    _fail(f"quarantine changed immediately before unlink: {relative}")
                os.unlink(name, dir_fd=parent)
                os.fsync(parent)
            self._append(events, binding, "PURGED", row)
            removed.add(relative)
            if i % 100 == 0:
                print(f"purged {i}/{len(ledger['entries'])} checkpointed files", flush=True)
        self._exact_quarantine(ledger, removed)
        # Only known, now-empty quarantine directories are removed. Original directories persist.
        if _exists(self.quarantine):
            directories = [p for p, s in self._walk(self.quarantine) if stat.S_ISDIR(s.st_mode)]
            for directory in sorted(directories, key=lambda p: len(p.parts), reverse=True) + [self.quarantine]:
                with _parent_fd(directory) as (parent, name):
                    os.rmdir(name, dir_fd=parent)
                    os.fsync(parent)
        result = dict(binding, gates={f"C{i}": "PASS" for i in range(1, 6)},
                      purged_files=len(removed), purged_logical_bytes=ledger["candidate_bytes"],
                      c5_receipt_sha256=_digest(_read(c5_receipt)), original_directories_retained=True)
        _write_or_verify(self.audit / "PURGE_RESULT.json", result)
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=["plan", "gate", "quarantine", "purge"])
    for name in ["clean-root", "code-root", "policy", "closure", "audit-root"]:
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--hash-workers", type=int, default=4)
    parser.add_argument("--metadata-workers", type=int, default=8)
    parser.add_argument("--native-dense-keep", action="store_true",
                        help="plan only: identity-free metadata only for dense all-independent-KEEP directories")
    parser.add_argument("--c5-receipt", type=Path)
    args = parser.parse_args(argv)
    try:
        utility = StoragePurge(args.clean_root, args.code_root, args.policy, args.closure, args.audit_root)
        if args.phase == "plan":
            result = utility.plan(hash_workers=args.hash_workers, metadata_workers=args.metadata_workers,
                                  native_dense_keep=args.native_dense_keep)
        elif args.phase == "gate":
            result = utility.gate()
        elif args.phase == "quarantine":
            result = utility.quarantine_files()
        else:
            if args.c5_receipt is None:
                _fail("purge requires --c5-receipt")
            result = utility.purge(args.c5_receipt)
        print(json.dumps({k: v for k, v in result.items() if k not in {"entries", "references"}}, sort_keys=True), flush=True)
        return 0
    except (PurgeError, OSError, ValueError, KeyError) as exc:
        print(f"STOP_PRESERVE_CURRENT_STATE: {exc}", file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
