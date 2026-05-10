"""Rebuild UBX byte streams from raw CSV data cells.

中文说明：仅当 CSV data 列包含完整 UBX frame bytes 时重建 runtime-only .ubx；
重建结果不提交 Git，也不代表 raw Doppler 已经进入滤波器。
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable


def parse_bytes_cell(value: str) -> bytes:
    text = (value or "").strip()
    if not text:
        return b""
    if text.startswith("b'") or text.startswith('b"'):
        parsed = ast.literal_eval(text)
        if isinstance(parsed, bytes):
            return parsed
    if text.startswith("[") and text.endswith("]"):
        parsed = ast.literal_eval(text)
        if isinstance(parsed, (list, tuple)):
            return bytes(int(x) & 0xFF for x in parsed)
    matches = re.findall(r"0x[0-9a-fA-F]+|[0-9a-fA-F]{2}", text)
    if matches:
        return bytes(int(item, 16) for item in matches)
    return b""


def ubx_checksum(payload: bytes) -> tuple[int, int]:
    ck_a = 0
    ck_b = 0
    for byte in payload:
        ck_a = (ck_a + byte) & 0xFF
        ck_b = (ck_b + ck_a) & 0xFF
    return ck_a, ck_b


def is_valid_ubx_frame(frame: bytes) -> bool:
    if len(frame) < 8 or frame[:2] != b"\xb5\x62":
        return False
    length = int.from_bytes(frame[4:6], "little")
    if len(frame) != length + 8:
        return False
    return ubx_checksum(frame[2:-2]) == (frame[-2], frame[-1])


def iter_ubx_frames(blob: bytes) -> Iterable[bytes]:
    index = 0
    while index + 8 <= len(blob):
        start = blob.find(b"\xb5\x62", index)
        if start < 0 or start + 8 > len(blob):
            return
        length = int.from_bytes(blob[start + 4 : start + 6], "little")
        end = start + length + 8
        if end > len(blob):
            return
        frame = blob[start:end]
        if is_valid_ubx_frame(frame):
            yield frame
        index = max(end, start + 2)


def rebuild_csv_to_ubx(input_csv: str | Path, output_ubx: str | Path) -> dict[str, Any]:
    input_csv = Path(input_csv)
    output_ubx = Path(output_ubx)
    output_ubx.parent.mkdir(parents=True, exist_ok=True)
    frame_count = 0
    rawx_frame_count = 0
    sfrbx_frame_count = 0
    invalid_frame_count = 0
    with input_csv.open("r", encoding="utf-8-sig", newline="") as handle, output_ubx.open("wb") as output:
        reader = csv.DictReader(handle)
        if "data" not in (reader.fieldnames or []):
            return {
                "input_csv": str(input_csv),
                "rebuilt_ubx_available": False,
                "frame_count": 0,
                "rawx_frame_count": 0,
                "sfrbx_frame_count": 0,
                "checksum_validation_status": "missing_data_column",
                "blocker_reasons": ["missing_data_column"],
            }
        for row in reader:
            data = parse_bytes_cell(row.get("data", ""))
            frames = list(iter_ubx_frames(data))
            if not frames and data.startswith(b"\xb5\x62"):
                invalid_frame_count += 1
            for frame in frames:
                output.write(frame)
                frame_count += 1
                msg_class, msg_id = frame[2], frame[3]
                if (msg_class, msg_id) == (0x02, 0x15):
                    rawx_frame_count += 1
                if (msg_class, msg_id) == (0x02, 0x13):
                    sfrbx_frame_count += 1
    if frame_count == 0 and output_ubx.exists():
        output_ubx.unlink()
    return {
        "input_csv": str(input_csv),
        "output_ubx": str(output_ubx),
        "rebuilt_ubx_available": frame_count > 0,
        "frame_count": frame_count,
        "rawx_frame_count": rawx_frame_count,
        "sfrbx_frame_count": sfrbx_frame_count,
        "checksum_validation_status": "validated" if frame_count > 0 else "no_valid_ubx_frame",
        "invalid_frame_count": invalid_frame_count,
        "blocker_reasons": [] if frame_count > 0 else ["no_valid_ubx_frame"],
    }


def rebuild_fix_root(fix_root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    root = Path(fix_root)
    output_dir = Path(output_dir)
    files: dict[str, Any] = {}
    for name, out_name in (("gnss1-raw.csv", "gnss1_rebuilt.ubx"), ("gnss2-raw.csv", "gnss2_rebuilt.ubx")):
        path = root / name
        if path.exists():
            files[name] = rebuild_csv_to_ubx(path, output_dir / out_name)
        else:
            files[name] = {"input_csv": str(path), "rebuilt_ubx_available": False, "blocker_reasons": ["missing_csv"]}
    return {
        "files": files,
        "rebuilt_ubx_available": any(item.get("rebuilt_ubx_available", False) for item in files.values()),
        "frame_count": sum(item.get("frame_count", 0) for item in files.values()),
        "rawx_frame_count": sum(item.get("rawx_frame_count", 0) for item in files.values()),
        "sfrbx_frame_count": sum(item.get("sfrbx_frame_count", 0) for item in files.values()),
        "checksum_validation_status": "validated"
        if any(item.get("frame_count", 0) for item in files.values())
        else "no_valid_ubx_frame",
        "blocker_reasons": sorted({reason for item in files.values() for reason in item.get("blocker_reasons", [])}),
    }


def write_report(report: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--output-json", required=True)
    args = parser.parse_args(argv)
    report = rebuild_fix_root(args.fix_root, args.output_dir)
    write_report(report, args.output_json)
    print(f"Wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
