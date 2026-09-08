"""Explicit C-05 header-only exception: never prefetch a data-line byte."""
from __future__ import annotations
import ast
import csv
import hashlib
import json
import os
from pathlib import Path
import re

from ..evidence import STRACE_OPENAT_RE
from .io_audit import audited_open_records, write_scope_audit
from .evaluation_process import write_json


def read_header(path):
    data = bytearray()
    fd = os.open(path, os.O_RDONLY)
    try:
        while len(data) < 65536:
            char = os.read(fd, 1)
            if not char:
                raise RuntimeError("Trace header lacks terminal newline")
            data.extend(char)
            if char == b"\n":
                break
        else:
            raise RuntimeError("Trace header exceeds fixed 64 KiB bound")
    finally:
        os.close(fd)
    text = bytes(data).decode("utf-8-sig")
    columns = next(csv.reader([text]))
    if len(columns) != len(set(columns)):
        raise RuntimeError("Duplicate trace header columns")
    return {"path": str(path), "read_role": "header_only_read", "data_line_bytes_read": 0,
            "bytes_read": len(data), "header_bytes_hex": data.hex(), "header_text": text,
            "columns": columns, "header_sha256": hashlib.sha256(data).hexdigest(), "pid": os.getpid()}


def select_columns(columns):
    choices = {"time": ["aligned_time", "time", "stamp", "timestamp"],
               "lat": ["lat", "latitude", "pos_lat"], "lon": ["lon", "longitude", "pos_lon"],
               "height": ["height", "alt", "altitude", "pos_height"],
               "yaw": ["yaw"], "pitch": ["pitch"], "roll": ["roll"]}
    result = {}
    for key, names in choices.items():
        result[key] = next((column for name in names for column in columns
                            if name.lower() == column.lower() or name.lower() in column.lower()), None)
    return result


def audit_headers(log, rows, *, cwd, raw_root, clean_root, output_root):
    records = audited_open_records(log, cwd)
    raw = [row for row in records if Path(raw_root) in Path(row["path"]).parents]
    expected = {row["path"]: row for row in rows}
    failures = []
    if len(raw) != 3 or {row["path"] for row in raw} != set(expected):
        failures.append("header session must open exactly the three registered traces")
    iterator = iter(records)
    active, received, opens = {}, {path: bytearray() for path in expected}, {path: 0 for path in expected}
    for line in Path(log).read_text().splitlines():
        prefix = re.match(r"(?:\[pid\s+)?(\d+)", line)
        pid = int(prefix[1]) if prefix else None
        if STRACE_OPENAT_RE.search(line):
            row = next(iterator)
            if row["path"] in expected:
                if row["return_code"] < 0 or "O_RDONLY" not in row["flags"]:
                    failures.append("header open must succeed read-only")
                active[(pid, row["return_code"])] = row["path"]
                opens[row["path"]] += 1
        read = re.search(r'\bread\((\d+)(?:<[^>]*>)?, ("(?:[^"\\]|\\.)*"), (\d+)\)\s*=\s*(-?\d+)', line)
        if read and (pid, int(read[1])) in active:
            path = active[(pid, int(read[1]))]
            if int(read[3]) != 1 or int(read[4]) != 1:
                failures.append("header reader used a non-single-byte read")
            value = ast.literal_eval(read[2]).encode("latin-1")
            received[path].extend(value)
        close = re.search(r"\bclose\((\d+)(?:<[^>]*>)?\)", line)
        if close:
            active.pop((pid, int(close[1])), None)
    for path, row in expected.items():
        want = bytes.fromhex(row["header_bytes_hex"])
        if opens[path] != 1 or received[path] != want or not want.endswith(b"\n") or b"\n" in want[:-1]:
            failures.append("read syscalls do not equal exactly one header line: " + path)
    scope = write_scope_audit(records, raw_root=raw_root, clean_root=clean_root, allowed_write_roots=[output_root])
    if not scope["pass"]:
        failures.append("header write scope violation")
    if any(row["path"].endswith((".bag", ".fpl")) for row in records):
        failures.append("header session opened bag/fpl")
    return {"passed": not failures, "failures": failures, "trace_open_count": len(raw),
            "bag_open_count": sum(row["path"].endswith(".bag") for row in records),
            "fpl_open_count": sum(row["path"].endswith(".fpl") for row in records),
            "data_line_bytes_read": 0 if not failures else None, "write_scope": scope,
            "strace_sha256": hashlib.sha256(Path(log).read_bytes()).hexdigest()}


def header_child(registry, output_root):
    rows = []
    for dataset in ("BY2", "BY2H", "BY2O"):
        row = read_header(registry.sequences[dataset].trace_path)
        row["dataset_id"] = dataset
        row["selected_columns_by_archived_source"] = select_columns(row["columns"])
        rows.append(row)
    write_json(Path(output_root) / "HEADER_ONLY_READS.json", rows)
