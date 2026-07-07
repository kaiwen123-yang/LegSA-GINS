import csv

from legsa_gins.da_repro.raw_csv_schema_probe import probe_raw_csv
from legsa_gins.raw_gnss.ubx_raw_binary_rebuilder import ubx_checksum


def _frame(msg_class: int = 0x02, msg_id: int = 0x15, payload: bytes = b"") -> bytes:
    body = bytes([msg_class, msg_id]) + len(payload).to_bytes(2, "little") + payload
    ck_a, ck_b = ubx_checksum(body)
    return b"\xb5\x62" + body + bytes([ck_a, ck_b])


def test_raw_csv_schema_detects_ubx_rawx(tmp_path):
    path = tmp_path / "gnss1-raw.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Time", "protocol", "data", "name", "seq", "info"])
        writer.writeheader()
        writer.writerow({"Time": "1.0", "protocol": "4", "data": repr(_frame()), "name": "UBX-RXM-RAWX", "seq": "1", "info": ""})
    report = probe_raw_csv(path)
    assert report["exists"] is True
    assert report["has_ubx_bytes"] is True
    assert report["rawx_frame_count"] == 1
    assert report["message_counts"]["UBX-RXM-RAWX"] == 1
