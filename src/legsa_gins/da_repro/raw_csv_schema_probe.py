"""Probe BY2 raw CSV schemas for UBX carrier-provider readiness."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import iter_ubx_frames, parse_bytes_cell


def probe_raw_csv(path: str | Path, *, max_rows: int | None = None) -> dict[str, Any]:
    source = Path(path)
    report: dict[str, Any] = {
        "path": str(source),
        "exists": source.exists(),
        "row_count": 0,
        "columns": [],
        "message_counts": {},
        "has_data_column": False,
        "has_ubx_bytes": False,
        "ubx_frame_count": 0,
        "rawx_frame_count": 0,
        "sfrbx_frame_count": 0,
        "first_time": None,
        "last_time": None,
        "blocker_reasons": [],
    }
    if not source.exists():
        report["blocker_reasons"].append("raw_csv_missing")
        return report
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        counts: Counter[str] = Counter()
        report["columns"] = columns
        report["has_data_column"] = "data" in columns
        for index, row in enumerate(reader):
            if max_rows is not None and index >= max_rows:
                break
            report["row_count"] += 1
            name = row.get("name") or row.get("message") or ""
            if name:
                counts[name] += 1
            try:
                time_value = float(row.get("Time") or row.get("time") or row.get("timestamp") or "nan")
            except ValueError:
                time_value = float("nan")
            if time_value == time_value:
                report["first_time"] = time_value if report["first_time"] is None else min(float(report["first_time"]), time_value)
                report["last_time"] = time_value if report["last_time"] is None else max(float(report["last_time"]), time_value)
            if "data" not in columns:
                continue
            frames = list(iter_ubx_frames(parse_bytes_cell(row.get("data", ""))))
            for frame in frames:
                report["ubx_frame_count"] += 1
                report["has_ubx_bytes"] = True
                msg_class, msg_id = frame[2], frame[3]
                if (msg_class, msg_id) == (0x02, 0x15):
                    report["rawx_frame_count"] += 1
                if (msg_class, msg_id) == (0x02, 0x13):
                    report["sfrbx_frame_count"] += 1
    report["message_counts"] = dict(sorted(counts.items()))
    if not report["has_data_column"]:
        report["blocker_reasons"].append("missing_data_column")
    if not report["has_ubx_bytes"]:
        report["blocker_reasons"].append("no_ubx_bytes_detected")
    return report


def probe_raw_pair(gnss1_raw: str | Path, gnss2_raw: str | Path, *, max_rows: int | None = None) -> dict[str, Any]:
    files = {
        "gnss1_raw": probe_raw_csv(gnss1_raw, max_rows=max_rows),
        "gnss2_raw": probe_raw_csv(gnss2_raw, max_rows=max_rows),
    }
    return {
        "files": files,
        "both_exist": all(item["exists"] for item in files.values()),
        "both_have_ubx_bytes": all(item["has_ubx_bytes"] for item in files.values()),
        "rawx_frame_count": sum(int(item["rawx_frame_count"]) for item in files.values()),
        "sfrbx_frame_count": sum(int(item["sfrbx_frame_count"]) for item in files.values()),
        "blocker_reasons": sorted({reason for item in files.values() for reason in item["blocker_reasons"]}),
    }
