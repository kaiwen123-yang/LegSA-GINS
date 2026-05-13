"""N7B4 literature review 单元测试：只检查 diagnostic boundary。"""

from legsa_gins.go2_prior.go2_literature_contact_review import build_literature_contact_review_report


def test_literature_contact_review_is_diagnostic_only():
    report = build_literature_contact_review_report()
    assert report["diagnostic_only"] is True
    assert report["paper_performance_claim"] is False
    assert report["runtime_online_dependency"] is False
    assert len(report["references"]) >= 3
