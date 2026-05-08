"""中文说明：检查 N4H4C stateFeedback 的符号约定和 dx 清零。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FEEDBACK_CPP = REPO_ROOT / "cpp/legsa_v23_core/src/filter/state_feedback.cpp"
FEEDBACK_HPP = REPO_ROOT / "cpp/legsa_v23_core/include/legsa_v23_core/filter/state_feedback.hpp"


def test_state_feedback_sign_convention_and_reset():
    text = FEEDBACK_HPP.read_text(encoding="utf-8") + "\n" + FEEDBACK_CPP.read_text(encoding="utf-8")
    for keyword in [
        "pos/vel 采用负号修正",
        "state.current_pva.pos_blh_rad_m[i] -= delta_blh[i]",
        "state.current_pva.vel_ned_mps[i] -= delta_velocity[i]",
        "state.current_pva.gyro_bias[i] +=",
        "state.current_pva.acc_bias[i] +=",
        "state.current_pva.gyro_scale[i] +=",
        "state.current_pva.acc_scale[i] +=",
        "Rotation::multiply(qpn, qbn)",
        "state.dx = zeroVector21()",
        "中文说明",
    ]:
        assert keyword in text


def test_state_feedback_is_not_output_only_correction():
    text = FEEDBACK_HPP.read_text(encoding="utf-8")
    assert "not output-only correction" in text
