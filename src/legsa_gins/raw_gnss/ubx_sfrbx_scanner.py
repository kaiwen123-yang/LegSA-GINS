"""Scan UBX-RXM-SFRBX messages for N5A ephemeris-readiness evidence.

中文说明：N5A 记录 SFRBX 存在性和星座覆盖；若未解码广播星历，必须标记
sfrbx_decode_not_implemented_in_N5A，除非 RTKLIB convbin 已成功处理。
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from .ubx_raw_binary_rebuilder import iter_ubx_frames, parse_bytes_cell


GNSS_NAMES = {0: "GPS", 1: "SBAS", 2: "GALILEO", 3: "BEIDOU", 5: "QZSS", 6: "GLONASS"}


def scan_sfrbx_csv(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    constellations: Counter[str] = Counter()
    svs: set[str] = set()
    count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if "data" not in (reader.fieldnames or []):
            return {"path": str(path), "message_count": 0, "blocker_reasons": ["missing_data_column"]}
        for row in reader:
            if "SFRBX" not in (row.get("name") or "").upper():
                continue
            for frame in iter_ubx_frames(parse_bytes_cell(row.get("data", ""))):
                payload = frame[6:-2]
                if len(payload) >= 8:
                    gnss_id = payload[0]
                    sv_id = payload[1]
                    name = GNSS_NAMES.get(gnss_id, f"GNSS_{gnss_id}")
                    constellations[name] += 1
                    svs.add(f"{name}:{sv_id}")
                    count += 1
    return {
        "path": str(path),
        "message_count": count,
        "constellations": dict(sorted(constellations.items())),
        "sv_count": len(svs),
        "ephemeris_decode_attempted": False,
        "status": "sfrbx_decode_not_implemented_in_N5A",
    }


def scan_fix_root(fix_root: str | Path) -> dict[str, Any]:
    root = Path(fix_root)
    files = {}
    for name in ("gnss1-raw.csv", "gnss2-raw.csv"):
        path = root / name
        files[name] = scan_sfrbx_csv(path) if path.exists() else {"path": str(path), "missing": True}
    return {
        "files": files,
        "message_count": sum(item.get("message_count", 0) for item in files.values()),
        "constellations": dict(
            sum((Counter(item.get("constellations", {})) for item in files.values()), Counter())
        ),
        "ephemeris_decode_attempted": False,
        "status": "sfrbx_decode_not_implemented_in_N5A",
        "rtklib_convbin_may_decode_sfrbx": True,
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
