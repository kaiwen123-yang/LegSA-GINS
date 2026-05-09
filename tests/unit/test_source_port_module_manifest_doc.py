"""中文说明：检查 N4H4R0 移植模块清单的关键函数和新目录。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/experiments/n4h4r0_source_port_module_manifest.md"
MATRIX = ROOT / "docs/experiments/n4h4r0_kfgins_to_legsa_port_matrix.md"


def test_manifest_contains_core_runtime_functions():
    text = MANIFEST.read_text(encoding="utf-8")
    for term in [
        "newImuProcess",
        "imuInterpolate",
        "imuCompensate",
        "insPropagation",
        "EKFUpdate",
        "stateFeedback",
    ]:
        assert term in text


def test_manifest_declares_new_port_target_and_comments():
    text = MANIFEST.read_text(encoding="utf-8") + "\n" + MATRIX.read_text(encoding="utf-8")
    assert "cpp/legsa_v23_port_core" in text
    assert "Chinese comment requirement" in text
    assert "Chinese comments" in text
    assert "diagnostic/self-written attempt" in text

