"""中文说明：N4H4D3 guarded formula source audit 单元测试。"""

from pathlib import Path

from legsa_gins.evaluation.legsa_v23_guarded_formula_fix_audit import audit_guarded_fix_source


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_guarded_formula_audit_detects_source_backed_formulas():
    report = audit_guarded_fix_source(REPO_ROOT)
    assert report["DR_height_sign_correct"] is True
    assert report["position_H_phi_fixed"] is True
    assert report["EKFUpdate_residual_sign_correct"] is True
    assert report["pos_vel_feedback_minus"] is True
    assert report["state_feedback_phi_left_multiply"] is True
    assert report["state_feedback_phi_positive"] is True
    assert report["bias_scale_feedback_plus"] is True
    assert report["dx_reset_after_feedback"] is True
    assert report["yaw_H_mapping_not_fixed_in_D3"] is True
    assert report["source_backed_fix_applied"] is True

