"""N7B5 horizontal diagnostic activation wrapper 单元测试。"""

from legsa_gins.go2_prior.go2_frame_sensitivity_runner import VARIANT_IDS
from legsa_gins.go2_prior.go2_horizontal_diagnostic_activation import HORIZONTAL_DIAGNOSTIC_VARIANTS


def test_horizontal_activation_wrapper_exposes_n7b5_variants():
    assert HORIZONTAL_DIAGNOSTIC_VARIANTS == VARIANT_IDS
    assert "probability_weighted_horizontal_only_diagnostic" in HORIZONTAL_DIAGNOSTIC_VARIANTS
    assert "baseline_no_go2_velocity" in HORIZONTAL_DIAGNOSTIC_VARIANTS
