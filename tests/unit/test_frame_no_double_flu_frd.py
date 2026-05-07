"""中文说明：unit 测试验证小模块约定和边界，不做 numerical performance claim。
"""

import pytest

from legsa_gins.frames.conventions import FrameName
from legsa_gins.frames.go2_adapter import Go2FrameAdapter


def test_go2_flu_input_can_transform_to_frd():
    adapter = Go2FrameAdapter()
    result = adapter.adapt_body_vector_to_frd(
        (1.0, 2.0, 3.0),
        input_frame=FrameName.GO2_BODY_FLU,
    )

    assert result.values == (1.0, -2.0, -3.0)
    assert result.output_frame == FrameName.IMU_FRD_COMPATIBLE.value
    assert result.transform_applied is True


def test_already_frd_compatible_input_is_not_transformed_twice():
    adapter = Go2FrameAdapter()
    result = adapter.adapt_body_vector_to_frd(
        (1.0, -2.0, -3.0),
        input_frame=FrameName.IMU_FRD_COMPATIBLE,
        already_frd_compatible=True,
    )

    assert result.values == (1.0, -2.0, -3.0)
    assert result.transform_applied is False


def test_conflicting_flu_and_already_frd_declaration_fails():
    adapter = Go2FrameAdapter()

    with pytest.raises(ValueError, match="no double FLU-to-FRD"):
        adapter.adapt_body_vector_to_frd(
            (1.0, 2.0, 3.0),
            input_frame=FrameName.GO2_BODY_FLU,
            already_frd_compatible=True,
        )
