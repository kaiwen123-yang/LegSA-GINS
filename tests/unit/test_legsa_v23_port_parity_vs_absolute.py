"""中文说明：测试 R3C parity-vs-absolute 拆分和 R3B misuse 检测。"""

from legsa_gins.evaluation.legsa_v23_port_metric_namespace import MetricNamespace
from legsa_gins.evaluation.legsa_v23_port_parity_vs_absolute import compare_parity_and_absolute


def test_detects_r3b_external_closeness_misuse():
    report = compare_parity_and_absolute(
        {"namespace": MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value, "parity_small": True, "aligned_count": 10},
        None,
        None,
        {
            "namespace": MetricNamespace.EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE.value,
            "compared_metric_namespace": MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value,
        },
    )
    assert report["r3b_external_closeness_misuse_detected"] is True
    assert report["corrected_parity_status"] == "parity_to_finalv23_passed_absolute_missing"
    assert report["paper_performance_claim"] is False


def test_corrected_backbone_parity_decision_when_absolute_close():
    parity = {"namespace": MetricNamespace.PORT_VS_FINAL_V23_NAV_PARITY.value, "parity_small": True, "aligned_count": 10}
    port_abs = {
        "namespace": MetricNamespace.PORT_VS_TRACE_ABSOLUTE.value,
        "absolute_trace_evaluation_status": "available",
        "aligned_count": 10,
        "horizontal_rmse_m": 0.36,
        "up_rmse_m": 0.82,
        "yaw_rmse_deg": 1.85,
        "roll_rmse_deg": 1.02,
        "pitch_rmse_deg": 1.52,
    }
    final_abs = {
        "namespace": MetricNamespace.FINAL_V23_VS_TRACE_ABSOLUTE.value,
        "absolute_trace_evaluation_status": "available",
        "official_summary_reproduced": True,
        "aligned_count": 10,
        "horizontal_rmse_m": 0.35,
        "up_rmse_m": 0.81,
        "yaw_rmse_deg": 1.81,
        "roll_rmse_deg": 1.02,
        "pitch_rmse_deg": 1.52,
    }
    report = compare_parity_and_absolute(
        parity,
        port_abs,
        final_abs,
        {"namespace": MetricNamespace.EXTERNAL_CLEAN_KFGINS_VS_TRACE_ABSOLUTE.value},
    )
    assert report["corrected_parity_status"] == "backbone_parity_passed"
    assert report["port_absolute_close_to_finalv23_absolute"] is True
