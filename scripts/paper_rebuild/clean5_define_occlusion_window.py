#!/usr/bin/env python3
"""Freeze CLEAN5 occlusion windows from GNSS receiver status and maintained A1 only.

The supervisor never opens raw data. Its fresh strace worker reads precisely the
six registered GNSS status files, then the supervisor audits all raw open calls.
Trace, archives, Go2 logs, providers, solvers and evaluators are not inputs.
"""
from __future__ import annotations

import argparse
import inspect
import json
import math
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from legsa_gins.paper_rebuild import evidence  # noqa: E402
from legsa_gins.paper_rebuild.clean5_sequence import probes, raw_lock  # noqa: E402
from legsa_gins.paper_rebuild.clean5_sequence.registry import load_registry  # noqa: E402
from legsa_gins.paper_rebuild.manifest import git_code_state, sha256_file, write_json_atomic  # noqa: E402
from legsa_gins.paper_rebuild.paths import guard_path  # noqa: E402

INDEPENDENT_LOCK_SHA256 = "faa31580c7fff73b52fcf6d27c97cfdd9187e67a55968a2ab42e6737b0eabb67"
MAX_BRIDGE_SECONDS = 5.0
STATUS_NAMES = ("gnss1-status.csv", "gnss2-status.csv")


def verify_locks(clean_root):
    original = raw_lock.verify_original_lock(clean_root)
    independent = raw_lock.read_independent_lock(clean_root)
    if independent["row_count"] != 44 or independent["sha256"] != INDEPENDENT_LOCK_SHA256:
        raise RuntimeError("C-02 independent raw lock must match its frozen 44-row identity")
    return original, independent


def status_paths(registry):
    return {seq.fix_root / name for seq in registry.sequences.values() for name in STATUS_NAMES}


def output_dir(seq, clean_root):
    stage = clean_root / "stages" / seq.stage_id
    destination = stage / "01_SEQUENCE_CONTRACT" if seq.dataset_id == "BY2O" else stage
    return guard_path(destination, role="C-02 occlusion contract output", allowed_root=clean_root)


def define_window(epochs, t_start, t_end):
    """Merge flagged epochs at <=5 s separation inside the closed frozen window."""
    if not all(math.isfinite(float(t)) for t in (t_start, t_end)) or t_start > t_end:
        raise ValueError("Closed sequence window must have finite ordered endpoints")
    included = []
    for epoch in epochs:
        stamp = float(epoch["relative_time_R1"])
        if not math.isfinite(stamp):
            raise ValueError("Occlusion epoch must have a finite relative time")
        if t_start <= stamp <= t_end:
            included.append(epoch)
    included.sort(key=lambda row: float(row["relative_time_R1"]))
    flagged = [row for row in included if row["flagged"]]
    groups = []
    for row in flagged:
        if not groups or float(row["relative_time_R1"]) - float(groups[-1][-1]["relative_time_R1"]) > MAX_BRIDGE_SECONDS:
            groups.append([row])
        else:
            groups[-1].append(row)
    segments = []
    for group in groups:
        first = float(group[0]["relative_time_R1"])
        last = float(group[-1]["relative_time_R1"])
        flags_counts = Counter(flag for row in group for flag in row["trigger_flags"])
        segments.append({"t0": first, "t1": last, "duration_seconds": last-first,
                         "epoch_count": sum(first <= float(row["relative_time_R1"]) <= last for row in included),
                         "flagged_epoch_count": len(group), "flags_counts": dict(sorted(flags_counts.items())),
                         "trigger_flags": sorted(flags_counts)})
    segments.sort(key=lambda row: (-row["duration_seconds"], row["t0"], row["t1"]))
    return {"closed_sequence_window": {"t_start": float(t_start), "t_end": float(t_end)},
            "max_bridge_seconds": MAX_BRIDGE_SECONDS,
            "bridge_definition": "adjacent flagged epoch separation <= 5 s; no time search or padding",
            "main_window": segments[0] if segments else None,
            "secondary_runs": segments[1:],
            "all_runs": segments,
            "flags_counts": dict(sorted(Counter(flag for row in flagged for flag in row["trigger_flags"]).items())),
            "main_selection": "maximum observed duration; earliest start resolves equal durations",
            "duration_definition": "last flagged GNSS2 sys_stamp minus first flagged GNSS2 sys_stamp",
            "epoch_count": len(included), "flagged_epoch_count": len(flagged),
            "excluded_outside_closed_window": len(epochs)-len(included), "epochs": included}


