"""中文说明：测试 R3C metric namespace 分类，不混用 parity 与 absolute。"""

from legsa_gins.evaluation.legsa_v23_port_metric_namespace import MetricNamespace, classify_metric_namespace


def test_classifies_port_vs_final_v23_nav_parity():
    report = classify_metric_namespace({"reference_path": "dual_final_v23/KF_GINS_Navresult.nav"})
    assert report["namespace"] == MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value
    assert report["comparable_to_port_finalv23_parity"] is True
    assert report["comparable_to_external_clean_absolute"] is False
    assert report["paper_performance_claim"] is False


def test_classifies_trace_absolute_namespace():
    report = classify_metric_namespace(
        {"solver_output_role": "port_nav", "reference_role": "trace/reference trajectory"}
    )
    assert report["namespace"] == MetricNamespace.PORT_VS_TRACE_ABSOLUTE.value
    assert report["comparable_to_external_clean_absolute"] is True


def test_unknown_namespace_is_evidence_missing():
    report = classify_metric_namespace({"metric": "unlabeled"})
    assert report["namespace"] == MetricNamespace.EVIDENCE_MISSING.value
    assert report["misuse_warning"] == "metric_namespace_evidence_missing"
