"""中文说明：测试 yaw_std 来源区分，不把观测标准差写成注入噪声。"""

from pathlib import Path

from legsa_gins.visualization.yaw_std_source_audit import analyze_yaw_std_source


def _std_line(time: float, yaw_std: float = 0.8) -> str:
    values = [time, 1, 1, 1, 0.1, 0.1, 0.1, 0.5, 0.5, yaw_std, 0.01, 0.01, 0.01, 1, 1, 1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]
    return " ".join(str(value) for value in values) + "\n"


def test_fixed_yaw_std_detected_and_not_noise(tmp_path):
    gnss = tmp_path / "input.gnss"
    gnss.write_text(
        "0 30 120 50 0.4 0.4 0.5 0 0 0 0.05 0.05 0.05 10 1.5\n"
        "1 30 120 50 0.4 0.4 0.5 0 0 0 0.05 0.05 0.05 10 1.5\n",
        encoding="utf-8",
    )
    std = tmp_path / "KF_GINS_STD.txt"
    std.write_text(_std_line(0, 0.9) + _std_line(1, 0.7), encoding="utf-8")
    report = analyze_yaw_std_source(gnss, std)
    assert report["observation_yaw_std"]["is_fixed_1p5"]
    assert report["yaw_std_is_measurement_std_not_noise_injection"]
    assert report["state_yaw_std_available"]
    assert report["state_yaw_std"]["is_state_covariance_std"]
    assert report["yaw_std_not_used_to_relax_gate"]