def flag_epochs(gnss1_rows, gnss2_rows, gnss2_names, a1_rows, base_time, association_tolerance):
    """Retain the original receiver fields and the maintained A1 association."""
    if association_tolerance != 0.6:
        raise RuntimeError("Maintained A1 association tolerance differs from the frozen 0.6 s")
    associated, _ = probes.occlusion_rows(gnss2_rows, gnss2_names, base_time, gnss1_rows,
                                          a1_rows, association_tolerance)
    gnss1_by_header = {}
    for row in sorted(gnss1_rows, key=lambda row: probes._stamp(row, "header.stamp")):
        gnss1_by_header.setdefault(probes._stamp(row, "header.stamp"), row)
    output = []
    for two, association in zip(sorted(gnss2_rows, key=probes._stamp), associated):
        header_relative = association["matched_gnss1_header_R1"]
        one = gnss1_by_header.get(header_relative + base_time) if header_relative is not None else None
        flags = []
        if one is None or probes._float(one.get("fix_type")) != 8.0:
            flags.append("gnss1_fix_type_not_8")
        if probes._float(two.get("fix_type")) != 8.0:
            flags.append("gnss2_fix_type_not_8")
        if not probes._true(two.get("pos_valid")):
            flags.append("gnss2_pos_valid_false")
        if not association["a1_constructed"]:
            flags.append("a1_not_constructed_at_matched_gnss1_epoch")
        for receiver, row in (("gnss1", one or {}), ("gnss2", two)):
            flags.extend(receiver+"_"+name for name, invalid in probes._status_flags(row).items() if invalid)
        output.append({"relative_time_R1": association["relative_time_R1"],
                       "gnss2_header_time_R1": association["header_time_R1"],
                       "matched_gnss1_header_R1": header_relative,
                       "matched_gnss1_sys_time_R1": probes._stamp(one)-base_time if one is not None else None,
                       "gnss1_association_delta_seconds": association["gnss1_association_delta_seconds"],
                       "gnss1_original_fields": one, "gnss2_original_fields": two,
                       "a1_constructed": association["a1_constructed"],
                       "flagged": bool(flags), "trigger_flags": flags})
    return output


def load_sequence_window(seq):
    path = seq.probe_dir / "PROBE_REPORT.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    if report["dataset_id"] != seq.dataset_id or report["data_mode"] != seq.data_mode:
        raise RuntimeError("Sequence identity differs from its C-01b input report")
    if not report.get("probe_strace_pass"):
        raise RuntimeError("C-02 requires the completed successful C-01b strace audit")
    base = float(report["b_base_time"]["R1"])
    window = report["d_window_candidates"]["rule_B_prime"]
    return base, float(window["t_start"]), float(window["t_end"]), path


