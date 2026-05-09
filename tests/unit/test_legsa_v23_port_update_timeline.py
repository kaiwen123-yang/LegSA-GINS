"""中文说明：测试 R3A runtime loop trace 分类。"""

from pathlib import Path

from legsa_gins.evaluation.legsa_v23_port_update_timeline import analyze_runtime_loop_trace


def test_detects_overwritten_gnss(tmp_path: Path):
    trace = tmp_path / "loop.csv"
    skipped = tmp_path / "skipped.csv"
    trace.write_text(
        "loop_index,imu_pre_time,imu_cur_time,current_gnss_time_before_loop,"
        "current_gnss_time_after_refresh,gnss_refresh_count_this_loop,gnss_added_time,"
        "gnss_valid_before_newImuProcess,isToUpdate_res,update_applied,update_type,"
        "timestamp_after_process,nav_written,gnss_eof,imu_eof\n"
        "0,0,1,0.5,1.5,1,1.5,1,0,0,none,1,1,0,0\n",
        encoding="utf-8",
    )
    skipped.write_text(
        "gnss_time,reason,nearest_imu_pre_time,nearest_imu_cur_time\n"
        "0.5,overwritten_before_update,0,1\n",
        encoding="utf-8",
    )
    report = analyze_runtime_loop_trace(trace, skipped)
    assert report["overwritten_before_update_count"] == 1


def test_actual_count_matching_overlap_not_naive_total(tmp_path: Path):
    trace = tmp_path / "loop.csv"
    trace.write_text(
        "loop_index,imu_pre_time,imu_cur_time,current_gnss_time_before_loop,"
        "current_gnss_time_after_refresh,gnss_refresh_count_this_loop,gnss_added_time,"
        "gnss_valid_before_newImuProcess,isToUpdate_res,update_applied,update_type,"
        "timestamp_after_process,nav_written,gnss_eof,imu_eof\n"
        "0,0,1,0.5,0.5,0,0.5,1,3,1,position_velocity_yaw,1,1,0,0\n",
        encoding="utf-8",
    )
    report = analyze_runtime_loop_trace(trace)
    assert report["update_applied_count"] == 1
    assert report["res_counts"]["3"] == 1
