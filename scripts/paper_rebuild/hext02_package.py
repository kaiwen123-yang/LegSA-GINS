#!/usr/bin/env python3
"""Package completed H-EXT-02 evidence after the result commit; no experiment runs.

This post-freeze bookkeeping command preserves original stop/adjudication
receipts.  It reads only derived evidence and code/documentation, never raw
payloads.  The external validation receipt includes the ZIP's real identity;
neither the result commit nor the internal manifest claims a self hash.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import errno
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import time
import uuid
import zipfile
import zlib

import yaml

from legsa_gins.paper_rebuild.hext.sequence_paths import LOCAL_CONFIG, load_sequence_paths


RESULT_SUBJECT = "feat(hext): H-EXT-02 three-sequence external comparison rows, FIG02S and handoff"
FREEZE_SUBJECT = "prereg(hext): H-EXT-02 authorized contract and code freeze"
ZIP_NAME = "hext_three_sequences_handoff.zip"
RECEIPT_NAME = "hext_three_sequences_handoff.validation.json"
INTERNAL_MANIFEST = "MEMBER_MANIFEST.json"
STAGE_DIRECTORIES = (
    "03_PREREG", "03_PROVIDER_CACHE", "04_NATIVE_RUNS", "04_ACCESS_AUDITS",
    "05_GEOMETRIC_AUDIT", "06_V3_NAV_INPUTS", "07_OFFLINE_EVALUATION",
    "08_AGGREGATE", "09_LEGSA_GAP_DIAGNOSTIC", "10_FIGURES",
    "RAW_CHECKPOINTS", "EVALUATION_RAW_CHECKPOINTS",
)
REQUIRED_DOCS = (
    "AGENTS.md", "docs/paper_rebuild/CONVERSATION_HANDOFF.md",
    "docs/paper_rebuild/HORIZONTAL_THREE_SEQUENCES.md",
    "docs/paper_rebuild/hext/H_EXT_02_EXECUTION_RECORD.md",
    "configs/paper_rebuild/hext/H_EXT_CONTRACT_V1.yaml",
)
CHUNK = 1024 * 1024


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def _write_json(path: Path, value):
    with path.open("xb") as stream:
        stream.write(_json_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())


def _git(root: Path, *args: str) -> str:
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    return subprocess.check_output(["git", *args], cwd=root, env=environment, text=True).strip()


def _read_json(path: Path):
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Required nonsymlink metadata missing: " + str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def _commit_gates(sequence, scratch: Path):
    freeze_path = sequence.output_root / "03_PREREG/CODE_FREEZE.json"
    freeze = _read_json(freeze_path)
    if _sha(freeze_path) != _sha(scratch / "03_PREREG/CODE_FREEZE.json"):
        raise RuntimeError("Archived/scratch code-freeze receipt mismatch")
    code_commit, result_commit = freeze["code_freeze"], _git(sequence.code_root, "rev-parse", "HEAD")
    if _git(sequence.code_root, "log", "-1", "--format=%s") != RESULT_SUBJECT:
        raise RuntimeError("Package requires the exact completed result-commit subject")
    if _git(sequence.code_root, "show", "-s", "--format=%s", code_commit) != FREEZE_SUBJECT:
        raise RuntimeError("Code-freeze commit subject mismatch")
    _git(sequence.code_root, "merge-base", "--is-ancestor", code_commit, result_commit)
    if code_commit == result_commit or _git(sequence.code_root, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("Package requires a distinct committed result and clean tracked files")
    for relative, expected in freeze["source_hashes"].items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Unsafe frozen code-source name")
        source = sequence.code_root / path
        if source.is_symlink() or _sha(source) != expected:
            raise RuntimeError("Scientific code changed after freeze: " + relative)
    commits = {
        "scientific_code_freeze": code_commit, "scientific_code_freeze_subject": FREEZE_SUBJECT,
        "result_commit": result_commit, "result_commit_subject": RESULT_SUBJECT,
        "code_freeze_receipt_sha256": _sha(freeze_path), "scientific_source_hashes": freeze["source_hashes"],
        "packaging_script_sha256": _sha(Path(__file__)),
        "postfreeze_packaging_role": "BOOKKEEPING_ONLY_NO_SCIENTIFIC_CODE_CHANGES",
        "circular_identity_resolution": "Result commit references external receipt; final ZIP embeds both commits.",
    }
    return freeze, commits


def _completion_gates(sequence):
    summary = _read_json(sequence.output_root / "08_AGGREGATE/FINAL_SUMMARY.json")
    if summary.get("status") != "COMPLETED_H_EXT_02_AGGREGATION":
        raise RuntimeError("Aggregation has not completed")
    ledger = summary["budget_ledger"]
    native, evaluated = ledger["native_actual"], ledger["evaluator_actual"]
    if not (0 < native <= 14 and evaluated == 2 * native and evaluated <= 28):
        raise RuntimeError("Registered native/evaluator budget mismatch")
    if summary["native_registered_count"] != native or summary["new_evaluation_rows"] != evaluated:
        raise RuntimeError("Aggregate row counts disagree with execution ledger")
    for name, expected in summary["files_sha256"].items():
        if _sha(sequence.output_root / "08_AGGREGATE" / name) != expected:
            raise RuntimeError("Aggregate output changed after final summary: " + name)
    figure = _read_json(sequence.output_root / "10_FIGURES/HEXT_RENDER_MANIFEST.json")
    if figure.get("original_v21_files_byte_unchanged") is not True or not all(row["pass"] for row in figure["qa"]):
        raise RuntimeError("Figure QA/frozen-original byte gate has not passed")
    return {"budget_ledger": ledger, "aggregate_status": summary["status"],
            "aggregate_code_commit": summary["code_commit"], "selection": summary["selection"],
            "figure_status": figure["status"], "frozen_v21_byte_unchanged": True}


def _collect(sequence, scratch: Path, freeze, local_config: Path):
    """Use an exact stage allowlist; reject links and all raw-role filenames."""
    entries = {}
    raw_root = sequence.raw_root.resolve()
    forbidden_names = {"gnss1-raw.csv", "gnss2-raw.csv"}
    for name in ("BY2", "BY2H", "BY2O"):
        record = load_sequence_paths(name, local_config=local_config)
        forbidden_names.update((record.trace.name, record.go2_body.name))

    def add(path, member, root):
        path, root = Path(path), Path(root)
        member_path = PurePosixPath(member)
        if member_path.is_absolute() or ".." in member_path.parts or member in entries:
            if member in entries and entries[member] == path:
                return
            raise ValueError("Duplicate/unsafe ZIP member: " + member)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Package source must be a regular nonsymlink file: " + str(path))
        resolved = path.resolve()
        resolved.relative_to(root.resolve())
        if (resolved == raw_root or raw_root in resolved.parents or path.name in forbidden_names
                or path.suffix.lower() in (".bag", ".fpl")):
            raise ValueError("Raw/reference payload is forbidden in package: " + str(path))
        entries[member] = path

    def tree(root, prefix):
        if root.is_symlink() or not root.is_dir():
            raise RuntimeError("Required evidence directory missing or symlink: " + str(root))
        count = 0
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError("Package never follows evidence symlinks: " + str(path))
            if path.is_file():
                add(path, prefix + "/" + path.relative_to(root).as_posix(), root)
                count += 1
        if not count:
            raise RuntimeError("Required evidence directory is empty: " + str(root))

    for name in STAGE_DIRECTORIES:
        tree(sequence.output_root / name, "STAGE/" + name)
    if (sequence.output_root / "01_PROBE").is_dir():
        tree(sequence.output_root / "01_PROBE", "STAGE/01_PROBE")
    # Preserve earlier stop + adjudication + controller receipts without
    # relabeling the first controller invocation as a first-pass success.
    for path in sorted(scratch.iterdir()):
        if path.is_file() and path.suffix.lower() in (".json", ".jsonl", ".log", ".strace"):
            add(path, "EXECUTION_BOOKKEEPING/" + path.name, scratch)
        elif path.is_dir() and path.name.startswith("BOOKKEEPING"):
            tree(path, "EXECUTION_BOOKKEEPING/" + path.name)
    for relative in REQUIRED_DOCS:
        add(sequence.code_root / relative, "REPOSITORY/" + relative, sequence.code_root)
    related = sorted((sequence.code_root / "docs/paper_rebuild/hext").glob("*.md"))
    related += sorted((sequence.code_root / "docs/paper_rebuild/hext").glob("*.csv"))
    related += sorted((sequence.code_root / "scripts/paper_rebuild").glob("hext02_*.py"))
    related += [sequence.code_root / relative for relative in freeze["source_hashes"]]
    for path in related:
        relative = path.relative_to(sequence.code_root).as_posix()
        _git(sequence.code_root, "ls-files", "--error-unmatch", "--", relative)
        add(path, "REPOSITORY/" + relative, sequence.code_root)
    return entries


def _member_row(name, payload):
    return {"name": name, "size_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
            "crc32": f"{zlib.crc32(payload) & 0xffffffff:08x}"}


def _create_zip(destination, entries, commits, completion):
    rows = []
    with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as package:
        for index, (name, path) in enumerate(sorted(entries.items()), 1):
            before = path.stat()
            digest, crc, count = hashlib.sha256(), 0, 0
            with path.open("rb") as source, package.open(name, "w", force_zip64=True) as target:
                for block in iter(lambda: source.read(CHUNK), b""):
                    target.write(block)
                    digest.update(block)
                    crc = zlib.crc32(block, crc)
                    count += len(block)
            after = path.stat()
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino) or count != before.st_size:
                raise RuntimeError("Evidence changed while packaging: " + name)
            rows.append({"name": name, "size_bytes": count, "sha256": digest.hexdigest(), "crc32": f"{crc & 0xffffffff:08x}"})
            if index % 100 == 0:
                print(f"PACKAGED_MEMBERS {index}/{len(entries)}", flush=True)
        commit_bytes = _json_bytes(commits)
        package.writestr("GIT_COMMITS.json", commit_bytes)
        rows.append(_member_row("GIT_COMMITS.json", commit_bytes))
        manifest = {"schema_version": "hext.handoff.members.v1", "data_mode": "real_external_and_frozen_comparison",
                    "synthetic_data_used": False, "semisynthetic_data_used": False,
                    "trace_payload_open_count": 0, "raw_payload_open_count": 0,
                    "solver_invocation_count": 0, "evaluator_invocation_count": 0,
                    "completion": completion, "git_commits": commits,
                    "member_count_excluding_this_manifest": len(rows),
                    "uncompressed_bytes_excluding_this_manifest": sum(row["size_bytes"] for row in rows),
                    "self_hash_policy": "This manifest excludes itself. External validation includes every member, including this manifest.",
                    "members": rows}
        payload = _json_bytes(manifest)
        package.writestr(INTERNAL_MANIFEST, payload)
        rows.append(_member_row(INTERNAL_MANIFEST, payload))
    return sorted(rows, key=lambda row: row["name"])


def _verify_zip(path, rows):
    expected = {row["name"]: row for row in rows}
    with zipfile.ZipFile(path, "r") as package:
        if len(package.infolist()) != len(expected) or set(package.namelist()) != set(expected):
            raise RuntimeError("ZIP member identity/count mismatch")
        for info in package.infolist():
            row, digest, crc, size = expected[info.filename], hashlib.sha256(), 0, 0
            with package.open(info, "r") as stream:
                for block in iter(lambda: stream.read(CHUNK), b""):
                    digest.update(block)
                    crc = zlib.crc32(block, crc)
                    size += len(block)
            if (size != row["size_bytes"] or info.file_size != size or digest.hexdigest() != row["sha256"]
                    or f"{crc & 0xffffffff:08x}" != row["crc32"] or info.CRC != (crc & 0xffffffff)):
                raise RuntimeError("ZIP member SHA/CRC/size mismatch: " + info.filename)
    return {"status": "PASS", "member_count": len(rows), "all_member_sha256": "PASS", "all_member_crc32": "PASS"}


def _exclusive_copy(source, target):
    """Only our own partial file may be rewritten on an ENOMEM/EIO retry."""
    source_hash, source_size = _sha(source), source.stat().st_size
    owned_inode, retry = None, 0
    while True:
        try:
            if target.is_symlink() or (owned_inode is not None and target.stat().st_ino != owned_inode):
                raise RuntimeError("Archive target was replaced or is a symlink")
            with source.open("rb") as src, target.open("xb" if owned_inode is None else "wb") as dst:
                owned_inode = os.fstat(dst.fileno()).st_ino
                shutil.copyfileobj(src, dst, CHUNK)
                dst.flush()
                os.fsync(dst.fileno())
            if target.stat().st_size != source_size or _sha(target) != source_hash:
                raise RuntimeError("Archive readback SHA/size mismatch")
            return {"sha256": source_hash, "size_bytes": source_size, "retries": retry}
        except OSError as exc:
            if exc.errno not in (errno.ENOMEM, errno.EIO) or retry >= 3:
                raise
            retry += 1
            time.sleep(retry)


def package_handoff(local_config=LOCAL_CONFIG):
    local_config = Path(local_config)
    sequence = load_sequence_paths("BY2", local_config=local_config)
    local = yaml.safe_load(local_config.read_text(encoding="utf-8"))["paths"]
    handoff = Path(local["handoff_root"])
    if handoff.is_symlink() or not handoff.is_dir():
        raise RuntimeError("Configured handoff_root must already exist without a symlink")
    scratch = sequence.hext_scratch / "H_EXT_02"
    freeze, commits = _commit_gates(sequence, scratch)
    completion = _completion_gates(sequence)
    if completion["aggregate_code_commit"] != commits["scientific_code_freeze"]:
        raise RuntimeError("Aggregate does not name the frozen scientific commit")
    target, receipt_path = handoff / ZIP_NAME, handoff / RECEIPT_NAME
    if target.exists() or receipt_path.exists():
        raise FileExistsError("Final handoff ZIP/receipt already exists; never overwrite or automatically retry")
    entries = _collect(sequence, scratch, freeze, local_config)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "_" + uuid.uuid4().hex[:12]
    build = scratch / "PACKAGE" / stamp
    build.mkdir(parents=True, exist_ok=False)
    local_zip = build / ZIP_NAME
    rows = _create_zip(local_zip, entries, commits, completion)
    local_validation = _verify_zip(local_zip, rows)
    # Recheck the same commit and every frozen source after copying evidence.
    _freeze_after, commits_after = _commit_gates(sequence, scratch)
    if commits_after != commits:
        raise RuntimeError("Commit/source identity changed while packaging")
    copy = _exclusive_copy(local_zip, target)
    remote_validation = _verify_zip(target, rows)
    receipt = {"schema_version": "hext.handoff.validation.v1", "status": "PASS_ZIP_SHA_MEMBERS_CRC",
               "package": "<HANDOFF_ROOT>/" + ZIP_NAME, "sha256": copy["sha256"], "bytes": copy["size_bytes"],
               "member_count": len(rows), "uncompressed_member_bytes": sum(row["size_bytes"] for row in rows),
               "git_commits": commits, "completion": completion,
               "ext4_build": "<HEXT_SCRATCH>/H_EXT_02/PACKAGE/" + stamp,
               "archive_copy_retries": copy["retries"], "archive_retry_policy": "ENOMEM_OR_EIO_ONLY_MAX_THREE_RETRIES",
               "ext4_validation": local_validation, "archived_validation": remote_validation,
               "CRC": "PASS", "member_manifest_includes_internal_manifest_sha256": True,
               "trace_payload_open_count": 0, "raw_payload_open_count": 0,
               "solver_invocation_count": 0, "evaluator_invocation_count": 0,
               "original_stop_and_bookkeeping_adjudication_preserved": True, "members": rows}
    local_receipt = build / RECEIPT_NAME
    _write_json(local_receipt, receipt)
    receipt_copy = _exclusive_copy(local_receipt, receipt_path)
    compact = {key: receipt[key] for key in ("status", "package", "sha256", "bytes", "member_count", "CRC", "git_commits", "archive_copy_retries")}
    compact.update(external_receipt="<HANDOFF_ROOT>/" + RECEIPT_NAME, external_receipt_sha256=receipt_copy["sha256"])
    _write_json(build / "FINAL_HANDOFF_RECEIPT.json", compact)
    _exclusive_copy(build / "FINAL_HANDOFF_RECEIPT.json", sequence.output_root / "FINAL_HANDOFF_RECEIPT.json")
    return compact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-config", type=Path, default=LOCAL_CONFIG)
    args = parser.parse_args()
    print(json.dumps(package_handoff(args.local_config), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