def execute(args, registry):
    original, independent = verify_locks(registry.clean_root)
    code_commit, dirty = git_code_state(registry.code_root)
    code_source_paths = ["scripts/paper_rebuild/clean5_define_occlusion_window.py",
                         "src/legsa_gins/paper_rebuild/clean5_sequence/probes.py",
                         "src/legsa_gins/paper_rebuild/providers.py",
                         "src/legsa_gins/input_generation/status_yaw_builder.py"]
    provenance = {"code_commit": code_commit, "code_worktree_dirty_at_run": dirty,
                  "config_hash": sha256_file(args.registry), "local_path_config_hash": sha256_file(args.paths_config),
                  "code_sources_sha256": {path: sha256_file(registry.code_root / path) for path in code_source_paths}}
    with probes.forbidden_path_guard(registry.raw_root, []):
        from legsa_gins.paper_rebuild import providers
    tolerance = float(inspect.signature(providers._shared_process_data_compat.generate_process_data_compat_inputs)
                      .parameters["dual_yaw_match_tolerance_seconds"].default)
    reports = {}
    with probes.forbidden_path_guard(registry.raw_root, status_paths(registry)):
        try:
            for dataset, seq in registry.sequences.items():
                base, start, end, report_path = load_sequence_window(seq)
                _, one = probes._csv(seq.fix_root / STATUS_NAMES[0])
                two_names, two = probes._csv(seq.fix_root / STATUS_NAMES[1])
                a1, a1_audit = providers.build_a1_dual_diff_yaw_rows(seq.fix_root / STATUS_NAMES[0],
                                                                 seq.fix_root / STATUS_NAMES[1], base_time=base)
                epochs = flag_epochs(one, two, two_names, a1, base, tolerance)
                contract = define_window(epochs, start, end)
                rows = original["rows"] if dataset == "BY2" else independent["rows"]
                source_hashes = {str((seq.fix_root / name).relative_to(registry.raw_root)):
                                 rows[str((seq.fix_root / name).relative_to(registry.raw_root))]["sha256"] for name in STATUS_NAMES}
                contract.update({"status": "PENDING_STRACE_AUDIT", "dataset_id": dataset,
                                 "stage_id": seq.stage_id, "data_mode": seq.data_mode,
                                 "synthetic_data_used": False, "semisynthetic_data_used": False,
                                 "trace_used_online": False, "trace_content_read": False,
                                 "solver_process_count": 0, "evaluator_process_count": 0,
                                 "provider_generation_count": 0, "base_time_R1": base,
                                 "defined_before_provider_generation": True,
                                 "evidence": "input_side_receiver_status_only",
                                 "fix_type_encoding": "8 = RTK fixed; rule uses only !=8",
                                 "reference_epoch": "GNSS2 sys_stamp; nearest GNSS1 header.stamp within the frozen tolerance",
                                 "flag_definition": "GNSS1 fix_type != 8 OR GNSS2 fix_type != 8 OR GNSS2 pos_valid false OR A1 not constructed/rel_valid/ant_valid/ant_state invalid",
                                 "association_tolerance_seconds": tolerance, "a1_input_audit": a1_audit,
                                 "window_source": str(report_path), "window_source_sha256": sha256_file(report_path),
                                 "raw_source_hashes": source_hashes, "original_lock_sha256": original["sha256"],
                                 "independent_lock_sha256": independent["sha256"], **provenance})
                reports[dataset] = contract
        finally:
            verify_locks(registry.clean_root)
    for dataset, report in reports.items():
        destination = output_dir(registry.sequences[dataset], registry.clean_root)
        write_json_atomic(destination / "OCCLUSION_WINDOW.json", report)
    return {dataset: {key: report[key] for key in ("main_window", "secondary_runs", "epoch_count", "flagged_epoch_count")}
            for dataset, report in reports.items()}


def audit_strace(path, registry):
    opened = evidence.parse_strace_openat_paths(path, cwd=registry.code_root)
    lines = [line for line in Path(path).read_text(encoding="utf-8").splitlines() if evidence.STRACE_OPENAT_RE.search(line)]
    if len(opened) != len(lines):
        raise RuntimeError("C-02 strace path/flag count mismatch")
    records = []
    for source, line in zip(opened, lines):
        if source != registry.raw_root and registry.raw_root not in source.parents:
            continue
        match = evidence.STRACE_OPENAT_RE.search(line)
        parsed = re.match(r",\s*([^,)]+)(?:,\s*[0-7]+)?\)\s*=\s*(-?\d+)", line[match.end():])
        if not parsed:
            raise RuntimeError("Unparseable C-02 raw openat flags")
        records.append({"path": str(source), "flags": parsed[1].strip(), "return_code": int(parsed[2])})
    counts = Counter(row["path"] for row in records)
    writes = [row for row in records if any(flag in row["flags"] for flag in ("O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND"))]
    forbidden = {"trace": sum(Path(row["path"]).name.startswith("trace_") and row["path"].endswith(".csv") for row in records),
                 "bag": sum(row["path"].endswith(".bag") for row in records),
                 "fpl": sum(row["path"].endswith(".fpl") for row in records)}
    failures = []
    if set(counts) != {str(path) for path in status_paths(registry)}:
        failures.append("Raw opened paths must equal the six registered GNSS status files")
    if writes:
        failures.append("Raw write-open detected")
    if any(forbidden.values()):
        failures.append("Trace/bag/fpl was opened")
    if any("O_RDONLY" not in row["flags"] or row["return_code"] < 0 for row in records):
        failures.append("Raw open must succeed with O_RDONLY")
    return {"pass": not failures, "failures": failures, "raw_forbidden_writes": len(writes),
            "forbidden_open_counts": forbidden, "raw_open_records": records,
            "per_file_open_count": dict(counts), "strace_sha256": sha256_file(path), "strace_path": str(path)}


