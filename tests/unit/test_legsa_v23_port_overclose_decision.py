"""中文说明：测试 R3B decision precedence。"""

from legsa_gins.evaluation.legsa_v23_port_overclose_decision import make_overclose_decision


BASE_OVERCLOSE = {"metric_gate_passed": True, "external_closeness_failed": True}
BASE_COPY = {"measurement_copy_suspect": False, "output_substitution_suspect": False}
BASE_REF = {"reference_independence_ok": True}
BASE_CONFIG = {"covariance_config_mismatch": False}
BASE_GAIN = {"over_tight_measurement_update_suspect": False}


def test_maps_copy_issue_to_writer_fix():
    decision = make_overclose_decision(BASE_OVERCLOSE, {"measurement_copy_suspect": True}, BASE_REF, BASE_CONFIG, BASE_GAIN)
    assert decision["recommended_next_stage"] == "N4H4R3C_writer_measurement_copy_fix"


def test_maps_reference_issue_to_evaluator_fix():
    decision = make_overclose_decision(BASE_OVERCLOSE, BASE_COPY, {"reference_independence_ok": False}, BASE_CONFIG, BASE_GAIN)
    assert decision["recommended_next_stage"] == "N4H4R3C_reference_evaluator_fix"


def test_maps_config_issue_to_config_fix():
    decision = make_overclose_decision(BASE_OVERCLOSE, BASE_COPY, BASE_REF, {"covariance_config_mismatch": True}, BASE_GAIN)
    assert decision["recommended_next_stage"] == "N4H4R3C_covariance_config_parity_fix"


def test_no_issue_metric_pass_goes_to_visual_validation_with_caveat():
    decision = make_overclose_decision(BASE_OVERCLOSE, BASE_COPY, BASE_REF, BASE_CONFIG, BASE_GAIN)
    assert decision["recommended_next_stage"] == "N4H4E_visual_validation_with_external_closeness_caveat"
    assert decision["paper_performance_claim"] is False
