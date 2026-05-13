from legsa_gins.fgo.fgo_no_feedback_smoother import run_no_feedback_smoother
from legsa_gins.fgo.fgo_state_types import FGOState, FGOStateDataset


def test_no_feedback_smoother_boundary() -> None:
    """中文说明：smoother 输出不得反馈 EKF 或替换 EKF NAV。"""
    rows, report = run_no_feedback_smoother(FGOStateDataset([FGOState(0, 0.0), FGOState(1, 1.0)]))
    assert len(rows) == 2
    assert report["fgo_output_feedback_to_ekf"] is False
    assert report["fgo_output_replaces_ekf_nav"] is False
