#!/usr/bin/env python3
"""C-01: separate traced lock and input-probe processes for CLEAN5 sequences.

The inventory JSON is a metadata-only directory listing made before either phase.
Each invocation launches exactly one fresh strace session, waits for its child to
exit, and then audits the completed log. No raw content is read by the supervisor.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.paper_rebuild import evidence  # noqa: E402
from legsa_gins.paper_rebuild.manifest import git_code_state, sha256_file, write_json_atomic  # noqa: E402
from legsa_gins.paper_rebuild.clean5_sequence import raw_lock  # noqa: E402
from legsa_gins.paper_rebuild.clean5_sequence.registry import load_registry  # noqa: E402


C01B_INDEPENDENT_LOCK_SHA256 = "faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67"


def verify_probe_lock(clean_root):
    """Read the sealed independent lock without opening any raw source."""
    lock = raw_lock.read_independent_lock(clean_root)
    if lock["row_count"] != 44 or lock["sha256"] != C01B_INDEPENDENT_LOCK_SHA256:
        raise RuntimeError("C-01b independent lock identity mismatch: " + str({k: lock[k] for k in ("row_count", "sha256")}))
    return lock


def summarize_report(report):
    """Keep item failures visible without treating them as strace/lock failure."""
    def item_summary(value):
        summary = {field: value[field] for field in ("status", "error_class", "error_message", "failed_subitems", "rule_B_prime")
                   if field in value}
        nested = {key: item_summary(child) for key, child in value.items() if isinstance(child, dict) and "status" in child}
        if nested:
            summary["subitems"] = nested
        return summary

    items = {key: item_summary(value) for key, value in report.items() if isinstance(value, dict) and "status" in value}
    return {"status": report.get("status", "UNREPORTED"),
            "R1": report.get("b_base_time", {}).get("R1"), "items": items,
            "all_items_pass": bool(items) and all(item["status"] == "PASS" for item in items.values())}


def load_inventory(path, registry):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document["raw_root"] != str(registry.raw_root):
        raise RuntimeError("Pre-inventory raw_root differs from registry")
    for entry in document["directories"]:
        p = registry.sequences[entry["dataset"]].fix_root
        if p.stat().st_mtime_ns != entry["mtime_ns"]:
            raise RuntimeError(f"Directory inventory changed before hashing: {entry['dataset']}")
    inventory = [(registry.sequences[row["dataset"]], registry.raw_root / row["relative_path"])
                 for row in document["files"]]
    return raw_lock._validate_inventory(registry, inventory)


def provenance(registry, registry_path, local_path):
    commit, dirty = git_code_state(registry.code_root)
    sources = [
        "scripts/paper_rebuild/clean5_lock_and_probe.py",
        "src/legsa_gins/paper_rebuild/clean5_sequence/registry.py",
        "src/legsa_gins/paper_rebuild/clean5_sequence/raw_lock.py",
        "src/legsa_gins/paper_rebuild/clean5_sequence/probes.py",
        "src/legsa_gins/paper_rebuild/providers.py",
        "src/legsa_gins/paper_rebuild/kick_alignment.py",
        "src/legsa_gins/input_generation/status_yaw_builder.py",
        "src/legsa_gins/datasets/by2/go2_body_state_parser.py",
        "src/legsa_gins/time_alignment/event_normalization.py",
    ]
    return {"code_commit": commit, "code_worktree_dirty_at_run": dirty,
            "config_hash": sha256_file(registry_path), "local_path_config_hash": sha256_file(local_path),
            "code_sources_sha256": {p: sha256_file(registry.code_root / p) for p in sources}}


def execute_phase(args, registry, inventory):
    original = raw_lock.verify_original_lock(registry.clean_root)
    if args.phase == "lock":
        result = raw_lock.build_independent_lock(registry, inventory=inventory)
        summary = {k: result[k] for k in ("lock_path", "sha256", "row_count")}
    else:
        result = verify_probe_lock(registry.clean_root)
        # A successful independent lock audit is required, not merely a 44-row CSV.
        audit_path = registry.sequences["BY2H"].probe_dir / "LOCK_PHASE_STRACE_AUDIT.json"
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        if not audit["pass"] or audit["phase_exit_code"] != 0 or audit["raw_forbidden_writes"] != 0 or audit["lock_sha256"] != result["sha256"]:
            raise RuntimeError("Probe phase requires the successful audit of this exact independent lock")
        from legsa_gins.paper_rebuild.clean5_sequence.probes import run_probes
        try:
            reports = run_probes(registry, original["rows"], result["rows"], provenance(registry, args.registry, args.paths_config),
                                 resume_heading_only=getattr(args, "resume_heading_only", False))
            summary = {dataset: summarize_report(report) for dataset, report in reports.items()}
        finally:
            raw_lock.verify_original_lock(registry.clean_root)
            verify_probe_lock(registry.clean_root)
    raw_lock.verify_original_lock(registry.clean_root)
    return summary


def audit_strace(path, registry, phase, inventory):
    opened = evidence.parse_strace_openat_paths(path, cwd=registry.code_root)
    lines = [line for line in Path(path).read_text(encoding="utf-8", errors="strict").splitlines()
             if evidence.STRACE_OPENAT_RE.search(line)]
    if len(lines) != len(opened):
        raise RuntimeError("strace path/flag record count mismatch")
    records = []
    for line, file in zip(lines, opened):
        if file != registry.raw_root and registry.raw_root not in file.parents:
            continue
        match = evidence.STRACE_OPENAT_RE.search(line)
        flag_match = re.match(r",\s*([^,)]+)(?:,\s*[0-7]+)?\)\s*=\s*(-?\d+)", line[match.end():])
        if not flag_match:
            raise RuntimeError("Unparseable raw openat flags/return value: " + line)
        records.append({"path": str(file), "relative_path": str(file.relative_to(registry.raw_root)),
                        "flags": flag_match[1].strip(), "return_code": int(flag_match[2])})
    counts = Counter(r["path"] for r in records)
    write_records = [r for r in records if any(flag in r["flags"] for flag in
                                             ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND"))]
    failures = []
    if write_records:
        failures.append("Raw write-open detected")
    if any("O_RDONLY" not in r["flags"] or r["return_code"] < 0 for r in records):
        failures.append("Raw open was not a successful O_RDONLY open")
    forbidden_counts = {
        "trace": sum(Path(r["path"]).name.startswith("trace_") and r["path"].endswith(".csv") for r in records),
        "bag": sum(r["path"].endswith(".bag") for r in records),
        "fpl": sum(r["path"].endswith(".fpl") for r in records),
    }
    if phase == "lock":
        expected = {str(p) for _, p in inventory}
        if set(counts) != expected:
            failures.append("Raw opened-path set differs from the 44-file lock inventory")
        if any(counts.get(p) != 1 for p in expected):
            failures.append("Each locked raw file must be opened exactly once")
    else:
        from legsa_gins.paper_rebuild.clean5_sequence.probes import probe_allowlist
        allowed = {str(p) for p in probe_allowlist(registry)}
        if set(counts) - allowed:
            failures.append("Probe opened raw paths outside its allowlist")
        if any(forbidden_counts.values()):
            failures.append("Probe opened trace/bag/fpl")
    return {"pass": not failures, "failures": failures, "raw_open_records": records,
            "per_file_open_count": dict(counts), "raw_forbidden_writes": len(write_records),
            "forbidden_open_counts": forbidden_counts, "strace_path": str(path), "strace_sha256": sha256_file(path)}


def supervise_phase(args, registry, inventory):
    control = registry.sequences["BY2"].probe_dir
    control.mkdir(parents=True, exist_ok=True)
    if args.phase == "probe":
        log_name = "PROBE_C01B_H_OPENAT.strace" if getattr(args, "resume_heading_only", False) else "PROBE_C01B_OPENAT.strace"
    else:
        log_name = "LOCK_OPENAT.strace"
    log = control / log_name
    if log.exists():
        raise RuntimeError(f"Refusing to overwrite an existing phase audit log: {log}")
    command = ["strace", "-f", "-s", "4096", "-yy", "-e", "trace=openat", "-o", str(log),
               sys.executable, "-B", str(Path(__file__).resolve()), "--phase", args.phase,
               "--paths-config", str(args.paths_config), "--registry", str(args.registry),
               "--inventory-file", str(args.inventory_file), "--_traced-worker"]
    if getattr(args, "resume_heading_only", False):
        command.append("--resume-heading-only")
    process = subprocess.run(command, cwd=registry.code_root,
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False)
    audited = audit_strace(log, registry, args.phase, inventory)
    original = raw_lock.verify_original_lock(registry.clean_root)
    lock = verify_probe_lock(registry.clean_root) if args.phase == "probe" else raw_lock.read_independent_lock(registry.clean_root)
    audit_pass = audited["pass"]
    terminal_pass = audit_pass and process.returncode == 0
    audit_name = ("LOCK" if args.phase == "lock" else "PROBE") + "_PHASE_STRACE_AUDIT.json"
    sequence_summaries = {}
    for dataset, seq in registry.sequences.items():
        dataset_paths = {str(p) for s, p in inventory if s.dataset_id == dataset}
        payload = {**audited, "pass": terminal_pass, "strace_pass": audit_pass,
                   "dataset_id": dataset, "stage_id": seq.stage_id, "data_mode": seq.data_mode,
                   "synthetic_data_used": False, "semisynthetic_data_used": False,
                   "phase": args.phase, "phase_exit_code": process.returncode,
                   "lock_row_count": lock["row_count"], "dataset_lock_row_count": sum(r["dataset"] == dataset for r in lock["rows"].values()),
                   "lock_sha256": lock["sha256"], "original_lock_sha256": original["sha256"],
                   "original_lock_row_count": original["row_count"],
                   "locked_file_opens_for_dataset": [r for r in audited["raw_open_records"] if r["path"] in dataset_paths]}
        write_json_atomic(seq.probe_dir / audit_name, payload)
        if args.phase == "probe":
            from legsa_gins.paper_rebuild.clean5_sequence.probes import write_report
            path = seq.probe_dir / "PROBE_REPORT.json"
            if path.exists():
                report = json.loads(path.read_text(encoding="utf-8"))
                report.update(lock_phase_forbidden_writes=0,
                              probe_phase_trace_opens=audited["forbidden_open_counts"]["trace"],
                              probe_phase_bag_opens=audited["forbidden_open_counts"]["bag"],
                              probe_phase_fpl_opens=audited["forbidden_open_counts"]["fpl"],
                              probe_phase_forbidden_writes=audited["raw_forbidden_writes"],
                              probe_strace_pass=audit_pass)
                if not audit_pass:
                    report.update(status="FAIL", strace_failures=audited["failures"])
                write_report(seq, report)
                sequence_summaries[dataset] = summarize_report(report)
            else:
                sequence_summaries[dataset] = {"status": "REPORT_UNAVAILABLE", "all_items_pass": False}
    print(json.dumps({"phase": args.phase, "pass": terminal_pass, "phase_exit_code": process.returncode,
                      "pass_scope": "completed_phase_and_strace_and_lock_identity_only",
                      "sequence_reports": sequence_summaries,
                      "all_items_pass": (all(s["all_items_pass"] for s in sequence_summaries.values())
                                         if args.phase == "probe" else None),
                      "strace_pass": audit_pass, "strace_failures": audited["failures"],
                      "forbidden_writes": audited["raw_forbidden_writes"], "open_counts": audited["forbidden_open_counts"],
                      "lock_row_count": lock["row_count"], "lock_sha256": lock["sha256"],
                      "original_lock_row_count": original["row_count"], "original_lock_sha256": original["sha256"]}, indent=2))
    return 0 if terminal_pass else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", required=True, choices=("lock", "probe"))
    parser.add_argument("--paths-config", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml")
    parser.add_argument("--inventory-file", type=Path, required=True, help="Metadata-only listing frozen before either strace session")
    parser.add_argument("--resume-heading-only", action="store_true",
                        help="Recompute only heading-quality item h, retaining the previous a-g reports and kick evidence")
    parser.add_argument("--_traced-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.resume_heading_only and args.phase != "probe":
        parser.error("--resume-heading-only requires --phase probe")
    registry = load_registry(args.registry, args.paths_config)
    inventory = load_inventory(args.inventory_file, registry)
    if args._traced_worker:
        try:
            result = execute_phase(args, registry, inventory)
            print(json.dumps({"phase": args.phase, "result": result}, ensure_ascii=False), flush=True)
            return 0
        except Exception as exc:
            print(f"FAIL {args.phase}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
            return 2
    return supervise_phase(args, registry, inventory)


if __name__ == "__main__":
    sys.exit(main())
