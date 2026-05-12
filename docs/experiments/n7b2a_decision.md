# N7B2A Decision

N7B2A emits `N7B2A_GO2_METRIC_CONTACT_DECISION_REPORT.json`.

Decision statuses:

- `needs_metric_namespace_fix`
- `contact_v2_not_ready`
- `ready_for_go2_velocity_contact_weak_prior_activation`
- `needs_attitude_std_policy_review`

Decision rules:

- If metric namespace is missing, next stage is
  `N7B2B_metric_namespace_report_fix`.
- If contact v2 physical plausibility is review or not-ready, next stage is
  `N7B3_contact_model_review_or_N8A_no_feedback_FGO_foundation`.
- If contact v2 is physically plausible and velocity consistency is acceptable,
  a future N7C activation review may be allowed.
- If attitude std policy is unclear, next stage is
  `N7B2B_attitude_prior_std_review`.

Always false:

- `paper_performance_claim`
- `go2_position_truth_claim`
- `go2_velocity_truth_claim`
- `trace_solver_input`
- `final_v23_output_solver_input`
- `go2_velocity_prior_enabled`
- `go2_yaw_prior_enabled`
- `output_only_correction`
- `bad_epoch_deletion_for_metric`
- `fgo`
