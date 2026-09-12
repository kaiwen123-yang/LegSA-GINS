"""Exact archived evaluator command, single-reference-open and write audits."""
from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

from ..manifest import sha256_file
from ..subprocess_guard import run_process_group
from ..evidence import STRACE_OPENAT_RE
from .io_audit import audited_open_records, write_scope_audit

EVALUATOR_SHA256 = "aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da"


def write_json(path, payload):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def evaluate(*, evaluator, trace, nav, std, outdir, base_time, window,
             trace_sha256, code_root, raw_root, clean_root, instrument=True,
             consistency_policy=None, measure_resources=False):
    if measure_resources and consistency_policy != "canonical_v2_wgs84_full_support":
        raise ValueError("Process resource measurement is only enabled for the canonical v2 policy")
    evaluator, trace, nav, std, outdir, code_root = map(Path, (evaluator, trace, nav, std, outdir, code_root))
    if evaluator.is_symlink() or sha256_file(evaluator) != EVALUATOR_SHA256:
        raise RuntimeError("Archived evaluator identity mismatch")
    if any(path.is_symlink() or not path.is_file() for path in (trace, nav, std)):
        raise RuntimeError("Evaluator input missing or symlink")
    outdir.mkdir(parents=True, exist_ok=False)
    config = {"evaluator": str(evaluator), "evaluator_sha256": EVALUATOR_SHA256,
              "trace": str(trace), "trace_sha256": trace_sha256,
              "window": list(window), "outdir": str(outdir)}
    if consistency_policy is not None:
        if consistency_policy != "canonical_v2_wgs84_full_support":
            raise ValueError("Unknown evaluator consistency policy")
        config["consistency_policy"] = consistency_policy
        (outdir / ".tmp").mkdir()
    config_path = outdir / "CAPTURE_CONFIG.json"
    write_json(config_path, config)
    environment = {"PYTHONDONTWRITEBYTECODE": "1", "GIT_OPTIONAL_LOCKS": "0",
                   "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                   "NUMEXPR_NUM_THREADS": "1", "MPLCONFIGDIR": str(outdir / ".matplotlib"),
                   "XDG_CACHE_HOME": str(outdir / ".cache"), "MPLBACKEND": "Agg"}
    if consistency_policy is not None:
        environment.update(TMPDIR=str(outdir / ".tmp"), TMP=str(outdir / ".tmp"),
                           TEMP=str(outdir / ".tmp"), VECLIB_MAXIMUM_THREADS="1",
                           BLIS_NUM_THREADS="1", NUMEXPR_MAX_THREADS="1")
    if instrument:
        environment["PYTHONPATH"] = os.pathsep.join((str(code_root / "scripts/paper_rebuild/clean5_evaluator_observer"), str(code_root / "src")))
        environment["CLEAN5_EVALUATOR_CAPTURE_CONFIG"] = str(config_path)
    else:
        environment["PYTHONPATH"] = str(code_root / "src")
        environment["CLEAN5_EVALUATOR_CAPTURE_CONFIG"] = ""
    # Identical evaluator argv to canonical541._run_exact_evaluator, with only
    # the sequence base_time supplied explicitly instead of its BY2 constant.
    argv = [sys.executable, str(evaluator), "--trace", str(trace), "--nav", str(nav),
            "--std", str(std), "--outdir", str(outdir), "--base_time", str(base_time),
            "--yaw_truth_mode", "enu"]
    log = outdir / "EVALUATOR_OPENAT.strace"
    launch_argv = argv
    resource_measurement = None
    if measure_resources:
        from ..clean6_canonical_v2.resources import resource_command, read_process_resources
        resource_path = outdir / "EVALUATOR_PROCESS_RESOURCES.txt"
        launch_argv = resource_command(argv, resource_path)
    command = ["env", *(f"{key}={value}" for key, value in environment.items()),
               "strace", "-f", "-yy", "-s", "4096", "-e", "trace=openat,execve", "-o", str(log), *launch_argv]
    started = time.monotonic()
    try:
        completed = run_process_group(command, cwd=code_root, timeout_seconds=1800,
            timeout_message="CLEAN5 evaluator timeout; no retry", launch_failure_message="CLEAN5 evaluator launch failed")
    finally:
        runtime = time.monotonic() - started
        if measure_resources:
            try:
                resource_measurement = read_process_resources(resource_path)
            except (OSError, ValueError) as error:
                resource_measurement = {"status": "UNAVAILABLE", "peak_rss_bytes": None,
                    "wall_seconds": None, "user_cpu_seconds": None, "system_cpu_seconds": None,
                    "exit_code": None, "source": str(resource_path),
                    "failure_type": type(error).__name__, "failure_message": str(error)}
            resource_measurement["evaluation_runtime_seconds"] = runtime
            resource_measurement["runtime_measurement"] = "monotonic wall time enclosing the guarded process group, including launch/termination"
            write_json(outdir / "EVALUATOR_RESOURCE_MEASUREMENT.json", resource_measurement)
    (outdir / "evaluator_stdout.log").write_text(completed.stdout, encoding="utf-8")
    (outdir / "evaluator_stderr.log").write_text(completed.stderr, encoding="utf-8")
    records = audited_open_records(log, code_root)
    lines = [line for line in log.read_text().splitlines() if STRACE_OPENAT_RE.search(line)]
    for record, line in zip(records, lines):
        match = re.match(r"(?:\[pid\s+)?(\d+)", line)
        if not match:
            raise RuntimeError("strace open lacks process identity")
        record["pid"] = int(match[1])
    trace_records = [row for row in records if Path(row["path"]) == trace]
    raw_records = [row for row in records if Path(raw_root) in Path(row["path"]).parents]
    scope = write_scope_audit(records, raw_root=raw_root, clean_root=clean_root, allowed_write_roots=[outdir])
    capture = json.loads((outdir / "EVALUATOR_CAPTURE.json").read_text()) if instrument and (outdir / "EVALUATOR_CAPTURE.json").is_file() else None
    bad = []
    if measure_resources and resource_measurement["status"] != "AVAILABLE":
        bad.append("evaluator peak RSS measurement unavailable")
    if completed.returncode:
        bad.append(f"evaluator_returncode={completed.returncode}")
    if len(trace_records) != 1 or any(row["return_code"] < 0 or "O_RDONLY" not in row["flags"] for row in trace_records):
        bad.append("reference must be opened exactly once, successfully and read-only")
    if any(Path(row["path"]) != trace for row in raw_records):
        bad.append("unexpected raw input opened")
    bag = sum(row["path"].endswith(".bag") for row in records)
    fpl = sum(row["path"].endswith(".fpl") for row in records)
    if bag or fpl:
        bad.append("bag/fpl open")
    if not scope["pass"]:
        bad.append("write scope violation")
    if instrument and (not isinstance(capture, dict) or capture.get("trace_sha256") != trace_sha256
                       or capture.get("trace_handle_hash_count") != 1
                       or not isinstance(capture.get("selected_columns"), dict)
                       or not isinstance(capture.get("consistency"), dict)
                       or any(row["pid"] != capture.get("pid") for row in trace_records)):
        bad.append("trace hash/process observation mismatch")
    audit = {"passed": not bad, "failures": bad, "trace_open_count": len(trace_records),
             "trace_open_records": trace_records, "bag_open_count": bag, "fpl_open_count": fpl,
             "raw_open_count": len(raw_records), "open_count": len(records), "write_scope": scope,
             "strace_sha256": sha256_file(log), "exit_code": completed.returncode,
             "runtime_seconds": runtime, "evaluator_argv": argv, "environment": environment,
             "instrumented": instrument, "trace_read_role": "archived_evaluator_child_only",
             "synthetic_data_used": Path(raw_root) not in trace.parents}
    if measure_resources:
        audit["process_resources"] = resource_measurement
    write_json(outdir / "EVALUATOR_STRACE_AUDIT.json", audit)
    if bad:
        raise RuntimeError("; ".join(bad) + "; stderr tail: " + completed.stderr[-2000:])
    for name in ("summary.json", "error_series.csv"):
        if not (outdir / name).is_file():
            raise RuntimeError("Evaluator missing " + name)
    with (outdir / "error_series.csv").open("rb") as source, gzip.open(outdir / "error_series.csv.gz", "wb", compresslevel=6) as target:
        shutil.copyfileobj(source, target)
    result = {"audit": audit, "capture": capture, "runtime_seconds": runtime,
              "summary": json.loads((outdir / "summary.json").read_text()), "outdir": str(outdir)}
    if measure_resources:
        result["process_resources"] = resource_measurement
    return result
