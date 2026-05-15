"""Unit tests for N8H correction review.

中文说明：测试 correction review 输出 top epochs 且不做论文宣称。
"""

from scripts.audit_n8h_fgo_feedback_visual_validation import make_toy_n8g_root
from legsa_gins.fgo_feedback.fgo_feedback_correction_review import build_correction_review
from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import load_n8h_visual_inputs


def test_correction_review_records_top_epochs(tmp_path):
    n8g_root = tmp_path / "n8g"
    make_toy_n8g_root(n8g_root)
    report = build_correction_review(load_n8h_visual_inputs(n8g_root))
    assert report["variant_count"] >= 5
    assert report["top_correction_epochs"]
    assert report["paper_performance_claim"] is False
