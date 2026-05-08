"""中文说明：runner toy integration 只验证生成合同，不读取真实 BY2。"""

import csv
import json
import struct
import subprocess
import sys


def _frame(vn, ve, vd, sacc):
    frame = bytearray(100)
    frame[:6] = bytes([0xB5, 0x62, 0x01, 0x07, 0x5C, 0x00])
    frame[54:58] = struct.pack("<i", vn)
    frame[58:62] = struct.pack("<i", ve)
    frame[62:66] = struct.pack("<i", vd)
    frame[68:72] = struct.pack("<I", sacc)
    return bytes(frame)


def _write_inputs(root, base_time=1772784000.0):
    fix = root / "fix"
    fix.mkdir()
    status_header = [
        "Time",
        "header.stamp.secs",
        "header.stamp.nsecs",
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
    for name in ["gnss1", "gnss2"]:
        with (fix / f"{name}-status.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=status_header)
            writer.writeheader()
            row_count = 10 if name == "gnss1" else 9
            for index in range(row_count):
                stamp = base_time + index * 0.1
                secs = int(stamp)
                nsecs = int(round((stamp - secs) * 1.0e9))
                writer.writerow(
                    {
                        "Time": f"{stamp:.9f}",
                        "header.stamp.secs": secs,
                        "header.stamp.nsecs": nsecs,
                        "pos_lat": 30.0,
                        "pos_lon": 120.0,
                        "pos_height": 15.0,
                        "pos_acc_h": 0.5,
                        "pos_acc_v": 0.8,
                        "rel_pos_n": 0.0 if name == "gnss1" else 1.0,
                        "rel_pos_e": 0.0 if name == "gnss1" else 1.0,
                        "rel_pos_d": 0.0,
                        "rel_acc_n": 0.01,
                        "rel_acc_e": 0.01,
                        "rel_acc_d": 0.02,
                        "rel_valid": "true",
                        "ant_valid": "true",
                        "ant_state": 2,
                    }
                )
    with (fix / "gnss1-raw.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Time", "stamp.secs", "stamp.nsecs", "protocol", "data", "name", "seq", "info"],
        )
        writer.writeheader()
        for index, offset in enumerate([0.0, 0.9]):
            stamp = base_time + offset
            secs = int(stamp)
            nsecs = int(round((stamp - secs) * 1.0e9))
            writer.writerow(
                {
                    "Time": f"{stamp:.9f}",
                    "stamp.secs": secs,
                    "stamp.nsecs": nsecs,
                    "protocol": "UBX",
                    "data": repr(_frame(100, 200, -50, 300)),
                    "name": "UBX-NAV-PVT",
                    "seq": index,
                    "info": "toy",
                }
            )
    body = root / "by2.txt"
    messages = []
    for index in range(3):
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
    body.write_text("\n---\n".join(messages) + "\n", encoding="utf-8")
    return fix, body


def test_runner_generates_process_data_compat_outputs(tmp_path):
    fix, body = _write_inputs(tmp_path)
    output = tmp_path / "out"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/experiments/run_process_data_compat_generation.py",
            "--fix-root",
            str(fix),
            "--body-imu",
            str(body),
            "--output-dir",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    for name in [
        "BY2_PROCESS_DATA_COMPAT.gnss",
        "BY2_PROCESS_DATA_COMPAT.imu",
        "PROCESS_DATA_COMPAT_REPORT.json",
        "PROCESS_DATA_COVERAGE_REPORT.json",
        "STATUS_YAW_A1_AUDIT.json",
        "IMU_PROCESS_DATA_COMPAT_REPORT.json",
    ]:
        assert (output / name).exists()
    report = json.loads((output / "PROCESS_DATA_COMPAT_REPORT.json").read_text())
    assert report["status_base_row_count"] == 10
    assert report["pvt_velocity_row_count"] == 2
    assert report["yaw_row_count"] == 9
    assert report["gnss_output_row_count"] == 10
    assert report["coverage_status"] == "passed"
