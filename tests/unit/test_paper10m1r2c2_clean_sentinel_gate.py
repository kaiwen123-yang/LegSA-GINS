from legsa_gins.evaluation.yaw_clean_sentinel_gate import evaluate_clean_sentinel_gate


def _row(method: str, yaw: float) -> dict[str, object]:
    return {
        "method_mode_id": method,
        "terminal_status": "COMPLETED_EVALUABLE",
        "yaw_rmse_deg": yaw,
        "trace_solver_input": False,
        "final_v23_output_solver_input": False,
        "legsa_output_solver_input": False,
        "output_only_correction_used": False,
        "epoch_deleted_for_metric": False,
    }


def test_clean_sentinel_gate_passes_clean_yaw_thresholds() -> None:
    rows = [
        _row("basic_dual_baseline", 2.2),
        _row("strong_dual_yaw_baseline", 1.8),
        _row("legsa_without_qm", 1.8),
        _row("legsa_full_candidate_with_qm", 2.1),
    ]

    gate = evaluate_clean_sentinel_gate(rows)

    assert gate["pass"] is True
    assert gate["gate_status"] == "PASS_PAPER10M1R2C2_CLEAN_SENTINEL_GATE"


def test_clean_sentinel_gate_blocks_strong_yaw_over_5deg() -> None:
    rows = [
        _row("basic_dual_baseline", 2.2),
        _row("strong_dual_yaw_baseline", 5.1),
        _row("legsa_without_qm", 1.8),
        _row("legsa_full_candidate_with_qm", 2.1),
    ]

    gate = evaluate_clean_sentinel_gate(rows)

    assert gate["pass"] is False
    assert "strong_dual_yaw_baseline" in gate["blockers"][0]
