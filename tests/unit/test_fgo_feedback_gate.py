"""中文说明：单测 feedback gate 的 accepted/rejected 计数合同。"""

from legsa_gins.fgo_feedback.feedback_state_types import NavStateSample
from legsa_gins.fgo_feedback.fgo_feedback_gate import apply_feedback_gate
from legsa_gins.fgo_feedback.fgo_feedback_observation import build_feedback_observations
from legsa_gins.fgo_feedback.sliding_window_manager import build_sliding_windows


def test_feedback_gate_accepts_nominal_and_reject_all_sanity():
    samples = [NavStateSample(float(i), 30.0, 120.0, 10.0, 1.0 + 0.01 * i, 0.0, 0.0, 0.0, 0.0, 2.0) for i in range(7)]
    windows, _ = build_sliding_windows(samples, candidate_feedback_times=[s.time for s in samples], window_duration_s=3.0)
    obs, _ = build_feedback_observations(samples, windows)
    _, report = apply_feedback_gate(obs, samples)
    assert report["accept_count"] > 0
    _, reject_report = apply_feedback_gate(obs, samples, reject_all=True)
    assert reject_report["reject_reasons"]["reject_all_sanity"] == len(obs)
