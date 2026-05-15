from pathlib import Path

from PIL import Image

from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import write_json
from legsa_gins.reporting.by2_feedback_applicability import materialize_n8k6_a0_feedback_applicability_fix

# 中文说明：toy 集成覆盖 A0 从 raw feedback rows 冲突到 not-applicable 修复的闭环。


def _png(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (80, 60), color).save(path)


def test_n8k6_a0_feedback_applicability_fix_toy(tmp_path):
    n8k5_root = tmp_path / "n8k5"
    n8k5_fig = tmp_path / "n8k5_fig"
    plot_root = tmp_path / "plot_audit"
    n8k5_root.mkdir()
    write_json(n8k5_root / "N8K5_BY2_FORMAL_ABLATION_CROSS_CATEGORY_FIX_DECISION_REPORT.json", {"status": "BY2_formal_ablation_cross_category_semantic_fix_complete"})
    for index, (category, filename) in enumerate([
        ("06_observation_quality", "feedback_accept_reject_time.png"),
        ("07_compare", "compare_feedback_delta.png"),
        ("07_compare", "reject_all_sanity_compare.png"),
        ("11_feedback", "feedback_accept_reject_timeline.png"),
        ("11_feedback", "reject_all_sanity.png"),
    ]):
        _png(n8k5_fig / "A0_source_backed_ekf_baseline" / category / filename, (80 + index, 20, 120))
        _png(n8k5_fig / "A8_feedback_selected_conservative_gate" / category / filename, (20, 80 + index, 120))
    n8k_dir = plot_root / "N8K_BY2_formal_ablation_plot_audit" / "运行结果"
    write_json(
        n8k_dir / "N8K_BY2_FORMAL_ABLATION_MATRIX.json",
        {
            "rows": [
                {"variant_id": "A0_source_backed_ekf_baseline", "n8j_source_variant": "baseline_no_feedback", "feedback_mode": "none"},
                {"variant_id": "A8_feedback_selected_conservative_gate", "n8j_source_variant": "n8j_selected_conservative_feedback", "feedback_mode": "horizontal_velocity_attitude_feedback"},
            ]
        },
    )
    write_json(
        n8k_dir / "N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json",
        {"metrics": [{"variant_id": "A0_source_backed_ekf_baseline", "feedback_accept": 0, "feedback_reject": 0}, {"variant_id": "A8_feedback_selected_conservative_gate", "feedback_accept": 151, "feedback_reject": 24}]},
    )
    n8k2_dir = plot_root / "N8K2_BY2_formal_ablation_real_plot_fix" / "运行结果"
    write_json(
        n8k2_dir / "N8K2_REAL_PLOT_DATA_LOAD_REPORT.json",
        {
            "feedback_rows_per_variant": {"A0_source_backed_ekf_baseline": 175, "A8_feedback_selected_conservative_gate": 151},
            "data_sources": {"A0_source_backed_ekf_baseline": "n8j_runtime_eval_nav", "A8_feedback_selected_conservative_gate": "n8j_runtime_eval_nav"},
        },
    )
    result = materialize_n8k6_a0_feedback_applicability_fix(
        n8k5_root=n8k5_root,
        n8k5_figure_root=n8k5_fig,
        n8k5_case_review_root=tmp_path / "case5",
        n8k5_summary_root=tmp_path / "summary5",
        plot_audit_root=plot_root,
        output_dir=tmp_path / "out",
        figure_output_dir=tmp_path / "fig6",
        case_review_dir=tmp_path / "case6",
        summary_dir=tmp_path / "summary6",
    )
    assert result["decision"]["status"] == "A0_feedback_applicability_fix_complete"
    assert result["fix"]["A0_feedback_applicable_after"] is False
    assert result["fix"]["A0_effective_feedback_rows_for_plotting_after"] == 0
