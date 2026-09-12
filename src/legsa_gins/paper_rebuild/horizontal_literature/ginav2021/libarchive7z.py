"""Pinned, fail-closed libarchive reader for the official GINav 7z sample.

This module intentionally exposes only two operations: a header-only inventory
and an exact-member extraction.  It never delegates to a command-line archive
tool and never invokes libarchive's general-purpose extraction API.
"""

from __future__ import annotations

import collections
import contextlib
import ctypes
import dataclasses
import hashlib
import json
import os
import stat
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping, Sequence


PINNED_LIBARCHIVE_SHA256 = (
    "b668621ff255cc106907516dc58c6454b32323328fe6014614f4719d9c3a6bb6"
)
PINNED_LIBARCHIVE_VERSION_NUMBER = 3_006_000
PINNED_LIBARCHIVE_VERSION_STRING = "libarchive 3.6.0"
PINNED_LIBARCHIVE_PACKAGE = "libarchive13"
PINNED_LIBARCHIVE_PACKAGE_VERSION = "3.6.0-1ubuntu1.8"
PINNED_LIBARCHIVE_SONAME = "libarchive.so.13"

ARCHIVE_EOF = 1
ARCHIVE_OK = 0
ARCHIVE_RETRY = -10
ARCHIVE_WARN = -20
ARCHIVE_FAILED = -25
ARCHIVE_FATAL = -30
ARCHIVE_FILTER_NONE = 0
ARCHIVE_FORMAT_7ZIP = 0xE0000
ARCHIVE_FORMAT_BASE_MASK = 0xFF0000

S_IFMT = 0o170000
S_IFREG = 0o100000
S_IFDIR = 0o040000

MAX_ARCHIVE_MEMBER_COUNT = 100_000
MAX_ARCHIVE_MEMBER_BYTES = 4 * 1024 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES = 8 * 1024 * 1024 * 1024
ARCHIVE_READ_BLOCK_SIZE = 64 * 1024
HASH_READ_BLOCK_SIZE = 1024 * 1024


class Libarchive7zError(RuntimeError):
    """Base class for pinned archive backend failures."""


class LibarchivePreflightError(Libarchive7zError):
    """The explicitly supplied library does not satisfy the pinned ABI."""


class LibarchiveInventoryError(Libarchive7zError):
    """The archive header inventory violates the frozen contract."""


class LibarchiveExtractionError(Libarchive7zError):
    """Exact-member extraction failed closed."""


@dataclasses.dataclass(frozen=True)
class _FileIdentity:
    path: Path
    device: int
    inode: int
    size: int
    sha256: str

    def evidence(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "device": self.device,
            "inode": self.inode,
            "bytes": self.size,
            "sha256": self.sha256,
        }


_ABI_SIGNATURES: dict[str, tuple[Sequence[Any], Any]] = {
    "archive_version_number": ((), ctypes.c_int),
    "archive_version_string": ((), ctypes.c_char_p),
    "archive_version_details": ((), ctypes.c_char_p),
    "archive_read_new": ((), ctypes.c_void_p),
    "archive_read_support_filter_none": ((ctypes.c_void_p,), ctypes.c_int),
    "archive_read_support_format_7zip": ((ctypes.c_void_p,), ctypes.c_int),
    "archive_read_open_fd": (
        (ctypes.c_void_p, ctypes.c_int, ctypes.c_size_t), ctypes.c_int
    ),
    "archive_read_next_header": (
        (ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)), ctypes.c_int
    ),
    "archive_read_data_skip": ((ctypes.c_void_p,), ctypes.c_int),
    "archive_read_data_block": (
        (
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.POINTER(ctypes.c_int64),
        ),
        ctypes.c_int,
    ),
    "archive_read_has_encrypted_entries": ((ctypes.c_void_p,), ctypes.c_int),
    "archive_filter_count": ((ctypes.c_void_p,), ctypes.c_int),
    "archive_filter_code": ((ctypes.c_void_p, ctypes.c_int), ctypes.c_int),
    "archive_format": ((ctypes.c_void_p,), ctypes.c_int),
    "archive_error_string": ((ctypes.c_void_p,), ctypes.c_char_p),
    "archive_errno": ((ctypes.c_void_p,), ctypes.c_int),
    "archive_read_close": ((ctypes.c_void_p,), ctypes.c_int),
    "archive_read_free": ((ctypes.c_void_p,), ctypes.c_int),
    "archive_entry_pathname_utf8": ((ctypes.c_void_p,), ctypes.c_char_p),
    "archive_entry_size_is_set": ((ctypes.c_void_p,), ctypes.c_int),
    "archive_entry_size": ((ctypes.c_void_p,), ctypes.c_int64),
    "archive_entry_filetype": ((ctypes.c_void_p,), ctypes.c_uint),
    "archive_entry_symlink_utf8": ((ctypes.c_void_p,), ctypes.c_char_p),
    "archive_entry_hardlink_utf8": ((ctypes.c_void_p,), ctypes.c_char_p),
    "archive_entry_is_encrypted": ((ctypes.c_void_p,), ctypes.c_int),
    "archive_entry_sparse_reset": ((ctypes.c_void_p,), ctypes.c_int),
}
REQUIRED_ABI_SYMBOLS = tuple(sorted(_ABI_SIGNATURES))


