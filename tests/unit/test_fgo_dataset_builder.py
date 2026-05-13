import csv
from pathlib import Path

from legsa_gins.fgo.fgo_dataset_builder import build_n8a_dataset


def test_dataset_builder_reads_selected_variant(tmp_path: Path) -> None:
    """中文说明：dataset builder 从 N7C6 selected runtime state 构建节点。"""
    path = tmp_path / "variants" / "joint_rp1deg_hv1p0" / "EVAL_NAV.csv"
    path.parent.mkdir(parents=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["time", "lat_deg", "lon_deg", "height_m", "roll_deg", "pitch_deg", "yaw_deg", "vn", "ve", "vd"])
        writer.writeheader()
        writer.writerow({"time": 0, "lat_deg": 1, "lon_deg": 2, "height_m": 3, "roll_deg": 0, "pitch_deg": 0, "yaw_deg": 0, "vn": 1, "ve": 0, "vd": 0})
    dataset, report = build_n8a_dataset(n7c6_root=tmp_path)
    assert dataset.state_count == 1
    assert report["trace_based_selection"] is False
