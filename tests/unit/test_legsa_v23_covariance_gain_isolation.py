from pathlib import Path

from legsa_gins.evaluation.legsa_v23_covariance_gain_isolation import analyze_covariance_gain_trace


"""中文说明：covariance/gain 单测检测 K spike、R scaling 和 P_phi 可疑。"""


def test_covariance_gain_detects_spike_and_unit_audit_need(tmp_path: Path):
    cov = tmp_path / "COVARIANCE_TRACE.csv"
    cov.write_text(
        "time,event_type,cov_trace,cov_min_diag,cov_max_diag,P_pos_trace,P_vel_trace,P_phi_trace,P_bg_trace,P_ba_trace,K_norm_if_update,dx_phi_norm_deg_if_update\n"
        "0,update_position,10,1e-6,1,1,1,0.2,1,1,80,12\n",
        encoding="utf-8",
    )
    blocks = tmp_path / "UPDATE_BLOCK_TRACE.csv"
    blocks.write_text(
        "update_index,block_type,gnss_time,K_norm,dx_delta_phi_norm_deg,R_trace,S_condition_estimate\n"
        "1,position,1.0,80,12,1,100\n",
        encoding="utf-8",
    )
    report = analyze_covariance_gain_trace(cov, blocks)
    assert report["gain_spike_drives_feedback"] is True
    assert report["attitude_covariance_too_large"] is True
    assert report["covariance_model_needs_unit_parity_audit"] is True
