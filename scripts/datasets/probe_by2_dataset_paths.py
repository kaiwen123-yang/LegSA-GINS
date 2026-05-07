#!/usr/bin/env python3
"""Probe BY2 local dataset paths and source roles without reading raw files fully.

中文说明：BY2 path probe 只验证路径、header 和 source role；不读取全量 raw data，trace 只能 evaluation-only，receiver IMU 不是 Go2 body IMU。
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


RECEIVER_FILES = {
    "gnss1_raw": "gnss1-raw.csv",
    "gnss1_status": "gnss1-status.csv",
    "gnss2_raw": "gnss2-raw.csv",
    "gnss2_status": "gnss2-status.csv",
    "trace_reference": "trace_vrtk2_a87c6e_2026-03-06-08-00-54_minimal.csv",
    "receiver_imu_data": "imu-data.csv",
    "receiver_imu_biases": "imu-biases.csv",
    "receiver_imu_temp": "imu-temp.csv",
    "ntrip_info": "ntrip-info.csv",
    "ntrip_latency": "ntrip-latency.csv",
    "tf": "tf.csv",
    "tf_static": "tf_static.csv",
    "user_io_out_odom_status": "user_io-out-odom_status.csv",
    "user_io_out_poi_geodetic": "user_io-out-poi_geodetic.csv",
    "user_io_out_poi_odometry": "user_io-out-poi_odometry.csv",
    "user_io_out_poi_smooth_odometry": "user_io-out-poi_smooth_odometry.csv",
    "user_io_status": "user_io-status.csv",
    "userio_raw": "userio-raw.csv",
    "corr_raw": "corr-raw.csv",
}

GNSS_RAW_REQUIRED = {"Time", "name", "info"}
GNSS_STATUS_REQUIRED = {"time_gps_tow", "pos_lat", "pos_lon", "pos_height", "fix_type"}
TRACE_REQUIRED = {"time", "lat", "lon", "height", "yaw", "pitch", "roll"}
BODY_MARKERS = [
    "imu_state:",
    "yaw_speed:",
    "foot_force:",
    "foot_position_body:",
    "foot_speed_body:",
]


def read_csv_header(path: Path) -> list[str]:
    # 中文说明：只读取第一行 header，避免把 BY2 raw data 读入或复制到仓库。
    # Read only the CSV header; never ingest or vendor raw data.
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            return [field.strip() for field in next(reader)]
        except StopIteration:
            return []


def header_check(path: Path, required: set[str]) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False, "passed": False, "missing_columns": sorted(required)}
    header = read_csv_header(path)
    header_set = set(header)
    missing = sorted(required - header_set)
    return {
        "present": True,
        "passed": not missing,
        "required_columns": sorted(required),
        "missing_columns": missing,
        "header_columns": header,
    }


def body_marker_check(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"present": False, "passed": False, "missing_markers": BODY_MARKERS}
    found = {marker: False for marker in BODY_MARKERS}
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            for marker in BODY_MARKERS:
                if marker in line:
                    found[marker] = True
            if all(found.values()):
                break
    missing = [marker for marker, present in found.items() if not present]
    return {"present": True, "passed": not missing, "missing_markers": missing}


def probe_paths(fix_root: str | Path, body_imu: str | Path) -> dict[str, Any]:
    # 中文说明：路径探测只确认 source role；trace evaluation-only，receiver IMU 不是 Go2 body IMU。
    # Path probing validates source roles only.
    root = Path(fix_root)
    body_path = Path(body_imu)
    file_roles: dict[str, dict[str, Any]] = {}
    for role, filename in RECEIVER_FILES.items():
        path = root / filename
        file_roles[role] = {
            "filename": filename,
            "exists": path.is_file(),
            "role": role,
        }

    header_checks = {
        "gnss1_raw": header_check(root / RECEIVER_FILES["gnss1_raw"], GNSS_RAW_REQUIRED),
        "gnss2_raw": header_check(root / RECEIVER_FILES["gnss2_raw"], GNSS_RAW_REQUIRED),
        "gnss1_status": header_check(root / RECEIVER_FILES["gnss1_status"], GNSS_STATUS_REQUIRED),
        "gnss2_status": header_check(root / RECEIVER_FILES["gnss2_status"], GNSS_STATUS_REQUIRED),
        "trace_reference": header_check(root / RECEIVER_FILES["trace_reference"], TRACE_REQUIRED),
        "body_imu_text": body_marker_check(body_path),
    }

    missing_files = [
        info["filename"] for info in file_roles.values() if not info["exists"]
    ]
    if not body_path.is_file():
        missing_files.append("BY2_BODY_IMU")
    missing_headers = [
        name for name, check in header_checks.items() if not check.get("passed", False)
    ]
    evidence_missing = missing_files + [f"header_or_marker_check:{name}" for name in missing_headers]

    return {
        "dataset_name": "BY2",
        "fix_root_exists": root.is_dir(),
        "body_imu_exists": body_path.is_file(),
        "file_roles": file_roles,
        "header_checks": header_checks,
        "solver_input_policy": {
            "trace_solver_input": False,
            "receiver_imu_as_body_imu": False,
            "body_imu_source": "BY2_BODY_IMU",
        },
        "evaluation_only_policy": {
            "trace_evaluation_only": True,
        },
        "evidence_status": "passed" if not evidence_missing and root.is_dir() else "evidence_missing",
        "evidence_missing": evidence_missing,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix-root", required=True, help="Local BY2 Fixposition data root.")
    parser.add_argument("--body-imu", required=True, help="Local BY2 Go2/body-state text file.")
    parser.add_argument("--output-json", required=True, help="Probe JSON output path, normally under /tmp.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = probe_paths(args.fix_root, args.body_imu)
    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
