"""Unit tests for N8H gate review.

中文说明：测试全接受且低于阈值时 gate 可判为 reasonable。
"""

from scripts.audit_n8h_fgo_feedback_visual_validation import make_toy_n8g_root
from legsa_gins.fgo_feedback.fgo_feedback_gate_review import build_gate_review
from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import load_n8h_visual_inputs


def test_gate_review_accept_all_below_caps_is_reasonable(tmp_path):
    n8g_root = tmp_path / "n8g"
    make_toy_n8g_root(n8g_root)
    report = build_gate_review(load_n8h_visual_inputs(n8g_root))
    assert report["accepted"] == 6
    assert report["rejected"] == 0
    assert report["classification"] == "gate_reasonable"
