"""BY2 GNSS raw message stream scanner.

中文说明：本模块只扫描 gnss*-raw.csv 的 message name/header 证据，不解析 pseudorange、Doppler、carrier phase，也不实现 raw GNSS factor。
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCAN_FIELDS = ["Time", "name", "info", "protocol", "seq"]
KNOWN_MESSAGES = [
    "UBX-NAV-PVT",
    "UBX-NAV-HPPOSECEF",
    "UBX-NAV-HPPOSLLH",
    "RTCM",
    "NMEA",
]


def _require_header(fieldnames: list[str] | None) -> list[str]:
    if not fieldnames:
        raise ValueError("GNSS raw CSV is missing a header.")
    missing = [field for field in SCAN_FIELDS if field not in fieldnames]
    if missing:
        raise ValueError(f"GNSS raw CSV missing required fields: {missing}")
    return fieldnames


def _sample(row: dict[str, str]) -> dict[str, str]:
    info = (row.get("info") or "")[:200]
    return {
        "Time": row.get("Time", ""),
        "info": info,
        "protocol": row.get("protocol", ""),
        "seq": row.get("seq", ""),
    }


def scan_gnss_raw_csv(
    path: str | Path, *, source_name: str, max_rows: int | None = None
) -> dict[str, Any]:
    """Scan message names without extracting raw measurement observables."""
    counts: Counter[str] = Counter()
    sample_info: dict[str, list[dict[str, str]]] = defaultdict(list)
    total = 0

    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _require_header(reader.fieldnames)
        for index, row in enumerate(reader):
            if max_rows is not None and index >= max_rows:
                break
            name = row.get("name", "") or "UNKNOWN"
            counts[name] += 1
            if len(sample_info[name]) < 3:
                sample_info[name].append(_sample(row))
            total += 1

    joined_names = " ".join(counts.keys()).upper()
    known_presence = {
        "has_ubx_nav_pvt": "UBX-NAV-PVT" in counts,
        "has_ubx_nav_hpposecef": "UBX-NAV-HPPOSECEF" in counts,
        "has_ubx_nav_hpposllh": "UBX-NAV-HPPOSLLH" in counts,
        "has_rtcm": any("RTCM" in key.upper() for key in counts) or "RTCM" in joined_names,
        "has_nmea": any("NMEA" in key.upper() for key in counts) or "NMEA" in joined_names,
    }

    return {
        "source_name": source_name,
        "total_rows_scanned": total,
        "message_counts": dict(sorted(counts.items())),
        "sample_info": dict(sorted(sample_info.items())),
        **known_presence,
        "raw_doppler_extracted": False,
        "raw_pseudorange_extracted": False,
        "carrier_phase_extracted": False,
        "evidence_status": "message_stream_scanned_only",
    }


def write_raw_message_summary(summary: dict[str, Any], output_json: str | Path) -> None:
    path = Path(output_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="BY2 gnss*-raw.csv input.")
    parser.add_argument("--source-name", required=True, help="Receiver source name, e.g. gnss1.")
    parser.add_argument("--output-json", required=True, help="JSON summary output path.")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional row limit for probes.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    summary = scan_gnss_raw_csv(args.input, source_name=args.source_name, max_rows=args.max_rows)
    write_raw_message_summary(summary, args.output_json)
    print(f"Wrote {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
