# N8F Decision

N8F decision status is computed from solver injection, Jacobian contracts,
variant stability, contact-aware scaling, and no-feedback boundaries.

Possible outcomes include:

- `candidate_factor_solver_injection_blocker`
- `foot_kinematic_factor_ready_for_N8G_feedback_review`
- `between_factors_active_low_marginal_value`
- `default_stack_ready_candidates_diagnostic_only`
- `contact_aware_weighting_ready`
- `legged_candidates_active_low_marginal_value`

Every status preserves:

- no paper performance claim
- no FGO feedback in N8F
- no output substitution
- no trace/final_v23 solver input or tuning
- no Go2 truth claim

