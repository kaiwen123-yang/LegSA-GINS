from pathlib import Path

from PIL import Image

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from legsa_gins.reporting.by2_semantic_filename_validator import materialize_n8k4_semantic_filename_fix

# 中文说明：toy 集成覆盖 N8K4 从 N8K3 错位报告到修复决策的闭环。


def test_n8k4_by2_formal_ablation_semantic_filename_fix_toy(tmp_path):
    n8k3_root = tmp_path / "n8k3"
    n8k2_root = tmp_path / "n8k2"
    fig = tmp_path / "fig"
    for root in [n8k3_root, n8k2_root]:
        root.mkdir()
    variant = fig / "V0"
    for category, names in {
        "04_attitude": ["yaw_residual_time.png", "yaw_wrap_check.png"],
        "07_compare": ["compare_horizontal_error.png", "reject_all_sanity_compare.png"],
        "11_feedback": ["feedback_accept_reject_timeline.png", "reject_all_sanity.png"],
    }.items():
        path = variant / category
        path.mkdir(parents=True)
        for index, name in enumerate(names):
            Image.new("RGB", (40, 30), (20 + index * 80, 40, 80)).save(path / name)
    write_json(
        n8k3_root / "N8K3_DUPLICATE_SEMANTIC_PLOT_FIX_REPORT.json",
        {
            "fixed_entries": [
                {"variant_id": "V0", "category": "04_attitude", "filename": "yaw_residual_time.png", "semantic_fix": "yaw_wrap_consistency_panel"},
                {"variant_id": "V0", "category": "07_compare", "filename": "compare_horizontal_error.png", "semantic_fix": "reject_all_compare_semantics"},
                {"variant_id": "V0", "category": "11_feedback", "filename": "feedback_accept_reject_timeline.png", "semantic_fix": "feedback_reject_all_semantics"},
            ]
        },
    )
    write_json(n8k2_root / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json", {"data_sources": {"V0": "derived_from_n8k_metrics_and_baseline_nav"}, "feedback_rows_per_variant": {"V0": 12}})
    result = materialize_n8k4_semantic_filename_fix(n8k3_root=n8k3_root, n8k3_figure_root=fig, n8k2_root=n8k2_root, n8k2_figure_root=fig, output_dir=tmp_path / "out", figure_output_dir=tmp_path / "fixed", case_review_dir=tmp_path / "case", summary_dir=tmp_path / "summary")
    assert result["decision"]["status"] == "BY2_formal_ablation_semantic_filename_fix_complete"
    assert result["fix"]["semantic_filename_mismatch_after_count"] == 0
