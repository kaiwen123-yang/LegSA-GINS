from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_b2_code_does_not_select_yaw_sign_by_rmse() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "src/legsa_gins/degradation").glob("*.py"))
    assert "rmse_selected_sign" in text
    assert "argmin" not in text.lower()
    assert "best_rmse" not in text.lower()
    assert "min_rmse" not in text.lower()
