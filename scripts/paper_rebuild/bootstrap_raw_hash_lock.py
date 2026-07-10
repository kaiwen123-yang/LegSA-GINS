#!/usr/bin/env python3
"""Create/resume the immutable raw-file SHA256 inventory without modifying raw data."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterator

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from legsa_gins.paper_rebuild.paths import guard_path, load_clean_paths


LOCK_FIELDS = [
    "relative_path",
    "size_bytes",
    "sha256",
    "line_count",
    "file_type",
    "role",
    "dataset",
    "immutable",
]
CHECKPOINT_FIELDS = LOCK_FIELDS + ["mtime_ns"]
TEXT_SUFFIXES = {
    ".csv",
    ".txt",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".obs",
    ".nav",
    ".gnss",
    ".imu",
    ".log",
}


def _walk_regular_files(root: Path) -> tuple[Iterator[Path], list[int]]:
    skipped_symlinks = [0]

    def iterator() -> Iterator[Path]:
        for directory, dirnames, filenames in os.walk(root, followlinks=False):
            base = Path(directory)
            kept_dirs: list[str] = []
            for name in sorted(dirnames):
                candidate = base / name
                if candidate.is_symlink():
                    skipped_symlinks[0] += 1
                else:
                    kept_dirs.append(name)
            dirnames[:] = kept_dirs
            for name in sorted(filenames):
                candidate = base / name
                if candidate.is_symlink():
                    skipped_symlinks[0] += 1
                    continue
                if candidate.is_file():
                    yield candidate

    return iterator(), skipped_symlinks


def _hash_and_lines(path: Path) -> tuple[str, int | None]:
    digest = hashlib.sha256()
    count_lines = path.suffix.casefold() in TEXT_SUFFIXES
    newline_count = 0
    last_byte = b""
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(4 * 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            if count_lines:
                newline_count += chunk.count(b"\n")
                last_byte = chunk[-1:]
    if count_lines and path.stat().st_size and last_byte != b"\n":
        newline_count += 1
    return digest.hexdigest(), newline_count if count_lines else None


def _dataset(relative: str) -> str:
    parts = [part.casefold() for part in Path(relative).parts]
    name = Path(relative).name.casefold()
    if "xb_pg" in parts or any(part.startswith(("xb", "pg")) for part in parts):
        return "XB_PG"
    if "by2" in parts or name == "by2.txt":
        return "BY2"
    if "by3" in parts or name == "by3.txt":
        return "BY3"
    if "by2_by3" in parts:
        return "BY2_BY3_SHARED_OR_UNCLASSIFIED"
    return "UNCLASSIFIED_RAW"


def _role(path: Path) -> str:
    name = path.name.casefold()
    suffix = path.suffix.casefold()
    if "trace" in name:
        return "evaluation_only_reference"
    if name in {"by2.txt", "by3.txt"} or name.startswith("nmb"):
        return "robot_body_high_level_source_not_truth"
    if "status" in name:
        return "gnss_status_source_observation"
    if "raw" in name or suffix == ".ubx":
        return "gnss_raw_source_observation"
    if suffix in {".obs", ".nav"}:
        return "rinex_source"
    if "imu" in name:
        return "receiver_imu_diagnostic_source"
    return "raw_source_unclassified"


def _load_checkpoint(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            relative = str(row.get("relative_path") or "")
            if relative:
                rows[relative] = dict(row)
    return rows


def _append_checkpoint(handle: Any, writer: csv.DictWriter, row: dict[str, Any]) -> None:
    writer.writerow(row)
    handle.flush()
    os.fsync(handle.fileno())


def _write_lock(path: Path, rows: list[dict[str, Any]]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOCK_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in LOCK_FIELDS})
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


def build_raw_hash_lock(config_path: str | Path) -> dict[str, Any]:
    paths = load_clean_paths(config_path)
    output_dir = guard_path(
        paths.clean_root / "01_RAW_HASH_LOCK",
        role="raw hash-lock output",
        allowed_root=paths.clean_root,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / "RAW_HASH_CHECKPOINT.csv"
    existing = _load_checkpoint(checkpoint_path)
    published = _load_checkpoint(output_dir / "RAW_FILE_HASH_LOCK.csv")
    rows_by_relative: dict[str, dict[str, Any]] = {}
    files, skipped_symlinks = _walk_regular_files(paths.raw_root)
    checkpoint_exists = checkpoint_path.exists()
    with checkpoint_path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHECKPOINT_FIELDS)
        if not checkpoint_exists or checkpoint_path.stat().st_size == 0:
            writer.writeheader()
            handle.flush()
            os.fsync(handle.fileno())
        for source in files:
            stat = source.stat(follow_symlinks=False)
            relative = source.relative_to(paths.raw_root).as_posix()
            cached = existing.get(relative)
            if (
                cached
                and not published
                and int(cached.get("size_bytes") or -1) == stat.st_size
                and int(cached.get("mtime_ns") or -1) == stat.st_mtime_ns
                and len(cached.get("sha256") or "") == 64
            ):
                row = dict(cached)
            else:
                digest, line_count = _hash_and_lines(source)
                row = {
                    "relative_path": relative,
                    "size_bytes": stat.st_size,
                    "sha256": digest,
                    "line_count": "" if line_count is None else line_count,
                    "file_type": source.suffix.casefold().lstrip(".") or "no_extension",
                    "role": _role(source),
                    "dataset": _dataset(relative),
                    "immutable": "true",
                    "mtime_ns": stat.st_mtime_ns,
                }
                _append_checkpoint(handle, writer, row)
            rows_by_relative[relative] = row

    missing_checkpoint_sources = sorted(set(existing) - set(rows_by_relative))
    if missing_checkpoint_sources:
        raise RuntimeError(
            "Raw files disappeared after checkpoint: " + ",".join(missing_checkpoint_sources[:20])
        )
    rows = [rows_by_relative[key] for key in sorted(rows_by_relative)]
    if not rows:
        raise RuntimeError("RAW_ROOT contains no regular files")
    if published:
        published_view = {key: (row.get("size_bytes"), row.get("sha256")) for key, row in published.items()}
        current_view = {key: (str(row.get("size_bytes")), str(row.get("sha256"))) for key, row in rows_by_relative.items()}
        if published_view != current_view:
            raise RuntimeError("Published raw hash lock no longer matches RAW_ROOT; refusing silent relock")
    _write_lock(output_dir / "RAW_FILE_HASH_LOCK.csv", rows)
    _write_lock(output_dir / "BY2_HASH_LOCK.csv", [row for row in rows if row["dataset"] == "BY2"])
    _write_lock(output_dir / "BY3_HASH_LOCK.csv", [row for row in rows if row["dataset"] == "BY3"])
    _write_lock(output_dir / "XB_PG_HASH_LOCK.csv", [row for row in rows if row["dataset"] == "XB_PG"])
    summary = {
        "regular_file_count": len(rows),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "skipped_symlink_count": skipped_symlinks[0],
        "dataset_counts": {
            dataset: sum(1 for row in rows if row["dataset"] == dataset)
            for dataset in sorted({str(row["dataset"]) for row in rows})
        },
        "raw_modified": False,
        "immutable": True,
        "checkpoint_resume_supported": True,
    }
    (output_dir / "RAW_HASH_SUMMARY.md").write_text(
        "# Raw hash lock summary\n\n"
        f"- regular_file_count: {summary['regular_file_count']}\n"
        f"- total_size_bytes: {summary['total_size_bytes']}\n"
        f"- skipped_symlink_count: {summary['skipped_symlink_count']}\n"
        "- raw_modified: false\n"
        "- immutable: true\n"
        f"- dataset_counts: `{json.dumps(summary['dataset_counts'], sort_keys=True)}`\n",
        encoding="utf-8",
    )
    return summary


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, help="Ignored DATA_PATHS.local.yaml")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    print(json.dumps(build_raw_hash_lock(args.config), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
