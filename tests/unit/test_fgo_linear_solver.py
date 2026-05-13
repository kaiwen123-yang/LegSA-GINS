from legsa_gins.fgo.fgo_linear_solver import moving_average, solve_no_feedback_linear_system


def test_linear_solver_smooths_without_feedback() -> None:
    """中文说明：fallback solver 只输出离线平滑诊断。"""
    assert moving_average([1.0, 3.0, 5.0], window=3)[1] == 3.0
    report = solve_no_feedback_linear_system([[1.0], [3.0], [5.0]])
    assert report["solved"] is True
    assert report["no_feedback"] is True
