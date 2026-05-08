"""中文说明：process_data compat 单元测试只使用 toy 输入，不提交真实数据。"""

import csv
import json
import struct

from legsa_gins.input_generation.process_data_compat import generate_process_data_compat_inputs


def _toy_pvt_frame(vn, ve, vd, sacc):
    frame = bytearray(100)
    frame[:6] = bytes([0xB5, 0x62, 0x01, 0x07, 0x5C, 0x00])
    frame[54:58] = struct.pack("<i", vn)
    frame[58:62] = struct.pack("<i", ve)
    frame[62:66] = struct.pack("<i", vd)
    frame[68:72] = struct.pack("<I", sacc)
    return bytes(frame)


def _write_status(path, receiver, base_time):
    header = [
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
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        for index in range(4):
            stamp = base_time + index * 0.1
            secs = int(stamp)
            nsecs = int(round((stamp - secs) * 1.0e9))
            rel_n = 0.0 if receiver == "gnss1" else 1.0
            rel_e = 0.0 if receiver == "gnss1" else 1.0
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


def _write_raw(path, base_time):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["Time", "stamp.secs", "stamp.nsecs", "protocol", "data", "name", "seq", "info"],
        )
        writer.writeheader()
        for index in range(4):
            stamp = base_time + index * 0.1
            secs = int(stamp)
            nsecs = int(round((stamp - secs) * 1.0e9))
            writer.writerow(
                {
                    "Time": f"{stamp:.9f}",
                    "stamp.secs": secs,
                    "stamp.nsecs": nsecs,
                    "protocol": "UBX",
                    "data": repr(_toy_pvt_frame(100, 200, -50, 300)),
                    "name": "UBX-NAV-PVT",
                    "seq": index,
                    "info": "toy",
                }
            )


def _write_body(path, base_time):
    messages = []
    for index in range(4):
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


def _make_toy_inputs(tmp_path, base_time=1772784000.0):
    fix = tmp_path / "fix"
    fix.mkdir()
    _write_status(fix / "gnss1-status.csv", "gnss1", base_time)
    _write_status(fix / "gnss2-status.csv", "gnss2", base_time)
    _write_raw(fix / "gnss1-raw.csv", base_time)
    body = tmp_path / "by2.txt"
    _write_body(body, base_time)
    return fix, body


def test_generate_process_data_compat_inputs_toy(tmp_path):
    fix, body = _make_toy_inputs(tmp_path)
    output = tmp_path / "out"

    result = generate_process_data_compat_inputs(fix, body, output)
    gnss_lines = (output / "BY2_PROCESS_DATA_COMPAT.gnss").read_text().strip().splitlines()
    imu_lines = (output / "BY2_PROCESS_DATA_COMPAT.imu").read_text().strip().splitlines()
    report = json.loads((output / "PROCESS_DATA_COMPAT_REPORT.json").read_text())

    assert result["report"]["runtime_input_reconstructed"] is True
    assert len(gnss_lines[0].split()) == 15
    assert len(imu_lines[0].split()) == 7
    assert report["enable_outage"] is False
    assert report["outlier_mode"] == "none"
    assert report["yaw_noise_injection"] is False
    assert report["trace_solver_input"] is False
    assert report["trace_yaw_for_solver"] is False
