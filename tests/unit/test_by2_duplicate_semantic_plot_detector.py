from pathlib import Path

from PIL import Image

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from legsa_gins.reporting.by2_duplicate_semantic_plot_detector import materialize_n8k3_duplicate_fix, scan_same_category_duplicates

# 中文说明：N8K3 detector 必须发现同类 exact duplicate，并在修复后清零。


def test_duplicate_detector_and_fix(tmp_path: Path):
    n8k2_root = tmp_path / "n8k2"
    fig = tmp_path / "n8k2_fig"
    _make_duplicate_figures(fig)
    write_json(n8k2_root / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json", {"data_sources": {"A": "derived_from_n8k_metrics_and_baseline_nav"}, "feedback_rows_per_variant": {"A": 0}, "paper_performance_claim": False})
    write_json(n8k2_root / "N8K2_REAL_PLOT_MATERIALIZATION_REPORT.json", {"generated": [], "paper_performance_claim": False})
    before = scan_same_category_duplicates(fig)
    assert before["blocking_same_category_exact_duplicate_count"] > 0
    result = materialize_n8k3_duplicate_fix(n8k2_root=n8k2_root, n8k2_figure_root=fig, output_dir=tmp_path / "out", figure_output_dir=tmp_path / "fixed", case_review_dir=tmp_path / "case", summary_dir=tmp_path / "summary")
    assert result["decision"]["status"] == "BY2_formal_ablation_duplicate_plot_fix_complete"
    assert result["fix"]["blocking_exact_duplicate_after_count"] == 0


def _make_duplicate_figures(root: Path) -> None:
    pairs = {
        "01_trajectory": ["local_trajectory_overlay.png", "baseline_vs_variant_trajectory.png"],
        "04_attitude": ["yaw_residual_time.png", "yaw_wrap_check.png"],
        "07_compare": ["compare_horizontal_error.png", "reject_all_sanity_compare.png"],
        "11_feedback": ["feedback_accept_reject_timeline.png", "reject_all_sanity.png"],
    }
    for category, names in pairs.items():
        path = root / "A" / category
        path.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (320, 200), (240, 240, 240))
        for name in names:
            image.save(path / name)
