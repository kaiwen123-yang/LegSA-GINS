from legsa_gins.evaluation.yaw_metric_repair import decide_m1r2d_gate


def test_gate_blocks_solver_provider_yaw_failure():
    decision = decide_m1r2d_gate(
        yaw_gate_status="BLOCKED_SOLVER_PROVIDER_YAW_SEMANTIC_FAILURE",
        qm_gate_status="QM_SEMANTICS_CLARIFIED",
        corrected_metrics_generated=False,
        forbidden_input_violation=False,
        row_completion_valid=True,
    )
    assert decision["m1r2d_gate"] == "BLOCKED_FOR_M1R2D"
    assert decision["final_decision"] == "BLOCKED_SOLVER_PROVIDER_YAW_SEMANTIC_FAILURE"


def test_gate_conditional_when_evaluator_only_corrected():
    decision = decide_m1r2d_gate(
        yaw_gate_status="CLEAN_YAW_EVALUATOR_ONLY_CANDIDATE",
        qm_gate_status="QM_SEMANTICS_CLARIFIED",
        corrected_metrics_generated=True,
        forbidden_input_violation=False,
        row_completion_valid=True,
    )
    assert decision["m1r2d_gate"] == "CONDITIONAL_FOR_M1R2D"
