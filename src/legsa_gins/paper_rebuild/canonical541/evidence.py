"""Fail-closed evidence closure for the canonical BY2 541-case stage.

The final evidence directory is deliberately *curated*.  It is not a recursive
snapshot of a stage root: every payload must be named, classified and copied
into an attempt-owned staging directory before the manifest is written.  This
keeps large runtime output out of the terminal ZIP and makes an unlisted file,
symlink, or path traversal a hard closure error.
"""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

from .authorization import validate_attempt_root


MANIFEST_NAME = "EVIDENCE_MANIFEST.csv"
SIDECAR_NAME = "EVIDENCE_MANIFEST.sha256"
MANIFEST_FIELDS = ("archive_path", "size_bytes", "sha256", "role", "source_class")
FINAL_ZIP_PREFIX = "LegSA_GINS_CANONICAL541_FINAL_"
FINAL_ZIP_MAX_BYTES = 512 * 1024 * 1024


class EvidenceClosureError(RuntimeError):
    """Raised when evidence cannot be proven to be closed and immutable."""


@dataclass(frozen=True)
class PayloadSpec:
    """One explicitly approved lightweight payload."""

    source: Path
    archive_path: str
    role: str
    source_class: str


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_symlink_components(path: Path) -> None:
    """Reject a symlink at the path or at any existing parent component."""

    candidate = path.absolute()
    for part in (candidate, *candidate.parents):
        if part.exists() and part.is_symlink():
            raise EvidenceClosureError(f"symlink is forbidden in evidence paths: {part}")


def _safe_relative(value: str) -> PurePosixPath:
    if not value or "\\" in value or "\x00" in value:
        raise EvidenceClosureError("archive_path must be a non-empty POSIX path")
    relative = PurePosixPath(value)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise EvidenceClosureError(f"unsafe archive_path: {value}")
    if relative.name in {MANIFEST_NAME, SIDECAR_NAME}:
        raise EvidenceClosureError("manifest and sidecar cannot be payload rows")
    return relative


def _regular_files_without_symlinks(root: Path) -> dict[str, Path]:
    """Return all regular files while rejecting every symlink/special file."""

    _reject_symlink_components(root)
    if not root.is_dir():
        raise EvidenceClosureError(f"evidence root is not a directory: {root}")
    output: dict[str, Path] = {}
    for directory, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        base = Path(directory)
        for name in tuple(directories):
            child = base / name
            if child.is_symlink():
                raise EvidenceClosureError(f"symlink directory is forbidden: {child}")
        for name in filenames:
            child = base / name
            if child.is_symlink():
                raise EvidenceClosureError(f"symlink payload is forbidden: {child}")
            mode = child.stat(follow_symlinks=False).st_mode
            if not stat.S_ISREG(mode):
                raise EvidenceClosureError(f"non-regular evidence entry is forbidden: {child}")
            relative = child.relative_to(root).as_posix()
            if relative in output:
                raise EvidenceClosureError(f"duplicate evidence entry: {relative}")
            output[relative] = child
    return output


def _normalize_payload_specs(payloads: Iterable[PayloadSpec | Mapping[str, Any]]) -> list[PayloadSpec]:
    normalized: list[PayloadSpec] = []
    seen: set[str] = set()
    for item in payloads:
        if isinstance(item, PayloadSpec):
            spec = item
        else:
            required = {"source", "archive_path", "role", "source_class"}
            if set(item) != required:
                raise EvidenceClosureError("payload classification must contain exactly source/archive_path/role/source_class")
            spec = PayloadSpec(Path(str(item["source"])), str(item["archive_path"]),
                               str(item["role"]), str(item["source_class"]))
        relative = _safe_relative(spec.archive_path).as_posix()
        if relative in seen:
            raise EvidenceClosureError(f"duplicate archive_path: {relative}")
        if not spec.role.strip() or not spec.source_class.strip():
            raise EvidenceClosureError(f"unclassified payload: {relative}")
        source = spec.source.absolute()
        _reject_symlink_components(source)
        if not source.is_file() or source.is_symlink():
            raise EvidenceClosureError(f"payload source must be a regular non-symlink file: {source}")
        seen.add(relative)
        normalized.append(PayloadSpec(source, relative, spec.role.strip(), spec.source_class.strip()))
    if not normalized:
        raise EvidenceClosureError("terminal evidence payload cannot be empty")
    return sorted(normalized, key=lambda value: value.archive_path.encode("utf-8"))


