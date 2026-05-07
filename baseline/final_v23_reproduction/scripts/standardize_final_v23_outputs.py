#!/usr/bin/env python3
"""Standardize observed KF-GINS final_v23 outputs for baseline evaluation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from parse_kfgins_imu_err import parse_imu_err_file, write_imu_err_csv
from parse_kfgins_nav import parse_nav_file, write_nav_csv
from parse_kfgins_std import parse_std_file, write_std_csv
from write_reproduction_manifest import write_manifest


EVAL_NAV_COLUMNS = [
    "timestamp",
    "lat_deg",
    "lon_deg",
    "height_m",
    "vn_mps",
    "ve_mps",
    "vd_mps",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
    "status",
    "source_role",
]


def write_eval_nav_csv(nav_rows: list[dict[str, object]], output_csv: str | Path) -> Path:
    output_path = Path(output_csv)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=EVAL_NAV_COLUMNS)
        writer.writeheader()
        for row in nav_rows:
            writer.writerow(
                {
                    "timestamp": row["tow"],
                    "lat_deg": row["lat_deg"],
                    "lon_deg": row["lon_deg"],
                    "height_m": row["height_m"],
                    "vn_mps": row["vn_mps"],
                    "ve_mps": row["ve_mps"],
                    "vd_mps": row["vd_mps"],
                    "roll_deg": row["roll_deg"],
                    "pitch_deg": row["pitch_deg"],
                    "yaw_deg": row["yaw_deg"],
                    "status": row["status"],
                    "source_role": row["source_role"],
                }
            )
    return output_path


def standardize_outputs(
    *,
    nav: str | Path,
    std: str | Path,
    imu_err: str | Path | None,
    output_dir: str | Path,
    dataset_name: str,
    source_root: str,
) -> dict[str, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    nav_rows = parse_nav_file(nav)
    std_rows = parse_std_file(std)

    outputs = {
        "nav": write_nav_csv(nav_rows, output_path / "FINAL_V23_NAV.csv"),
        "std": write_std_csv(std_rows, output_path / "FINAL_V23_STD.csv"),
        "eval_nav": write_eval_nav_csv(nav_rows, output_path / "FINAL_V23_EVAL_NAV.csv"),
    }

    evidence_missing: list[str] = []
    if imu_err is not None and Path(imu_err).exists():
        imu_err_rows = parse_imu_err_file(imu_err)
        outputs["imu_err"] = write_imu_err_csv(
            imu_err_rows, output_path / "FINAL_V23_IMU_ERR.csv"
        )
    else:
        evidence_missing.append("KF_GINS_IMU_ERR.txt")

    outputs["manifest"] = write_manifest(
        output_dir=output_path,
        dataset_name=dataset_name,
        source_root=source_root,
        evidence_missing=evidence_missing,
    )
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nav", required=True, help="KF_GINS_Navresult.nav input.")
    parser.add_argument("--std", required=True, help="KF_GINS_STD.txt input.")
    parser.add_argument("--imu-err", required=False, help="Optional KF_GINS_IMU_ERR.txt input.")
    parser.add_argument("--output-dir", required=True, help="Output directory for standardized files.")
    parser.add_argument("--dataset-name", required=True, help="Dataset name for RUN_MANIFEST.json.")
    parser.add_argument("--source-root", required=True, help="External final_v23/KF-GINS source root.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    outputs = standardize_outputs(
        nav=args.nav,
        std=args.std,
        imu_err=args.imu_err,
        output_dir=args.output_dir,
        dataset_name=args.dataset_name,
        source_root=args.source_root,
    )
    for name, path in sorted(outputs.items()):
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
