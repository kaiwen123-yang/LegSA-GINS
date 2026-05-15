"""Unit tests for N8H visual decision.

中文说明：测试完整 toy review 可进入 visual validation passed。
"""

from scripts.audit_n8h_fgo_feedback_visual_validation import make_toy_n8g_root
from legsa_gins.fgo_feedback.fgo_feedback_correction_review import build_correction_review
from legsa_gins.fgo_feedback.fgo_feedback_gate_review import build_gate_review
from legsa_gins.fgo_feedback.fgo_feedback_plot_semantic_guard import build_plot_semantic_guard
from legsa_gins.fgo_feedback.fgo_feedback_position_disabled_audit import build_position_disabled_audit
from legsa_gins.fgo_feedback.fgo_feedback_variant_ablation_review import build_variant_ablation_review
from legsa_gins.fgo_feedback.fgo_feedback_visual_decision import build_visual_decision_report
from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import load_n8h_visual_inputs


def test_visual_decision_passes_complete_toy_review(tmp_path):
    n8g_root = tmp_path / "n8g"
    make_toy_n8g_root(n8g_root)
    bundle = load_n8h_visual_inputs(n8g_root)
    position = build_position_disabled_audit(bundle)
    variant = build_variant_ablation_review(bundle)
    gate = build_gate_review(bundle)
    correction = build_correction_review(bundle)
    guard = build_plot_semantic_guard(visual_manifest=bundle.manifest, position_audit=position, variant_review=variant)
    report = build_visual_decision_report(
        visual_manifest=bundle.manifest,
        position_audit=position,
        variant_review=variant,
        gate_review=gate,
        correction_review=correction,
        semantic_guard=guard,
        plot_coverage={"all_required_figures_nonempty": True},
    )
    assert report["status"] == "fgo_feedback_visual_validation_passed"
    assert report["fgo_feedback_output_substitution"] is False
