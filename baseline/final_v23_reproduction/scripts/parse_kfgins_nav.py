#!/usr/bin/env python3
"""Parse KF_GINS_Navresult.nav into a standardized baseline CSV.

中文说明：本模块只处理 final_v23/KF-GINS baseline 输出或只读外部源码探测；不修改外部源码、不复制源码、不做数值修正或性能结论。
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


NAV_COLUMNS = [
    "gps_week",
    "tow",
    "lat_deg",
    "lon_deg",
    "height_m",
    "vn_mps",
    "ve_mps",
    "vd_mps",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
]

OUTPUT_COLUMNS = NAV_COLUMNS + ["status", "source_role"]


def _split_fields(line: str) -> list[str]:
    return line.replace(",", " ").split()


def _parse_gps_week(value: str) -> int | float:
    number = float(value)
    if number.is_integer():
        return int(number)
    return number


def parse_nav_file(input_path: str | Path) -> list[dict[str, Any]]:
    """Return baseline rows without correcting or filtering any epochs."""

    # 中文说明：KF_GINS_Navresult.nav 是 baseline NAV；这里只检查列数和时间单调性。
    # This parser validates the NAV contract only and never corrects coordinates.
    path = Path(input_path)
    rows: list[dict[str, Any]] = []
    previous_tow: float | None = None

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            fields = _split_fields(stripped)
            if len(fields) != len(NAV_COLUMNS):
                raise ValueError(
                    f"{path}:{line_number} expected {len(NAV_COLUMNS)} columns, got {len(fields)}"
                )

            values = [_parse_gps_week(fields[0])] + [float(value) for value in fields[1:]]
            tow = float(values[1])
            if previous_tow is not None and tow < previous_tow:
                raise ValueError(f"{path}:{line_number} tow must be monotonic non-decreasing")
            previous_tow = tow

            row = dict(zip(NAV_COLUMNS, values))
            row["status"] = "baseline_final_v23"
            row["source_role"] = "baseline"
            rows.append(row)

    return rows


def write_nav_csv(rows: list[dict[str, Any]], output_csv: str | Path) -> Path:
    # 中文说明：写出的 FINAL_V23_NAV.csv 仍是 baseline，不是 proposed solver 输出。
    # The standardized NAV remains a baseline artifact.
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="KF_GINS_Navresult.nav path.")
    parser.add_argument("--output-csv", required=True, help="Standardized output CSV path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = parse_nav_file(args.input)
    output_path = write_nav_csv(rows, args.output_csv)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
