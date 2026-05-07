#!/usr/bin/env python3
"""Parse KF_GINS_STD.txt into a standardized baseline CSV.

中文说明：本模块只处理 final_v23/KF-GINS baseline 输出或只读外部源码探测；不修改外部源码、不复制源码、不做数值修正或性能结论。
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


STD_COLUMNS = [
    "tow",
    "std_pos_n_m",
    "std_pos_e_m",
    "std_pos_d_m",
    "std_vel_n_mps",
    "std_vel_e_mps",
    "std_vel_d_mps",
    "std_roll_deg",
    "std_pitch_deg",
    "std_yaw_deg",
    "std_gyrbias_x_dph",
    "std_gyrbias_y_dph",
    "std_gyrbias_z_dph",
    "std_accbias_x_mgal",
    "std_accbias_y_mgal",
    "std_accbias_z_mgal",
    "std_gyrscale_x_ppm",
    "std_gyrscale_y_ppm",
    "std_gyrscale_z_ppm",
    "std_accscale_x_ppm",
    "std_accscale_y_ppm",
    "std_accscale_z_ppm",
]


def _split_fields(line: str) -> list[str]:
    return line.replace(",", " ").split()


def parse_std_file(input_path: str | Path) -> list[dict[str, Any]]:
    # 中文说明：KF_GINS_STD.txt 是 baseline STD 输出；std 字段只校验非负，不重估不调参。
    # Baseline STD parsing validates non-negative standard deviations only.
    path = Path(input_path)
    rows: list[dict[str, Any]] = []
    previous_tow: float | None = None

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            fields = _split_fields(stripped)
            if len(fields) != len(STD_COLUMNS):
                raise ValueError(
                    f"{path}:{line_number} expected {len(STD_COLUMNS)} columns, got {len(fields)}"
                )

            values = [float(value) for value in fields]
            tow = values[0]
            if previous_tow is not None and tow < previous_tow:
                raise ValueError(f"{path}:{line_number} tow must be monotonic non-decreasing")
            previous_tow = tow

            for column, value in zip(STD_COLUMNS[1:], values[1:]):
                if value < 0:
                    raise ValueError(f"{path}:{line_number} {column} must be >= 0")
            rows.append(dict(zip(STD_COLUMNS, values)))

    return rows


def write_std_csv(rows: list[dict[str, Any]], output_csv: str | Path) -> Path:
    # 中文说明：标准化只改变容器格式，不改变数值含义。
    # Standardization changes file shape only, not values.
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STD_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="KF_GINS_STD.txt path.")
    parser.add_argument("--output-csv", required=True, help="Standardized output CSV path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = parse_std_file(args.input)
    output_path = write_std_csv(rows, args.output_csv)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
