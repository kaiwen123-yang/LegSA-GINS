"""Append-only CLEAN5 raw locks, with one streaming read per locked source."""
from __future__ import annotations

import csv
import os
from pathlib import Path

from ..manifest import ManifestContractError, sha256_file
from ..paths import guard_path, legacy_reason
from .registry import BundleRegistry, Sequence

LOCK_COLUMNS = ("relative_path", "size_bytes", "sha256", "line_count_or_file_type", "role", "dataset", "immutable", "mtime_ns")
ORIGINAL_LOCK_SHA256 = "f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7"
ORIGINAL_LOCK_ROWS = 9980
INDEPENDENT_LOCK_NAME = "RAW_FILE_HASH_LOCK_CLEAN5.csv"


def _lock_path(clean_root: Path, name: str) -> Path:
    return guard_path(Path(clean_root) / "01_RAW_HASH_LOCK" / name, role="raw hash lock", allowed_root=clean_root)


def _read_rows(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != LOCK_COLUMNS:
            raise ManifestContractError(f"Hash-lock columns differ from the frozen schema: {path.name}")
        rows = {}
        for row in reader:
            if set(row) != set(LOCK_COLUMNS) or any(value is None for value in row.values()):
                raise ManifestContractError("Malformed hash-lock row")
            relative = row["relative_path"]
            if not relative or Path(relative).is_absolute() or ".." in Path(relative).parts or "\\" in relative or ":" in relative:
                raise ManifestContractError("Unsafe hash-lock relative path")
            if relative in rows:
                raise ManifestContractError(f"Duplicate hash-lock row: {relative}")
            rows[relative] = row
    return rows


def verify_original_lock(clean_root: Path, *, expected_hash: str = ORIGINAL_LOCK_SHA256,
                         expected_rows: int = ORIGINAL_LOCK_ROWS) -> dict:
    """Verify the immutable full BY2-era lock; row count excludes the header."""
    path = _lock_path(clean_root, "RAW_FILE_HASH_LOCK.csv")
    digest = sha256_file(path, chunk_size=1024 * 1024)
    if digest != expected_hash:
        raise ManifestContractError(f"Original raw lock SHA-256 mismatch: {digest}")
    rows = _read_rows(path)
    if len(rows) != expected_rows:
        raise ManifestContractError(f"Original raw lock row count mismatch: {len(rows)} != {expected_rows}")
    return {"lock_path": str(path), "sha256": digest, "row_count": len(rows), "rows": rows}


def _validate_inventory(registry: BundleRegistry, inventory: list[tuple[Sequence, Path]]) -> list[tuple[Sequence, Path]]:
    accepted = []
    seen = set()
    for sequence, raw_path in inventory:
        if sequence.dataset_id not in {"BY2H", "BY2O"} or sequence != registry.sequences[sequence.dataset_id]:
            raise ManifestContractError("Independent lock may contain only registered BY2H/BY2O files")
        source = guard_path(raw_path, role="CLEAN5 lock source", allowed_root=registry.raw_root,
                            must_exist=True, regular_file=True)
        if legacy_reason(source):
            raise ManifestContractError("CLEAN5 lock source resolves into legacy material")
        sibling = source in (Path(str(sequence.fix_root) + ".bag"), Path(str(sequence.fix_root) + ".fpl"))
        csv_source = source.parent == sequence.fix_root and source.suffix == ".csv"
        if not (sibling or csv_source or source == sequence.body_path):
            raise ManifestContractError("CLEAN5 lock source is outside the registered sequence inventory")
        if source in seen:
            raise ManifestContractError("Duplicate source in independent raw lock inventory")
        seen.add(source)
        accepted.append((sequence, source))
    for dataset in ("BY2H", "BY2O"):
        sequence = registry.sequences[dataset]
        sources = {path for seq, path in accepted if seq.dataset_id == dataset}
        required = {sequence.trace_path, sequence.body_path, Path(str(sequence.fix_root) + ".bag"), Path(str(sequence.fix_root) + ".fpl")}
        csv_sources = {path for path in sources if path.parent == sequence.fix_root and path.suffix == ".csv"}
        if len(sources) != 22 or len(csv_sources) != 19 or not required.issubset(sources):
            raise ManifestContractError(f"{dataset}: expected 18 CSVs, trace, bag, fpl and Go2 body (22 files)")
        if {path for path in csv_sources if path.name.startswith("trace_")} != {sequence.trace_path}:
            raise ManifestContractError(f"{dataset}: trace identity differs from registry")
    return sorted(accepted, key=lambda pair: (pair[0].dataset_id, str(pair[1])))


def inventory_lock_paths(registry: BundleRegistry) -> list[tuple[Sequence, Path]]:
    """List/stat sources only. Run before strict file-open tracing of the lock phase."""
    inventory = []
    for dataset in ("BY2H", "BY2O"):
        sequence = registry.sequences[dataset]
        sources = list(sequence.fix_root.glob("*.csv"))
        sources += [sequence.body_path, Path(str(sequence.fix_root) + ".bag"), Path(str(sequence.fix_root) + ".fpl")]
        inventory.extend((sequence, path) for path in sources)
    return _validate_inventory(registry, inventory)


def read_independent_lock(clean_root: Path, *, expected_rows: int = 44) -> dict:
    path = _lock_path(clean_root, INDEPENDENT_LOCK_NAME)
    rows = _read_rows(path)
    counts = {dataset: sum(row["dataset"] == dataset for row in rows.values()) for dataset in ("BY2H", "BY2O")}
    if len(rows) != expected_rows or counts != {"BY2H": 22, "BY2O": 22}:
        raise ManifestContractError(f"CLEAN5 lock must have 22 rows per sequence and 44 total: {counts}")
    return {"lock_path": str(path), "sha256": sha256_file(path, chunk_size=1024 * 1024), "row_count": len(rows), "rows": rows}


def build_independent_lock(registry: BundleRegistry, *, inventory: list[tuple[Sequence, Path]] | None = None,
                           original_expected_hash: str = ORIGINAL_LOCK_SHA256,
                           original_expected_rows: int = ORIGINAL_LOCK_ROWS) -> dict:
    """Hash each selected file once (1 MiB chunks), then append only missing rows.

    Existing lock bytes and existing rows never change. A matching old hash permits
    reuse of its line-count metadata without parsing any raw CSV or archive.
    Pass a pre-inventoried list under strace to avoid raw directory open calls.
    """
    original = verify_original_lock(registry.clean_root, expected_hash=original_expected_hash,
                                    expected_rows=original_expected_rows)
    selected = inventory_lock_paths(registry) if inventory is None else _validate_inventory(registry, inventory)
    path = _lock_path(registry.clean_root, INDEPENDENT_LOCK_NAME)
    existing = _read_rows(path) if path.exists() else {}
    expected_paths = {str(source.relative_to(registry.raw_root)) for _, source in selected}
    if set(existing) - expected_paths:
        raise ManifestContractError("Existing CLEAN5 lock contains rows outside the 44-file inventory")
    additions = []
    result_rows = dict(existing)
    for sequence, source in selected:
        relative = str(source.relative_to(registry.raw_root))
        before = source.stat()
        digest = sha256_file(source, chunk_size=1024 * 1024)
        after = source.stat()
        identity = lambda stat: (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if identity(before) != identity(after):
            raise ManifestContractError(f"Raw source changed while hashing: {relative}")
        previous = existing.get(relative)
        if previous is not None:
            if previous["sha256"] != digest or previous["size_bytes"] != str(after.st_size) or previous["dataset"] != sequence.dataset_id:
                raise ManifestContractError(f"Existing CLEAN5 lock disagrees with immutable raw source: {relative}")
            continue
        inherited = original["rows"].get(relative, {})
        if inherited.get("sha256") == digest and inherited.get("size_bytes") == str(after.st_size):
            count_or_type = inherited["line_count_or_file_type"]
        else:
            count_or_type = "UNAVAILABLE_NOT_PARSED" if source.suffix == ".csv" else f"file_type:{source.suffix.lstrip('.')}"
        role = "evaluation_reference_hash_only" if source == sequence.trace_path else "raw_input_hash_only"
        row = dict(zip(LOCK_COLUMNS, (relative, str(after.st_size), digest, count_or_type, role,
                                      sequence.dataset_id, "true", str(after.st_mtime_ns))))
        additions.append(row)
        result_rows[relative] = row
    if len(result_rows) != 44:
        raise ManifestContractError("Independent raw lock must contain exactly 44 rows")
    verify_original_lock(registry.clean_root, expected_hash=original_expected_hash, expected_rows=original_expected_rows)
    if additions:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=LOCK_COLUMNS, lineterminator="\n")
            if not existing:
                if handle.tell() != 0:
                    raise ManifestContractError("Existing CLEAN5 lock has a header but no data; append refused")
                writer.writeheader()
            writer.writerows(additions)
            handle.flush()
            os.fsync(handle.fileno())
    verify_original_lock(registry.clean_root, expected_hash=original_expected_hash, expected_rows=original_expected_rows)
    return read_independent_lock(registry.clean_root)
