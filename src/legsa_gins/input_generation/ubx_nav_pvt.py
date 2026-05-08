"""UBX-NAV-PVT velocity extraction for process_data parity.

中文说明：本模块只从 gnss1-raw.csv 的 UBX-NAV-PVT frame 提取 legacy
process_data 使用的速度字段；不解析 RAWX/SFRBX，不构造 raw GNSS factor。
"""

from __future__ import annotations

import ast
import csv
import math
import struct
from pathlib import Path
from typing import Any


UBX_NAV_PVT_HEADER = bytes([0xB5, 0x62, 0x01, 0x07])


def _as_float(value: Any, default: float | None = None) -> float | None:
    if value is None:
        return default
    text = str(value).strip()
    if text == "":
        return default
    try:
        parsed = float(text)
    except ValueError:
        return default
    if math.isnan(parsed):
        return default
    return parsed


def _payload_bytes(data_field: str | bytes | bytearray) -> bytes:
    if isinstance(data_field, bytes):
        return data_field
    if isinstance(data_field, bytearray):
        return bytes(data_field)
    text = str(data_field).strip()
    if not text:
        raise ValueError("UBX-NAV-PVT data field is empty.")
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError) as exc:
        raise ValueError("UBX-NAV-PVT data field is not a bytes/list repr.") from exc
    if isinstance(parsed, bytes):
        return parsed
    if isinstance(parsed, bytearray):
        return bytes(parsed)
    if isinstance(parsed, list):
        try:
            return bytes(int(item) & 0xFF for item in parsed)
        except (TypeError, ValueError) as exc:
            raise ValueError("UBX-NAV-PVT list repr contains non-byte values.") from exc
    raise ValueError(f"Unsupported UBX-NAV-PVT data repr type: {type(parsed).__name__}")


def parse_ubx_nav_pvt_payload(data_field: str | bytes | bytearray) -> dict[str, Any]:
    """Parse a full UBX-NAV-PVT frame using the uploaded process_data offsets."""

    frame = _payload_bytes(data_field)
    if frame[:4] != UBX_NAV_PVT_HEADER:
        raise ValueError("UBX frame is not UBX-NAV-PVT.")
    if len(frame) < 92:
        raise ValueError(f"UBX-NAV-PVT frame has {len(frame)} bytes; expected at least 92.")
    return {
        "vn": struct.unpack("<i", frame[54:58])[0] / 1000.0,
        "ve": struct.unpack("<i", frame[58:62])[0] / 1000.0,
        "vd": struct.unpack("<i", frame[62:66])[0] / 1000.0,
        "sAcc": struct.unpack("<I", frame[68:72])[0] / 1000.0,
        "frame_length": len(frame),
        "evidence_status": "decoded_ubx_nav_pvt_process_data_offsets",
    }


def extract_pvt_velocity_rows(
    raw_csv_path: str | Path,
    *,
    base_time: float,
    max_rows: int | None = None,
) -> list[dict[str, Any]]:
    """Extract timestamped UBX-NAV-PVT velocity rows from gnss1-raw.csv."""

    rows: list[dict[str, Any]] = []
    with Path(raw_csv_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            if max_rows is not None and index >= max_rows:
                break
            if row.get("name") != "UBX-NAV-PVT":
                continue
            secs = _as_float(row.get("stamp.secs"))
            nsecs = _as_float(row.get("stamp.nsecs"), 0.0)
            if secs is None:
                secs = _as_float(row.get("Time"))
                nsecs = 0.0
            if secs is None:
                continue
            try:
                decoded = parse_ubx_nav_pvt_payload(row.get("data", ""))
            except ValueError:
                continue
            rows.append(
                {
                    "time": float(secs) + float(nsecs or 0.0) * 1.0e-9 - base_time,
                    "stamp": float(secs) + float(nsecs or 0.0) * 1.0e-9,
                    "vn": decoded["vn"],
                    "ve": decoded["ve"],
                    "vd": decoded["vd"],
                    "sAcc": decoded["sAcc"],
                    "source": "gnss1_raw_UBX_NAV_PVT",
                    "evidence_status": decoded["evidence_status"],
                }
            )
    rows.sort(key=lambda item: float(item["time"]))
    return rows
