"""Unit tests for N7C5A visual decision.

中文说明：测试 N7C5A 是否允许进入 N7C6 的决策。
"""

from legsa_gins.go2_prior.go2_n7c5a_decision import make_n7c5a_visual_decision


def test_n7c5a_decision_blocks_or_passes():
    passed = make_n7c5a_visual_decision(
        sanity_report={"visual_blocker": False, "blocker_reasons": []},
        coverage_report={"contact_rows_summary_only": False},
        figure_manifest={"figure_count_total": 18, "required_figures_generated": True, "required_figures_nonempty": True},
    )
    assert passed["status"] == "n7c5_visual_review_passed"
    blocked = make_n7c5a_visual_decision(
        sanity_report={"visual_blocker": True, "blocker_reasons": ["required_figures_nonempty"]},
        coverage_report={},
        figure_manifest={},
    )
    assert blocked["status"] == "n7c5_visual_blocker"
