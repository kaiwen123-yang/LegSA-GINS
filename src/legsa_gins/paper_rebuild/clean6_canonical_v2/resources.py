"""Resource measurement and bounded concurrency, without scientific inputs."""
from __future__ import annotations

import math
import os
from pathlib import Path

RESOURCE_FORMAT = ("P09C_RESOURCE_V1\nwall_seconds=%e\nuser_cpu_seconds=%U\n"
                   "system_cpu_seconds=%S\nmax_rss_kib=%M\nexit_code=%x")


def resource_command(command, path):
    """Wrap an argv, preserving each token; no shell, output overwrite or run.

    Place this wrapper immediately before the native command, inside strace,
    to measure that command's wait4 high-water RSS rather than the tracer.
    """
    path = Path(path)
    if not command or any(not isinstance(token, (str, os.PathLike)) for token in command):
        raise ValueError("A nonempty explicit argv is required")
    if not path.is_absolute() or not path.parent.is_dir() or path.exists() or path.is_symlink():
        raise ValueError("Resource output must be a fresh absolute file in the run directory")
    if not Path("/usr/bin/time").is_file():
        raise FileNotFoundError("GNU /usr/bin/time is required for native peak RSS")
    return ["/usr/bin/time", "--quiet", "--format", RESOURCE_FORMAT,
            "--output", str(path), "--", *(str(token) for token in command)]


def read_process_resources(path):
    """Parse one completed GNU-time record, including nonzero child exits.

    Missing, truncated and malformed records raise; callers preserve an
    UNAVAILABLE measurement rather than substituting a zero RSS or duration.
    """
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Resource record cannot be a symlink")
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "P09C_RESOURCE_V1":
        raise ValueError("Missing GNU-time resource record header")
    fields = {}
    for line in lines[1:]:
        if "=" not in line:
            raise ValueError("Malformed GNU-time resource field")
        key, value = line.split("=", 1)
        if key in fields:
            raise ValueError("Duplicate GNU-time resource field")
        fields[key] = value
    expected = {"wall_seconds", "user_cpu_seconds", "system_cpu_seconds", "max_rss_kib", "exit_code"}
    if set(fields) != expected:
        raise ValueError("Incomplete GNU-time resource record")
    try:
        seconds = {key: float(fields[key]) for key in expected if key.endswith("seconds")}
        rss_kib, exit_code = int(fields["max_rss_kib"]), int(fields["exit_code"])
    except ValueError as error:
        raise ValueError("Nonnumeric GNU-time resource field") from error
    if any(not math.isfinite(value) or value < 0 for value in seconds.values()) or rss_kib <= 0 or not 0 <= exit_code <= 255:
        raise ValueError("Invalid GNU-time time/RSS/exit measurement")
    return {"status": "AVAILABLE", "peak_rss_bytes": rss_kib*1024, **seconds,
            "exit_code": exit_code, "source": str(path),
            "measurement": "GNU time wait4 ru_maxrss; KiB converted to bytes; measured command maximum, not sum of concurrent RSS",
            "exit_code_source": "GNU time %x; outer process return code remains authoritative for signals/timeouts"}


def solver_workers(nproc=None):
    """Reserve two visible CPUs and cap the authorized solver pool at 22."""
    nproc = len(os.sched_getaffinity(0)) if nproc is None else nproc
    if isinstance(nproc, bool) or not isinstance(nproc, int) or nproc < 3:
        raise ValueError("At least three visible CPUs are required to reserve two")
    return min(nproc-2, 22)


def choose_evaluator_workers(available_memory_bytes, solver_peak_bytes, evaluator_rss_peak_bytes, nproc):
    """Use measured probe peak and solver reservation under a 75% budget.

    The caller must first complete the six registered serial probes. Each
    evaluator slot reserves ceil(1.25 * measured probe maximum RSS). The
    measured solver phase RSS remains reserved even for nonoverlapping phases.
    """
    for name, value in (("available_memory_bytes", available_memory_bytes), ("solver_peak_bytes", solver_peak_bytes),
                        ("evaluator_rss_peak_bytes", evaluator_rss_peak_bytes)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(name+" must be a positive measured byte count")
    budget = available_memory_bytes*3//4
    per_worker = (evaluator_rss_peak_bytes*5+3)//4
    memory_slots = (budget-solver_peak_bytes)//per_worker
    count = min(solver_workers(nproc), memory_slots)
    if count < 1:
        raise ValueError("No evaluator slot fits 1.25x measured RSS plus solver peak within 75% available memory")
    return count


def process_tree_rss(root_pid=None):
    """Sample controller plus current descendants from /proc, including threads' children.

    RSS is summed over process leaders, not threads. Shared resident mappings
    are counted once per process; this is a conservative resident-memory sum,
    not proportional-set size. The separate GNU-time measurement catches a
    native process high-water mark between monitor samples.
    """
    root_pid = os.getpid() if root_pid is None else root_pid
    if isinstance(root_pid, bool) or not isinstance(root_pid, int) or root_pid <= 0:
        raise ValueError("Invalid process-tree root PID")
    processes, children = {}, {}
    page_size = os.sysconf("SC_PAGE_SIZE")
    for entry in Path("/proc").iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            raw = (entry / "stat").read_text()
            fields = raw[raw.rindex(")")+2:].split()
            pid, parent, rss = int(entry.name), int(fields[1]), int(fields[21])*page_size
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        except (ValueError, IndexError) as error:
            raise ValueError("Malformed /proc process resource record") from error
        processes[pid] = max(0, rss)
        children.setdefault(parent, []).append(pid)
    if root_pid not in processes:
        raise ProcessLookupError("Owned controller PID no longer present")
    pending, owned = [root_pid], set()
    while pending:
        pid = pending.pop()
        if pid in owned:
            continue
        owned.add(pid)
        pending.extend(children.get(pid, ()))
    return {"owned_rss_bytes": sum(processes[pid] for pid in owned),
            "owned_process_count": len(owned), "owned_pids": sorted(owned),
            "root_pid": root_pid, "scope": "root controller and current descendants; summed process RSS; shared mappings counted per process"}
