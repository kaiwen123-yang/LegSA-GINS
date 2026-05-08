"""中文说明：error_series parity 测试只使用 toy CSV/JSON。"""

import json

from legsa_gins.evaluation.error_series_parity import (
    compare_error_series,
    compare_summary_metrics,
    load_official_error_series,
    load_official_summary,
)


def test_parse_toy_official_summary(tmp_path) -> None:
    path = tmp_path / "summary.json"
    path.write_text(
        json.dumps(
            {
                "position": {"horizontal_rmse_m": 0.35, "up_rmse_m": 0.8},
                "attitude": {"roll_rmse_deg": 0.1, "pitch_rmse_deg": 0.2, "yaw_rmse_deg": 1.8},
                "meta": {"num_samples": 2},
            }
        ),
        encoding="utf-8",
    )
    summary = load_official_summary(path)
    assert summary["horizontal_rmse_m"] == 0.35
    assert summary["yaw_rmse_deg"] == 1.8


def test_parse_toy_error_series_and_parity(tmp_path) -> None:
    path = tmp_path / "error_series.csv"
    path.write_text(
        "time,err_n_m,err_e_m,err_u_m,roll_err_deg,pitch_err_deg,yaw_err_deg\n"
        "0,1,2,3,4,5,6\n"
        "1,2,3,4,5,6,7\n",
        encoding="utf-8",
    )
    rows = load_official_error_series(path)
    assert rows[0]["timestamp"] == 0.0
    assert rows[0]["north_error_m"] == 1.0
    assert rows[0]["yaw_error_deg"] == 6.0
    parity = compare_error_series(rows, rows)
    assert parity["yaw_error_series_parity_status"] == "passed"
    assert parity["yaw_error_series_rmse_diff"] == 0.0


def test_summary_parity() -> None:
    official = {"horizontal_rmse_m": 1.0, "up_rmse_m": 2.0, "yaw_rmse_deg": 3.0}
    recomputed = {"horizontal_rmse_m": 1.01, "up_rmse_m": 2.01, "yaw_rmse_deg": 3.05}
    parity = compare_summary_metrics(official, recomputed)
    assert parity["summary_close"] is True
    assert parity["summary_parity_status"] == "passed"
