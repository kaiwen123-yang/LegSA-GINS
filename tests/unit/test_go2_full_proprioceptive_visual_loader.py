"""Unit tests for N7C5A visual loader.

中文说明：测试 N7C5A 图像数据加载边界。
"""

from pathlib import Path

from scripts.audit_n7c5a_go2_full_proprioceptive_visual_review import _prepare_n7c5_root
from legsa_gins.go2_prior.go2_full_proprioceptive_visual_loader import load_n7c5_visual_inputs


def test_load_n7c5_visual_inputs_toy(tmp_path: Path):
    n7c5 = _prepare_n7c5_root(tmp_path)
    inputs = load_n7c5_visual_inputs(n7c5)
    assert inputs["go2_not_truth"] is True
    assert inputs["contact_rows"]
    assert inputs["foot_rows"]
    assert inputs["ranking_report"]["candidates"]
