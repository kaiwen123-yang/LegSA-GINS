"""中文说明：单测 covariance policy 只放大 R，不做 R shrink。"""

from legsa_gins.fgo_feedback.feedback_state_types import NavStateSample
from legsa_gins.fgo_feedback.fgo_feedback_covariance_policy import apply_conservative_covariance_policy
from legsa_gins.fgo_feedback.fgo_feedback_observation import build_feedback_observations
from legsa_gins.fgo_feedback.sliding_window_manager import build_sliding_windows


def test_covariance_policy_inflates_without_shrink():
    samples = [NavStateSample(float(i), 30.0, 120.0, 10.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0) for i in range(5)]
    windows, _ = build_sliding_windows(samples, candidate_feedback_times=[s.time for s in samples], window_duration_s=2.0)
    obs, _ = build_feedback_observations(samples, windows)
    adjusted, report = apply_conservative_covariance_policy(obs, residual_proxy_p95=5.0)
    assert adjusted[0].std_vN >= obs[0].std_vN
    assert report["no_R_shrink"] is True
