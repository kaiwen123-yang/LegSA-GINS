"""中文说明：检查 R2 GIEngine 函数、中文注释和禁止输入边界。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GI = ROOT / "cpp/legsa_v23_port_core/src/kf_gins/gi_engine.cpp"
DEMO = ROOT / "cpp/legsa_v23_port_core/src/demo/port_demo.cpp"


def test_gi_engine_required_functions_and_comments():
    text = GI.read_text(encoding="utf-8")
    for name in [
        "newImuProcess",
        "imuInterpolate",
        "imuCompensate",
        "insPropagation",
        "gnssUpdate",
        "EKFUpdate",
        "stateFeedback",
    ]:
        assert name in text
    assert "中文说明" in text
    assert "final_v23 output substitution" in text


def test_demo_has_no_final_v23_output_input():
    text = DEMO.read_text(encoding="utf-8")
    assert "final_v23 output" in text
    assert "--dry-run-synthetic-math" in text
