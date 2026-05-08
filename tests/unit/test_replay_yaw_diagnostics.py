"""中文说明：replay yaw diagnostics 测试只用 toy input/nav/error。"""

from pathlib import Path

from legsa_gins.evaluation.replay_yaw_diagnostics import compare_input_yaw_to_replay_nav


def _write_input(path: Path, yaw: float) -> None:
    path.write_text(
        "\n".join(f"{i} 0 0 0 1 1 1 0 0 0 1 1 1 {yaw} 1.5" for i in range(20)) + "\n",
        encoding="utf-8",
    )


def _write_nav(path: Path, yaw: float) -> None:
    path.write_text(
        "timestamp,lat_deg,lon_deg,height_m,vn_mps,ve_mps,vd_mps,roll_deg,pitch_deg,yaw_deg,status,source_role\n"
        + "\n".join(f"{i},0,0,0,0,0,0,0,0,{yaw},baseline,baseline" for i in range(20))
        + "\n",
        encoding="utf-8",
    )


def _write_error(path: Path, nav_yaw: float, trace_yaw: float) -> None:
    yaw_error = nav_yaw - trace_yaw
    path.write_text(
        "timestamp,reference_timestamp,dt,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        + "\n".join(f"{i},{i},0,0,0,0,0,0,0,{yaw_error}" for i in range(20))
        + "\n",
        encoding="utf-8",
    )


def test_replay_yaw_diagnostics_distinguishes_runtime_issue(tmp_path: Path):
    input_path = tmp_path / "input.gnss"
    nav_path = tmp_path / "nav.csv"
    error_path = tmp_path / "error.csv"
    _write_input(input_path, 10.0)
    _write_nav(nav_path, 100.0)
    _write_error(error_path, nav_yaw=100.0, trace_yaw=10.0)
    report = compare_input_yaw_to_replay_nav(input_path, nav_path, error_series_csv=error_path)
    assert report["likely_issue_classification"] == "likely_runtime_yaw_update_or_initialization_issue"


def test_replay_yaw_diagnostics_distinguishes_input_issue(tmp_path: Path):
    input_path = tmp_path / "input.gnss"
    nav_path = tmp_path / "nav.csv"
    error_path = tmp_path / "error.csv"
    _write_input(input_path, 100.0)
    _write_nav(nav_path, 100.0)
    _write_error(error_path, nav_yaw=100.0, trace_yaw=10.0)
    report = compare_input_yaw_to_replay_nav(input_path, nav_path, error_series_csv=error_path)
    assert report["likely_issue_classification"] == "likely_input_yaw_generation_issue"
