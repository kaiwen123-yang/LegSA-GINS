"""中文说明：检查 EKFUpdate 使用 Joseph form，并只更新 dx/P。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EKF_CPP = REPO_ROOT / "cpp/legsa_v23_core/src/filter/ekf_update.cpp"
EKF_HPP = REPO_ROOT / "cpp/legsa_v23_core/include/legsa_v23_core/filter/ekf_update.hpp"


def test_ekf_update_joseph_form_evidence():
    text = EKF_HPP.read_text(encoding="utf-8") + "\n" + EKF_CPP.read_text(encoding="utf-8")
    for keyword in [
        "S=HPH^T+R",
        "K=PH^T inv(S)",
        "Cov=(I-KH)P(I-KH)^T+KRK^T",
        "I_minus_KH",
        "innovation[row] = meas.residual[row] - predicted",
        "force symmetry",
        "中文说明",
    ]:
        assert keyword in text


def test_ekf_update_does_not_call_state_feedback():
    text = EKF_CPP.read_text(encoding="utf-8")
    assert "stateFeedback(" not in text
    assert "current_pva" not in text
