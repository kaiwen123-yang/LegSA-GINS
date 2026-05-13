# N7B4 Decision

N7B4 decides whether literature-informed contact probability plus velocity-frame scoring is enough to justify a later N7C review.

Possible statuses:

- `ready_for_N7C_diagnostic_to_formal_go2_velocity_prior_review`
- `contact_ready_frame_ambiguous`
- `go2_velocity_prior_not_recommended`
- `go2_contact_model_not_ready`
- `diagnostic_activation_no_effect_or_blocked`

Even the ready status is only permission to review a future formal weak-prior stage. N7B4 itself remains diagnostic-only.

Boundary: `"diagnostic_only": True`, `"paper_performance_claim": False`, `"trace_solver_input": False`, `"final_v23_output_solver_input": False`, `"fgo": False`.
