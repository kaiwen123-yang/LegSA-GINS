import csv
import struct
from pathlib import Path

from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import ubx_checksum
from legsa_gins.raw_gnss.ubx_rawx_parser import parse_rawx_from_csv, report_measurements

# 中文说明：测试 RAWX parser 提取卫星级 doMes，不使用 NAV-PVT velocity。

def make_ubx(msg_class: int, msg_id: int, payload: bytes) -> bytes:
    header = bytes([msg_class, msg_id]) + len(payload).to_bytes(2, "little") + payload
    ck_a, ck_b = ubx_checksum(header)
    return b"\xb5\x62" + header + bytes([ck_a, ck_b])


def make_rawx_frame() -> bytes:
    head = struct.pack("<dHbbBBH", 460873.998, 2408, 18, 1, 1, 0, 0)
    meas = struct.pack("<ddfBBBBHBBBBBB", 2.1e7, 1.1e5, -1234.5, 0, 3, 0, 0, 10, 45, 1, 1, 1, 7, 0)
    return make_ubx(0x02, 0x15, head + meas)


def test_ubx_rawx_parser_extracts_domes(tmp_path: Path):
    csv_path = tmp_path / "gnss1-raw.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Time", "protocol", "data", "name", "seq", "info"])
        writer.writeheader()
        writer.writerow({"Time": "10.0", "protocol": "4", "data": repr(make_rawx_frame()), "name": "UBX-RXM-RAWX", "seq": "1", "info": ""})
    measurements = parse_rawx_from_csv(csv_path)
    report = report_measurements(measurements)
    assert report["rawx_epoch_count"] == 1
    assert report["doppler_measurement_count"] == 1
    assert report["doMes_valid_count"] == 1
    assert report["wavelength_resolved_count"] == 1
