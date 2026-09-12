"""Exact, no-follow, self-contained compact stage publication."""

from __future__ import annotations

import copy
import ctypes
import errno
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Any, Mapping, Sequence

from .constants import RUNTIME_ONLY_BASENAMES, STAGE_NAME, STAGE_RELATIVE_LAYOUT
from .source import sha256_file


class PublicationError(RuntimeError):
    def __init__(self, message: str, *, report: Mapping[str, Any] | None = None):
        super().__init__(message)
        self.report = dict(report or {})


MAX_COMPACT_FILE_BYTES = 64 * 1024 * 1024
FINAL_STATUS_RELATIVE = Path("11_REPORT/LC02_GINAV2021_TRANSACTION_STATUS.json")
PARITY_RELATIVE = Path("11_REPORT/GINAV_PUBLICATION_PARITY.json")

SECTION_FILE_ALLOWLIST: dict[str, frozenset[str]] = {
    "00_SOURCE_AND_ENVIRONMENT": frozenset({
        "GINAV_SOURCE_LOCK.json",
        "GINAV_MATLAB_ENVIRONMENT.json",
        "GINAV_MATLAB_DISCOVERY_ATTEMPTS.json",
        "GINAV_CORE_CLEANLINESS_BEFORE_AFTER.json",
    }),
    "01_OFFICIAL_SAMPLE_REGRESSION": frozenset({
        "OFFICIAL_SAMPLE_ARCHIVE_INVENTORY.json",
        "OFFICIAL_SAMPLE_REGRESSION_REPORT.md",
        "OFFICIAL_SAMPLE_REGRESSION_STATUS.json",
        "OFFICIAL_SAMPLE_OUTPUT_SUMMARY.csv",
        "OFFICIAL_SAMPLE_DETERMINISM.json",
    }),
    "02_BY2_GNSS_ADAPTER": frozenset({
        "BY2_GNSS1_RINEX_CONTRACT.yaml",
        "BY2_GNSS1_RINEX_AUDIT.json",
        "BY2_GNSS1_EPOCH_AND_SIGNAL_SUMMARY.csv",
    }),
    "03_BY2_IMU_ADAPTER": frozenset({
        "BY2_GINAV_IMU_CONTRACT.yaml",
        "BY2_GINAV_IMU_AUDIT.json",
    }),
    "04_BY2_CONFIG_AND_TIME_CONTRACT": frozenset({
        "BY2_GINAV_CONFIG_DIFF.csv",
        "BY2_GINAV_CONFIG_CONTRACT.yaml",
        "BY2_GINAV_TIME_NORMALIZATION_CONTRACT.yaml",
        "BY2_GINAV_TIME_NORMALIZATION_LEDGER.csv",
        "BY2_GINAV_OFFICIAL_EPOCH_ACCEPTANCE_AUDIT.json",
    }),
    "05_BY2_ACTIVATION_PROBE": frozenset({
        "BY2_GINAV_TDCP_ALIGNMENT_PROBE.csv",
        "BY2_GINAV_ALIGNMENT_ACTIVATION_SUMMARY.json",
    }),
    "06_BY2_C00_NATIVE": frozenset({
        "GINAV_BY2_C00_NATIVE_SOLUTION.pos",
        "GINAV_BY2_C00_STATUS_STREAM.csv",
        "GINAV_BY2_C00_FAILURE_LEDGER.csv",
        "GINAV_BY2_C00_RUNTIME.csv",
        "GINAV_BY2_C00_NATIVE_SUMMARY.json",
        "GINAV_BY2_C00_NATIVE_FREEZE.json",
    }),
    "07_NATIVE_OUTPUT_NORMALIZATION": frozenset({
        "GINAV_BY2_C00_STANDARD_NAV.csv",
    }),
    "11_REPORT": frozenset({
        "LC02_GINAV2021_TRANSACTION_STATUS.json",
        "GINAV_FORBIDDEN_INPUT_AUDIT.json",
        "GINAV_CONSOLIDATED_PROVENANCE.json",
        "GINAV_PUBLICATION_PARITY.json",
        "LC02_GINAV2021_FINAL_REPORT.md",
    }),
}

