"""中文说明：测试 N4H4E1 plot semantics 修正和 up diff 诊断。"""

from legsa_gins.visualization.legsa_v23_port_plot_semantics_fix import (
    CORRECTED_FIGURES,
    analyze_up_diff_initial_step,
    detect_vector_line_plot_misuse,
)


def test_detects_vector_line_plot_misuse_from_legacy_manifest():
    report = detect_vector_line_plot_misuse(
        {"figure_paths": ["01_trajectory/trajectory_xy_error_to_reference.png"]}
    )
    assert report["vector_line_plot_misuse_detected"] is True


def test_corrected_figures_include_scatter_and_3sigma_outputs():
    assert "04_port_finalv23_parity/port_minus_finalv23_horizontal_diff_scatter.png" in CORRECTED_FIGURES
    assert "07_std_consistency/error_vs_3sigma_yaw_corrected.png" in CORRECTED_FIGURES


def test_up_diff_initial_step_report_keeps_first_sample():
    report = analyze_up_diff_initial_step(
        [
            {"timestamp": 0.0, "up_error_m": 0.0},
            {"timestamp": 0.01, "up_error_m": 0.05},
            {"timestamp": 0.02, "up_error_m": 0.05},
        ]
    )
    assert report["first_sample_up_diff"] == 0.0
    assert report["second_sample_up_diff"] == 0.05
    assert report["median_up_diff"] == 0.05
    assert report["up_diff_step_suspect"] is True


def test_corrected_3sigma_report_contract_names_present():
    corrected = [name for name in CORRECTED_FIGURES if "3sigma" in name]
    assert len(corrected) == 4
