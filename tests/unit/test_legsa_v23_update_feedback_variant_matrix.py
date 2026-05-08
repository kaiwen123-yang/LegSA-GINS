"""中文说明：N4H4D2 update-feedback variant matrix 单元测试。"""

from legsa_gins.evaluation.legsa_v23_update_feedback_variant_matrix import classify_variant_matrix


def test_variant_matrix_identifies_best_candidate_and_diagnostic_only():
    baseline = {"horizontal_rmse_m": 500.0, "up_rmse_m": 50.0, "yaw_rmse_deg": 90.0, "roll_rmse_deg": 90.0, "pitch_rmse_deg": 30.0}
    good = {"horizontal_rmse_m": 20.0, "up_rmse_m": 5.0, "yaw_rmse_deg": 20.0, "roll_rmse_deg": 10.0, "pitch_rmse_deg": 5.0}
    report = classify_variant_matrix(
        {
            "baseline_current": {"summary": baseline},
            "position_H_phi_sign_flip": {"summary": good},
            "yaw_H_sign_flip": {"summary": baseline},
        }
    )
    assert report["candidate_fix_detected"] is True
    assert report["candidate_fix_variant"] == "position_H_phi_sign_flip"
    assert report["diagnostic_only"] is True
    assert report["numerical_performance_claim"] is False

