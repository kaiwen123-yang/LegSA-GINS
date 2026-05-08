"""中文说明：测试 dual replay plot loader 的 parser 与只读边界。"""

import json
from pathlib import Path

from legsa_gins.visualization.dual_replay_plot_loader import (
    load_dual_official_artifacts,
    local_neu_from_origin,
    parse_15col_gnss,
    parse_error_series,
    parse_kfgins_nav,
    parse_kfgins_std,
    wrap_deg180,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _std_line(time: float) -> str:
    values = [
        time,
        0.4,
        0.4,
        0.5,
        0.02,
        0.02,
        0.03,
        0.5,
        0.5,
        0.8,
        0.01,
        0.01,
        0.01,
        1.0,
        1.0,
        1.0,
        0.1,
        0.1,
        0.1,
        0.1,
        0.1,
        0.1,
    ]
    return " ".join(str(value) for value in values) + "\n"


def test_toy_loader_parses_nav_std_error_series_and_summary(tmp_path):
    root = tmp_path / "dual"
    _write(root / "input.gnss", "100 30 120 50 0.4 0.4 0.5 0 0 0 0.02 0.02 0.03 10 1\n")
    _write(root / "KF_GINS_Navresult.nav", "2234 100 30 120 50 0 0 0 0.5 -0.2 10\n")
    _write(root / "KF_GINS_STD.txt", _std_line(100.0))
    _write(
        root / "error_series.csv",
        "timestamp,north_error_m,east_error_m,up_error_m,horizontal_error_m,roll_error_deg,pitch_error_deg,yaw_error_deg\n"
        "100,0.1,0.2,0.3,0.2236,0.01,0.02,1.0\n",
    )
    _write(root / "summary.json", json.dumps({"horizontal_rmse_m": 0.2, "yaw_rmse_deg": 1.0}))

    assert parse_15col_gnss(root / "input.gnss")[0]["yaw"] == 10.0
    assert parse_kfgins_nav(root / "KF_GINS_Navresult.nav")[0]["yaw_deg"] == 10.0
    assert parse_kfgins_std(root / "KF_GINS_STD.txt")[0]["std_yaw_deg"] == 0.8
    assert parse_error_series(root / "error_series.csv")[0]["yaw_error_deg"] == 1.0

    loaded = load_dual_official_artifacts(root)
    assert loaded["evidence_status"] == "loaded"
    assert loaded["validation"]["nav"]["time_monotonic"]
    assert loaded["validation"]["std"]["no_nan_inf"]


def test_yaw_wrap_and_local_neu():
    assert wrap_deg180(181.0) == -179.0
    rows = [
        {"timestamp": 0.0, "lat_deg": 30.0, "lon_deg": 120.0, "height_m": 50.0},
        {"timestamp": 1.0, "lat_deg": 30.000001, "lon_deg": 120.000001, "height_m": 51.0},
    ]
    neu = local_neu_from_origin(rows, rows[0])
    assert neu[0]["north_m"] == 0.0
    assert neu[1]["north_m"] > 0.0
    assert neu[1]["east_m"] > 0.0
    assert neu[1]["up_m"] == 1.0
