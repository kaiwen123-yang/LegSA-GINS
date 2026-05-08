"""中文说明：N4H2G2 yaw input sensitivity probe 单元测试。"""

from pathlib import Path

from legsa_gins.evaluation.yaw_input_sensitivity_probe import classify_yaw_sensitivity, create_yaw_shifted_gnss


def test_yaw_shifted_gnss_changes_only_yaw_column(tmp_path: Path) -> None:
    clean = tmp_path / "clean.gnss"
    shifted = tmp_path / "shifted.gnss"
    clean.write_text("0 40 116 10 0.5 0.5 0.8 1 2 3 0.1 0.1 0.1 350 1.5\n", encoding="utf-8")
    report = create_yaw_shifted_gnss(clean, shifted, yaw_shift_deg=30.0)
    parts = shifted.read_text(encoding="utf-8").strip().split()
    assert float(parts[13]) == 20.0
    assert float(parts[14]) == 1.5
    assert report["formal_allowed"] is False
    assert report["numerical_performance_claim"] is False


def test_yaw_sensitivity_classification() -> None:
    assert classify_yaw_sensitivity(0.1)["yaw_input_has_low_runtime_effect_or_update_rejected"] is True
    assert classify_yaw_sensitivity(6.0)["yaw_input_affects_runtime"] is True
    assert classify_yaw_sensitivity(2.0)["yaw_input_runtime_effect_bounded"] is True
