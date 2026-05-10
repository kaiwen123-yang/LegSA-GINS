import csv
from pathlib import Path

from legsa_gins.raw_gnss.ubx_raw_message_scanner import scan_fix_root

# 中文说明：测试 scanner 明确区分 NAV-PVT 和 RAWX。

def test_raw_gnss_message_scanner_distinguishes_pvt_and_rawx(tmp_path: Path):
    path = tmp_path / "gnss1-raw.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Time", "protocol", "data", "name", "seq", "info"])
        writer.writeheader()
        writer.writerow({"Time": "1", "protocol": "4", "data": "b''", "name": "UBX-NAV-PVT", "seq": "1", "info": ""})
        writer.writerow({"Time": "2", "protocol": "4", "data": "b''", "name": "UBX-RXM-RAWX", "seq": "2", "info": ""})
        writer.writerow({"Time": "3", "protocol": "4", "data": "b''", "name": "UBX-RXM-SFRBX", "seq": "3", "info": ""})
    (tmp_path / "corr-raw.csv").write_text("Time,protocol,data,name,seq,info\n4,5,b'',RTCM3-TYPE1074,4,\n", encoding="utf-8")
    report = scan_fix_root(tmp_path)
    assert report["nav_pvt_found"] is True
    assert report["rawx_found"] is True
    assert report["sfrbx_found"] is True
    assert report["rtcm_found"] is True
    assert report["pvt_velocity_not_raw_doppler"] is True
