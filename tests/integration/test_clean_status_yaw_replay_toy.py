"""中文说明：N4H2G toy integration 不运行外部 KF-GINS，只验证 clean 输入和评价链路。"""

import csv
import struct

from legsa_gins.evaluation.clean_status_yaw_replay import (
    evaluate_clean_replay_against_dual_reference,
    generate_clean_process_data_input,
)
from legsa_gins.evaluation.clean_vs_noisy_replay_comparison import compare_clean_vs_noisy_replay


def _frame(vn: int, ve: int, vd: int, sacc: int) -> bytes:
    frame = bytearray(100)
    frame[:6] = bytes([0xB5, 0x62, 0x01, 0x07, 0x5C, 0x00])
    frame[54:58] = struct.pack("<i", vn)
    frame[58:62] = struct.pack("<i", ve)
    frame[62:66] = struct.pack("<i", vd)
    frame[68:72] = struct.pack("<I", sacc)
    return bytes(frame)


def _write_toy_sources(root, base_time=1772784000.0):
    fix = root / "fix"
    fix.mkdir()
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
    for name in ["gnss1", "gnss2"]:
        with (fix / f"{name}-status.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=header)
            writer.writeheader()
            for index in range(5):
                stamp = base_time + index * 0.1
                secs = int(stamp)
                nsecs = int(round((stamp - secs) * 1.0e9))
                writer.writerow(
                    {
                        "Time": f"{stamp:.9f}",
                        "header.stamp.secs": secs,
                        "header.stamp.nsecs": nsecs,
                        "pos_lat": 40.0,
                        "pos_lon": 116.0,
                        "pos_height": 10.0,
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
        writer = csv.DictWriter(handle, fieldnames=["Time", "stamp.secs", "stamp.nsecs", "protocol", "data", "name"])
        writer.writeheader()
        for index in range(2):
            stamp = base_time + index * 0.2
            secs = int(stamp)
            nsecs = int(round((stamp - secs) * 1.0e9))
            writer.writerow(
                {
                    "Time": f"{stamp:.9f}",
                    "stamp.secs": secs,
                    "stamp.nsecs": nsecs,
                    "protocol": "UBX",
                    "data": repr(_frame(100, 0, 0, 300)),
                    "name": "UBX-NAV-PVT",
                }
            )
    body = root / "by2.txt"
    body.write_text(
        "\n---\n".join(
            [
                "\n".join(
                    [
                        "stamp:",
                        f"  sec: {int(base_time + index * 0.01)}",
                        "  nanosec: 0",
                        "imu_state:",
                        "  gyroscope: [0.0, 0.0, 0.0]",
                        "  accelerometer: [0.0, 0.0, -9.8]",
                    ]
                )
                for index in range(3)
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return fix, body


def test_clean_status_yaw_replay_toy(tmp_path) -> None:
    fix, body = _write_toy_sources(tmp_path)
    out = tmp_path / "clean"
    generated = generate_clean_process_data_input(fix, body, out)
    manifest = generated["manifest"]
    assert manifest["yaw_noise_std_deg"] == 0.0
    assert manifest["outlier_mode"] == "none"
    assert manifest["enable_outage"] is False

    nav = out / "KF_GINS_Navresult.nav"
    nav.write_text("0 0 40 116 10 0 0 0 0 0 10\n0 1 40 116 10 0 0 0 0 0 10\n", encoding="utf-8")
    reference = [
        {"timestamp": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 10.0},
        {"timestamp": 1.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 10.0},
    ]
    evaluation = evaluate_clean_replay_against_dual_reference(nav, reference, out)
    summary = evaluation["clean_replay_summary"]
    assert summary["yaw_gate_pass"] is True
    comparison = compare_clean_vs_noisy_replay(clean_summary=summary, noisy_summary={"horizontal_rmse_m": 0.0, "up_rmse_m": 0.0, "yaw_rmse_deg": 93.0})
    assert comparison["clean_replay_parity_status"] == "passed"
    assert comparison["trace_solver_input"] is False