_OUTCOME_MAX_SECTION = {
    "BLOCKED_LC02_GINAV_SOURCE_IDENTITY_MISMATCH": 0,
    "BLOCKED_LC02_GINAV_MATLAB_RUNTIME_UNAVAILABLE": 0,
    "BLOCKED_LC02_GINAV_OFFICIAL_SAMPLE_REGRESSION_FAILURE": 1,
    "BLOCKED_LC02_GINAV_BY2_GNSS_ADAPTER_FAILURE": 2,
    "BLOCKED_LC02_GINAV_BY2_IMU_ADAPTER_FAILURE": 3,
    "BLOCKED_LC02_GINAV_BY2_CONFIG_CONTRACT_FAILURE": 4,
    "UNSUPPORTED_LC02_GINAV_BY2_NONINTEGER_EPOCH_POLICY": 4,
    "UNSUPPORTED_LC02_GINAV_BY2_TDCP_ALIGNMENT_CONDITION_NOT_MET": 5,
    "UNSUPPORTED_LC02_GINAV_BY2_INSUFFICIENT_INTERNAL_SPP": 5,
    "PASS_LC02_GINAV2021_EXACT_ROUTE_AND_BY2_C00_VALIDATED": 7,
    "PASS_LC02_GINAV2021_EXACT_ROUTE_VALIDATED_BY2_C00_POOR_APPLICABILITY_RESULT": 7,
}

_MACHINE_PATH_PATTERNS = (
    re.compile(r"/home/"),
    re.compile(r"/mnt/[A-Za-z]/"),
    re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]"),
    re.compile(r"\\\\(?:wsl(?:\.localhost|\$)?|[^\\\s]+)\\", re.IGNORECASE),
)


def _absolute_lexical(path: str | Path) -> Path:
    value = Path(path).expanduser()
    return value if value.is_absolute() else Path.cwd() / value


def assert_no_symlink_components(
    path: str | Path, *, allow_missing_leaf: bool
) -> Path:
    """Reject symlinks, including dangling leaves and symlinked ancestors."""

    absolute = _absolute_lexical(path)
    parts = absolute.parts
    current = Path(parts[0])
    for index, part in enumerate(parts[1:], start=1):
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            if allow_missing_leaf and index == len(parts) - 1:
                return absolute
            raise PublicationError(f"path component does not exist: {current}")
        if stat.S_ISLNK(mode):
            raise PublicationError(f"symlinked path component is forbidden: {current}")
    return absolute


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def assert_outside_protected_roots(
    path: str | Path, protected_roots: Sequence[str | Path]
) -> Path:
    candidate = _absolute_lexical(path).resolve(strict=False)
    for value in protected_roots:
        protected = _absolute_lexical(value).resolve(strict=False)
        if candidate == protected or _is_relative_to(candidate, protected):
            raise PublicationError(
                f"runtime scratch/source is inside protected root: {protected}"
            )
    return candidate


def validate_exact_destination(
    destination: str | Path,
    *,
    expected_destination: str | Path,
    clean_root: str | Path,
    other_protected_roots: Sequence[str | Path],
) -> Path:
    target = assert_no_symlink_components(destination, allow_missing_leaf=True)
    expected = _absolute_lexical(expected_destination)
    if target != expected or target.name != STAGE_NAME:
        raise PublicationError("publication destination is not the exact authorized stage")
    clean = _absolute_lexical(clean_root).resolve(strict=True)
    resolved = target.resolve(strict=False)
    exact_parent = (
        clean / "stages" / "CLEAN4_BY2_HORIZONTAL_LITERATURE_COMPARISON"
        / STAGE_NAME
    )
    if resolved != exact_parent:
        raise PublicationError("publication destination identity does not match clean_root")
    if resolved == clean:
        raise PublicationError("publication destination cannot equal CLEAN_ROOT")
    for value in other_protected_roots:
        protected = _absolute_lexical(value).resolve(strict=False)
        if resolved == protected or _is_relative_to(resolved, protected):
            raise PublicationError(
                f"publication destination enters non-clean protected root: {protected}"
            )
    return target


