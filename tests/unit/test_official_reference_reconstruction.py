"""中文说明：official reference reconstruction 单元测试只使用 toy NAV/error。"""

from legsa_gins.evaluation.official_reference_reconstruction import (
    reconstruct_reference_from_official_errors,
    select_reference_sign_by_summary,
)


def _nav() -> list[dict[str, float]]:
    return [
        {"timestamp": 0.0, "time": 0.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 10.0},
        {"timestamp": 1.0, "time": 1.0, "lat_deg": 40.0, "lon_deg": 116.0, "height_m": 10.0, "roll_deg": 0.0, "pitch_deg": 0.0, "yaw_deg": 20.0},
    ]


def _errors(yaw: float = 2.0) -> list[dict[str, float]]:
    return [
        {"timestamp": 0.0, "north_error_m": 1.0, "east_error_m": 0.0, "up_error_m": 0.5, "roll_error_deg": 0.5, "pitch_error_deg": 1.0, "yaw_error_deg": yaw},
        {"timestamp": 1.0, "north_error_m": 1.0, "east_error_m": 0.0, "up_error_m": 0.5, "roll_error_deg": 0.5, "pitch_error_deg": 1.0, "yaw_error_deg": yaw},
    ]


def test_reconstruct_reference_candidates() -> None:
    candidates = reconstruct_reference_from_official_errors(_nav(), _errors())
    assert set(candidates) == {"official_ref_sign_minus", "official_ref_sign_plus"}
    assert len(candidates["official_ref_sign_minus"]) == 2


def test_reference_selection_reproduces_official_summary() -> None:
    report = select_reference_sign_by_summary(
        _nav(),
        _errors(),
        {"horizontal_rmse_m": 1.0, "up_rmse_m": 0.5, "roll_rmse_deg": 0.5, "pitch_rmse_deg": 1.0, "yaw_rmse_deg": 2.0},
    )
    assert report["actual_dual_summary_reproduced"] is True
    assert report["selected_reference_sign"] == "official_ref_sign_minus"
    assert report["trace_solver_input"] is False
