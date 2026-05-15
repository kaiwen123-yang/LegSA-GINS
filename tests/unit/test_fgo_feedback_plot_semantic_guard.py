"""Unit tests for N8H plot semantic guard.

中文说明：测试图像语义 guard 不允许 output substitution 标签。
"""

from scripts.audit_n8h_fgo_feedback_visual_validation import make_toy_n8g_root
from legsa_gins.fgo_feedback.fgo_feedback_plot_semantic_guard import build_plot_semantic_guard
from legsa_gins.fgo_feedback.fgo_feedback_position_disabled_audit import build_position_disabled_audit
from legsa_gins.fgo_feedback.fgo_feedback_variant_ablation_review import build_variant_ablation_review
from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import load_n8h_visual_inputs


def test_plot_semantic_guard_passes_toy_boundaries(tmp_path):
    n8g_root = tmp_path / "n8g"
    make_toy_n8g_root(n8g_root)
    bundle = load_n8h_visual_inputs(n8g_root)
    report = build_plot_semantic_guard(
        visual_manifest=bundle.manifest,
        position_audit=build_position_disabled_audit(bundle),
        variant_review=build_variant_ablation_review(bundle),
    )
    assert report["status"] == "plot_semantics_passed"
