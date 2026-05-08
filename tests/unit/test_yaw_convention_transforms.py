"""中文说明：yaw convention 单元测试只验证 evaluator diagnostic 变换。"""

from legsa_gins.evaluation.yaw_convention_transforms import (
    compute_yaw_error,
    generate_yaw_transform_grid,
    transform_yaw,
    wrap_deg180,
    wrap_deg360,
)


def test_wrap_deg180_and_360() -> None:
    assert wrap_deg180(190.0) == -170.0
    assert wrap_deg180(180.0) == -180.0
    assert wrap_deg360(-10.0) == 350.0


def test_basic_yaw_transforms() -> None:
    assert transform_yaw(10.0, "identity") == 10.0
    assert transform_yaw(10.0, "neg") == 350.0
    assert transform_yaw(10.0, "plus90") == 100.0
    assert transform_yaw(10.0, "heading_to_math_yaw") == 80.0


def test_yaw_error_wrap_and_grid() -> None:
    assert compute_yaw_error(179.0, -179.0, est_transform="identity", ref_transform="identity") == -2.0
    grid = generate_yaw_transform_grid()
    assert grid
    assert any(item["candidate_id"] == "est=identity|ref=heading_to_math_yaw" for item in grid)
