"""C-04b explicit device exceptions; protected data writes always fail."""
from __future__ import annotations
import ast
import os
from pathlib import Path
import re

from ..evidence import STRACE_OPENAT_RE
from .generation_audit import WRITE_FLAGS, open_records


def audited_open_records(log, cwd):
    records = open_records(log, cwd)
    lines = [line for line in Path(log).read_text().splitlines() if STRACE_OPENAT_RE.search(line)]
    for row, line in zip(records, lines):
        match = STRACE_OPENAT_RE.search(line)
        value = ast.literal_eval(match[2])
        try:
            value = value.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        lexical = Path(value)
        if not lexical.is_absolute():
            fd = match[1].strip()
            parent = Path(cwd) if fd == "AT_FDCWD" else Path(re.search(r"<([^>]+)>", fd)[1])
            lexical = parent / lexical
        row["lexical_path"] = os.path.abspath(lexical)
        # Only a kernel fd annotation establishes a pipe; a filename that looks
        # like pipe:[123] is still an ordinary, confined filesystem path.
        row["anonymous_pipe"] = bool(re.search(r"=\s*\d+<pipe:\[\d+\]>", line))
    return records


def write_scope_audit(records, *, raw_root, allowed_write_roots, clean_root=None):
    raw_root = Path(raw_root)
    roots = [Path(path) for path in allowed_write_roots]
    def within(path, root):
        return path == root or root in path.parents
    writes, forbidden, devices, pipes, raw_writes, clean_outside = [], [], [], [], [], []
    for row in records:
        if not any(flag in row["flags"] for flag in WRITE_FLAGS):
            continue
        writes.append(row)
        path, lexical = Path(row["path"]), Path(row.get("lexical_path", row["path"]))
        if within(path, raw_root) or within(lexical, raw_root):
            raw_writes.append(row)
            forbidden.append(row)
            continue
        in_run = any(within(path, root) and within(lexical, root) for root in roots)
        if clean_root is not None and (within(path, Path(clean_root)) or within(lexical, Path(clean_root))) and not in_run:
            clean_outside.append(row)
            forbidden.append(row)
            continue
        if row.get("anonymous_pipe") is True:
            pipes.append(row)
        elif str(path) == "/dev/null" or re.fullmatch(r"/dev/pts/[^/]+", str(path)):
            devices.append(row)
        elif not in_run:
            forbidden.append(row)
    return {"pass": not forbidden, "write_open_count": len(writes),
        "write_outside_run_count": len(forbidden), "outside_run_write_open_count": len(forbidden),
        "outside_run_write_open_records": forbidden, "write_open_records": writes,
        "allowed_device_write_count": len(devices), "allowed_device_write_records": devices,
        "allowed_anonymous_pipe_write_count": len(pipes), "allowed_anonymous_pipe_write_records": pipes,
        "raw_write_open_count": len(raw_writes), "clean_root_outside_run_write_count": len(clean_outside),
        "write_scope_exceptions": ["/dev/null", "/dev/pts/*", "kernel-identified anonymous pipe"]}
