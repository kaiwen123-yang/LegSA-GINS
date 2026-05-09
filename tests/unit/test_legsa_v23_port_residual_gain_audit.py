"""中文说明：测试 residual/gain 过强更新诊断。"""

from pathlib import Path

from legsa_gins.evaluation.legsa_v23_port_residual_gain_audit import analyze_residual_gain


def test_detects_over_tight_update(tmp_path):
    trace = tmp_path / "trace.csv"
    trace.write_text(
        "update_index,gnss_time,pos_residual_norm,vel_residual_norm,yaw_residual_deg,R_pos_trace,"
        "R_vel_trace,R_yaw,K_pos_norm,K_vel_norm,K_yaw_norm,cov_trace_before,cov_trace_after,"
        "dx_pos_norm,dx_vel_norm,dx_phi_norm_deg,yaw_mode\n"
        "1,1,0.01,0.01,0.1,0.000001,0.000001,0.000000001,20,1,1,10,9,0.1,0.1,0.1,NORMAL\n",
        encoding="utf-8",
    )
    report = analyze_residual_gain(trace)
    assert report["over_tight_measurement_update_suspect"] is True
    assert report["K_too_large_suspect"] is True


def test_detects_nav_hugs_measurement_suspect(tmp_path):
    trace = tmp_path / "trace.csv"
    trace.write_text(
        "update_index,gnss_time,pos_residual_norm,vel_residual_norm,yaw_residual_deg,R_pos_trace,"
        "R_vel_trace,R_yaw,K_pos_norm,K_vel_norm,K_yaw_norm,cov_trace_before,cov_trace_after,"
        "dx_pos_norm,dx_vel_norm,dx_phi_norm_deg,yaw_mode\n"
        "1,1,0.01,0.01,0.1,1,1,1,,,,10,9,,,,NORMAL\n",
        encoding="utf-8",
    )
    report = analyze_residual_gain(trace)
    assert report["nav_hugs_measurement_suspect"] is True
    assert report["K_evidence_missing"] is True
