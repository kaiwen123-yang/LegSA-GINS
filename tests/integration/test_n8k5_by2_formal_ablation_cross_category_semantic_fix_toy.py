from pathlib import Path

from PIL import Image

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from legsa_gins.reporting.by2_cross_category_duplicate_detector import materialize_n8k5_cross_category_fix, scan_cross_category_duplicates

# 中文说明：toy 集成覆盖 N8K5 从 N8K4 跨类别重复到修复决策的闭环。


def _png(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (70, 52), color).save(path)


def test_n8k5_by2_formal_ablation_cross_category_semantic_fix_toy(tmp_path):
    n8k4_root = tmp_path / "n8k4"
    n8k3_root = tmp_path / "n8k3"
    n8k2_root = tmp_path / "n8k2"
    plot_root = tmp_path / "plot_audit"
    fig = tmp_path / "n8k4_fig"
    for root in [n8k4_root, n8k3_root, n8k2_root]:
        root.mkdir()
    duplicate_velocity = (10, 80, 130)
    duplicate_feedback = (120, 70, 20)
    _png(fig / "V0" / "03_velocity" / "velocity_residual_time.png", duplicate_velocity)
    _png(fig / "V0" / "07_compare" / "compare_velocity_error.png", duplicate_velocity)
    _png(fig / "V0" / "06_observation_quality" / "feedback_accept_reject_time.png", duplicate_feedback)
    _png(fig / "V0" / "07_compare" / "compare_feedback_delta.png", duplicate_feedback)
    _png(fig / "V0" / "07_compare" / "compare_horizontal_error.png", (20, 30, 40))

    assert scan_cross_category_duplicates(fig)["same_variant_cross_category_duplicate_count"] == 2
    write_json(n8k4_root / "N8K4_SEMANTIC_FILENAME_FIX_REPORT.json", {"semantic_filename_mismatch_after_count": 0})
    write_json(n8k2_root / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json", {"data_sources": {"V0": "derived_from_n8k_metrics_and_baseline_nav"}, "feedback_rows_per_variant": {"V0": 0}})
    metrics_dir = plot_root / "N8K_BY2_formal_ablation_plot_audit" / "运行结果"
    write_json(metrics_dir / "N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json", {"metrics": [{"variant_id": "V0", "velocity_rmse": 0.12, "velocity_p95": 0.34}]})

    result = materialize_n8k5_cross_category_fix(
        n8k4_root=n8k4_root,
        n8k4_figure_root=fig,
        n8k3_root=n8k3_root,
        n8k2_root=n8k2_root,
        plot_audit_root=plot_root,
        output_dir=tmp_path / "out",
        figure_output_dir=tmp_path / "fixed",
        case_review_dir=tmp_path / "case",
        summary_dir=tmp_path / "summary",
    )

    assert result["decision"]["status"] == "BY2_formal_ablation_cross_category_semantic_fix_complete"
    assert result["fix"]["velocity_residual_vs_compare_velocity_duplicate_count_after"] == 0
    assert result["fix"]["feedback_quality_vs_compare_feedback_delta_duplicate_count_after"] == 0
    assert result["fix"]["compare_feedback_delta_not_applicable_count"] == 1
