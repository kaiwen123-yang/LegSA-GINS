"""Check the N4H3 transplant matrix contract text.

中文说明：矩阵测试只检查关键函数和边界措辞，不复制外部源码。
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_transplant_matrix_doc_contains_contract_terms():
    text = (ROOT / "docs/experiments/kfgins_full_framework_transplant_matrix.md").read_text(encoding="utf-8")
    for term in [
        "newImuProcess",
        "isToUpdate",
        "imuInterpolate",
        "imuCompensate",
        "insPropagation",
        "F/G/Phi/Qd",
        "EKFPredict",
        "EKFUpdate",
        "stateFeedback",
        "gnss position/velocity/yaw update",
    ]:
        assert term in text
    assert "final_v23 is not proposed" in text
    assert "Chinese comments required" in text
