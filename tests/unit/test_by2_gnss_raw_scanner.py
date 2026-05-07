"""中文说明：BY2 raw scanner 测试只统计 message name，不解析 Doppler、伪距或载波相位。
"""

import csv

from legsa_gins.datasets.by2.gnss_raw_scanner import scan_gnss_raw_csv


def test_scan_raw_messages_without_observable_extraction(tmp_path):
    path = tmp_path / "gnss1-raw.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Time", "name", "info", "protocol", "seq"])
        writer.writeheader()
        writer.writerow(
            {
                "Time": "1700000000",
                "name": "UBX-NAV-PVT",
                "info": "sample",
                "protocol": "UBX",
                "seq": "1",
            }
        )
        writer.writerow(
            {
                "Time": "1700000001",
                "name": "UBX-NAV-HPPOSECEF",
                "info": "sample",
                "protocol": "UBX",
                "seq": "2",
            }
        )

    summary = scan_gnss_raw_csv(path, source_name="gnss1")

    assert summary["message_counts"]["UBX-NAV-PVT"] == 1
    assert summary["message_counts"]["UBX-NAV-HPPOSECEF"] == 1
    assert summary["raw_doppler_extracted"] is False
    assert summary["carrier_phase_extracted"] is False
    assert summary["raw_pseudorange_extracted"] is False
