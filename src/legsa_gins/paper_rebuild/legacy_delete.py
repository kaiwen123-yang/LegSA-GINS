"""Exact-manifest legacy deletion with protected-root and resume guards."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .manifest import assert_run_manifest


DELETE_MANIFEST_REQUIRED_FIELDS = {
    "delete_id",
    "exact_path",
    "realpath",
    "size_bytes",
    "file_count",
    "category",
    "contains_protected",
    "contains_unique_raw",
    "contains_unique_paper",
    "contains_unique_code",
    "inside_allowed_delete_root",
    "delete_allowed",
    "reason",
}
GLOB_META = frozenset("*?[]")


class DeleteGuardError(ValueError):
    """A deletion request failed a fail-closed safety gate."""


@dataclass(frozen=True)
class DeleteRoots:
    project_root: Path
    raw_root: Path
    paper_root: Path
    clean_root: Path
    legacy_freeze_root: Path
    code_root: Path

    @property
    def protected(self) -> tuple[Path, ...]:
        return (
            self.raw_root,
            self.paper_root,
            self.clean_root,
            self.legacy_freeze_root,
            self.code_root,
        )


def _resolve_root(path: str | Path, label: str) -> Path:
    root = Path(path).expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise DeleteGuardError(f"{label} must be an existing absolute directory")
    return root.resolve(strict=True)


def make_delete_roots(
    *,
    project_root: str | Path,
    raw_root: str | Path,
    paper_root: str | Path,
    clean_root: str | Path,
    legacy_freeze_root: str | Path,
    code_root: str | Path,
) -> DeleteRoots:
    roots = DeleteRoots(
        project_root=_resolve_root(project_root, "project_root"),
        raw_root=_resolve_root(raw_root, "raw_root"),
        paper_root=_resolve_root(paper_root, "paper_root"),
        clean_root=_resolve_root(clean_root, "clean_root"),
        legacy_freeze_root=_resolve_root(legacy_freeze_root, "legacy_freeze_root"),
        code_root=_resolve_root(code_root, "code_root"),
    )
    for label, protected in (
        ("raw_root", roots.raw_root),
        ("paper_root", roots.paper_root),
        ("clean_root", roots.clean_root),
        ("legacy_freeze_root", roots.legacy_freeze_root),
    ):
        if roots.project_root != protected and roots.project_root not in protected.parents:
            raise DeleteGuardError(f"{label} must be inside project_root")
    return roots


def _bool(value: Any) -> bool:
    return str(value).strip().casefold() in {"1", "true", "yes"}


def _within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _lexists(path: Path) -> bool:
    return os.path.lexists(path)


def load_delete_manifest(path: str | Path) -> list[dict[str, str]]:
    source = Path(path)
    if not source.is_file():
        raise DeleteGuardError("Exact delete manifest is missing")
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not DELETE_MANIFEST_REQUIRED_FIELDS.issubset(reader.fieldnames):
            missing = sorted(DELETE_MANIFEST_REQUIRED_FIELDS - set(reader.fieldnames or []))
            raise DeleteGuardError("Exact delete manifest missing fields: " + ",".join(missing))
        rows = [{key: str(value or "") for key, value in row.items()} for row in reader]
    ids = [row["delete_id"] for row in rows]
    if not rows or any(not value for value in ids) or len(ids) != len(set(ids)):
        raise DeleteGuardError("Exact delete manifest must have unique nonempty delete_id values")
    return rows


def verify_clean_smoke_gate(path: str | Path) -> dict[str, Any]:
    import json

    source = Path(path)
    if not source.is_file():
        raise DeleteGuardError("Clean smoke RUN_MANIFEST is missing")
    try:
        manifest = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeleteGuardError(f"Clean smoke RUN_MANIFEST is invalid: {exc}") from exc
    if not isinstance(manifest, dict):
        raise DeleteGuardError("Clean smoke RUN_MANIFEST must contain an object")
    try:
        assert_run_manifest(manifest, require_pass=True)
    except ValueError as exc:
        raise DeleteGuardError(f"Clean smoke gate failed: {exc}") from exc
    return manifest


def guard_delete_row(row: Mapping[str, str], roots: DeleteRoots, *, require_exists: bool = True) -> tuple[bool, str, Path | None, Path | None]:
    if not _bool(row.get("delete_allowed")):
        return False, "NOT_SELECTED", None, None
    raw_exact = str(row.get("exact_path") or "")
    if not raw_exact or any(character in raw_exact for character in GLOB_META):
        return False, "UNSAFE_OR_GLOB_EXACT_PATH", None, None
    exact = Path(raw_exact).expanduser()
    if not exact.is_absolute():
        return False, "EXACT_PATH_NOT_ABSOLUTE", exact, None
    exact_absolute = Path(os.path.abspath(exact))
    if exact_absolute == roots.project_root:
        return False, "PROJECT_ROOT_SELF_FORBIDDEN", exact_absolute, roots.project_root
    if roots.project_root not in exact_absolute.parents:
        return False, "EXACT_PATH_OUTSIDE_PROJECT_ROOT", exact_absolute, None
    if require_exists and not _lexists(exact_absolute):
        return False, "EXACT_PATH_MISSING", exact_absolute, None
    if not _lexists(exact_absolute):
        return True, "PASS_ABSENT_RESUME", exact_absolute, None
    try:
        real = exact_absolute.resolve(strict=True)
    except OSError as exc:
        return False, f"REALPATH_RESOLUTION_FAILED:{exc}", exact_absolute, None
    declared_real = str(row.get("realpath") or "")
    if not declared_real or Path(declared_real).resolve(strict=False) != real:
        return False, "REALPATH_CHANGED_FROM_MANIFEST", exact_absolute, real
    if real == roots.project_root or roots.project_root not in real.parents:
        return False, "REALPATH_OUTSIDE_OR_PROJECT_ROOT_SELF", exact_absolute, real
    for protected in roots.protected:
        if _within(exact_absolute, protected) or _within(real, protected):
            return False, f"PROTECTED_ROOT:{protected.name}", exact_absolute, real
    for field in ("contains_protected", "contains_unique_raw", "contains_unique_paper", "contains_unique_code"):
        if _bool(row.get(field)):
            return False, f"MANIFEST_PROTECTION_FLAG:{field}", exact_absolute, real
    if not _bool(row.get("inside_allowed_delete_root")):
        return False, "MANIFEST_NOT_INSIDE_ALLOWED_DELETE_ROOT", exact_absolute, real
    return True, "PASS", exact_absolute, real


def measure_path(path: Path) -> tuple[int, int, int]:
    """Return apparent bytes, allocated bytes, and regular/symlink file count."""

    if path.is_symlink() or path.is_file():
        stat = path.lstat()
        return stat.st_size, stat.st_blocks * 512, 1
    apparent = 0
    allocated = 0
    file_count = 0
    for directory, dirnames, filenames in os.walk(path, followlinks=False):
        base = Path(directory)
        for name in [*dirnames, *filenames]:
            entry = base / name
            try:
                stat = entry.lstat()
            except FileNotFoundError:
                continue
            apparent += stat.st_size
            allocated += stat.st_blocks * 512
            if entry.is_symlink() or entry.is_file():
                file_count += 1
    return apparent, allocated, file_count


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fieldnames} for row in rows])


DRY_FIELDS = [
    "delete_id",
    "exact_path",
    "realpath",
    "size_bytes",
    "category",
    "delete_allowed",
    "guard_result",
    "manifest_row_sha256",
    "manifest_rows_sha256",
]
EXEC_FIELDS = [
    "delete_id",
    "exact_path",
    "realpath",
    "category",
    "status",
    "apparent_bytes",
    "allocated_bytes",
    "file_count",
    "message",
]
FAIL_FIELDS = ["delete_id", "exact_path", "category", "error"]


def delete_row_sha256(row: Mapping[str, str]) -> str:
    """Bind dry-run approval to every required manifest field, not only its ID."""

    payload = {field: str(row.get(field) or "") for field in sorted(DELETE_MANIFEST_REQUIRED_FIELDS)}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def delete_manifest_rows_sha256(rows: Iterable[Mapping[str, str]]) -> str:
    """Hash the ordered semantic manifest so approval cannot be reused after any drift."""

    payload = [
        {field: str(row.get(field) or "") for field in sorted(DELETE_MANIFEST_REQUIRED_FIELDS)}
        for row in rows
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def dry_run_delete_manifest(rows: list[dict[str, str]], roots: DeleteRoots, output_path: Path) -> tuple[list[dict[str, Any]], bool]:
    report: list[dict[str, Any]] = []
    passed = True
    manifest_rows_hash = delete_manifest_rows_sha256(rows)
    for row in rows:
        ok, reason, _exact, real = guard_delete_row(row, roots)
        selected = _bool(row.get("delete_allowed"))
        if selected and not ok:
            passed = False
        report.append(
            {
                "delete_id": row["delete_id"],
                "exact_path": row["exact_path"],
                "realpath": str(real or row.get("realpath") or ""),
                "size_bytes": row.get("size_bytes", ""),
                "category": row.get("category", ""),
                "delete_allowed": "true" if selected else "false",
                "guard_result": reason,
                "manifest_row_sha256": delete_row_sha256(row),
                "manifest_rows_sha256": manifest_rows_hash,
            }
        )
    _write_csv(output_path, DRY_FIELDS, report)
    return report, passed


def verify_dry_run_approval(path: Path, rows: list[dict[str, str]]) -> None:
    if not path.is_file():
        raise DeleteGuardError("Approved dry-run log is missing")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        approval_rows = list(csv.DictReader(handle))
    approval: dict[str, dict[str, str]] = {}
    for approved in approval_rows:
        delete_id = str(approved.get("delete_id") or "")
        if not delete_id or delete_id in approval:
            raise DeleteGuardError("Approved dry-run log has duplicate or empty delete_id")
        approval[delete_id] = approved
    current_ids = [row["delete_id"] for row in rows]
    if set(approval) != set(current_ids):
        raise DeleteGuardError("Approved dry-run log does not match the exact manifest ID set")
    current_manifest_hash = delete_manifest_rows_sha256(rows)
    approved_manifest_hashes = {row.get("manifest_rows_sha256") for row in approval.values()}
    if approved_manifest_hashes != {current_manifest_hash}:
        raise DeleteGuardError("Exact delete manifest changed after dry-run approval")
    for row in rows:
        if _bool(row.get("delete_allowed")):
            approved = approval.get(row["delete_id"])
            if not approved or approved.get("guard_result") != "PASS":
                raise DeleteGuardError(f"Delete row lacks passing dry-run approval: {row['delete_id']}")
            if approved.get("manifest_row_sha256") != delete_row_sha256(row):
                raise DeleteGuardError(f"Delete row changed after dry-run approval: {row['delete_id']}")


def _load_execution_states(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    states: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            states[str(row.get("delete_id") or "")] = str(row.get("status") or "")
    return states


def _open_append_csv(path: Path, fields: list[str]) -> tuple[Any, csv.DictWriter]:
    exists = path.is_file() and path.stat().st_size > 0
    handle = path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(handle, fieldnames=fields)
    if not exists:
        writer.writeheader()
        handle.flush()
        os.fsync(handle.fileno())
    return handle, writer


def _checkpoint(handle: Any, writer: csv.DictWriter, row: Mapping[str, Any], fields: list[str]) -> None:
    writer.writerow({field: row.get(field, "") for field in fields})
    handle.flush()
    os.fsync(handle.fileno())


def execute_delete_manifest(
    rows: list[dict[str, str]],
    roots: DeleteRoots,
    *,
    log_root: Path,
    dry_run_log: Path,
) -> dict[str, Any]:
    verify_dry_run_approval(dry_run_log, rows)
    log_root.mkdir(parents=True, exist_ok=True)
    execution_path = log_root / "DELETE_EXECUTION_LOG.csv"
    failure_path = log_root / "DELETE_FAILURE_LOG.csv"
    previous = _load_execution_states(execution_path)
    before_free = shutil.disk_usage(roots.project_root).free
    execution_handle, execution_writer = _open_append_csv(execution_path, EXEC_FIELDS)
    failure_handle, failure_writer = _open_append_csv(failure_path, FAIL_FIELDS)
    successful: dict[str, dict[str, Any]] = {}
    failed: dict[str, str] = {}
    try:
        for row in rows:
            delete_id = row["delete_id"]
            if not _bool(row.get("delete_allowed")):
                continue
            if previous.get(delete_id) in {"DELETED", "RECOVERED_ALREADY_ABSENT"}:
                continue
            require_exists = previous.get(delete_id) != "STARTED"
            ok, reason, exact, real = guard_delete_row(row, roots, require_exists=require_exists)
            if not ok or exact is None:
                error = reason
                failed[delete_id] = error
                _checkpoint(
                    failure_handle,
                    failure_writer,
                    {"delete_id": delete_id, "exact_path": row["exact_path"], "category": row.get("category", ""), "error": error},
                    FAIL_FIELDS,
                )
                continue
            if reason == "PASS_ABSENT_RESUME":
                record = {
                    "delete_id": delete_id,
                    "exact_path": row["exact_path"],
                    "realpath": row.get("realpath", ""),
                    "category": row.get("category", ""),
                    "status": "RECOVERED_ALREADY_ABSENT",
                    "apparent_bytes": 0,
                    "allocated_bytes": 0,
                    "file_count": 0,
                    "message": "resumed after STARTED checkpoint",
                }
                _checkpoint(execution_handle, execution_writer, record, EXEC_FIELDS)
                successful[delete_id] = record
                continue
            try:
                apparent, allocated, count = measure_path(exact)
            except Exception as exc:  # noqa: BLE001 - isolate one unreadable candidate and continue.
                error = f"MEASURE_FAILED:{exc!r}"
                failed[delete_id] = error
                _checkpoint(
                    failure_handle,
                    failure_writer,
                    {
                        "delete_id": delete_id,
                        "exact_path": str(exact),
                        "category": row.get("category", ""),
                        "error": error,
                    },
                    FAIL_FIELDS,
                )
                continue
            started = {
                "delete_id": delete_id,
                "exact_path": str(exact),
                "realpath": str(real or ""),
                "category": row.get("category", ""),
                "status": "STARTED",
                "apparent_bytes": apparent,
                "allocated_bytes": allocated,
                "file_count": count,
                "message": "pre-delete checkpoint",
            }
            _checkpoint(execution_handle, execution_writer, started, EXEC_FIELDS)
            try:
                if exact.is_symlink() or exact.is_file():
                    exact.unlink()
                else:
                    shutil.rmtree(exact)
                if _lexists(exact):
                    raise OSError("exact path still exists after deletion")
                deleted = dict(started)
                deleted["status"] = "DELETED"
                deleted["message"] = "exact deletion complete"
                _checkpoint(execution_handle, execution_writer, deleted, EXEC_FIELDS)
                successful[delete_id] = deleted
            except Exception as exc:  # noqa: BLE001 - continue through independent safe candidates.
                error = repr(exc)
                failed[delete_id] = error
                _checkpoint(
                    failure_handle,
                    failure_writer,
                    {"delete_id": delete_id, "exact_path": str(exact), "category": row.get("category", ""), "error": error},
                    FAIL_FIELDS,
                )
    finally:
        execution_handle.close()
        failure_handle.close()
    after_free = shutil.disk_usage(roots.project_root).free
    summary = {
        "selected_count": sum(1 for row in rows if _bool(row.get("delete_allowed"))),
        "deleted_count_this_invocation": len(successful),
        "failed_count_this_invocation": len(failed),
        "apparent_bytes_removed_this_invocation": sum(int(row["apparent_bytes"]) for row in successful.values()),
        "allocated_bytes_removed_this_invocation": sum(int(row["allocated_bytes"]) for row in successful.values()),
        "filesystem_free_bytes_before": before_free,
        "filesystem_free_bytes_after": after_free,
        "filesystem_free_delta_bytes": after_free - before_free,
        "failed_delete_ids": sorted(failed),
        "resume_supported": True,
    }
    (log_root / "STORAGE_FREED_SUMMARY.md").write_text(
        "# Storage freed summary\n\n"
        f"- selected_count: {summary['selected_count']}\n"
        f"- deleted_count_this_invocation: {summary['deleted_count_this_invocation']}\n"
        f"- failed_count_this_invocation: {summary['failed_count_this_invocation']}\n"
        f"- apparent_bytes_removed_this_invocation: {summary['apparent_bytes_removed_this_invocation']}\n"
        f"- allocated_bytes_removed_this_invocation: {summary['allocated_bytes_removed_this_invocation']}\n"
        f"- filesystem_free_delta_bytes: {summary['filesystem_free_delta_bytes']}\n"
        f"- failed_delete_ids: {','.join(summary['failed_delete_ids'])}\n",
        encoding="utf-8",
    )
    return summary
