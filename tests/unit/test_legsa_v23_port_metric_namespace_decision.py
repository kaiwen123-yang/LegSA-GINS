"""中文说明：测试 R3C corrected status 到下一阶段的映射。"""

from legsa_gins.evaluation.legsa_v23_port_metric_namespace_decision import make_metric_namespace_decision


def test_backbone_parity_passed_maps_to_visual_validation():
    decision = make_metric_namespace_decision({"comparison": {"corrected_parity_status": "backbone_parity_passed"}})
    assert decision["recommended_next_stage"] == "N4H4E_visual_validation_for_source_backed_port"
    assert decision["engineering_backbone_candidate"] is True
    assert decision["paper_performance_claim"] is False


def test_absolute_missing_maps_to_recovery():
    decision = make_metric_namespace_decision(
        {"comparison": {"corrected_parity_status": "parity_to_finalv23_passed_absolute_missing"}}
    )
    assert decision["recommended_next_stage"] == "N4H4R3D_absolute_trace_evaluation_recovery"
    assert decision["engineering_backbone_candidate"] == "conditional"
