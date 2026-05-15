"""Unit tests for N8H position-disabled audit.

中文说明：测试 primary applied position 为零而 diagnostic PVA 单独统计。
"""

from scripts.audit_n8h_fgo_feedback_visual_validation import make_toy_n8g_root
from legsa_gins.fgo_feedback.fgo_feedback_position_disabled_audit import build_position_disabled_audit
from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import load_n8h_visual_inputs


def test_position_disabled_audit_splits_primary_and_pva(tmp_path):
    n8g_root = tmp_path / "n8g"
    make_toy_n8g_root(n8g_root)
    report = build_position_disabled_audit(load_n8h_visual_inputs(n8g_root))
    assert report["status"] == "aggregate_explained"
    assert report["primary_position_enabled"] is False
    assert report["primary_position_correction_applied_stats_m"]["max"] == 0.0
    assert report["diagnostic_pva_position_correction_applied_stats_m"]["max"] > 0.0
