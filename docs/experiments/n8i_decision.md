# N8I Decision

N8I writes `N8I_FEEDBACK_ABLATION_GATE_COVARIANCE_DECISION_REPORT.json`.

Decision statuses:

- `feedback_policy_not_ready`;
- `default_feedback_policy_ready`;
- `conservative_feedback_gate_ready`;
- `refined_covariance_policy_ready`;
- `velocity_feedback_only_recommended`.

The decision records selected feedback policy, selected gate, selected
covariance policy, selected window policy, reject-all sanity, and the PVA
diagnostic caveat.

Always false:

- `fgo_feedback_output_substitution`;
- `fgo_feedback_direct_nav_override`;
- `trace_solver_input`;
- `final_v23_output_solver_input`;
- `paper_performance_claim`.