def _allowed_sections(terminal_status: str) -> frozenset[str]:
    if terminal_status not in _OUTCOME_MAX_SECTION:
        raise PublicationError(f"publication has unknown terminal: {terminal_status}")
    maximum = _OUTCOME_MAX_SECTION[terminal_status]
    numbered = {
        section for section in STAGE_RELATIVE_LAYOUT
        if section == "11_REPORT" or int(section[:2]) <= maximum
    }
    return frozenset(numbered)


def compact_artifact_paths(
    scratch_stage_root: str | Path, *, terminal_status: str
) -> tuple[Path, ...]:
    root = assert_no_symlink_components(scratch_stage_root, allow_missing_leaf=False)
    if root.name != STAGE_NAME or not root.is_dir():
        raise PublicationError("scratch publication source is not the exact LC02 stage")
    allowed_sections = _allowed_sections(terminal_status)
    selected: list[Path] = []
    for path in sorted(root.rglob("*")):
        mode = os.lstat(path).st_mode
        if stat.S_ISLNK(mode):
            raise PublicationError(f"source stage contains symlink: {path.relative_to(root)}")
        if not stat.S_ISREG(mode):
            continue
        relative = path.relative_to(root)
        if not relative.parts or relative.parts[0] not in STAGE_RELATIVE_LAYOUT:
            raise PublicationError(f"artifact escapes stage layout: {relative}")
        if len(relative.parts) != 2:
            continue
        section, name = relative.parts
        if section not in allowed_sections:
            raise PublicationError(
                f"artifact is impossible for terminal {terminal_status}: {relative}"
            )
        if name not in SECTION_FILE_ALLOWLIST[section]:
            raise PublicationError(f"artifact filename is not allowlisted: {relative}")
        if name in RUNTIME_ONLY_BASENAMES:
            raise PublicationError(f"runtime-only artifact reached section root: {relative}")
        if path.stat(follow_symlinks=False).st_size > MAX_COMPACT_FILE_BYTES:
            raise PublicationError(f"artifact is not compact: {relative}")
        selected.append(path)
    required = {
        FINAL_STATUS_RELATIVE,
        Path("11_REPORT/GINAV_FORBIDDEN_INPUT_AUDIT.json"),
        Path("11_REPORT/GINAV_CONSOLIDATED_PROVENANCE.json"),
    }
    available = {path.relative_to(root) for path in selected}
    missing = required - available
    if missing:
        raise PublicationError(
            "compact evidence is incomplete: "
            + ",".join(sorted(item.as_posix() for item in missing))
        )
    return tuple(selected)


def _replace_aliases(text: str, aliases: Mapping[str | Path, str]) -> str:
    replacements: list[tuple[str, str]] = []
    for path, alias in aliases.items():
        lexical = str(_absolute_lexical(path))
        replacements.extend(((lexical, alias), (lexical.replace("/", "\\"), alias)))
        mounted_drive = re.match(r"^/mnt/([A-Za-z])(?:/(.*))?$", lexical)
        if mounted_drive:
            tail = (mounted_drive.group(2) or "").replace("/", "\\")
            replacements.append(
                (mounted_drive.group(1).upper() + ":\\" + tail, alias)
            )
    for source, alias in sorted(replacements, key=lambda item: len(item[0]), reverse=True):
        text = text.replace(source, alias)
        text = text.replace(source.replace("\\", "\\\\"), alias)
    # Known WSL/drive prefixes can remain before a successfully substituted
    # alias when a Windows MATLAB command is serialized.
    text = re.sub(
        r"(?:\\\\wsl(?:\.localhost|\$)?\\[^\\\s\"']+)?(?=<[A-Z0-9_]+>)",
        "", text, flags=re.IGNORECASE,
    )
    text = re.sub(r"[A-Za-z]:\\(?=<[A-Z0-9_]+>)", "", text)
    for pattern in _MACHINE_PATH_PATTERNS:
        if pattern.search(text):
            raise PublicationError("compact evidence contains an unaliased machine-local path")
    return text