def supervise(args, registry):
    verify_locks(registry.clean_root)
    destination = output_dir(registry.sequences["BY2O"], registry.clean_root)
    destination.mkdir(parents=True, exist_ok=True)
    log = destination / "C02_OCCLUSION_OPENAT.strace"
    if log.exists():
        raise RuntimeError("Refusing to overwrite the existing C-02 strace session")
    command = ["strace", "-f", "-s", "4096", "-yy", "-e", "trace=openat", "-o", str(log),
               sys.executable, "-B", str(Path(__file__).resolve()), "--paths-config", str(args.paths_config),
               "--registry", str(args.registry), "--_traced-worker"]
    process = subprocess.run(command, cwd=registry.code_root, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}, check=False)
    audited = audit_strace(log, registry)
    original, independent = verify_locks(registry.clean_root)
    passed = audited["pass"] and process.returncode == 0
    for dataset, seq in registry.sequences.items():
        output = output_dir(seq, registry.clean_root)
        payload = {**audited, "pass": passed, "strace_pass": audited["pass"], "worker_exit_code": process.returncode,
                   "dataset_id": dataset, "stage_id": seq.stage_id, "data_mode": seq.data_mode,
                   "synthetic_data_used": False, "semisynthetic_data_used": False,
                   "original_lock_sha256": original["sha256"], "original_lock_row_count": original["row_count"],
                   "independent_lock_sha256": independent["sha256"], "independent_lock_row_count": independent["row_count"]}
        write_json_atomic(output / "OCCLUSION_WINDOW_STRACE_AUDIT.json", payload)
        path = output / "OCCLUSION_WINDOW.json"
        if path.exists():
            report = json.loads(path.read_text(encoding="utf-8"))
            report.update(status="PASS_INPUT_DEFINED_OCCLUSION_WINDOW" if passed else "FAIL_STRACE_OR_EXECUTION",
                          strace_pass=audited["pass"], strace_failures=audited["failures"],
                          trace_opens=audited["forbidden_open_counts"]["trace"], bag_opens=audited["forbidden_open_counts"]["bag"],
                          fpl_opens=audited["forbidden_open_counts"]["fpl"], raw_forbidden_writes=audited["raw_forbidden_writes"])
            write_json_atomic(path, report)
    print(json.dumps({"pass": passed, "worker_exit_code": process.returncode,
                      "strace_pass": audited["pass"], "strace_failures": audited["failures"],
                      "forbidden_open_counts": audited["forbidden_open_counts"], "raw_forbidden_writes": audited["raw_forbidden_writes"],
                      "original_lock_row_count": original["row_count"], "original_lock_sha256": original["sha256"],
                      "independent_lock_row_count": independent["row_count"], "independent_lock_sha256": independent["sha256"]}, indent=2))
    return 0 if passed else 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paths-config", type=Path, required=True)
    parser.add_argument("--registry", type=Path, default=ROOT / "configs/paper_rebuild/clean5/CLEAN5_SEQUENCE_REGISTRY.yaml")
    parser.add_argument("--_traced-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    registry = load_registry(args.registry, args.paths_config)
    if args._traced_worker:
        print(json.dumps(execute(args, registry), ensure_ascii=False), flush=True)
        return 0
    return supervise(args, registry)


if __name__ == "__main__":
    sys.exit(main())
