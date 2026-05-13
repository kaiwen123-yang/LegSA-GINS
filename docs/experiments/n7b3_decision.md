# N7B3 Decision

N7B3 writes `N7B3_GO2_CONTACT_VELOCITY_DIAGNOSTIC_DECISION_REPORT.json`.

Decision statuses:

- `go2_velocity_contact_not_ready`
- `velocity_frame_ready_contact_not_ready`
- `ready_for_N7C_go2_velocity_contact_weak_prior_activation`
- `diagnostic_activation_degraded`

N7C can only be recommended when the contact model is plausible and diagnostic
velocity activation is stable without degradation. If frame/contact remains
blocked, N7B4 or N8A remains the next step. Any yaw-rate recommendation is
secondary because yaw-rate is not activated in the current state model.

Always false:

- `paper_performance_claim`
- `go2_velocity_truth_claim`
- `trace_solver_input`
- `final_v23_output_solver_input`
- `output_only_correction`
- `fgo`