def _sanitize_json_value(
    value: Any, aliases: Mapping[str | Path, str]
) -> Any:
    """Sanitize decoded JSON string values before deterministic encoding."""

    if isinstance(value, str):
        return _replace_aliases(value, aliases)
    if isinstance(value, Mapping):
        sanitized: dict[Any, Any] = {}
        for key, item in value.items():
            sanitized_key = (
                _replace_aliases(key, aliases)
                if isinstance(key, str) else key
            )
            if sanitized_key in sanitized:
                raise PublicationError(
                    "JSON mapping key collision after path sanitization"
                )
            sanitized[sanitized_key] = _sanitize_json_value(item, aliases)
        return sanitized
    if isinstance(value, (list, tuple)):
        return [_sanitize_json_value(item, aliases) for item in value]
    return value


def _sanitized_bytes(
    source: Path, aliases: Mapping[str | Path, str]
) -> tuple[bytes, bool]:
    original = source.read_bytes()
    try:
        text = original.decode("utf-8")
    except UnicodeDecodeError:
        return original, False
    if source.suffix.casefold() == ".json":
        try:
            payload = json.loads(text)
        except ValueError as exc:
            raise PublicationError(
                f"compact JSON evidence is invalid: {source.name}"
            ) from exc
        sanitized = _json_bytes(payload, aliases)
        return sanitized, sanitized != original
    sanitized = _replace_aliases(text, aliases).encode("utf-8")
    return sanitized, sanitized != original


def _write_exclusive(path: Path, content: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o644)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(descriptor)


def _json_bytes(payload: Any, aliases: Mapping[str | Path, str]) -> bytes:
    sanitized_payload = _sanitize_json_value(payload, aliases)
    encoded = json.dumps(
        sanitized_payload, ensure_ascii=False, indent=2, sort_keys=True
    ) + "\n"
    return encoded.encode("utf-8")


def _publication_temporary_root(
    destination_root: Path, source_root: Path
) -> tuple[Path, str]:
    """Return a validated attempt-specific sibling without touching legacy partials."""

    source_identity = str(source_root.resolve(strict=True)).encode("utf-8")
    identity = hashlib.sha256(
        b"ginav2021.compact-publication-attempt.v1\0" + source_identity
    ).hexdigest()
    temporary = destination_root.with_name(
        destination_root.name + ".partial." + identity[:16]
    )
    expected_name = re.fullmatch(
        re.escape(destination_root.name) + r"\.partial\.[0-9a-f]{16}",
        temporary.name,
    )
    if expected_name is None or temporary.parent != destination_root.parent:
        raise PublicationError("invalid attempt-specific publication temporary identity")
    return (
        assert_no_symlink_components(temporary, allow_missing_leaf=True),
        identity,
    )


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _guarded_atomic_rename(source: Path, destination: Path) -> str:
    """Fallback for filesystems that reject ``RENAME_NOREPLACE``.

    An exclusive, fsynced parent lock serializes this publisher. The exact
    destination is checked again while the lock is held before one atomic
    directory rename. The lock is removed only after inode identity is proven.
    """

    lock_path = destination.parent / ("." + destination.name + ".publish.lock")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(lock_path, flags, 0o600)
    lock_identity = os.fstat(descriptor)
    rename_complete = False
    try:
        os.write(descriptor, b"GINAV_LC02_COMPACT_PUBLICATION\n")
        os.fsync(descriptor)
        _fsync_directory(destination.parent)
        if os.path.lexists(destination):
            raise PublicationError(
                "guarded publication refused an existing destination"
            )
        os.rename(source, destination)
        rename_complete = True
        _fsync_directory(destination.parent)
        return "exclusive_parent_lock_guarded_atomic_rename"
    finally:
        try:
            current = os.lstat(lock_path)
            if (
                current.st_dev != lock_identity.st_dev
                or current.st_ino != lock_identity.st_ino
                or not stat.S_ISREG(current.st_mode)
            ):
                raise PublicationError(
                    "publication lock identity changed before cleanup"
                )
            os.unlink(lock_path)
            _fsync_directory(destination.parent)
        except FileNotFoundError as exc:
            if rename_complete:
                raise PublicationError(
                    "publication completed but its exclusive lock disappeared"
                ) from exc
            raise PublicationError("publication lock disappeared") from exc
        finally:
            os.close(descriptor)


