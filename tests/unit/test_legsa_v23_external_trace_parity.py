from pathlib import Path

from legsa_gins.evaluation.legsa_v23_external_trace_parity import (
    compare_legsa_to_external_nav,
    locate_first_divergence,
)


"""中文说明：external trace parity 单测只做离线对齐和发散阈值判断。"""


def _write_nav(path: Path, lat_offset: float = 0.0, yaw: float = 0.0) -> None:
    path.write_text(
        "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n"
        + "\n".join(f"{i}.0,{31.0 + lat_offset},121.0,10.0,0,0,0,0,0,{yaw}" for i in range(3))
        + "\n",
        encoding="utf-8",
    )


def test_external_trace_aligns_and_detects_diff(tmp_path: Path):
    legsa = tmp_path / "legsa.csv"
    external = tmp_path / "external.csv"
    _write_nav(legsa, lat_offset=0.00002, yaw=8.0)
    _write_nav(external, yaw=0.0)
    report = compare_legsa_to_external_nav(legsa, external)
    assert report["aligned_count"] == 3
    assert report["full_diff"]["horizontal_rmse_m"] > 1.0
    divergence = locate_first_divergence(report["diff_series"], first_update_time=0.5)
    assert divergence["first_H_gt_1m_time"] == 0.0
