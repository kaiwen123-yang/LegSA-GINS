"""中文说明：单测滑动窗口只使用当前及历史 epoch，不使用未来数据。"""

from legsa_gins.fgo_feedback.feedback_state_types import NavStateSample
from legsa_gins.fgo_feedback.sliding_window_manager import build_sliding_windows


def test_sliding_window_uses_no_future_data():
    samples = [NavStateSample(float(i), 30.0, 120.0, 10.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0) for i in range(8)]
    windows, report = build_sliding_windows(samples, candidate_feedback_times=[0, 1, 2, 3, 4, 5], window_duration_s=2.0)
    assert windows
    assert report["no_future_data_verified"] is True
    assert all(samples[index].time <= window.feedback_time for window in windows for index in window.sample_indices)