def _absolute_no_symlink_regular(path: Path, *, role: str) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        raise LibarchivePreflightError(f"{role} path must be absolute")
    candidate = Path(os.path.normpath(str(candidate)))
    current = Path(candidate.anchor)
    for part in candidate.parts[1:]:
        current = current / part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise LibarchivePreflightError(
                f"cannot resolve {role} path component: {current}: {exc}"
            ) from exc
        if stat.S_ISLNK(metadata.st_mode):
            raise LibarchivePreflightError(
                f"{role} path has a symlink component: {current}"
            )
    metadata = os.lstat(candidate)
    if not stat.S_ISREG(metadata.st_mode):
        raise LibarchivePreflightError(f"{role} path is not a regular file")
    resolved = candidate.resolve(strict=True)
    if resolved != candidate:
        raise LibarchivePreflightError(f"{role} path is not its resolved identity")
    return resolved


def _snapshot_regular_file(path: Path, *, role: str) -> _FileIdentity:
    resolved = _absolute_no_symlink_regular(path, role=role)
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(resolved, flags)
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise LibarchivePreflightError(f"{role} descriptor is not a regular file")
        digest = hashlib.sha256()
        while True:
            block = os.read(descriptor, HASH_READ_BLOCK_SIZE)
            if not block:
                break
            digest.update(block)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    if (before.st_dev, before.st_ino, before.st_size) != (
        after.st_dev, after.st_ino, after.st_size
    ):
        raise LibarchivePreflightError(f"{role} changed while hashing")
    path_metadata = os.lstat(resolved)
    if (before.st_dev, before.st_ino, before.st_size) != (
        path_metadata.st_dev, path_metadata.st_ino, path_metadata.st_size
    ):
        raise LibarchivePreflightError(f"{role} path identity changed while hashing")
    return _FileIdentity(
        resolved, before.st_dev, before.st_ino, before.st_size, digest.hexdigest()
    )


def _same_file_identity(before: _FileIdentity, after: _FileIdentity, *, role: str) -> None:
    if before != after:
        raise Libarchive7zError(f"{role} hash/inode/size identity changed")


def _strict_text(raw: bytes | None, *, field: str, error_type: type[Libarchive7zError]) -> str:
    if raw is None:
        raise error_type(f"archive entry {field} is null")
    try:
        value = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise error_type(f"archive entry {field} is not strict UTF-8") from exc
    if not value or "\x00" in value:
        raise error_type(f"archive entry {field} is empty or contains NUL")
    if unicodedata.normalize("NFC", value) != value:
        raise error_type(f"archive entry {field} is not NFC-normalized")
    return value


