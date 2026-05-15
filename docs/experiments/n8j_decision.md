# N8J Decision

N8J writes `N8J_FEEDBACK_FINAL_VALIDATION_DECISION_REPORT.json`.

Decision statuses:

- `selected_policy_mismatch`;
- `runtime_output_missing`;
- `feedback_not_entering_ekf`;
- `output_substitution_blocker`;
- `selected_feedback_policy_not_ready`;
- `feedback_joint_filter_ready_for_BY2_packaging`.

The pass status recommends
`N9_BY2_paper_experiment_packaging_or_BY3_replication`.

Always false:

- `fgo_feedback_output_substitution`;
- `fgo_feedback_direct_nav_override`;
- `trace_solver_input`;
- `final_v23_output_solver_input`;
- `paper_performance_claim`;
- `outperform_final_v23_claim`.
