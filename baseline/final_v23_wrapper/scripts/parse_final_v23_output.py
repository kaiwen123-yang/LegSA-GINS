#!/usr/bin/env python3
"""Parse final_v23-style output into a conservative baseline CSV.
中文说明：final_v23 wrapper 只服务 baseline/oracle/backbone reference；final_v23 不是 proposed，wrapper 不允许 output substitution。

This parser is an N1 wrapper skeleton. The real field mapping will be completed
after the actual final_v23 output format is connected.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


TIMESTAMP_FIELDS = ("timestamp", "time", "t")
POSITION_FIELDS = ("x", "y", "z", "lat", "lon", "height", "latitude", "longitude", "altitude")
ATTITUDE_FIELDS = ("roll", "pitch", "yaw", "q0", "q1", "q2", "q3")
STANDARD_FIELDS = [
    "timestamp",
    "position_x",
    "position_y",
    "position_z",
    "roll",
    "pitch",
    "yaw",
]


def first_present(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    lowered = {field.lower(): field for field in fieldnames}
    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]
    return None


def parse_csv(input_path: Path, output_path: Path) -> None:
    # 中文说明：N1 wrapper 只做保守字段抽取，不做数值修正或 final_v23 output substitution。
    # N1 parsing is conservative field extraction only.
    with input_path.open(newline="", encoding="utf-8") as src:
        reader = csv.DictReader(src)
        if reader.fieldnames is None:
            raise SystemExit(f"CSV input has no header: {input_path}")

        timestamp_field = first_present(reader.fieldnames, TIMESTAMP_FIELDS)
        position_field = first_present(reader.fieldnames, POSITION_FIELDS)
        attitude_field = first_present(reader.fieldnames, ATTITUDE_FIELDS)
        if timestamp_field is None:
            raise SystemExit("CSV input must contain a timestamp/time/t field")
        if position_field is None:
            raise SystemExit("CSV input must contain at least one placeholder position field")
        if attitude_field is None:
            raise SystemExit("CSV input must contain at least one placeholder attitude field")

        rows = []
        for row in reader:
            rows.append(
                {
                    "timestamp": row.get(timestamp_field, ""),
                    "position_x": row.get("x", row.get(position_field, "")),
                    "position_y": row.get("y", ""),
                    "position_z": row.get("z", ""),
                    "roll": row.get("roll", row.get(attitude_field, "")),
                    "pitch": row.get("pitch", ""),
                    "yaw": row.get("yaw", ""),
                }
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as dst:
        writer = csv.DictWriter(dst, fieldnames=STANDARD_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Input final_v23-style output file.")
    parser.add_argument("--output", required=True, help="Output standardized baseline CSV.")
    parser.add_argument("--format", required=True, choices=["csv"], help="Input format. N1 supports csv only.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"input file does not exist: {input_path}")

    if args.format == "csv":
        parse_csv(input_path, Path(args.output))
    else:
        raise SystemExit(f"unsupported format: {args.format}")

    print(f"Wrote standardized baseline CSV: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
