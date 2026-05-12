"""中文说明：time alignment 测试不使用 trace 估计 clock offset。"""

from legsa_gins.go2_state.go2_time_alignment import build_time_alignment_report


def test_go2_time_alignment_overlap():
    rows = [{"aligned_time": str(i * 0.01)} for i in range(100)]
    clean_times = [i * 0.01 for i in range(100)]
    report = build_time_alignment_report(rows, clean_times)
    assert report["time_alignment_ok"] is True
    assert report["expected_prior_count"] == 100
    assert report["activation_allowed"] is True
    assert report["alignment_uses_trace"] is False
