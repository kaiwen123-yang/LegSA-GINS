"""中文说明：actual/replay yaw path 单元测试只使用 toy rows。"""

from legsa_gins.evaluation.actual_vs_replay_yaw_path import (
    compare_input_to_nav_yaw,
    compare_input_yaw_paths,
    compare_nav_yaw_paths,
    make_actual_vs_replay_yaw_path_report,
    wrap_deg180,
    wrap_deg360,
)


def _input(yaw0: float = 10.0, yaw1: float = 20.0) -> list[dict[str, float]]:
    return [
        {"time": 0.0, "lat": 40.0, "lon": 116.0, "height": 10.0, "vn": 1.0, "ve": 0.0, "vd": 0.0, "yaw": yaw0, "yaw_std": 1.5},
        {"time": 1.0, "lat": 40.0, "lon": 116.00001, "height": 10.0, "vn": 1.0, "ve": 0.0, "vd": 0.0, "yaw": yaw1, "yaw_std": 1.5},
    ]


def _nav(yaw0: float, yaw1: float) -> list[dict[str, float]]:
    return [
        {"time": 0.0, "lat": 40.0, "lon": 116.0, "height": 10.0, "roll": 0.0, "pitch": 0.0, "yaw": yaw0},
        {"time": 1.0, "lat": 40.0, "lon": 116.00001, "height": 10.0, "roll": 0.0, "pitch": 0.0, "yaw": yaw1},
    ]


def test_wrap_helpers() -> None:
    assert wrap_deg180(181.0) == -179.0
    assert wrap_deg360(-1.0) == 359.0


def test_input_paths_match() -> None:
    report = compare_input_yaw_paths(_input(), _input())
    assert report["input_path_parity_status"] == "input_paths_match"
    assert report["input_yaw_diff_rmse_deg"] == 0.0
    assert report["trace_solver_input"] is False


def test_nav_yaw_diverges_while_position_close() -> None:
    report = compare_nav_yaw_paths(_nav(100.0, 110.0), _nav(10.0, 20.0))
    assert report["nav_path_parity_status"] == "position_close_yaw_diverged"
    assert report["nav_yaw_diff_rmse_deg"] == 90.0


def test_replay_nav_tracks_input_but_actual_nav_differs() -> None:
    report = make_actual_vs_replay_yaw_path_report(
        _input(),
        _input(),
        _nav(100.0, 110.0),
        _nav(10.0, 20.0),
    )
    assert report["likely_runtime_yaw_update_or_config_difference"] is True
    assert report["replay_input_vs_replay_nav_yaw"]["classification"] == "nav_tracks_input_yaw"
    assert report["trace_solver_input"] is False


def test_input_to_nav_transform_candidate() -> None:
    report = compare_input_to_nav_yaw(_input(10.0, 20.0), _nav(80.0, 70.0))
    assert report["classification"] == "nav_applies_yaw_transform"
    assert report["best_transform_candidate"] == "heading_to_math"
