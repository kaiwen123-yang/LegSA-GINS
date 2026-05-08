"""中文说明：测试 actual input 与 yaw variant 对比分类。"""

from pathlib import Path

from legsa_gins.evaluation.actual_input_yaw_variant_match import compare_actual_input_to_variants


def _write(path: Path, yaw_values: list[float]) -> None:
    lines = []
    for index, yaw in enumerate(yaw_values):
        lines.append(f"{index} 30 120 50 0.4 0.4 0.5 0 0 0 0.05 0.05 0.05 {yaw} 1.5\n")
    path.write_text("".join(lines), encoding="utf-8")


def test_variant_comparison_classifies_no_noise(tmp_path):
    actual = tmp_path / "actual.gnss"
    safe = tmp_path / "safe.gnss"
    gaussian = tmp_path / "gaussian.gnss"
    legacy = tmp_path / "legacy.gnss"
    _write(actual, [10.0, 10.0, 10.0])
    _write(safe, [10.0, 10.0, 10.0])
    _write(gaussian, [11.0, 9.0, 10.5])
    _write(legacy, [30.0, -10.0, 10.0])
    report = compare_actual_input_to_variants(
        actual,
        {
            "status_safe_no_noise": safe,
            "status_gaussian_1p5_no_outlier": gaussian,
            "status_gaussian_1p5_legacy15": legacy,
        },
    )
    assert report["best_matching_variant"] == "status_safe_no_noise"
    assert report["actual_yaw_noise_injection_status"] == "no_evidence_of_injected_yaw_noise"
    assert report["nominal_clean_claim_allowed"]
    assert report["yaw_std_is_not_yaw_noise"]
