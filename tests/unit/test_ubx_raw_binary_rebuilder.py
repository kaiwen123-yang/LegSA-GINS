import csv
from pathlib import Path

from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import rebuild_csv_to_ubx, ubx_checksum

# 中文说明：测试 CSV bytes literal 可重建 runtime-only UBX frame。

def make_ubx(msg_class: int, msg_id: int, payload: bytes) -> bytes:
    header = bytes([msg_class, msg_id]) + len(payload).to_bytes(2, "little") + payload
    ck_a, ck_b = ubx_checksum(header)
    return b"\xb5\x62" + header + bytes([ck_a, ck_b])


def test_ubx_raw_binary_rebuilder_writes_valid_frames(tmp_path: Path):
    frame = make_ubx(0x02, 0x13, b"\x00" * 8)
    csv_path = tmp_path / "gnss1-raw.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Time", "protocol", "data", "name", "seq", "info"])
        writer.writeheader()
        writer.writerow({"Time": "1", "protocol": "4", "data": repr(frame), "name": "UBX-RXM-SFRBX", "seq": "1", "info": ""})
    report = rebuild_csv_to_ubx(csv_path, tmp_path / "out.ubx")
    assert report["rebuilt_ubx_available"] is True
    assert report["frame_count"] == 1
    assert report["sfrbx_frame_count"] == 1