def stage_curated_payloads(
    *, stage_evidence_root: str | Path, attempt_id: str,
    payloads: Iterable[PayloadSpec | Mapping[str, Any]],
) -> tuple[Path, dict[str, tuple[str, str]]]:
    """Copy only explicit payloads into an attempt-owned staging directory.

    Copying (rather than linking) prevents later mutation of a source report
    from silently changing the finalized evidence bytes.
    """

    if not attempt_id or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for character in attempt_id):
        raise EvidenceClosureError("attempt_id contains unsafe characters")
    root = Path(stage_evidence_root).absolute()
    if root.name != "17_FINAL_EVIDENCE":
        raise EvidenceClosureError("stage evidence root must be attempt-owned 17_FINAL_EVIDENCE")
    try:
        validate_attempt_root(root.parent)
    except Exception as exc:
        raise EvidenceClosureError("stage evidence root is not owned by a repaired attempt") from exc
    _reject_symlink_components(root)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise EvidenceClosureError(
            "stage evidence root must be an empty skeleton before the one terminal attempt"
        )
    staging = root / f".staging_{attempt_id}"
    if staging.exists() or staging.is_symlink():
        raise EvidenceClosureError(f"attempt-owned staging already exists: {staging}")
    specs = _normalize_payload_specs(payloads)
    roles: dict[str, tuple[str, str]] = {}
    staging.mkdir(mode=0o755)
    try:
        for spec in specs:
            destination = staging.joinpath(*PurePosixPath(spec.archive_path).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with spec.source.open("rb") as source_handle, destination.open("xb") as destination_handle:
                shutil.copyfileobj(source_handle, destination_handle, length=1024 * 1024)
            os.chmod(destination, 0o644)
            roles[spec.archive_path] = (spec.role, spec.source_class)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return staging, roles


def build_manifest(staging_root: str | Path,
                   roles: Mapping[str, tuple[str, str]] | None = None) -> list[dict[str, Any]]:
    """Build a manifest and sidecar only when every payload is classified."""

    root = Path(staging_root).absolute()
    entries = _regular_files_without_symlinks(root)
    if MANIFEST_NAME in entries or SIDECAR_NAME in entries:
        raise EvidenceClosureError("manifest/sidecar already exists; immutable rebuild required")
    role_map = dict(roles or {})
    if set(role_map) != set(entries):
        missing = sorted(set(entries) - set(role_map))
        extras = sorted(set(role_map) - set(entries))
        raise EvidenceClosureError(f"payload classification mismatch missing={missing} extras={extras}")
    rows: list[dict[str, Any]] = []
    for relative in sorted(entries, key=lambda item: item.encode("utf-8")):
        role, source_class = role_map[relative]
        if not str(role).strip() or not str(source_class).strip():
            raise EvidenceClosureError(f"unclassified payload: {relative}")
        path = entries[relative]
        rows.append({"archive_path": relative, "size_bytes": path.stat().st_size,
                     "sha256": sha256_file(path), "role": str(role),
                     "source_class": str(source_class)})
    if not rows:
        raise EvidenceClosureError("manifest cannot describe zero payloads")
    manifest = root / MANIFEST_NAME
    with manifest.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    digest = sha256_file(manifest)
    sidecar = root / SIDECAR_NAME
    with sidecar.open("x", encoding="utf-8", newline="") as handle:
        handle.write(f"{digest}  {MANIFEST_NAME}\n")
        handle.flush()
        os.fsync(handle.fileno())
    validate_stage_closure(root)
    return rows


def _read_manifest(manifest: Path) -> list[dict[str, str]]:
    with manifest.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != MANIFEST_FIELDS:
            raise EvidenceClosureError("manifest schema/order mismatch")
        rows = list(reader)
    paths = [row["archive_path"] for row in rows]
    if not rows or len(paths) != len(set(paths)):
        raise EvidenceClosureError("manifest is empty or has duplicate paths")
    return rows


def validate_stage_closure(root_value: str | Path) -> dict[str, Any]:
    root = Path(root_value).absolute()
    entries = _regular_files_without_symlinks(root)
    manifest = root / MANIFEST_NAME
    sidecar = root / SIDECAR_NAME
    if not manifest.is_file() or not sidecar.is_file():
        raise EvidenceClosureError("manifest/sidecar missing")
    expected_manifest_sha = sha256_file(manifest)
    expected_sidecar = f"{expected_manifest_sha}  {MANIFEST_NAME}\n"
    if sidecar.read_text(encoding="utf-8") != expected_sidecar:
        raise EvidenceClosureError("stage sidecar check failed")
    rows = _read_manifest(manifest)
    listed = {row["archive_path"] for row in rows}
    expected_entries = listed | {MANIFEST_NAME, SIDECAR_NAME}
    if set(entries) != expected_entries:
        raise EvidenceClosureError(
            f"stage entry set mismatch unlisted={sorted(set(entries)-expected_entries)} "
            f"missing={sorted(expected_entries-set(entries))}"
        )
    for row in rows:
        relative = _safe_relative(row["archive_path"])
        path = root.joinpath(*relative.parts)
        if (not path.is_file() or path.is_symlink() or path.stat().st_size != int(row["size_bytes"])
                or sha256_file(path) != row["sha256"]):
            raise EvidenceClosureError(f"stage payload closure mismatch: {relative}")
        if not row["role"].strip() or not row["source_class"].strip():
            raise EvidenceClosureError(f"unclassified manifest row: {relative}")
    return {"payload_count": len(rows), "entry_count": len(entries),
            "manifest_sha256": expected_manifest_sha, "sidecar_check": True,
            "exact_entry_set": True, "symlink_count": 0,
            "missing": 0, "size_mismatch": 0, "hash_mismatch": 0,
            "unlisted_extra_count": 0}


def promote_finalized(*, staging_root: str | Path, finalized_root: str | Path) -> dict[str, Any]:
    """Atomically promote a closed attempt; never replace an existing final."""

    staging = Path(staging_root).absolute()
    finalized = Path(finalized_root).absolute()
    _reject_symlink_components(staging)
    _reject_symlink_components(finalized.parent)
    if not staging.name.startswith(".staging_"):
        raise EvidenceClosureError("promotion source is not attempt-owned staging")
    if staging.parent != finalized.parent:
        raise EvidenceClosureError("atomic promotion requires staging and FINALIZED to share a parent")
    if finalized.exists() or finalized.is_symlink():
        raise EvidenceClosureError("FINALIZED already exists; immutable terminal evidence cannot be replaced")
    closure = validate_stage_closure(staging)
    try:
        os.replace(staging, finalized)
    except Exception as error:
        if finalized.exists() and not staging.exists():
            # Extremely defensive rollback if an injected/host error happens
            # after rename.  Never remove either tree.
            try:
                os.replace(finalized, staging)
            except Exception as rollback_error:  # pragma: no cover - host failure
                raise EvidenceClosureError(f"promotion and rollback failed: {error}; {rollback_error}") from error
        raise EvidenceClosureError(f"atomic promotion failed: {error}") from error
    promoted = validate_stage_closure(finalized)
    if promoted["manifest_sha256"] != closure["manifest_sha256"]:
        raise EvidenceClosureError("manifest identity changed during atomic promotion")
    return {**promoted, "atomic_promotion": True, "finalized_root": str(finalized)}


def finalize_curated_evidence(
    *, stage_evidence_root: str | Path, attempt_id: str,
    payloads: Iterable[PayloadSpec | Mapping[str, Any]],
) -> dict[str, Any]:
    """Curate, close, and atomically promote one final evidence attempt."""

    staging: Path | None = None
    try:
        staging, roles = stage_curated_payloads(stage_evidence_root=stage_evidence_root,
                                                attempt_id=attempt_id, payloads=payloads)
        build_manifest(staging, roles)
        return promote_finalized(staging_root=staging,
                                 finalized_root=Path(stage_evidence_root) / "FINALIZED")
    except Exception:
        # Cleanup is confined to the exact attempt-owned staging directory.
        if staging is not None and staging.exists() and staging.name == f".staging_{attempt_id}":
            shutil.rmtree(staging)
        raise


def _validate_zip_exact(output: Path, stage: Mapping[str, Any], expected_names: set[str]) -> dict[str, Any]:
    with zipfile.ZipFile(output, "r") as archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)) or set(names) != expected_names:
            raise EvidenceClosureError("ZIP exact entry set mismatch")
        for info in infos:
            relative = _safe_relative(info.filename) if info.filename not in {MANIFEST_NAME, SIDECAR_NAME} else PurePosixPath(info.filename)
            if info.is_dir() or stat.S_ISLNK(info.external_attr >> 16):
                raise EvidenceClosureError(f"ZIP directory/symlink entry forbidden: {relative}")
        if archive.testzip() is not None:
            raise EvidenceClosureError("unzip test failed")
        manifest_bytes = archive.read(MANIFEST_NAME)
        sidecar = archive.read(SIDECAR_NAME).decode("utf-8")
        if hashlib.sha256(manifest_bytes).hexdigest() != stage["manifest_sha256"]:
            raise EvidenceClosureError("stage/ZIP manifest SHA mismatch")
        if sidecar != f"{stage['manifest_sha256']}  {MANIFEST_NAME}\n":
            raise EvidenceClosureError("ZIP sidecar check failed")
        rows = list(csv.DictReader(manifest_bytes.decode("utf-8-sig").splitlines()))
        listed = {row["archive_path"] for row in rows}
        if listed | {MANIFEST_NAME, SIDECAR_NAME} != expected_names:
            raise EvidenceClosureError("ZIP manifest does not bind exact entry set")
        for row in rows:
            data = archive.read(row["archive_path"])
            if len(data) != int(row["size_bytes"]) or hashlib.sha256(data).hexdigest() != row["sha256"]:
                raise EvidenceClosureError(f"ZIP payload closure mismatch: {row['archive_path']}")
    return {"unzip_test": True, "zip_manifest_closure": True,
            "zip_sidecar_check": True, "zip_exact_entry_set": True}


