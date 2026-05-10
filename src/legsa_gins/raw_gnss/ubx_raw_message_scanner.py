"""Scan BY2 raw GNSS CSV message streams for N5A.

中文说明：本扫描器只区分 UBX-NAV-PVT、UBX-RXM-RAWX、UBX-RXM-SFRBX 和 RTCM
消息证据；NAV-PVT velocity 明确不是 raw Doppler，不能作为新增因子来源。
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


RAW_FILE_NAMES = ("gnss1-raw.csv", "gnss2-raw.csv", "corr-raw.csv")


def classify_payload_format(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return "missing"
    if text.startswith("b'") or text.startswith('b"'):
        return "python_bytes_literal"
    if text.startswith("[") and text.endswith("]"):
        return "byte_list"
    if all(ch in "0123456789abcdefABCDEF xX,;:-" for ch in text[:120]):
        return "hex_or_numeric_text"
    return "unknown"


def _row_message(row: dict[str, str]) -> str:
    name = row.get("name") or row.get("Name") or row.get("message") or ""
    info = row.get("info") or row.get("Info") or ""
    protocol = row.get("protocol") or row.get("Protocol") or ""
    joined = f"{name} {protocol} {info}".upper()
    if "UBX-RXM-RAWX" in joined or "RXM-RAWX" in joined:
        return "UBX-RXM-RAWX"
    if "UBX-RXM-SFRBX" in joined or "RXM-SFRBX" in joined:
        return "UBX-RXM-SFRBX"
    if "UBX-NAV-PVT" in joined or "NAV-PVT" in joined:
        return "UBX-NAV-PVT"
    if "RTCM" in joined:
        return name if "RTCM" in name.upper() else "RTCM"
    return name or "UNKNOWN"


def scan_raw_csv(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    counts: Counter[str] = Counter()
    data_column_exists = False
    payload_formats: Counter[str] = Counter()
    rawx_rows = 0
    sfrbx_rows = 0
    pvt_rows = 0
    rtcm_rows = 0
    total = 0
    samples: dict[str, list[dict[str, str]]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        data_column_exists = "data" in fieldnames
        for row in reader:
            msg = _row_message(row)
            counts[msg] += 1
            if data_column_exists:
                payload_formats[classify_payload_format(row.get("data", ""))] += 1
            if msg == "UBX-RXM-RAWX":
                rawx_rows += 1
            if msg == "UBX-RXM-SFRBX":
                sfrbx_rows += 1
            if msg == "UBX-NAV-PVT":
                pvt_rows += 1
            if "RTCM" in msg.upper():
                rtcm_rows += 1
            if len(samples.setdefault(msg, [])) < 2:
                samples[msg].append(
                    {
                        "time": row.get("Time", row.get("time", "")),
                        "name": row.get("name", ""),
                        "info": (row.get("info", "") or "")[:160],
                    }
                )
            total += 1
    return {
        "path": str(path),
        "row_count": total,
        "message_counts": dict(sorted(counts.items())),
        "data_column_exists": data_column_exists,
        "payload_format_counts": dict(sorted(payload_formats.items())),
        "payload_format": payload_formats.most_common(1)[0][0] if payload_formats else "missing",
        "rawx_row_count": rawx_rows,
        "sfrbx_row_count": sfrbx_rows,
        "nav_pvt_row_count": pvt_rows,
        "rtcm_row_count": rtcm_rows,
        "pvt_velocity_available": pvt_rows > 0,
        "pvt_velocity_not_raw_doppler": True,
        "samples": samples,
    }


def scan_fix_root(fix_root: str | Path) -> dict[str, Any]:
    root = Path(fix_root)
    by_file: dict[str, Any] = {}
    for file_name in RAW_FILE_NAMES:
        path = root / file_name
        if path.exists():
            by_file[file_name] = scan_raw_csv(path)
        else:
            by_file[file_name] = {"path": str(path), "missing": True}
    rawx_count = sum(item.get("rawx_row_count", 0) for item in by_file.values())
    sfrbx_count = sum(item.get("sfrbx_row_count", 0) for item in by_file.values())
    pvt_count = sum(item.get("nav_pvt_row_count", 0) for item in by_file.values())
    rtcm_count = sum(item.get("rtcm_row_count", 0) for item in by_file.values())
    return {
        "message_counts_by_file": {key: value.get("message_counts", {}) for key, value in by_file.items()},
        "files": by_file,
        "nav_pvt_found": pvt_count > 0,
        "rawx_found": rawx_count > 0,
        "sfrbx_found": sfrbx_count > 0,
        "rtcm_found": rtcm_count > 0,
        "data_column_exists": any(value.get("data_column_exists", False) for value in by_file.values()),
        "payload_format": "python_bytes_literal"
        if any(value.get("payload_format") == "python_bytes_literal" for value in by_file.values())
        else "mixed_or_missing",
        "rawx_row_count": rawx_count,
        "sfrbx_row_count": sfrbx_count,
        "pvt_velocity_available": pvt_count > 0,
        "pvt_velocity_not_raw_doppler": True,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
    }


def write_report(report: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)
    write_report(scan_fix_root(args.fix_root), args.output_json)
    print(f"Wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
