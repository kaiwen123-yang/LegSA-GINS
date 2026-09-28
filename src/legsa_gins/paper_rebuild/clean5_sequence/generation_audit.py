"""CLEAN5 C-03 phase isolation and immutable raw checkpoints.

The checkpoint process hashes, never parses, the selected 22 raw files. A separate
generation process is denied trace and archive opens. The checkpoint strace
session spans pre and post; stage-owned marker opens delimit the two audits.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

from .. import evidence
from ..manifest import sha256_file, verify_raw_sources
from . import raw_lock

INDEPENDENT_LOCK_SHA256 = "faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67"
WRITE_FLAGS = ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND")


def write_json_exclusive(path: Path, payload: dict) -> None:
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def selected_lock(registry, sequence) -> dict:
    original = raw_lock.verify_original_lock(registry.clean_root)
    independent = raw_lock.read_independent_lock(registry.clean_root)
    if independent["sha256"] != INDEPENDENT_LOCK_SHA256:
        raise RuntimeError("Independent 44-row raw lock SHA-256 mismatch")
    source = original if sequence.dataset_id == "BY2" else independent
    rows = {key: value for key, value in source["rows"].items()
            if value["dataset"] == sequence.dataset_id}
    expected = {str(sequence.fix_root.relative_to(registry.raw_root)) + "/" + name
                for name in ("corr-raw.csv", "gnss1-raw.csv", "gnss1-status.csv", "gnss2-raw.csv",
                             "gnss2-status.csv", "imu-biases.csv", "imu-data.csv", "imu-temp.csv",
                             "ntrip-info.csv", "ntrip-latency.csv", "tf.csv", "tf_static.csv",
                             sequence.trace_name, "user_io-out-odom_status.csv", "user_io-out-poi_geodetic.csv",
                             "user_io-out-poi_odometry.csv", "user_io-out-poi_smooth_odometry.csv",
                             "user_io-status.csv", "userio-raw.csv")}
    expected.update({sequence.fix_prefix + ".bag", sequence.fix_prefix + ".fpl", sequence.go2_body})
    if len(rows) != 22 or set(rows) != expected:
        raise RuntimeError("Sequence lock path set differs from its registered 22 files")
    return {"rows": rows, "sha256": source["sha256"], "path": source["lock_path"],
            "original_sha256": original["sha256"], "original_rows": original["row_count"],
            "independent_sha256": independent["sha256"], "independent_rows": independent["row_count"]}


def validate_checkpoint(checkpoint: dict, *, phase: str, lock: dict) -> dict:
    """Sequence-parameterized counterpart of final_v23 validate_raw_checkpoint."""
    expected = {"schema_version": "paper_rebuild.final_v23_external_raw_checkpoint.v1",
                "audit_phase": phase, "raw_hash_lock_sha256": lock["sha256"],
                "expected": 22, "verified": 22, "missing": 0, "mismatch": 0,
                "symlink_escape": 0, "raw_mutation": 0, "passed": True,
                "trace_read_role": "outer_raw_integrity_hash_audit_only",
                "trace_provider_or_solver_input": False}
    bad = [key for key, value in expected.items() if checkpoint.get(key) != value]
    hashes = checkpoint.get("verified_hashes")
    if bad or hashes != {key: row["sha256"] for key, row in lock["rows"].items()}:
        raise RuntimeError(f"Raw checkpoint differs from its frozen identity: {bad}")
    return dict(hashes)


def checkpoint(registry, sequence, phase: str, audit_dir: Path) -> dict:
    if phase not in ("pre_generation", "post_generation"):
        raise ValueError("Unknown checkpoint phase")
    lock = selected_lock(registry, sequence)
    marker = audit_dir / (phase + "_BEGIN")
    with marker.open("x", encoding="utf-8") as handle:
        handle.write(phase + "\n")
    hashes = verify_raw_sources(registry.raw_root, sorted(lock["rows"]), lock["rows"])
    payload = {"schema_version": "paper_rebuild.final_v23_external_raw_checkpoint.v1",
               "audit_phase": phase, "dataset_id": sequence.dataset_id,
               "raw_hash_lock_sha256": lock["sha256"], "expected": 22, "verified": len(hashes),
               "missing": 0, "mismatch": 0, "symlink_escape": 0, "raw_mutation": 0,
               "passed": True, "trace_read_role": "outer_raw_integrity_hash_audit_only",
               "trace_provider_or_solver_input": False, "verified_hashes": hashes,
               "synthetic_data_used": False, "semisynthetic_data_used": False}
    validate_checkpoint(payload, phase=phase, lock=lock)
    write_json_exclusive(audit_dir / (phase + "_CHECKPOINT.json"), payload)
    return payload


def open_records(path: Path, cwd: Path) -> list[dict]:
    """Use the maintained path parser, preserving flags and failed open attempts."""
    opened = evidence.parse_strace_openat_paths(path, cwd=cwd)
    lines = [line for line in path.read_text(encoding="utf-8").splitlines()
             if evidence.STRACE_OPENAT_RE.search(line)]
    if len(opened) != len(lines):
        raise RuntimeError("strace path/flags association failed")
    records = []
    for source, line in zip(opened, lines):
        match = evidence.STRACE_OPENAT_RE.search(line)
        parsed = re.match(r",\s*([^,)]+)(?:,\s*[0-7]+)?\)\s*=\s*(-?\d+)", line[match.end():])
        if not parsed:
            raise RuntimeError(f"Unparseable strace flags: {source}")
        records.append({"path": str(source), "flags": parsed[1].strip(), "return_code": int(parsed[2])})
    return records


def audit_records(records: list[dict], raw_root: Path, expected_paths: set[Path], *, checkpoint_phase: bool) -> dict:
    raw = [row for row in records if Path(row["path"]) == raw_root or raw_root in Path(row["path"]).parents]
    counts = Counter(row["path"] for row in raw)
    writes = [row for row in raw if any(flag in row["flags"] for flag in WRITE_FLAGS)]
    forbidden = {"trace": sum(Path(row["path"]).name.startswith("trace_") and row["path"].endswith(".csv") for row in raw),
                 "bag": sum(row["path"].endswith(".bag") for row in raw),
                 "fpl": sum(row["path"].endswith(".fpl") for row in raw)}
    expected = {str(p) for p in expected_paths}
    failures = []
    if (checkpoint_phase and set(counts) != expected) or (not checkpoint_phase and set(counts) - expected):
        failures.append("Raw open path set mismatch")
    if checkpoint_phase and any(count != 1 for count in counts.values()):
        failures.append("Checkpoint must open each selected file exactly once")
    if writes:
        failures.append("Raw write-open detected")
    if any("O_RDONLY" not in row["flags"] or row["return_code"] < 0 for row in raw):
        failures.append("Every raw open must succeed and be O_RDONLY")
    if not checkpoint_phase and any(forbidden.values()):
        failures.append("Generation opened trace/bag/fpl")
    return {"pass": not failures, "failures": failures, "raw_open_count": len(raw),
            "per_file_open_count": dict(sorted(counts.items())), "raw_open_records": raw,
            "raw_forbidden_writes": len(writes), "forbidden_open_counts": forbidden}


def audit_checkpoint_session(path: Path, registry, sequence, audit_dir: Path) -> dict:
    records = open_records(path, registry.code_root)
    marker_ids = {}
    for phase in ("pre_generation", "post_generation"):
        marker = str(audit_dir / (phase + "_BEGIN"))
        hits = [i for i, row in enumerate(records) if row["path"] == marker]
        if len(hits) != 1:
            raise RuntimeError(f"Checkpoint phase marker must occur once: {phase}")
        marker_ids[phase] = hits[0]
    first, second = marker_ids["pre_generation"], marker_ids["post_generation"]
    if first >= second:
        raise RuntimeError("Checkpoint phase order reversed")
    expected = {registry.raw_root / relative for relative in selected_lock(registry, sequence)["rows"]}
    before = audit_records(records[:first], registry.raw_root, set(), checkpoint_phase=True)
    pre = audit_records(records[first:second], registry.raw_root, expected, checkpoint_phase=True)
    post = audit_records(records[second:], registry.raw_root, expected, checkpoint_phase=True)
    return {"pass": before["pass"] and pre["pass"] and post["pass"],
            "pre_generation": pre, "post_generation": post, "before_first_marker": before,
            "raw_open_count": pre["raw_open_count"] + post["raw_open_count"],
            "session_count": 1, "strace_sha256": sha256_file(path)}


def code_freeze_state(repo: Path, expected_commit: str) -> dict:
    """Require the clean detached snapshot of the already-pushed exact freeze."""
    repo = Path(repo).resolve(strict=True)
    git_env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}
    if not re.fullmatch(r"[0-9a-f]{40}", expected_commit):
        raise RuntimeError("code_freeze_commit must be a full lowercase Git commit SHA")
    top = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=repo, text=True, env=git_env).strip()).resolve()
    if top != repo:
        raise RuntimeError("--code-root must be the worktree root")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True, env=git_env).strip()
    remote_head = subprocess.check_output(
        ["git", "rev-parse", "refs/remotes/origin/stage/clean3-math-repair"], cwd=repo, text=True, env=git_env).strip()
    if head != expected_commit or remote_head != expected_commit:
        raise RuntimeError("Execution HEAD must equal code_freeze_commit and origin/stage/clean3-math-repair")
    symbolic = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=repo, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, env=git_env)
    if symbolic.returncode != 1:
        raise RuntimeError("C-03 generation requires a detached execution worktree")
    status = subprocess.check_output(["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=repo, text=True, env=git_env)
    if status:
        raise RuntimeError("C-03 generation requires a clean committed worktree; preserve existing untracked files")
    return {"code_freeze_commit": head, "code_worktree_dirty_at_generation": False,
            "execution_worktree": str(repo), "execution_worktree_head": head,
            "execution_worktree_git_status": status, "execution_worktree_untracked_files": "all",
            "execution_worktree_detached": True, "origin_stage_clean3_math_repair_head": remote_head}
