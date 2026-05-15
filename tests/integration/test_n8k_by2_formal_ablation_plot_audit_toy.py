from pathlib import Path

from legsa_gins.reporting.by2_formal_ablation_runner import run_n8k_formal_ablation_plot_audit
from scripts.audit_n8j_feedback_final_validation import make_toy_n8j_root

# 中文说明：集成 toy 运行完整 N8K 报告和绘图审计流程。


def test_n8k_by2_formal_ablation_plot_audit_toy(tmp_path: Path):
    n8j = tmp_path / "n8j"
    make_toy_n8j_root(n8j)
    summary = run_n8k_formal_ablation_plot_audit(
        previous_roots={"n5b": "role", "n6b": "role", "n7c6": "role", "n8f1": "role", "n8i": "role", "n8j": str(n8j)},
        plot_audit_root=tmp_path / "by2_audit",
        output_dir=tmp_path / "out",
        figure_output_dir=tmp_path / "by2_audit" / "N8K" / "figures",
        case_review_dir=tmp_path / "by2_audit" / "N8K" / "case",
        summary_dir=tmp_path / "by2_audit" / "N8K" / "summary",
        allow_run=True,
    )
    assert summary["status"] == "BY2_formal_ablation_plot_audit_complete"
    assert summary["total_figures_generated"] > 0
