#!/usr/bin/env python3
"""Parse KF_GINS_IMU_ERR.txt into a standardized baseline CSV.

中文说明：本模块只处理 final_v23/KF-GINS baseline 输出或只读外部源码探测；不修改外部源码、不复制源码、不做数值修正或性能结论。
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any


IMU_ERR_COLUMNS = [
    "tow",
    "gyrbias_x_dph",
    "gyrbias_y_dph",
    "gyrbias_z_dph",
    "accbias_x_mgal",
    "accbias_y_mgal",
    "accbias_z_mgal",
    "gyrscale_x_ppm",
    "gyrscale_y_ppm",
    "gyrscale_z_ppm",
    "accscale_x_ppm",
    "accscale_y_ppm",
    "accscale_z_ppm",
]


def _split_fields(line: str) -> list[str]:
    return line.replace(",", " ").split()


def parse_imu_err_file(input_path: str | Path) -> list[dict[str, Any]]:
    # 中文说明：KF_GINS_IMU_ERR.txt 是 baseline IMU error output，不是 Go2 body-state 输入。
    # Baseline IMU error output is not a Go2 body-state source.
    path = Path(input_path)
    rows: list[dict[str, Any]] = []
    previous_tow: float | None = None

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            fields = _split_fields(stripped)
            if len(fields) != len(IMU_ERR_COLUMNS):
                raise ValueError(
                    f"{path}:{line_number} expected {len(IMU_ERR_COLUMNS)} columns, got {len(fields)}"
                )

            values = [float(value) for value in fields]
            tow = values[0]
            if previous_tow is not None and tow < previous_tow:
                raise ValueError(f"{path}:{line_number} tow must be monotonic non-decreasing")
            previous_tow = tow
            rows.append(dict(zip(IMU_ERR_COLUMNS, values)))

    return rows


def write_imu_err_csv(rows: list[dict[str, Any]], output_csv: str | Path) -> Path:
    # 中文说明：写 CSV 只服务 baseline evidence，不进入 proposed solver。
    # CSV output is baseline evidence only and never solver input.
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=IMU_ERR_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="KF_GINS_IMU_ERR.txt path.")
    parser.add_argument("--output-csv", required=True, help="Standardized output CSV path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    rows = parse_imu_err_file(args.input)
    output_path = write_imu_err_csv(rows, args.output_csv)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
