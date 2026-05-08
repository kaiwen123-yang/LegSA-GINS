"""中文说明：N4H4D1 update isolation matrix 单元测试。"""

from legsa_gins.evaluation.legsa_v23_update_isolation_matrix import classify_isolation_matrix


def _variant(horizontal=0.0, roll=0.0, pitch=0.0, yaw=0.0):
    return {"summary": {"horizontal_rmse_m": horizontal, "roll_rmse_deg": roll, "pitch_rmse_deg": pitch, "yaw_rmse_deg": yaw}}


def test_isolation_detects_propagation_only_explosion():
    report = classify_isolation_matrix(
        {
            "propagation_only": _variant(horizontal=100.0, roll=30.0, pitch=2.0),
            "all_updates_current": _variant(horizontal=120.0),
            "all_updates_no_state_feedback": _variant(horizontal=110.0),
        }
    )
    assert "likely_mechanization_or_initialization_issue" in report["divergence_categories"]
    assert report["diagnostic_only"] is True
    assert report["numerical_performance_claim"] is False


def test_isolation_detects_update_or_feedback_explosion():
    report = classify_isolation_matrix(
        {
            "propagation_only": _variant(horizontal=2.0),
            "all_updates_current": _variant(horizontal=100.0),
            "all_updates_no_state_feedback": _variant(horizontal=2.0),
        }
    )
    assert "likely_state_feedback_sign_issue" in report["divergence_categories"]

