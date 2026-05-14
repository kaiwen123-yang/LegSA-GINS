"""Tests for N8E decision rules.

中文说明：验证 N8E ready-with-caveats 决策边界。
"""

from legsa_gins.fgo.fgo_n8e_decision import make_n8e_decision


def test_n8e_decision_ready_with_caveats() -> None:
    decision = make_n8e_decision(
        matrix_report={
            "matrix_complete": True,
            "no_fgo_feedback": True,
            "no_fgo_output_substitution": True,
            "no_trace_finalv23_solver_input_or_tuning": True,
            "paper_performance_claim": False,
            "raw_doppler_fgo_active_but_low_marginal_value": True,
        },
        caveat_report={
            "all_required_caveats_present": True,
            "candidate_factors_need_deeper_review": True,
            "fgo_output_feedback_to_ekf": False,
            "fgo_output_substitution": False,
        },
        claim_boundary_report={"forbidden_claim_count": 0, "decision": "pass"},
        figure_manifest={"figure_count_total": 10, "required_figures_nonempty": True},
    )
    assert decision["status"] == "formal_engineering_ablation_ready_with_caveats"
    assert decision["secondary_recommendation"] == "N8F_candidate_factor_review"
    assert not decision["paper_performance_claim"]
    assert decision["no_outperform_final_v23_claim"]
