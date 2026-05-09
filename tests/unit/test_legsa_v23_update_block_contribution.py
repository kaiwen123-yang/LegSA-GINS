from pathlib import Path

from legsa_gins.evaluation.legsa_v23_update_block_contribution import analyze_update_block_trace


"""中文说明：update-block 单测定位哪个量测块贡献过大 dx_phi。"""


def test_update_block_detects_block_overdrive_and_feedback_spike(tmp_path: Path):
    blocks = tmp_path / "UPDATE_BLOCK_TRACE.csv"
    blocks.write_text(
        "update_index,block_type,gnss_time,dz_norm,dz_0,dz_1,dz_2,H_norm,R_trace,S_condition_estimate,K_norm,"
        "dx_before_norm,dx_after_norm,dx_delta_norm,dx_delta_pos_norm,dx_delta_vel_norm,dx_delta_phi_norm_deg,"
        "cov_trace_before,cov_trace_after,cov_min_diag_before,cov_min_diag_after,accepted,yaw_scheme_mode\n"
        "1,position,1.0,1,0,0,0,1,1,1,2,0,10,10,1,1,8,1,1,1,1,true,NONE\n"
        "1,velocity,1.0,1,0,0,0,1,1,1,2,0,1,1,1,1,0.1,1,1,1,1,true,NONE\n",
        encoding="utf-8",
    )
    feedback = tmp_path / "FEEDBACK_DELTA_TRACE.csv"
    feedback.write_text(
        "update_index,gnss_time,dx_pos_norm_before,dx_vel_norm_before,dx_phi_norm_deg_before,pos_delta_ned_norm,"
        "vel_delta_norm,phi_delta_deg_norm,roll_before,pitch_before,yaw_before,roll_after,pitch_after,yaw_after,"
        "roll_delta,pitch_delta,yaw_delta,bias_delta_norm,scale_delta_norm,dx_reset_after_feedback\n"
        "1,1.0,0,0,8,0,0,8,0,0,0,8,0,0,8,0,0,0,0,true\n",
        encoding="utf-8",
    )
    report = analyze_update_block_trace(blocks, feedback)
    assert report["position_block_overdrives_attitude"] is True
    assert report["feedback_applies_large_phi"] is True
    assert report["feedback_reset_ok"] is True
