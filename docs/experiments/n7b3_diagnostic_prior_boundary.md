# N7B3 Diagnostic Prior Boundary

N7B3 may attempt diagnostic Go2 velocity/contact activation through runtime-only
prior CSVs, but it does not enable a formal Go2 velocity prior.

Required flags and manifest fields:

- `enable_go2_velocity_prior_diagnostic=false` by default
- `go2_velocity_prior_diagnostic_path`
- `go2_velocity_prior_std_scale`
- `enable_go2_yaw_rate_prior_diagnostic=false` by default
- `go2_yaw_rate_prior_diagnostic_path`
- `go2_diagnostic_prior_only=true`
- `go2_velocity_prior_diagnostic_enabled`
- `go2_velocity_prior_update_count`
- `go2_velocity_prior_reject_count`
- `go2_yaw_rate_prior_diagnostic_enabled`
- `go2_yaw_rate_prior_update_count`
- `diagnostic_only=true`
- `paper_performance_claim=false`
- `go2_velocity_truth_claim=false`

The velocity diagnostic residual is `nav.vel - go2_velocity_prior` with a
conservative diagonal covariance. The yaw-rate CSV is diagnostic evidence only:
the current error-state model has no yaw-rate state, so the manifest records
`yaw_rate_prior_not_activated_due_to_state_model`.
