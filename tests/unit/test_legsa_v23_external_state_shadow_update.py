from pathlib import Path

from legsa_gins.evaluation.legsa_v23_external_state_shadow_update import run_external_state_shadow_update


"""中文说明：external-state shadow update 单测确认 external NAV 不进入 solver。"""


def test_external_state_dx_small_internal_dx_huge_means_state_divergence(tmp_path: Path):
    nav = tmp_path / "external.csv"
    nav.write_text(
        "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n"
        "0.0,31.0,121.0,10.0,0,0,0,0,0,10\n",
        encoding="utf-8",
    )
    gnss = tmp_path / "clean.gnss"
    gnss.write_text("0.0 31.0 121.0 10.0 1 1 1 0 0 0 1 1 1 10 1.5\n", encoding="utf-8")
    updates = tmp_path / "ALL_UPDATES.csv"
    updates.write_text(
        "position_residual_norm,velocity_residual_norm,yaw_scheme_mode,K_norm_pos,K_norm_vel,K_norm_yaw,"
        "dx_phi_norm_deg,dx_pos_norm,dx_vel_norm,cov_trace_after,cov_min_diag_after,state_feedback_applied\n"
        "100,50,REJECT,1,1,1,30,0,0,1,1,true\n",
        encoding="utf-8",
    )
    report = run_external_state_shadow_update(nav, gnss, tmp_path / "COVARIANCE_TRACE.csv", updates)
    assert report["large_dx_caused_by_state_divergence"] is True
    assert report["shadow_external_nav_solver_input"] is False


def test_external_state_dx_huge_means_gain_or_measurement_scaling(tmp_path: Path):
    nav = tmp_path / "external.csv"
    nav.write_text(
        "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n"
        "0.0,31.0,121.0,10.0,0,0,0,0,0,80\n",
        encoding="utf-8",
    )
    gnss = tmp_path / "clean.gnss"
    gnss.write_text("0.0 31.0 121.0 10.0 1 1 1 0 0 0 1 1 1 10 1.5\n", encoding="utf-8")
    report = run_external_state_shadow_update(nav, gnss, tmp_path / "COVARIANCE_TRACE.csv")
    assert report["gain_or_measurement_scaling_issue"] is True
