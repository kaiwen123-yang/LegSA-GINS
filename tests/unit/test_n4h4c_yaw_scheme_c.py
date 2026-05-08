"""中文说明：检查 N4H4C scheme_C yaw gate 的三段规则。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
YAW_CPP = REPO_ROOT / "cpp/legsa_v23_core/src/updates/yaw_scheme_c.cpp"
YAW_HPP = REPO_ROOT / "cpp/legsa_v23_core/include/legsa_v23_core/updates/yaw_scheme_c.hpp"


def test_yaw_scheme_c_thresholds_and_modes_present():
    text = YAW_HPP.read_text(encoding="utf-8") + "\n" + YAW_CPP.read_text(encoding="utf-8")
    for keyword in [
        "soft_deg = 6.0",
        "hard_deg = 15.0",
        "downweight_scale = 2.5",
        "YAW-NORMAL",
        "YAW-DOWNWEIGHT",
        "YAW-REJECT",
        "accepted",
        "中文说明",
    ]:
        assert keyword in text


def test_yaw_scheme_c_downweight_and_reject_logic_present():
    text = YAW_CPP.read_text(encoding="utf-8")
    assert "abs_residual <= options.soft_deg" in text
    assert "abs_residual <= options.hard_deg" in text
    assert "std_floor * options.downweight_scale" in text
    assert "return {YawSchemeCMode::REJECT, false" in text
