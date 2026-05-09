from pathlib import Path

from legsa_gins.evaluation.legsa_v23_runtime_loop_parity import compare_update_timeline


"""中文说明：runtime loop parity 单测只检查 GNSS 行计数和 update_count_low。"""


def test_runtime_loop_detects_missed_updates(tmp_path: Path):
    gnss = tmp_path / "input.gnss"
    gnss.write_text("\n".join(f"{i} 0 0 0 1 1 1 0 0 0 1 1 1 0 1" for i in range(10)) + "\n", encoding="utf-8")
    updates = tmp_path / "ALL_UPDATES.csv"
    updates.write_text("gnss_time,isToUpdate_res\n0,3\n1,3\n", encoding="utf-8")
    loop = {"gnss_rows_seen": 10, "gnss_updates_applied": 2}
    report = compare_update_timeline(gnss, loop, updates)
    assert report["update_count_low"] is True
    assert report["gnss_rows_skipped_unexpectedly"] is True
