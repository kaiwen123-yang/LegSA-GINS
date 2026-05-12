# N7B Decision

N7B emits `N7B_GO2_VELOCITY_CONTACT_DECISION_REPORT.json`.

Decision rules:

- If contact state is invalid or too uncertain, status is
  `contact_not_ready` and the next stage is `N7B2_contact_threshold_review`.
- If Go2 velocity is strongly inconsistent with receiver/raw Doppler, status is
  `velocity_not_ready` and the next stage is
  `N7B2_velocity_frame_or_quality_review`.
- If contact state is good and Go2 velocity cross-source consistency is
  acceptable, status is `ready_for_go2_velocity_weak_prior_activation` and the
  next stage is `N7C_go2_velocity_contact_weak_prior_activation`.
- If Go2 velocity is weak but yaw-speed is promising, status is
  `ready_for_go2_yaw_rate_prior_review` and the next stage is
  `N7C_go2_yaw_rate_weak_prior_review`.
- If roll/pitch prior is enough and velocity/contact evidence is weak, status
  is `skip_extended_go2_priors_prepare_FGO` and the next stage is
  `N8A_no_feedback_FGO_foundation`.

Always false:

- `paper_performance_claim`
- `go2_position_truth_claim`
- `go2_velocity_truth_claim`
- `trace_solver_input`
- `final_v23_output_solver_input`
- `output_only_correction`
- `bad_epoch_deletion_for_metric`
- `go2_velocity_prior_enabled`
- `go2_yaw_prior_enabled`
- `fgo`
