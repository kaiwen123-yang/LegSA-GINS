"""中文说明：clean/noisy replay comparison 只做 toy 指标分类。"""

from legsa_gins.evaluation.clean_vs_noisy_replay_comparison import (
    classify_clean_replay_parity,
    compare_clean_vs_noisy_replay,
)


def test_clean_replay_parity_classification() -> None:
    base = {"horizontal_rmse_m": 0.3, "up_rmse_m": 0.8, "yaw_rmse_deg": 1.9}
    assert classify_clean_replay_parity(base) == "passed"
    assert classify_clean_replay_parity({**base, "yaw_rmse_deg": 2.06}) == "near_gate"
    assert classify_clean_replay_parity({**base, "yaw_rmse_deg": 2.3}) == "failed_yaw"
    assert classify_clean_replay_parity({**base, "horizontal_rmse_m": 2.5}) == "failed_position_or_up"


def test_noisy_artifact_not_called_clean() -> None:
    report = compare_clean_vs_noisy_replay(
        clean_summary={"horizontal_rmse_m": 0.3, "up_rmse_m": 0.8, "yaw_rmse_deg": 1.9},
        noisy_summary={"horizontal_rmse_m": 0.35, "up_rmse_m": 0.79, "yaw_rmse_deg": 1.98},
    )
    assert report["clean_replay_parity_status"] == "passed"
    assert report["noisy_artifact_has_gaussian_yaw_noise"] is True
    assert report["clean_input_has_synthetic_yaw_noise"] is False
    assert report["noisy_artifact_clean_nominal_claim_allowed"] is False
    assert report["trace_solver_input"] is False
    assert report["numerical_performance_claim"] is False
