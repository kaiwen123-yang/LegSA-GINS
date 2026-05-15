"""Unit tests for N8H variant ablation review.

中文说明：测试 reject-all sanity 和 no-substitution 边界。
"""

from scripts.audit_n8h_fgo_feedback_visual_validation import make_toy_n8g_root
from legsa_gins.fgo_feedback.fgo_feedback_variant_ablation_review import build_variant_ablation_review
from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import load_n8h_visual_inputs


def test_variant_ablation_requires_reject_all_sanity(tmp_path):
    n8g_root = tmp_path / "n8g"
    make_toy_n8g_root(n8g_root)
    report = build_variant_ablation_review(load_n8h_visual_inputs(n8g_root))
    assert report["variant_count"] == 7
    assert report["reject_all_sanity_passed"] is True
    assert report["no_output_substitution"] is True
