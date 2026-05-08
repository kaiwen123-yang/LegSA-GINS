"""中文说明：N4H4B engine 边界测试，确保传播 toy 仍保持无量测更新边界。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE = REPO_ROOT / "cpp/legsa_v23_core/src/runtime/legsa_v23_engine.cpp"
RUNTIME = REPO_ROOT / "cpp/legsa_v23_core/src/runtime/legsa_v23_runtime.cpp"


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
    runtime = RUNTIME.read_text(encoding="utf-8")
    propagation_toy = runtime[runtime.find("runDryPropagationToy") : runtime.find("runDryUpdateToy")]
    assert "measurement_update_implemented = false" in propagation_toy
    assert "state_feedback_implemented = false" in propagation_toy
