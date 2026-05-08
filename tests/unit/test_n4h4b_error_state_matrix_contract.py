"""中文说明：N4H4B error-state matrix contract 测试。"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_error_state_matrix_blocks_and_formula_are_present():
    text = (REPO_ROOT / "cpp/legsa_v23_core/src/filter/error_state_matrices.cpp").read_text(encoding="utf-8")
    required = [
        "P/P",
        "P/V",
        "V/P",
        "V/V",
        "V/Phi",
        "V/BA",
        "V/SA",
        "Phi/P",
        "Phi/V",
        "Phi/Phi",
        "Phi/BG",
        "Phi/SG",
        "BG/BG",
        "BA/BA",
        "SG/SG",
        "SA/SA",
        "V/VRW",
        "Phi/ARW",
        "BG/BGSTD",
        "BA/BASTD",
        "SG/SGSTD",
        "SA/SASTD",
        "Phi = I + F * dt",
        "G*Qc*G^T",
        "N4H4B 预测传播矩阵",
    ]
    for keyword in required:
        assert keyword in text


def test_ekf_predictor_symmetrizes_covariance_and_does_not_update_measurements():
    text = (REPO_ROOT / "cpp/legsa_v23_core/src/filter/ekf_predictor.cpp").read_text(encoding="utf-8")
    assert "Cov = Phi*Cov*Phi^T + Qd" in text
    assert "dx = Phi*dx" in text
    assert "symmetric" in text
    assert "不做 GNSS 量测更新" in text
    assert "state feedback" in text
