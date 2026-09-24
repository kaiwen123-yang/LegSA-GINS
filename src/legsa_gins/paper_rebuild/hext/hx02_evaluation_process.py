"""HX-02 launcher for the registered heading, relative-pose and coverage evaluator children.

Adapted from hext/external_evaluation._evaluate_process: the child runs as
``python -m <module> --spec SPEC`` under ``strace -f -yy -e trace=openat,execve``;
the parent never opens the reference trace and afterwards asserts, from the
openat log, that the reference was opened exactly once, successfully and
read-only (or not at all for the coverage child), that no other raw file and no
bag/fpl file was opened, that the child wrote only inside its output directory,
and that no other program was executed.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Mapping

from ..clean5_sequence.io_audit import audited_open_records, write_scope_audit
from ..evidence import STRACE_OPENAT_RE
from ..manifest import sha256_file
from ..subprocess_guard import run_process_group

REGISTERED_CHILDREN = {
    "HEADING": "legsa_gins.paper_rebuild.hext.hx02_heading_evaluation",
    "RELATIVE_POSE": "legsa_gins.paper_rebuild.hext.hx02_relative_pose_evaluation",
    "COVERAGE": "legsa_gins.paper_rebuild.hext.hx02_coverage_evaluation",
}
EXECVE_RE = re.compile(r'execve\("([^"]+)"')


class EvaluationProcessError(RuntimeError):
    """A registered evaluator child failed its run or its access audit."""


def child_environment(code_root: Path, outdir: Path) -> dict[str, str]:
    return {
        "PYTHONDONTWRITEBYTECODE": "1", "GIT_OPTIONAL_LOCKS": "0",
        "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
        "NUMEXPR_NUM_THREADS": "1", "MPLBACKEND": "Agg",
        "MPLCONFIGDIR": str(outdir / ".matplotlib"), "XDG_CACHE_HOME": str(outdir / ".cache"),
        "PYTHONPATH": str(Path(code_root) / "src"),
    }


def run_child(kind: str, spec: Mapping[str, Any], *, workdir: Path, code_root: Path, raw_root: Path,
              clean_root: Path, trace: Path | None, timeout_seconds: float = 3600.0) -> dict[str, Any]:
    """Run one registered child; ``trace=None`` means the reference must not be opened at all."""
    if kind not in REGISTERED_CHILDREN:
        raise EvaluationProcessError(f"unregistered evaluator child {kind}")
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=False)
    outdir = workdir / "OUTPUT"
    spec = {**spec, "outdir": str(outdir)}
    spec_path = workdir / "SPEC.json"
    with spec_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(spec, indent=2, sort_keys=True) + "\n")
    environment = child_environment(code_root, outdir)
    log = workdir / "EVALUATOR_OPENAT.strace"
    argv = [sys.executable, "-m", REGISTERED_CHILDREN[kind], "--spec", str(spec_path)]
    command = ["env", *(f"{key}={value}" for key, value in environment.items()),
               "strace", "-f", "-yy", "-s", "4096", "-e", "trace=openat,execve", "-o", str(log), *argv]
    started = time.monotonic()
    completed = run_process_group(command, cwd=code_root, timeout_seconds=timeout_seconds,
                                  timeout_message=f"HX-02 {kind} evaluator timeout; no retry",
                                  launch_failure_message=f"HX-02 {kind} evaluator launch failed")
    runtime = time.monotonic() - started
    (workdir / "evaluator_stdout.log").write_text(completed.stdout, encoding="utf-8")
    (workdir / "evaluator_stderr.log").write_text(completed.stderr, encoding="utf-8")
    records = audited_open_records(log, code_root)
    lines = [line for line in log.read_text().splitlines() if STRACE_OPENAT_RE.search(line)]
    for record, line in zip(records, lines):
        match = re.match(r"(?:\[pid\s+)?(\d+)", line)
        record["pid"] = int(match[1]) if match else None
    trace_records = [row for row in records if trace is not None and Path(row["path"]) == Path(trace)]
    named_trace = [row for row in records if "trace_vrtk" in Path(row["path"]).name]
    raw_records = [row for row in records if Path(raw_root) in Path(row["path"]).parents]
    scope = write_scope_audit(records, raw_root=raw_root, clean_root=clean_root, allowed_write_roots=[outdir])
    executed = [match[1] for match in (EXECVE_RE.search(line) for line in log.read_text().splitlines()) if match]
    failures = []
    if completed.returncode:
        failures.append(f"evaluator_returncode={completed.returncode}")
    if trace is None:
        if named_trace or trace_records:
            failures.append("reference opened by a child registered as reference-free")
    elif (len(trace_records) != 1 or any(row["return_code"] < 0 or "O_RDONLY" not in row["flags"]
                                          for row in trace_records)
          or len(named_trace) != len(trace_records)):
        failures.append("reference must be opened exactly once, successfully and read-only")
    if any(trace is None or Path(row["path"]) != Path(trace) for row in raw_records):
        failures.append("unexpected raw input opened")
    if any(row["path"].endswith((".bag", ".fpl")) for row in records):
        failures.append("bag/fpl open")
    if not scope["pass"]:
        failures.append("write scope violation")
    programs = sorted(set(executed))
    if any(Path(program).name not in {"env", "strace"} and not Path(program).name.startswith("python")
           for program in programs):
        failures.append(f"unexpected program executed: {programs}")
    audit = {
        "kind": kind, "module": REGISTERED_CHILDREN[kind], "passed": not failures, "failures": failures,
        "trace_open_count": len(trace_records), "trace_open_records": trace_records,
        "raw_open_count": len(raw_records), "write_scope": scope, "execve_programs": programs,
        "strace_sha256": sha256_file(log), "exit_code": completed.returncode, "runtime_seconds": runtime,
        "argv": argv, "environment": environment, "spec_sha256": sha256_file(spec_path),
        "trace_read_role": "registered_evaluator_child_only" if trace is not None else "reference_free_child",
    }
    with (workdir / "EVALUATOR_STRACE_AUDIT.json").open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(audit, indent=2, sort_keys=True, default=str) + "\n")
    if failures:
        raise EvaluationProcessError("; ".join(failures) + "; stderr tail: " + completed.stderr[-3000:])
    return {"audit": audit, "outdir": str(outdir), "runtime_seconds": runtime}

