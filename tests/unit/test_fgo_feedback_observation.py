"""中文说明：单测 feedback observation builder 输出 runtime-only 观测字段。"""

from legsa_gins.fgo_feedback.feedback_state_types import NavStateSample
from legsa_gins.fgo_feedback.fgo_feedback_observation import build_feedback_observations, local_ned_from_sample
from legsa_gins.fgo_feedback.sliding_window_manager import build_sliding_windows


def test_feedback_observation_builder_outputs_runtime_columns():
    samples = [
        NavStateSample(float(i), 30.0 + i * 1e-6, 120.0, 10.0, 1.0 + 0.1 * i, 0.0, 0.0, 0.1 * i, 0.0, 5.0)
        for i in range(6)
    ]
    windows, _ = build_sliding_windows(samples, candidate_feedback_times=[s.time for s in samples], window_duration_s=2.0)
    observations, report = build_feedback_observations(samples, windows)
    assert observations
    assert report["no_output_substitution"] is True
    assert local_ned_from_sample(samples[1], samples[0])[0] > 0
