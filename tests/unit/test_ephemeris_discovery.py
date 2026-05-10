from pathlib import Path

from legsa_gins.raw_gnss.ephemeris_discovery import discover_ephemeris

# 中文说明：测试 BY2 日期星历候选排序。

def test_ephemeris_discovery_ranks_by2_broadcast_nav(tmp_path: Path):
    nav = tmp_path / "BRDC00IGS_R_20260650000_01D_MN.rnx.gz"
    nav.write_text("toy", encoding="utf-8")
    sp3 = tmp_path / "WUM0MGXFIN_20260650000_01D_05M_ORB.SP3"
    sp3.write_text("toy", encoding="utf-8")
    report = discover_ephemeris([tmp_path])
    assert report["candidate_count"] == 2
    assert report["ephemeris_available"] is True
    assert report["by2_date_match"] is True
    assert report["best_broadcast_nav_candidate"].endswith(nav.name)
