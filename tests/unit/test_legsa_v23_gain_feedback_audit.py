from pathlib import Path

from legsa_gins.evaluation.legsa_v23_gain_feedback_audit import analyze_gain_feedback


"""中文说明：gain/feedback 单测只检查 K、dx、covariance 诊断分类。"""


def test_gain_feedback_detects_spikes(tmp_path: Path):
    updates = tmp_path / "ALL_UPDATES.csv"
    updates.write_text(
        "K_norm_pos,K_norm_vel,K_norm_yaw,dx_phi_norm_deg,dx_pos_norm,dx_vel_norm,cov_trace_after,cov_min_diag_after,state_feedback_applied\n"
        "200,0,0,12,20,0,1,1e-20,true\n",
        encoding="utf-8",
    )
    report = analyze_gain_feedback(updates)
    assert report["kalman_gain_too_large"] is True
    assert report["feedback_overcorrection"] is True
    assert report["covariance_collapse"] is True