def create_final_zip(
    *, finalized_root: str | Path, zip_path: str | Path,
    maximum_bytes: int = FINAL_ZIP_MAX_BYTES, enforce_canonical_name: bool = True,
) -> dict[str, Any]:
    """Create and re-open exactly one deterministic terminal ZIP."""

    root = Path(finalized_root).absolute()
    stage = validate_stage_closure(root)
    output = Path(zip_path).absolute()
    _reject_symlink_components(output.parent)
    if not output.parent.is_dir():
        raise EvidenceClosureError("export root does not exist")
    if enforce_canonical_name and (not output.name.startswith(FINAL_ZIP_PREFIX) or not output.name.endswith(".zip")):
        raise EvidenceClosureError("terminal ZIP name does not match canonical contract")
    if enforce_canonical_name:
        existing = [path for path in output.parent.iterdir()
                    if path.is_file() and path.name.startswith(FINAL_ZIP_PREFIX) and path.suffix == ".zip"]
        if existing:
            raise EvidenceClosureError("a canonical541 terminal ZIP already exists")
    outer_sidecar = output.with_suffix(output.suffix + ".sha256")
    if output.exists() or output.is_symlink() or outer_sidecar.exists() or outer_sidecar.is_symlink():
        raise EvidenceClosureError("terminal ZIP or outer sidecar already exists")
    entries = _regular_files_without_symlinks(root)
    expected_names = set(entries)
    fixed = (2026, 7, 19, 0, 0, 0)
    try:
        with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED,
                             compresslevel=9, strict_timestamps=True) as archive:
            for relative in sorted(entries, key=lambda item: item.encode("utf-8")):
                path = entries[relative]
                info = zipfile.ZipInfo(relative, date_time=fixed)
                info.create_system = 3
                info.external_attr = (stat.S_IFREG | 0o644) << 16
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED,
                                 compresslevel=9)
        if output.stat().st_size > int(maximum_bytes):
            raise EvidenceClosureError(
                f"terminal ZIP exceeds size limit: {output.stat().st_size} > {maximum_bytes}"
            )
        zip_checks = _validate_zip_exact(output, stage, expected_names)
        digest = sha256_file(output)
        with outer_sidecar.open("x", encoding="utf-8", newline="") as handle:
            handle.write(f"{digest}  {output.name}\n")
            handle.flush()
            os.fsync(handle.fileno())
        if outer_sidecar.read_text(encoding="utf-8") != f"{digest}  {output.name}\n":
            raise EvidenceClosureError("outer ZIP sidecar check failed")
    except Exception:
        if outer_sidecar.exists() and not outer_sidecar.is_symlink():
            outer_sidecar.unlink()
        if output.exists() and not output.is_symlink():
            output.unlink()
        raise
    return {"zip_path": str(output), "zip_sha256": digest,
            "outer_sha256_path": str(outer_sidecar), "outer_sha256_check": True,
            "zip_size_bytes": output.stat().st_size, "max_zip_size_bytes": int(maximum_bytes),
            "entry_count": len(expected_names), "manifest_sha256": stage["manifest_sha256"],
            **zip_checks}
