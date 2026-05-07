"""BY2 receiver-native GNSS status standardization.

中文说明：
本模块标准化 gnss1/gnss2 status CSV 中的 receiver-native 位置与相对基线候选信息。
它不解析 raw Doppler，不做 output-only correction，不使用 trace，也不生成 numerical claim。
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Any


SOURCE_ROLE = "receiver_native_gnss_status"

REQUIRED_FIELDS = [
    "Time",
    "time_gps_wno",
    "time_gps_tow",
    "msg_valid",
    "pos_lat",
    "pos_lon",
    "pos_height",
    "pos_acc_h",
    "pos_acc_v",
    "pos_valid",
    "fix_ok",
    "fix_type",
]

HEADING_FIELDS = [
    "rel_pos_n",
    "rel_pos_e",
    "rel_pos_d",
    "rel_acc_n",
    "rel_acc_e",
    "rel_acc_d",
    "rel_valid",
    "ant_valid",
]

STANDARD_HEADER = [
    "time_unix",
    "gps_week",
    "tow",
    "lat_deg",
    "lon_deg",
    "height_m",
    "pos_acc_h_m",
    "pos_acc_v_m",
    "pos_valid",
    "fix_ok",
    "fix_type",
    "has_position",
    "rel_pos_n_m",
    "rel_pos_e_m",
    "rel_pos_d_m",
    "rel_acc_n_m",
    "rel_acc_e_m",
    "rel_acc_d_m",
    "rel_valid",
    "ant_valid",
    "heading_deg",
    "heading_valid",
    "source_name",
    "source_role",
]


def _require_header(fieldnames: list[str] | None) -> list[str]:
    if not fieldnames:
        raise ValueError("GNSS status CSV is missing a header.")
    missing = [field for field in REQUIRED_FIELDS if field not in fieldnames]
    if missing:
        raise ValueError(f"GNSS status CSV missing required fields: {missing}")
    return fieldnames


def _as_float(value: str | None, field: str) -> float | None:
    if value is None or value.strip() == "":
        return None
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"GNSS status field {field} is not numeric: {value}") from exc
    if math.isnan(parsed):
        return None
    return parsed


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "t", "yes", "y"}


def _heading_available(row: dict[str, str]) -> bool:
    return all(field in row for field in HEADING_FIELDS)


def _make_row(row: dict[str, str], *, source_name: str) -> dict[str, Any]:
    msg_valid = _as_bool(row.get("msg_valid"))
    pos_valid = _as_bool(row.get("pos_valid"))
    fix_ok = _as_bool(row.get("fix_ok"))
    rel_fields_present = _heading_available(row)

    rel_pos_n = _as_float(row.get("rel_pos_n"), "rel_pos_n") if rel_fields_present else None
    rel_pos_e = _as_float(row.get("rel_pos_e"), "rel_pos_e") if rel_fields_present else None
    rel_pos_d = _as_float(row.get("rel_pos_d"), "rel_pos_d") if rel_fields_present else None
    rel_acc_n = _as_float(row.get("rel_acc_n"), "rel_acc_n") if rel_fields_present else None
    rel_acc_e = _as_float(row.get("rel_acc_e"), "rel_acc_e") if rel_fields_present else None
    rel_acc_d = _as_float(row.get("rel_acc_d"), "rel_acc_d") if rel_fields_present else None
    rel_valid = _as_bool(row.get("rel_valid")) if rel_fields_present else False
    ant_valid = _as_bool(row.get("ant_valid")) if rel_fields_present else False

    heading_valid = bool(rel_valid and ant_valid and rel_pos_n is not None and rel_pos_e is not None)
    heading_deg = None
    if heading_valid:
        heading_deg = math.degrees(math.atan2(rel_pos_e, rel_pos_n)) % 360.0

    return {
        "time_unix": _as_float(row.get("Time"), "Time"),
        "gps_week": int(_as_float(row.get("time_gps_wno"), "time_gps_wno") or 0),
        "tow": _as_float(row.get("time_gps_tow"), "time_gps_tow"),
        "lat_deg": _as_float(row.get("pos_lat"), "pos_lat"),
        "lon_deg": _as_float(row.get("pos_lon"), "pos_lon"),
        "height_m": _as_float(row.get("pos_height"), "pos_height"),
        "pos_acc_h_m": _as_float(row.get("pos_acc_h"), "pos_acc_h"),
        "pos_acc_v_m": _as_float(row.get("pos_acc_v"), "pos_acc_v"),
        "pos_valid": pos_valid,
        "fix_ok": fix_ok,
        "fix_type": row.get("fix_type", ""),
        "has_position": bool(msg_valid and pos_valid and fix_ok),
        "rel_pos_n_m": rel_pos_n,
        "rel_pos_e_m": rel_pos_e,
        "rel_pos_d_m": rel_pos_d,
        "rel_acc_n_m": rel_acc_n,
        "rel_acc_e_m": rel_acc_e,
        "rel_acc_d_m": rel_acc_d,
        "rel_valid": rel_valid,
        "ant_valid": ant_valid,
        "heading_deg": heading_deg,
        "heading_valid": heading_valid,
        "source_name": source_name,
        "source_role": SOURCE_ROLE,
    }


def parse_gnss_status_csv(
    path: str | Path, *, source_name: str, max_rows: int | None = None
) -> list[dict[str, Any]]:
    """Parse a BY2 GNSS status CSV into standardized receiver-native rows."""
    rows: list[dict[str, Any]] = []
    previous_tow: float | None = None
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        _require_header(reader.fieldnames)
        for index, raw_row in enumerate(reader):
            if max_rows is not None and index >= max_rows:
                break
            row = _make_row(raw_row, source_name=source_name)
            tow = row["tow"]
            if tow is None:
                raise ValueError("GNSS status row is missing time_gps_tow.")
            if previous_tow is not None and tow < previous_tow:
                raise ValueError("GNSS status tow must be monotonic non-decreasing.")
            previous_tow = tow
            rows.append(row)
    return rows


def _csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def write_standardized_gnss_status(rows: list[dict[str, Any]], output_path: str | Path) -> None:
    """Write standardized receiver-native GNSS status CSV."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STANDARD_HEADER)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field)) for field in STANDARD_HEADER})


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="BY2 gnss*-status.csv input.")
    parser.add_argument("--source-name", required=True, help="Receiver source name, e.g. gnss1.")
    parser.add_argument("--output", required=True, help="Standardized CSV output path.")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional row limit for probes.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    rows = parse_gnss_status_csv(args.input, source_name=args.source_name, max_rows=args.max_rows)
    write_standardized_gnss_status(rows, args.output)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
