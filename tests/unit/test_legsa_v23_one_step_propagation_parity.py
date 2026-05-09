from pathlib import Path

from legsa_gins.evaluation.legsa_v23_one_step_propagation_parity import run_one_step_propagation_parity


"""中文说明：one-step parity 单测确认 external state 只是 shadow diagnostic seed。"""


def test_one_step_ok_and_not_solver_input(tmp_path: Path):
    nav = tmp_path / "external.csv"
    nav.write_text(
        "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n"
        "0.0,31.0,121.0,10.0,1,0,0,0,0,1\n"
        "0.01,31.0000000898315,121.0,10.0,1,0,0,0,0,1.01\n",
        encoding="utf-8",
    )
    report = run_one_step_propagation_parity(nav)
    assert report["one_step_mechanization_ok"] is True
    assert report["shadow_external_nav_solver_input"] is False
    assert report["numerical_performance_claim"] is False


def test_one_step_suspect_for_large_attitude_jump(tmp_path: Path):
    nav = tmp_path / "external.csv"
    nav.write_text(
        "time,lat_deg,lon_deg,height_m,vn,ve,vd,roll_deg,pitch_deg,yaw_deg\n"
        "0.0,31.0,121.0,10.0,0,0,0,0,0,1\n"
        "0.01,31.0,121.0,10.0,0,0,0,4,0,1\n",
        encoding="utf-8",
    )
    report = run_one_step_propagation_parity(nav)
    assert report["one_step_mechanization_suspect"] is True
