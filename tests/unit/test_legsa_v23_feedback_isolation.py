from legsa_gins.evaluation.legsa_v23_feedback_isolation import classify_feedback_matrix


"""中文说明：feedback isolation 单测确认 variant 只生成 diagnostic 判断。"""


def _report(h: float, up: float, yaw: float, roll: float, pitch: float):
    return {"summary": {"horizontal_rmse_m": h, "up_rmse_m": up, "yaw_rmse_deg": yaw, "roll_rmse_deg": roll, "pitch_rmse_deg": pitch}}


def test_feedback_matrix_detects_no_attitude_feedback_improvement():
    matrix = {
        "baseline_current": _report(100, 50, 90, 100, 40),
        "no_attitude_feedback": _report(90, 40, 80, 20, 10),
        "inflate_measurement_R_10x": _report(100, 50, 90, 100, 40),
    }
    report = classify_feedback_matrix(matrix)
    assert report["attitude_feedback_primary_issue"] is True
    assert report["diagnostic_only"] is True
    assert report["numerical_performance_claim"] is False


def test_feedback_matrix_detects_r_inflation_candidate():
    matrix = {
        "baseline_current": _report(100, 50, 90, 100, 40),
        "inflate_measurement_R_10x": _report(100, 50, 20, 40, 30),
    }
    report = classify_feedback_matrix(matrix)
    assert report["gain_or_R_scaling_issue"] is True
