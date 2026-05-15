"""Unit tests for N8H visual loader.

中文说明：测试 loader 只输出 role/path-safe manifest。
"""

from scripts.audit_n8h_fgo_feedback_visual_validation import make_toy_n8g_root
from legsa_gins.fgo_feedback.fgo_feedback_visual_loader import load_n8h_visual_inputs


def test_visual_loader_builds_path_safe_manifest(tmp_path):
    n8g_root = tmp_path / "n8g"
    make_toy_n8g_root(n8g_root)
    bundle = load_n8h_visual_inputs(n8g_root)
    assert bundle.manifest["all_required_n8g_reports_found"] is True
    assert bundle.manifest["primary_feedback_variant_found"] is True
    assert bundle.manifest["output_substitution_false"] is True
    assert bundle.manifest["absolute_path_recorded"] is False