def _atomic_rename_noreplace(source: Path, destination: Path) -> str:
    """Atomically install one prepared directory without replacing any target."""

    library = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(library, "renameat2", None)
    if renameat2 is None:
        return _guarded_atomic_rename(source, destination)
    renameat2.argtypes = (
        ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    at_fdcwd = -100
    rename_noreplace = 1
    result = renameat2(
        at_fdcwd, os.fsencode(source), at_fdcwd, os.fsencode(destination),
        rename_noreplace,
    )
    if result != 0:
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise PublicationError(
                "atomic publication refused to replace an existing destination"
            )
        unsupported = {
            errno.EINVAL, errno.ENOSYS,
            getattr(errno, "EOPNOTSUPP", errno.EINVAL),
        }
        if code in unsupported:
            return _guarded_atomic_rename(source, destination)
        raise PublicationError(
            "atomic no-replace publication failed: " + os.strerror(code)
        )
    return "renameat2_noreplace"


def publish_compact_stage(
    scratch_stage_root: str | Path,
    destination_stage_root: str | Path,
    *,
    terminal_status: str,
    final_status_payload: Mapping[str, Any],
    expected_destination_stage_root: str | Path,
    clean_root: str | Path,
    protected_roots: Sequence[str | Path],
    path_aliases: Mapping[str | Path, str],
) -> dict[str, Any]:
    source_root = assert_no_symlink_components(
        scratch_stage_root, allow_missing_leaf=False
    )
    assert_outside_protected_roots(source_root, protected_roots)
    destination_root = validate_exact_destination(
        destination_stage_root,
        expected_destination=expected_destination_stage_root,
        clean_root=clean_root,
        other_protected_roots=tuple(
            root for root in protected_roots
            if _absolute_lexical(root).resolve(strict=False)
            != _absolute_lexical(clean_root).resolve(strict=False)
        ),
    )
    if _is_relative_to(destination_root.resolve(strict=False), source_root.resolve(strict=True)):
        raise PublicationError("publication destination overlaps scratch source")
    if not destination_root.parent.is_dir():
        raise PublicationError("exact publication parent directory does not exist")
    assert_no_symlink_components(destination_root.parent, allow_missing_leaf=False)
    temporary_root, temporary_identity = _publication_temporary_root(
        destination_root, source_root
    )
    if os.path.lexists(destination_root):
        raise PublicationError("non-overwriting destination already exists")
    if os.path.lexists(temporary_root):
        raise PublicationError(
            "non-overwriting attempt-specific publication temporary already exists"
        )

    selected = compact_artifact_paths(source_root, terminal_status=terminal_status)
    report: dict[str, Any] = {
        "schema_version": "ginav2021.compact_publication.v2",
        "requested": True,
        "pass": False,
        "phase": "PREFLIGHT_COMPLETE",
        "source_stage_root": str(source_root),
        "destination_stage_root": str(destination_root),
        "publication_temporary_identity_sha256": temporary_identity,
        "attempt_temporary_root": str(temporary_root),
        "retained_partial_root": str(temporary_root),
        "copied_file_count": 0,
        "files": [],
    }
    try:
        temporary_root.mkdir(exist_ok=False)
        for relative_dir in STAGE_RELATIVE_LAYOUT:
            (temporary_root / relative_dir).mkdir(exist_ok=False)
        report["phase"] = "COPYING_EVIDENCE"
        ledger: list[dict[str, Any]] = []
        publication_summary = {
            "schema_version": "ginav2021.compact_publication.v2",
            "requested": True,
            "artifact_publication": "COMPLETE",
            "pass": True,
            "destination_stage_root": "<STAGE_ROOT>",
            "parity_ledger": PARITY_RELATIVE.as_posix(),
            "atomic_final_rename": True,
            "atomic_noreplace": True,
            "zip_created": False,
            "runtime_rinex_published": False,
            "runtime_imu_csv_published": False,
        }
        for source in selected:
            relative = source.relative_to(source_root)
            if relative in {FINAL_STATUS_RELATIVE, PARITY_RELATIVE}:
                continue
            if relative == Path("11_REPORT/GINAV_CONSOLIDATED_PROVENANCE.json"):
                try:
                    provenance = json.loads(source.read_text(encoding="utf-8"))
                except (OSError, ValueError) as exc:
                    raise PublicationError(
                        "consolidated provenance is not valid JSON"
                    ) from exc
                provenance.update({
                    "artifact_publication": "COMPLETE",
                    "artifact_publication_complete": True,
                    "transaction_complete": True,
                    "publication": publication_summary,
                })
                content = _json_bytes(provenance, path_aliases)
                sanitized = True
            else:
                content, sanitized = _sanitized_bytes(source, path_aliases)
            destination = temporary_root / relative
            _write_exclusive(destination, content)
            destination_hash = sha256_file(destination)
            ledger.append({
                "relative_path": relative.as_posix(),
                "bytes": len(content),
                "scratch_source_sha256": sha256_file(source),
                "prepared_destination_sha256": destination_hash,
                "content_path_aliased": sanitized,
                "prepared_hash_verified": destination_hash
                == hashlib.sha256(content).hexdigest(),
            })
            report["files"] = list(ledger)
            report["copied_file_count"] = len(ledger)
        destination_status = copy.deepcopy(dict(final_status_payload))
        destination_status.update({
            "artifact_publication_complete": True,
            "artifact_publication": "COMPLETE",
            "transaction_complete": True,
            "publication": publication_summary,
        })
        status_content = _json_bytes(destination_status, path_aliases)
        status_path = temporary_root / FINAL_STATUS_RELATIVE
        _write_exclusive(status_path, status_content)
        ledger.append({
            "relative_path": FINAL_STATUS_RELATIVE.as_posix(),
            "bytes": len(status_content),
            "scratch_source_sha256": sha256_file(source_root / FINAL_STATUS_RELATIVE),
            "prepared_destination_sha256": sha256_file(status_path),
            "content_path_aliased": True,
            "prepared_hash_verified": True,
            "finalized_destination_status": True,
        })
        report["files"] = list(ledger)
        report["copied_file_count"] = len(ledger)
        parity_payload = {
            "schema_version": "ginav2021.publication_parity_ledger.v2",
            "terminal_status": terminal_status,
            "destination_stage_root": "<STAGE_ROOT>",
            "file_count_excluding_parity_ledger_itself": len(ledger),
            "parity_ledger_self_hash_excluded_by_design": True,
            "all_prepared_hashes_verified": all(
                row["prepared_hash_verified"] for row in ledger
            ),
            "files": ledger,
            "atomic_rename_pending_at_ledger_write": True,
            "pass": True,
        }
        parity_content = _json_bytes(parity_payload, path_aliases)
        parity_path = temporary_root / PARITY_RELATIVE
        _write_exclusive(parity_path, parity_content)
        report.update({
            "phase": "FINALIZED_TEMPORARY_DESTINATION",
            "files": ledger,
            "copied_file_count": len(ledger),
            "file_count": len(ledger) + 1,
            "parity_ledger_sha256": sha256_file(parity_path),
        })
        for path in temporary_root.rglob("*"):
            mode = os.lstat(path).st_mode
            if stat.S_ISLNK(mode):
                raise PublicationError("temporary publication tree contains a symlink")
            if stat.S_ISREG(mode):
                _sanitized_bytes(path, {})
        atomic_method = _atomic_rename_noreplace(temporary_root, destination_root)
        report.update({
            "phase": "ATOMIC_RENAME_COMPLETE",
            "pass": True,
            "atomic_publication_method": atomic_method,
            "retained_partial_root": None,
            "scientific_terminal_status_unchanged": True,
        })
        return report
    except Exception as exc:
        report.update({
            "pass": False,
            "error": str(exc),
            "partial_exists": os.path.lexists(temporary_root),
            "final_exists": os.path.lexists(destination_root),
            "scientific_terminal_status_unchanged": True,
        })
        if isinstance(exc, PublicationError):
            raise PublicationError(str(exc), report=report) from exc
        raise PublicationError(str(exc), report=report) from exc
