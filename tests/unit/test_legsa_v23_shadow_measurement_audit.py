from pathlib import Path

from legsa_gins.evaluation.legsa_v23_shadow_measurement_audit import build_shadow_measurement_residuals


"""中文说明：shadow measurement 单测确认 external NAV 不作为 solver 输入。"""


def test_shadow_external_small_internal_large_state_diverges(tmp_path: Path):
    nav = tmp_path / "external.csv"
    nav.write_text(
        "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n"
        "0.0,31.0,121.0,10.0,0,0,0,0,0,10.0\n",
        encoding="utf-8",
    )
    gnss = tmp_path / "clean.gnss"
    gnss.write_text("0.0 31.0 121.0 10.0 1 1 1 0 0 0 1 1 1 10.0 1.5\n", encoding="utf-8")
    updates = tmp_path / "ALL_UPDATES.csv"
    updates.write_text("position_residual_norm,velocity_residual_norm,yaw_scheme_mode\n50,20,REJECT\n", encoding="utf-8")
    report = build_shadow_measurement_residuals(nav, gnss, updates)
    assert report["measurement_model_likely_ok_state_diverges"] is True
    assert report["shadow_external_nav_solver_input"] is False


def test_shadow_external_large_marks_measurement_issue(tmp_path: Path):
    nav = tmp_path / "external.csv"
    nav.write_text(
        "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n"
        "0.0,31.1,121.0,10.0,0,0,0,0,0,60.0\n",
        encoding="utf-8",
    )
    gnss = tmp_path / "clean.gnss"
    gnss.write_text("0.0 31.0 121.0 10.0 1 1 1 0 0 0 1 1 1 10.0 1.5\n", encoding="utf-8")
    report = build_shadow_measurement_residuals(nav, gnss)
    assert report["measurement_model_or_convention_issue"] is True
