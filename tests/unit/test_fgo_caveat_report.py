"""Tests for N8E caveat report.

中文说明：验证 N8E 必需 caveat 均存在。
"""

from legsa_gins.fgo.fgo_caveat_report import REQUIRED_CAVEATS, build_caveat_report


def test_caveat_report_has_required_boundary_caveats() -> None:
    report = build_caveat_report(matrix_report={"matrix_complete": True}, module_summary={"module_count": 8})
    assert report["all_required_caveats_present"]
    assert sorted(report["required_caveats"]) == sorted(REQUIRED_CAVEATS)
    assert report["raw_doppler_low_marginal_value_is_not_failure"]
    assert report["candidate_factors_need_deeper_review"]
    assert not report["paper_performance_claim"]
