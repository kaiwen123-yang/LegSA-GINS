"""中文说明：N4H4B engine 边界测试，确保量测更新仍未实现。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE = REPO_ROOT / "cpp/legsa_v23_core/src/runtime/legsa_v23_engine.cpp"


def test_engine_uses_propagation_predict_path():
    text = ENGINE.read_text(encoding="utf-8")
    for keyword in [
        "INSMechanization::insMech",
        "buildErrorStateMatrices",
        "legsa_v23_core::EKFPredict",
        "imuCompensate",
        "checkCov",
        "中文说明",
    ]:
        assert keyword in text


def test_gnss_update_ekf_update_state_feedback_remain_n4h4c_todo():
    text = ENGINE.read_text(encoding="utf-8")
    for keyword in [
        "TODO(N4H4C): measurement update not implemented in N4H4B",
        "TODO(N4H4C): GNSS position update not implemented in N4H4B",
        "TODO(N4H4C): GNSS velocity update not implemented in N4H4B",
        "TODO(N4H4C): GNSS yaw update not implemented in N4H4B",
        "TODO(N4H4C): EKF measurement update not implemented in N4H4B",
        "TODO(N4H4C): state feedback not implemented in N4H4B",
    ]:
        assert keyword in text
    assert "stateFeedback();" not in text
