"""中文说明：N4H2G2 fresh summary recomputation 不使用旧 summary。"""

from pathlib import Path

from legsa_gins.evaluation.clean_replay_fresh_summary_audit import recompute_clean_summary_from_nav


def test_fresh_summary_does_not_use_old_summary(tmp_path: Path) -> None:
    nav = tmp_path / "KF_GINS_Navresult.nav"
    nav.write_text("0 0 40 116 10 0 0 0 0 0 10\n0 1 40 116 10 0 0 0 0 0 10\n", encoding="utf-8")
    reference = [
        {"timestamp": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 10.0},
        {"timestamp": 1.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 10.0},
    ]
    old = tmp_path / "CLEAN_REPLAY_SUMMARY.json"
    old.write_text('{"horizontal_rmse_m": 99, "up_rmse_m": 99, "yaw_rmse_deg": 99, "roll_rmse_deg": 99, "pitch_rmse_deg": 99}\n', encoding="utf-8")
    report = recompute_clean_summary_from_nav(nav, reference, tmp_path / "out", old_clean_summary_path=old)
    assert report["fresh_summary_computed"] is True
    assert report["old_clean_summary_used_as_input"] is False
    assert report["fresh_summary"]["yaw_rmse_deg"] == 0.0
    assert (tmp_path / "out" / "CLEAN_REPLAY_FRESH_SUMMARY.json").exists()
    assert report["output_only_correction"] is False
