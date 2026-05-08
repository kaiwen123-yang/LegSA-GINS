#!/usr/bin/env python3
"""Audit N4H1P process_data-compatible input generation.

中文说明：本审计只用 toy 数据验证重建器合同；不读取真实 BY2 路径，
不生成性能结论，不实现 raw Doppler / Go2 prior / FGO。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


REQUIRED_FILES = [
    "src/legsa_gins/input_generation/process_data_compat.py",
    "src/legsa_gins/input_generation/ubx_nav_pvt.py",
    "src/legsa_gins/input_generation/status_yaw_builder.py",
    "src/legsa_gins/input_generation/imu_txt_builder.py",
]


def _toy_pvt_frame(vn: int, ve: int, vd: int, sacc: int) -> bytes:
    frame = bytearray(100)
    frame[:6] = bytes([0xB5, 0x62, 0x01, 0x07, 0x5C, 0x00])
    frame[54:58] = struct.pack("<i", vn)
    frame[58:62] = struct.pack("<i", ve)
    frame[62:66] = struct.pack("<i", vd)
    frame[68:72] = struct.pack("<I", sacc)
    return bytes(frame)


def _write_status(path: Path, *, receiver: str, base_time: float) -> None:
    header = [
        "Time",
        "header.stamp.secs",
        "header.stamp.nsecs",
        "sys_stamp.secs",
        "sys_stamp.nsecs",
        "pos_lat",
        "pos_lon",
        "pos_height",
        "pos_acc_h",
        "pos_acc_v",
        "rel_pos_n",
        "rel_pos_e",
        "rel_pos_d",
        "rel_acc_n",
        "rel_acc_e",
        "rel_acc_d",
        "rel_valid",
        "ant_valid",
        "ant_state",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for index in range(5):
            stamp = base_time + index * 0.1
            secs = int(stamp)
            nsecs = int(round((stamp - secs) * 1.0e9))
            if receiver == "gnss1":
                rel_n, rel_e = 0.0, 0.0
            else:
                rel_n, rel_e = 1.0, 1.0
            writer.writerow(
                {
                    "Time": f"{stamp:.9f}",
                    "header.stamp.secs": secs,
                    "header.stamp.nsecs": nsecs,
                    "sys_stamp.secs": secs,
                    "sys_stamp.nsecs": nsecs,
                    "pos_lat": 30.0 + index * 1.0e-6,
                    "pos_lon": 120.0 + index * 1.0e-6,
                    "pos_height": 15.0 + index * 0.1,
                    "pos_acc_h": 0.5,
                    "pos_acc_v": 0.8,
                    "rel_pos_n": rel_n,
                    "rel_pos_e": rel_e,
                    "rel_pos_d": 0.0,
                    "rel_acc_n": 0.01,
                    "rel_acc_e": 0.01,
                    "rel_acc_d": 0.02,
                    "rel_valid": "true",
                    "ant_valid": "true",
                    "ant_state": 2,
                }
            )


def _write_raw(path: Path, *, base_time: float) -> None:
    header = ["Time", "stamp.secs", "stamp.nsecs", "protocol", "data", "name", "seq", "info"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for index in range(5):
            stamp = base_time + index * 0.1
            secs = int(stamp)
            nsecs = int(round((stamp - secs) * 1.0e9))
            writer.writerow(
                {
                    "Time": f"{stamp:.9f}",
                    "stamp.secs": secs,
                    "stamp.nsecs": nsecs,
                    "protocol": "UBX",
                    "data": repr(_toy_pvt_frame(100 + index, -200, 50, 300)),
                    "name": "UBX-NAV-PVT",
                    "seq": index,
                    "info": "toy",
                }
            )


def _write_body(path: Path, *, base_time: float) -> None:
    messages = []
    for index in range(5):
        stamp = base_time + index * 0.01
        secs = int(stamp)
        nsecs = int(round((stamp - secs) * 1.0e9))
        messages.append(
            "\n".join(
                [
                    "stamp:",
                    f"  sec: {secs}",
                    f"  nanosec: {nsecs}",
                    "imu_state:",
                    "  gyroscope: [0.0, 0.0, 0.0]",
                    "  accelerometer: [1.0, 2.0, -3.0]",
                ]
            )
        )
    path.write_text("\n---\n".join(messages) + "\n", encoding="utf-8")


def _columns(path: Path) -> tuple[int, int]:
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return 0, 0
    return len(lines), len(lines[0].split())


def main() -> int:
    missing = [rel_path for rel_path in REQUIRED_FILES if not (REPO_ROOT / rel_path).exists()]
    if missing:
        print("N4H1P audit failed. Missing files:")
        for rel_path in missing:
            print(f"- {rel_path}")
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="legsa_n4h1p_audit_"))
    try:
        fix_root = tmp / "fix"
        output_dir = tmp / "out"
        fix_root.mkdir()
        body = tmp / "by2.txt"
        base_time = 1772784000.0
        _write_status(fix_root / "gnss1-status.csv", receiver="gnss1", base_time=base_time)
        _write_status(fix_root / "gnss2-status.csv", receiver="gnss2", base_time=base_time)
        _write_raw(fix_root / "gnss1-raw.csv", base_time=base_time)
        _write_body(body, base_time=base_time)
        completed = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts/experiments/run_process_data_compat_generation.py"),
                "--fix-root",
                str(fix_root),
                "--body-imu",
                str(body),
                "--output-dir",
                str(output_dir),
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            print("N4H1P audit failed. Generator failed.")
            print(completed.stdout)
            print(completed.stderr)
            return 1
        required_outputs = [
            "BY2_PROCESS_DATA_COMPAT.gnss",
            "BY2_PROCESS_DATA_COMPAT.imu",
            "PROCESS_DATA_COMPAT_REPORT.json",
            "STATUS_YAW_A1_AUDIT.json",
            "IMU_PROCESS_DATA_COMPAT_REPORT.json",
        ]
        missing_outputs = [name for name in required_outputs if not (output_dir / name).exists()]
        if missing_outputs:
            print("N4H1P audit failed. Missing generated outputs:")
            for name in missing_outputs:
                print(f"- {name}")
            return 1
        gnss_shape = _columns(output_dir / "BY2_PROCESS_DATA_COMPAT.gnss")
        imu_shape = _columns(output_dir / "BY2_PROCESS_DATA_COMPAT.imu")
        if gnss_shape[1] != 15:
            print(f"N4H1P audit failed. .gnss columns={gnss_shape[1]}")
            return 1
        if imu_shape[1] != 7:
            print(f"N4H1P audit failed. .imu columns={imu_shape[1]}")
            return 1
        report = json.loads((output_dir / "PROCESS_DATA_COMPAT_REPORT.json").read_text())
        checks = {
            "trace_solver_input": False,
            "trace_yaw_for_solver": False,
            "raw_doppler_claim": False,
            "numerical_performance_claim": False,
            "enable_outage": False,
        }
        for key, expected in checks.items():
            if report.get(key) is not expected:
                print(f"N4H1P audit failed. {key}={report.get(key)!r}")
                return 1
        if report.get("velocity_std_policy") != "fixed_0p05_observed_in_uploaded_code":
            print("N4H1P audit failed. velocity_std_policy mismatch.")
            return 1
        if report.get("outlier_mode") != "none":
            print("N4H1P audit failed. outlier_mode is not none.")
            return 1
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("N4H1P process_data-compatible input generation audit passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
