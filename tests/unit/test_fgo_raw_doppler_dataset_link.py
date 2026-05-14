"""Tests for N8C3 Raw Doppler dataset linking.

中文说明：验证 Raw Doppler CSV 能对齐生成 FGO factor table rows。
"""

import csv
from pathlib import Path

from legsa_gins.fgo.fgo_raw_doppler_dataset_link import link_raw_doppler_to_fgo_epochs


def test_raw_doppler_dataset_link_creates_aligned_rows(tmp_path: Path) -> None:
    csv_path = tmp_path / "RAW_DOPPLER_VELOCITY_FACTORS.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "vn", "ve", "vd", "std_vn", "std_ve", "std_vd"])
        writer.writeheader()
        for index in range(3):
            writer.writerow({"time": index * 0.2, "vn": 0.1, "ve": 0.2, "vd": 0.3, "std_vn": 0.2, "std_ve": 0.2, "std_vd": 0.2})
    fgo_rows = [{"index": index, "time": index * 0.2} for index in range(3)]
    factors, report = link_raw_doppler_to_fgo_epochs(fgo_rows=fgo_rows, n5b_root=tmp_path)
    assert len(factors) == 3
    assert report["aligned_factor_count"] == 3
    assert report["factor_table_rows"] == 3
    assert not report["trace_solver_input"]
