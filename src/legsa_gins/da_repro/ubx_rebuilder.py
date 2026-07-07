"""DA01 wrapper around runtime-only UBX byte-stream rebuilding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import rebuild_csv_to_ubx


def rebuild_receiver_ubx(fix_root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    root = Path(fix_root)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files: dict[str, Any] = {}
    for csv_name, ubx_name in (("gnss1-raw.csv", "gnss1.ubx"), ("gnss2-raw.csv", "gnss2.ubx")):
        source = root / csv_name
        if source.exists():
            files[csv_name] = rebuild_csv_to_ubx(source, out / ubx_name)
        else:
            files[csv_name] = {
                "input_csv": str(source),
                "output_ubx": str(out / ubx_name),
                "rebuilt_ubx_available": False,
                "frame_count": 0,
                "rawx_frame_count": 0,
                "sfrbx_frame_count": 0,
                "blocker_reasons": ["missing_csv"],
            }
    return {
        "files": files,
        "rebuilt_ubx_available": all(item.get("rebuilt_ubx_available", False) for item in files.values()),
        "frame_count": sum(int(item.get("frame_count", 0)) for item in files.values()),
        "rawx_frame_count": sum(int(item.get("rawx_frame_count", 0)) for item in files.values()),
        "sfrbx_frame_count": sum(int(item.get("sfrbx_frame_count", 0)) for item in files.values()),
        "checksum_validation_status": "validated"
        if all(item.get("rebuilt_ubx_available", False) for item in files.values())
        else "incomplete",
        "blocker_reasons": sorted({reason for item in files.values() for reason in item.get("blocker_reasons", [])}),
    }
