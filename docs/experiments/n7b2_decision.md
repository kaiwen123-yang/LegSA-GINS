# N7B2 Decision

N7B2 emits `N7B2_GO2_CONTACT_THRESHOLD_DECISION_REPORT.json`.

Decision statuses:

- `contact_still_not_ready`
- `ready_for_go2_velocity_contact_weak_prior_activation`
- `contact_ready_velocity_not_ready`
- `foot_force_field_not_reliable`

Decision rules:

- If the foot-force field is sparse, mostly zero, or low dynamic range, the
  status is `foot_force_field_not_reliable`.
- If the smoothed v2 uncertain ratio remains above 0.5, the status is
  `contact_still_not_ready`.
- If contact is ready and contact-conditioned velocity consistency is
  acceptable, the status may be
  `ready_for_go2_velocity_contact_weak_prior_activation`.
- If contact is ready but velocity consistency is not acceptable, the status is
  `contact_ready_velocity_not_ready`.

Always false:

- `paper_performance_claim`
- `go2_position_truth_claim`
- `go2_velocity_truth_claim`
- `contact_conditioned_velocity_truth_error_claim`
- `trace_solver_input`
- `final_v23_output_solver_input`
- `go2_velocity_prior_enabled`
- `go2_yaw_prior_enabled`
- `output_only_correction`
- `bad_epoch_deletion_for_metric`
- `fgo`