def _safe_member_path(
    raw: bytes | None,
    *,
    directory: bool,
    error_type: type[Libarchive7zError] = LibarchiveInventoryError,
) -> tuple[str, str, bool]:
    value = _strict_text(
        raw, field="pathname", error_type=error_type
    )
    if "\\" in value:
        raise error_type(
            f"archive member uses a non-POSIX path separator: {value!r}"
        )
    if (
        len(value.encode("utf-8")) > 4096
        or any(len(part.encode("utf-8")) > 255 for part in value.split("/"))
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise error_type(
            f"archive member path has a control character or exceeds bounds: {value!r}"
        )
    trailing_slash = value.endswith("/")
    if trailing_slash:
        if not directory:
            raise error_type(
                "archive regular/special member path has a trailing slash: "
                f"{value!r}"
            )
        if value.endswith("//"):
            raise error_type(
                f"archive directory path has more than one trailing slash: {value!r}"
            )
        canonical = value[:-1]
    else:
        canonical = value
    pure = PurePosixPath(canonical)
    if (
        pure.is_absolute()
        or canonical.startswith("//")
        or any(part in {"", ".", ".."} for part in canonical.split("/"))
        or any(":" in part for part in pure.parts)
    ):
        raise error_type(f"unsafe archive member path: {value!r}")
    normalized = pure.as_posix()
    if normalized != canonical:
        raise error_type(
            f"archive member path is not canonical POSIX form: {value!r}"
        )
    return normalized, value, trailing_slash


def _validate_member_collisions(members: Sequence[Mapping[str, Any]]) -> None:
    by_fold: dict[str, str] = {}
    by_path = {str(item["path"]): str(item["kind"]) for item in members}
    for item in members:
        value = str(item["path"])
        folded = value.casefold()
        prior = by_fold.get(folded)
        if prior is not None:
            raise LibarchiveInventoryError(
                f"archive has duplicate/casefold-colliding paths: {prior!r}, {value!r}"
            )
        by_fold[folded] = value
    folded_paths = set(by_fold)
    for value, kind in by_path.items():
        parts = PurePosixPath(value).parts
        for index in range(1, len(parts)):
            prefix = PurePosixPath(*parts[:index]).as_posix()
            prefix_folded = prefix.casefold()
            if prefix_folded in folded_paths:
                actual = by_fold[prefix_folded]
                if by_path[actual] != "directory":
                    raise LibarchiveInventoryError(
                        f"archive path prefix is not a directory: {actual!r} prefixes {value!r}"
                    )
                if actual != prefix:
                    raise LibarchiveInventoryError(
                        f"archive path prefix has a casefold collision: {actual!r}, {prefix!r}"
                    )
        if kind == "regular":
            prefix = value.casefold() + "/"
            descendants = [path for path in folded_paths if path.startswith(prefix)]
            if descendants:
                raise LibarchiveInventoryError(
                    f"regular archive member prefixes another member: {value!r}"
                )


def _selected_paths(inventory: Mapping[str, Any]) -> tuple[str, str, str]:
    selected = tuple(
        str(inventory[key])
        for key in (
            "selected_observation_member",
            "selected_navigation_member",
            "selected_imu_member",
        )
    )
    if len(selected) != 3 or len(set(selected)) != 3:
        raise LibarchiveExtractionError("selected archive member allowlist is not exact")
    inventory_files = {
        str(item["path"])
        for item in inventory.get("members", ())
        if item.get("kind") == "regular" or not item.get("directory", False)
    }
    if set(selected) - inventory_files:
        raise LibarchiveExtractionError("selected member is absent from inventory")
    return selected  # type: ignore[return-value]


def _strict_sha256(value: Any, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise LibarchiveExtractionError(
            f"frozen archive inventory has an invalid {field}"
        )
    return value


def _frozen_archive_content_identity(
    inventory: Mapping[str, Any],
) -> dict[str, Any]:
    """Return the relocation-safe hash/size identity frozen by inventory."""

    archive_sha256 = _strict_sha256(
        inventory.get("archive_sha256"), field="archive_sha256"
    )
    before = inventory.get("archive_identity_before")
    after = inventory.get("archive_identity_after")
    if not isinstance(before, Mapping) or not isinstance(after, Mapping):
        raise LibarchiveExtractionError(
            "frozen archive inventory lacks before/after identity evidence"
        )
    before_sha256 = _strict_sha256(
        before.get("sha256"), field="archive_identity_before.sha256"
    )
    after_sha256 = _strict_sha256(
        after.get("sha256"), field="archive_identity_after.sha256"
    )
    before_bytes = before.get("bytes")
    after_bytes = after.get("bytes")
    if (
        isinstance(before_bytes, bool)
        or not isinstance(before_bytes, int)
        or before_bytes < 0
        or isinstance(after_bytes, bool)
        or not isinstance(after_bytes, int)
        or after_bytes < 0
    ):
        raise LibarchiveExtractionError(
            "frozen archive inventory has invalid before/after byte sizes"
        )
    if not (
        archive_sha256 == before_sha256 == after_sha256
        and before_bytes == after_bytes
    ):
        raise LibarchiveExtractionError(
            "frozen archive inventory hash/size evidence is internally inconsistent"
        )
    return {"sha256": archive_sha256, "bytes": before_bytes}


def frozen_inventory_binding_sha256(inventory: Mapping[str, Any]) -> str:
    """Digest the exact archive content, ordered headers, and selected roles."""

    content_identity = _frozen_archive_content_identity(inventory)
    selected = _selected_paths(inventory)
    members = []
    member_fields = (
        "index", "path", "bytes", "kind", "directory", "encrypted",
        "link_or_reparse", "sparse_extent_count", "size_is_set", "size_contract",
        "archive_pathname_utf8", "directory_pathname_trailing_slash",
        "header_metadata_sha256",
    )
    for item in inventory.get("members", ()):
        if not isinstance(item, Mapping):
            raise LibarchiveExtractionError(
                "frozen archive inventory member is not a mapping"
            )
        members.append({key: item.get(key) for key in member_fields})
    if not members:
        raise LibarchiveExtractionError("archive inventory is empty")
    payload = {
        "archive_content_identity": content_identity,
        "members": members,
        "selected_members": {
            "observation": selected[0],
            "navigation": selected[1],
            "imu": selected[2],
        },
    }
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def _open_absolute_directory_nofollow(path: Path) -> int:
    """Open an existing absolute directory one no-follow component at a time."""

    candidate = Path(os.path.normpath(str(path)))
    if not candidate.is_absolute():
        raise LibarchiveExtractionError("extraction destination must be absolute")
    flags = (
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(candidate.anchor, flags)
    try:
        for part in candidate.parts[1:]:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except OSError as exc:
        os.close(descriptor)
        raise LibarchiveExtractionError(
            f"extraction parent is missing, non-directory, or symlinked: {candidate}"
        ) from exc
    except BaseException:
        os.close(descriptor)
        raise


class Libarchive7zBackend:
    """One pinned libarchive ABI with auditable header/read call counts."""

    def __init__(self, library_path: Path, *, _loader: Any = None) -> None:
        self._api_counts: collections.Counter[str] = collections.Counter()
        self._library_before = _snapshot_regular_file(
            library_path, role="libarchive library"
        )
        if self._library_before.sha256 != PINNED_LIBARCHIVE_SHA256:
            raise LibarchivePreflightError(
                "libarchive library SHA256 does not match the pinned binary"
            )
        loader = ctypes.CDLL if _loader is None else _loader
        try:
            mode = getattr(os, "RTLD_LOCAL", 0) | getattr(os, "RTLD_NOW", 0)
            self._library = loader(
                str(self._library_before.path), mode=mode, use_errno=True
            )
        except (OSError, TypeError) as exc:
            raise LibarchivePreflightError(f"cannot load pinned libarchive: {exc}") from exc
        self._library_after_load = _snapshot_regular_file(
            self._library_before.path, role="libarchive library"
        )
        _same_file_identity(
            self._library_before, self._library_after_load, role="libarchive library"
        )
        missing = [name for name in REQUIRED_ABI_SYMBOLS if not hasattr(self._library, name)]
        if missing:
            raise LibarchivePreflightError(
                "pinned libarchive is missing required ABI symbols: " + ",".join(missing)
            )
        for name, (argtypes, restype) in _ABI_SIGNATURES.items():
            function = getattr(self._library, name)
            function.argtypes = list(argtypes)
            function.restype = restype
        version_number = int(self._call("archive_version_number"))
        version_raw = self._call("archive_version_string")
        version_details_raw = self._call("archive_version_details")
        version_string = _strict_text(
            version_raw, field="version string", error_type=LibarchivePreflightError
        )
        version_details = _strict_text(
            version_details_raw, field="version details",
            error_type=LibarchivePreflightError,
        )
        if version_number != PINNED_LIBARCHIVE_VERSION_NUMBER:
            raise LibarchivePreflightError(
                f"libarchive ABI version mismatch: {version_number}"
            )
        if version_string != PINNED_LIBARCHIVE_VERSION_STRING:
            raise LibarchivePreflightError(
                f"libarchive runtime version mismatch: {version_string!r}"
            )
        support_evidence = self._preflight_reader_support()
        library_after_preflight = _snapshot_regular_file(
            self._library_before.path, role="libarchive library"
        )
        _same_file_identity(
            self._library_before, library_after_preflight, role="libarchive library"
        )
        self.identity = {
            "schema_version": "ginav2021.libarchive7z_backend.v1",
            "backend": "ctypes_libarchive_public_abi",
            "library_path": str(self._library_before.path),
            "library_sha256": self._library_before.sha256,
            "library_device": self._library_before.device,
            "library_inode": self._library_before.inode,
            "library_bytes": self._library_before.size,
            "package": PINNED_LIBARCHIVE_PACKAGE,
            "package_version": PINNED_LIBARCHIVE_PACKAGE_VERSION,
            "soname": PINNED_LIBARCHIVE_SONAME,
            "archive_version_number": version_number,
            "archive_version_string": version_string,
            "archive_version_details": version_details,
            "required_symbols": list(REQUIRED_ABI_SYMBOLS),
            "enabled_filter": "filter_none",
            "enabled_format": "format_7zip",
            "reader_support_preflight": support_evidence,
            "install_performed": False,
            "subprocess_used": False,
            "general_extract_api_used": False,
            "preflight_api_call_counts": dict(sorted(self._api_counts.items())),
            "source_identity_before": self._library_before.evidence(),
            "source_identity_after_load": self._library_after_load.evidence(),
            "source_identity_after_preflight": library_after_preflight.evidence(),
            "pass": True,
        }

    def _call(self, name: str, *arguments: Any) -> Any:
        self._api_counts[name] += 1
        return getattr(self._library, name)(*arguments)

    def _error(self, archive: Any) -> str:
        archive_errno = int(self._call("archive_errno", archive))
        raw = self._call("archive_error_string", archive)
        if raw is None:
            return f"errno={archive_errno}; libarchive supplied no error string"
        try:
            return f"errno={archive_errno}; " + raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return f"errno={archive_errno}; libarchive supplied a non-UTF8 error string"

    def _require_ok(
        self, status: int, *, operation: str, archive: Any,
        error_type: type[Libarchive7zError],
    ) -> None:
        if int(status) != ARCHIVE_OK:
            raise error_type(
                f"{operation} returned non-OK status {int(status)}: {self._error(archive)}"
            )

    def _preflight_reader_support(self) -> dict[str, Any]:
        archive = self._call("archive_read_new")
        if not archive:
            raise LibarchivePreflightError("archive_read_new returned null in preflight")
        primary: LibarchivePreflightError | None = None
        try:
            self._require_ok(
                self._call("archive_read_support_filter_none", archive),
                operation="archive_read_support_filter_none", archive=archive,
                error_type=LibarchivePreflightError,
            )
            self._require_ok(
                self._call("archive_read_support_format_7zip", archive),
                operation="archive_read_support_format_7zip", archive=archive,
                error_type=LibarchivePreflightError,
            )
        except LibarchivePreflightError as exc:
            primary = exc
        free_status = int(self._call("archive_read_free", archive))
        if free_status != ARCHIVE_OK:
            cleanup = f"archive_read_free={free_status} in reader-support preflight"
            if primary is None:
                primary = LibarchivePreflightError(cleanup)
            else:
                primary.args = (f"{primary}; {cleanup}",)
            setattr(primary, "cleanup_diagnostics", (cleanup,))
        try:
            self._verify_library_unchanged()
        except (OSError, Libarchive7zError) as exc:
            identity_error = f"libarchive source identity after preflight: {exc}"
            if primary is None:
                raise LibarchivePreflightError(identity_error) from exc
            primary.args = (f"{primary}; {identity_error}",)
            diagnostics = tuple(getattr(primary, "cleanup_diagnostics", ()))
            setattr(primary, "cleanup_diagnostics", diagnostics + (identity_error,))
        if primary is not None:
            raise primary
        return {
            "archive_read_new_nonnull": True,
            "archive_read_support_filter_none_status": ARCHIVE_OK,
            "archive_read_support_format_7zip_status": ARCHIVE_OK,
            "archive_read_free_status": ARCHIVE_OK,
            "archive_opened": False,
            "pass": True,
        }

    def _verify_library_unchanged(self) -> dict[str, Any]:
        after = _snapshot_regular_file(
            self._library_before.path, role="libarchive library"
        )
        _same_file_identity(self._library_before, after, role="libarchive library")
        return after.evidence()

    @contextlib.contextmanager
    def _reader(
        self, archive_path: Path, *, error_type: type[Libarchive7zError]
    ) -> Iterator[tuple[Any, _FileIdentity]]:
        archive_identity = _snapshot_regular_file(archive_path, role="7z archive")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = -1
        archive = self._call("archive_read_new")
        if not archive:
            after_archive = _snapshot_regular_file(
                archive_identity.path, role="7z archive"
            )
            _same_file_identity(archive_identity, after_archive, role="7z archive")
            self._verify_library_unchanged()
            raise error_type("archive_read_new returned null")
        open_attempted = False
        body_error: BaseException | None = None
        try:
            self._require_ok(
                self._call("archive_read_support_filter_none", archive),
                operation="archive_read_support_filter_none", archive=archive,
                error_type=error_type,
            )
            self._require_ok(
                self._call("archive_read_support_format_7zip", archive),
                operation="archive_read_support_format_7zip", archive=archive,
                error_type=error_type,
            )
            descriptor = os.open(archive_identity.path, flags)
            descriptor_stat = os.fstat(descriptor)
            if (descriptor_stat.st_dev, descriptor_stat.st_ino, descriptor_stat.st_size) != (
                archive_identity.device, archive_identity.inode, archive_identity.size
            ):
                raise error_type("7z archive identity changed before open")
            open_attempted = True
            self._require_ok(
                self._call(
                    "archive_read_open_fd", archive, descriptor,
                    ARCHIVE_READ_BLOCK_SIZE,
                ),
                operation="archive_read_open_fd", archive=archive,
                error_type=error_type,
            )
            yield archive, archive_identity
        except BaseException as exc:
            body_error = exc
            raise
        finally:
            cleanup_errors: list[str] = []
            if open_attempted:
                close_status = int(self._call("archive_read_close", archive))
                if close_status != ARCHIVE_OK:
                    cleanup_errors.append(f"archive_read_close={close_status}")
            free_status = int(self._call("archive_read_free", archive))
            if free_status != ARCHIVE_OK:
                cleanup_errors.append(f"archive_read_free={free_status}")
            if descriptor >= 0:
                os.close(descriptor)
            identity_errors: list[str] = []
            try:
                after_archive = _snapshot_regular_file(
                    archive_identity.path, role="7z archive"
                )
                _same_file_identity(
                    archive_identity, after_archive, role="7z archive"
                )
            except (OSError, Libarchive7zError) as exc:
                identity_errors.append(str(exc))
            try:
                self._verify_library_unchanged()
            except (OSError, Libarchive7zError) as exc:
                identity_errors.append(str(exc))
            all_cleanup_errors = cleanup_errors + identity_errors
            if all_cleanup_errors:
                message = "libarchive cleanup/identity failure: " + ";".join(
                    all_cleanup_errors
                )
                if body_error is None:
                    raise error_type(message)
                setattr(body_error, "cleanup_diagnostics", tuple(all_cleanup_errors))
                if hasattr(body_error, "add_note"):
                    body_error.add_note(message)
                else:
                    body_error.args = (f"{body_error}; {message}",)

    def _validate_reader_identity(
        self, archive: Any, *, error_type: type[Libarchive7zError]
    ) -> None:
        filter_count = int(self._call("archive_filter_count", archive))
        if filter_count != 1:
            raise error_type(f"archive filter count is not exactly one: {filter_count}")
        filter_code = int(self._call("archive_filter_code", archive, 0))
        if filter_code != ARCHIVE_FILTER_NONE:
            raise error_type(f"archive filter is not NONE: {filter_code}")
        archive_format = int(self._call("archive_format", archive))
        if archive_format & ARCHIVE_FORMAT_BASE_MASK != ARCHIVE_FORMAT_7ZIP:
            raise error_type(f"archive format is not 7zip: {archive_format}")

    def _read_member(
        self, entry: Any, *, index: int,
        error_type: type[Libarchive7zError] = LibarchiveInventoryError,
    ) -> dict[str, Any]:
        filetype = int(self._call("archive_entry_filetype", entry)) & S_IFMT
        path, archive_pathname, directory_trailing_slash = _safe_member_path(
            self._call("archive_entry_pathname_utf8", entry),
            directory=filetype == S_IFDIR,
            error_type=error_type,
        )
        if filetype == S_IFREG:
            kind = "regular"
            raw_size_state = int(
                self._call("archive_entry_size_is_set", entry)
            )
            size_is_set = raw_size_state != 0
            if not size_is_set:
                raise error_type(f"archive member size is unset: {path}")
            size = int(self._call("archive_entry_size", entry))
            if size < 0 or size > MAX_ARCHIVE_MEMBER_BYTES:
                raise error_type(
                    f"archive member size is invalid or exceeds cap: {path}: {size}"
                )
            size_contract = "REQUIRED_SET_NONNEGATIVE_WITHIN_CAP_FOR_REGULAR_FILE"
        elif filetype == S_IFDIR:
            kind = "directory"
            raw_size_state = int(
                self._call("archive_entry_size_is_set", entry)
            )
            size_is_set = raw_size_state != 0
            if size_is_set:
                declared_size = int(self._call("archive_entry_size", entry))
                if declared_size != 0:
                    raise error_type(
                        f"archive directory has nonzero size: {path}: {declared_size}"
                    )
            size = 0
            size_contract = "NOT_APPLICABLE_FOR_DIRECTORY"
        else:
            raise error_type(f"archive member is special, not regular/directory: {path}")
        if self._call("archive_entry_symlink_utf8", entry) is not None:
            raise error_type(f"archive symlink member is forbidden: {path}")
        if self._call("archive_entry_hardlink_utf8", entry) is not None:
            raise error_type(f"archive hardlink member is forbidden: {path}")
        encrypted = int(self._call("archive_entry_is_encrypted", entry))
        if encrypted != 0:
            raise error_type(
                f"archive member encryption is present or unknown: {path}: {encrypted}"
            )
        sparse_count = int(self._call("archive_entry_sparse_reset", entry))
        if sparse_count != 0:
            raise error_type(
                f"archive member sparse metadata is present or invalid: {path}: {sparse_count}"
            )
        member = {
            "index": index,
            "path": path,
            "bytes": size,
            "kind": kind,
            "directory": kind == "directory",
            "encrypted": False,
            "link_or_reparse": False,
            "sparse_extent_count": 0,
            "size_is_set": size_is_set,
            "size_contract": size_contract,
            "archive_pathname_utf8": archive_pathname,
            "directory_pathname_trailing_slash": directory_trailing_slash,
        }
        header_digest_fields = {
            key: member[key]
            for key in (
                "index", "path", "bytes", "kind", "directory", "encrypted",
                "link_or_reparse", "sparse_extent_count", "size_is_set",
                "size_contract",
                "archive_pathname_utf8", "directory_pathname_trailing_slash",
            )
        }
        member["header_metadata_sha256"] = hashlib.sha256(
            json.dumps(
                header_digest_fields, ensure_ascii=False, sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        return member

    def inventory(self, archive_path: Path) -> dict[str, Any]:
        before_calls = self._api_counts.copy()
        members: list[dict[str, Any]] = []
        total_size = 0
        with self._reader(archive_path, error_type=LibarchiveInventoryError) as (
            archive, archive_identity,
        ):
            while True:
                entry = ctypes.c_void_p()
                status = int(
                    self._call("archive_read_next_header", archive, ctypes.byref(entry))
                )
                if status == ARCHIVE_EOF:
                    break
                if status != ARCHIVE_OK:
                    raise LibarchiveInventoryError(
                        "archive_read_next_header returned non-OK/non-EOF status "
                        f"{status}: {self._error(archive)}"
                    )
                if not entry.value:
                    raise LibarchiveInventoryError(
                        "archive_read_next_header returned OK with null entry"
                    )
                if len(members) >= MAX_ARCHIVE_MEMBER_COUNT:
                    raise LibarchiveInventoryError("archive member-count cap exceeded")
                member = self._read_member(entry, index=len(members))
                members.append(member)
                total_size += int(member["bytes"])
                if total_size > MAX_ARCHIVE_TOTAL_BYTES:
                    raise LibarchiveInventoryError("archive total uncompressed-size cap exceeded")
                self._validate_reader_identity(
                    archive, error_type=LibarchiveInventoryError
                )
            encrypted_state = int(
                self._call("archive_read_has_encrypted_entries", archive)
            )
            if encrypted_state != 0:
                raise LibarchiveInventoryError(
                    "archive global encryption state is present or unknown after EOF: "
                    f"{encrypted_state}"
                )
        if not members:
            raise LibarchiveInventoryError("7z header inventory has no members")
        _validate_member_collisions(members)
        after_archive = _snapshot_regular_file(archive_identity.path, role="7z archive")
        _same_file_identity(archive_identity, after_archive, role="7z archive")
        after_library = self._verify_library_unchanged()
        call_delta = self._counter_delta(before_calls)
        if call_delta.get("archive_read_data_block", 0) != 0:
            raise LibarchiveInventoryError("inventory unexpectedly called a payload API")
        if call_delta.get("archive_read_data_skip", 0) != 0:
            raise LibarchiveInventoryError("inventory unexpectedly called a payload API")
        return {
            "members": members,
            "member_count": len(members),
            "file_member_count": sum(item["kind"] == "regular" for item in members),
            "total_declared_uncompressed_bytes": total_size,
            "resource_limits": {
                "maximum_member_count": MAX_ARCHIVE_MEMBER_COUNT,
                "maximum_member_bytes": MAX_ARCHIVE_MEMBER_BYTES,
                "maximum_total_declared_uncompressed_bytes": MAX_ARCHIVE_TOTAL_BYTES,
                "maximum_path_utf8_bytes": 4096,
                "maximum_path_component_utf8_bytes": 255,
            },
            "archive_read_open_fd_block_bytes": ARCHIVE_READ_BLOCK_SIZE,
            "archive_sha256": archive_identity.sha256,
            "archive_identity_before": archive_identity.evidence(),
            "archive_identity_after": after_archive.evidence(),
            "library_identity_after": after_library,
            "inventory_operation": "libarchive_next_header_only",
            "payload_api_calls": 0,
            "api_call_counts": call_delta,
            "global_encryption_state_after_eof": 0,
            "filter": "NONE",
            "format": "7ZIP",
            "solid_archive_internal_decode_absence_claimed": False,
            "pass": True,
        }

    def _counter_delta(self, before: collections.Counter[str]) -> dict[str, int]:
        return {
            key: self._api_counts[key] - before[key]
            for key in sorted(set(self._api_counts) | set(before))
            if self._api_counts[key] - before[key]
        }

    def extract_selected(
        self,
        archive_path: Path,
        destination: Path,
        inventory: Mapping[str, Any],
    ) -> dict[str, Any]:
        selected = _selected_paths(inventory)
        selected_set = set(selected)
        inventory_members = tuple(dict(item) for item in inventory.get("members", ()))
        if not inventory_members:
            raise LibarchiveExtractionError("archive inventory is empty")
        frozen_content_identity = _frozen_archive_content_identity(inventory)
        frozen_binding = _strict_sha256(
            inventory.get("frozen_inventory_binding_sha256"),
            field="frozen_inventory_binding_sha256",
        )
        recomputed_binding = frozen_inventory_binding_sha256(inventory)
        if frozen_binding != recomputed_binding:
            raise LibarchiveExtractionError(
                "frozen archive inventory binding digest does not match its evidence"
            )
        if os.path.lexists(destination):
            raise LibarchiveExtractionError(
                f"sample extraction root already exists: {destination}"
            )
        before_calls = self._api_counts.copy()
        extracted: list[dict[str, Any]] = []
        excluded: list[dict[str, Any]] = []
        seen_selected: set[str] = set()
        root_fd = -1
        try:
            with self._reader(archive_path, error_type=LibarchiveExtractionError) as (
                archive, archive_identity,
            ):
                fresh_content_identity = {
                    "sha256": archive_identity.sha256,
                    "bytes": archive_identity.size,
                }
                if fresh_content_identity != frozen_content_identity:
                    raise LibarchiveExtractionError(
                        "fresh archive hash/size identity does not match the frozen "
                        "inventory before payload"
                    )
                parent_fd = _open_absolute_directory_nofollow(destination.parent)
                try:
                    os.mkdir(destination.name, mode=0o700, dir_fd=parent_fd)
                    root_flags = (
                        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                        | getattr(os, "O_CLOEXEC", 0)
                        | getattr(os, "O_NOFOLLOW", 0)
                    )
                    root_fd = os.open(
                        destination.name, root_flags, dir_fd=parent_fd
                    )
                except OSError as exc:
                    raise LibarchiveExtractionError(
                        "cannot exclusively create no-follow extraction root: "
                        f"{destination}"
                    ) from exc
                finally:
                    os.close(parent_fd)
                index = 0
                while True:
                    entry = ctypes.c_void_p()
                    status = int(
                        self._call(
                            "archive_read_next_header", archive, ctypes.byref(entry)
                        )
                    )
                    if status == ARCHIVE_EOF:
                        break
                    if status != ARCHIVE_OK:
                        raise LibarchiveExtractionError(
                            "archive_read_next_header returned non-OK/non-EOF status "
                            f"{status}: {self._error(archive)}"
                        )
                    if not entry.value:
                        raise LibarchiveExtractionError(
                            "archive_read_next_header returned OK with null entry"
                        )
                    if index >= len(inventory_members):
                        raise LibarchiveExtractionError(
                            "archive header count exceeds frozen inventory"
                        )
                    member = self._read_member(
                        entry, index=index, error_type=LibarchiveExtractionError
                    )
                    frozen = inventory_members[index]
                    comparison_fields = (
                        "index", "path", "bytes", "kind", "directory",
                        "encrypted", "link_or_reparse", "sparse_extent_count",
                        "size_is_set", "size_contract", "archive_pathname_utf8",
                        "directory_pathname_trailing_slash",
                        "header_metadata_sha256",
                    )
                    if any(member.get(key) != frozen.get(key) for key in comparison_fields):
                        raise LibarchiveExtractionError(
                            f"archive header changed from inventory at index {index}"
                        )
                    self._validate_reader_identity(
                        archive, error_type=LibarchiveExtractionError
                    )
                    path = str(member["path"])
                    if path not in selected_set:
                        skip_status = int(self._call("archive_read_data_skip", archive))
                        if skip_status != ARCHIVE_OK:
                            raise LibarchiveExtractionError(
                                "archive_read_data_skip returned non-OK status "
                                f"{skip_status}: {self._error(archive)}"
                            )
                        excluded.append(
                            {
                                "path": path,
                                "reason": "not_in_exact_obs_nav_imu_allowlist",
                                "header_metadata_sha256": member[
                                    "header_metadata_sha256"
                                ],
                                "payload_read_calls": 0,
                                "data_skip_calls": 1,
                            }
                        )
                    else:
                        if member["kind"] != "regular":
                            raise LibarchiveExtractionError(
                                f"selected member is not a regular file: {path}"
                            )
                        extracted.append(
                            self._extract_one(archive, entry, member, root_fd)
                        )
                        seen_selected.add(path)
                    index += 1
                if index != len(inventory_members):
                    raise LibarchiveExtractionError(
                        "archive header count is shorter than frozen inventory"
                    )
                encrypted_state = int(
                    self._call("archive_read_has_encrypted_entries", archive)
                )
                if encrypted_state != 0:
                    raise LibarchiveExtractionError(
                        "archive global encryption state is present or unknown after EOF: "
                        f"{encrypted_state}"
                    )
            if seen_selected != selected_set:
                raise LibarchiveExtractionError(
                    "extracted member set does not equal exact selected allowlist"
                )
            self._verify_exact_tree(destination, selected_set)
            after_archive = _snapshot_regular_file(
                archive_identity.path, role="7z archive"
            )
            _same_file_identity(archive_identity, after_archive, role="7z archive")
            after_library = self._verify_library_unchanged()
        except BaseException:
            raise
        finally:
            if root_fd >= 0:
                os.close(root_fd)
        call_delta = self._counter_delta(before_calls)
        by_path = {item["path"]: item for item in extracted + excluded}
        for key in ("reference_member_paths", "ubx_member_paths"):
            for path in inventory.get(key, ()):
                if by_path.get(str(path), {}).get("payload_read_calls") != 0:
                    raise LibarchiveExtractionError(
                        f"excluded reference/UBX member had payload reads: {path}"
                    )
        return {
            "backend": "ctypes_libarchive_public_abi",
            "subprocess_used": False,
            "selected_members": list(selected),
            "extracted_members": sorted(seen_selected),
            "selected_member_ledger": sorted(extracted, key=lambda item: item["path"]),
            "excluded_member_ledger": sorted(excluded, key=lambda item: item["path"]),
            "reference_member_excluded_without_payload_read": True,
            "reference_member_payload_read_calls": 0,
            "ubx_members_excluded_without_payload_read": True,
            "ubx_member_payload_read_calls": 0,
            "archive_sha256": archive_identity.sha256,
            "archive_identity_before": archive_identity.evidence(),
            "archive_identity_after": after_archive.evidence(),
            "frozen_archive_content_identity": frozen_content_identity,
            "fresh_archive_content_identity_before_payload": fresh_content_identity,
            "fresh_archive_identity_match_before_payload": True,
            "selected_payload_started_only_after_identity_match": True,
            "frozen_inventory_binding_sha256": frozen_binding,
            "library_identity_after": after_library,
            "api_call_counts": call_delta,
            "global_encryption_state_after_eof": 0,
            "filter": "NONE",
            "format": "7ZIP",
            "solid_archive_internal_decode_absence_claimed": False,
            "pass": True,
        }

    def _extract_one(
        self, archive: Any, entry: Any, member: Mapping[str, Any], root_fd: int
    ) -> dict[str, Any]:
        del entry
        path = str(member["path"])
        parts = PurePosixPath(path).parts
        parent_fd = os.dup(root_fd)
        try:
            for part in parts[:-1]:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=parent_fd)
                except FileExistsError:
                    metadata = os.stat(part, dir_fd=parent_fd, follow_symlinks=False)
                    if not stat.S_ISDIR(metadata.st_mode):
                        raise LibarchiveExtractionError(
                            f"extraction parent is not a directory: {path}"
                        )
                flags = (
                    os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
                )
                child_fd = os.open(part, flags, dir_fd=parent_fd)
                os.close(parent_fd)
                parent_fd = child_fd
            flags = (
                os.O_WRONLY | os.O_CREAT | os.O_EXCL
                | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
            )
            output_fd = os.open(parts[-1], flags, 0o600, dir_fd=parent_fd)
            digest = hashlib.sha256()
            expected_offset = 0
            payload_calls = 0
            try:
                while True:
                    buffer_pointer = ctypes.c_void_p()
                    block_size = ctypes.c_size_t()
                    block_offset = ctypes.c_int64()
                    status = int(
                        self._call(
                            "archive_read_data_block", archive,
                            ctypes.byref(buffer_pointer), ctypes.byref(block_size),
                            ctypes.byref(block_offset),
                        )
                    )
                    if status == ARCHIVE_EOF:
                        break
                    if status != ARCHIVE_OK:
                        raise LibarchiveExtractionError(
                            "archive_read_data_block returned non-OK/non-EOF status "
                            f"{status}: {self._error(archive)}"
                        )
                    payload_calls += 1
                    size = int(block_size.value)
                    offset = int(block_offset.value)
                    if not buffer_pointer.value or size <= 0:
                        raise LibarchiveExtractionError(
                            f"archive payload block is null/empty: {path}"
                        )
                    if offset != expected_offset:
                        raise LibarchiveExtractionError(
                            f"archive payload offsets are not contiguous: {path}"
                        )
                    expected_size = int(member["bytes"])
                    if size > expected_size - expected_offset:
                        raise LibarchiveExtractionError(
                            f"archive payload exceeds declared size: {path}"
                        )
                    block = ctypes.string_at(buffer_pointer, size)
                    digest.update(block)
                    view = memoryview(block)
                    while view:
                        written = os.write(output_fd, view)
                        if written <= 0:
                            raise LibarchiveExtractionError(
                                f"short/zero output write: {path}"
                            )
                        view = view[written:]
                    expected_offset += size
                if expected_offset != int(member["bytes"]):
                    raise LibarchiveExtractionError(
                        f"archive payload size differs from header: {path}"
                    )
                os.fsync(output_fd)
                metadata = os.fstat(output_fd)
                if not stat.S_ISREG(metadata.st_mode) or metadata.st_size != expected_offset:
                    raise LibarchiveExtractionError(
                        f"extracted output fstat mismatch: {path}"
                    )
            finally:
                os.close(output_fd)
            read_flags = (
                os.O_RDONLY | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_NOFOLLOW", 0)
            )
            read_fd = os.open(parts[-1], read_flags, dir_fd=parent_fd)
            try:
                readback = hashlib.sha256()
                readback_size = 0
                while True:
                    block = os.read(read_fd, HASH_READ_BLOCK_SIZE)
                    if not block:
                        break
                    readback.update(block)
                    readback_size += len(block)
                read_metadata = os.fstat(read_fd)
            finally:
                os.close(read_fd)
            if (
                readback_size != int(member["bytes"])
                or read_metadata.st_size != readback_size
                or readback.hexdigest() != digest.hexdigest()
            ):
                raise LibarchiveExtractionError(
                    f"extracted output readback conservation failed: {path}"
                )
            return {
                "path": path,
                "header_metadata_sha256": member["header_metadata_sha256"],
                "declared_bytes": int(member["bytes"]),
                "written_bytes": readback_size,
                "sha256": readback.hexdigest(),
                "payload_read_calls": payload_calls,
                "data_skip_calls": 0,
            }
        finally:
            os.close(parent_fd)

    @staticmethod
    def _verify_exact_tree(destination: Path, selected: set[str]) -> None:
        actual_files: set[str] = set()
        actual_directories: set[str] = set()
        pending = [destination]
        while pending:
            current = pending.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    relative = Path(entry.path).relative_to(destination).as_posix()
                    metadata = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(metadata.st_mode):
                        raise LibarchiveExtractionError(
                            f"symlink appeared in extraction tree: {relative}"
                        )
                    if stat.S_ISDIR(metadata.st_mode):
                        actual_directories.add(relative)
                        pending.append(Path(entry.path))
                    elif stat.S_ISREG(metadata.st_mode):
                        actual_files.add(relative)
                    else:
                        raise LibarchiveExtractionError(
                            f"special file appeared in extraction tree: {relative}"
                        )
        expected_directories = {
            PurePosixPath(*PurePosixPath(path).parts[:index]).as_posix()
            for path in selected
            for index in range(1, len(PurePosixPath(path).parts))
        }
        if actual_files != selected or actual_directories != expected_directories:
            raise LibarchiveExtractionError(
                "extraction tree differs from exact selected file/parent set"
            )


__all__ = [
    "ARCHIVE_EOF",
    "ARCHIVE_OK",
    "Libarchive7zBackend",
    "Libarchive7zError",
    "LibarchiveExtractionError",
    "LibarchiveInventoryError",
    "LibarchivePreflightError",
    "PINNED_LIBARCHIVE_SHA256",
    "PINNED_LIBARCHIVE_VERSION_NUMBER",
    "PINNED_LIBARCHIVE_VERSION_STRING",
    "REQUIRED_ABI_SYMBOLS",
]
