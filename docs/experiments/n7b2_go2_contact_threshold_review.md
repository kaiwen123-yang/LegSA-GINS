# N7B2 Go2 Contact Threshold Review

N7B2 follows the N7B decision that Go2 velocity and yaw-speed are promising
diagnostic signals, but the contact classifier is not ready because the
uncertain ratio is too high.

N7B2 is contact threshold readiness only. It reviews foot-force and
foot-speed distributions, mode/gait/body-height context, motion velocity, and
contact-conditioned velocity consistency. It does not activate a Go2 velocity
prior, does not activate a Go2 yaw prior, does not implement FGO, and does not
make a paper performance claim.

Inputs are role aliases:

- N7A Go2 body-state runtime report root.
- N7B velocity/contact runtime report root.
- N5B raw Doppler runtime report root.
- N6B source-aware runtime report root.
- Clean receiver-velocity runtime root.

Outputs are runtime-only:

- `GO2_CONTACT_DISTRIBUTION_REPORT.json`
- `GO2_CONTACT_THRESHOLD_REVIEW_REPORT.json`
- `GO2_CONTACT_STATE_V2_REPORT.json`
- `GO2_CONTACT_STATE_V2_TIMESERIES.csv`
- `GO2_CONTACT_SMOOTHING_REPORT.json`
- `GO2_CONTACT_VELOCITY_SEGMENT_REVIEW.json`
- `N7B2_GO2_CONTACT_THRESHOLD_DECISION_REPORT.json`
- `N7B2_FIGURE_MANIFEST.json`
- `n7b2_contact_threshold_case_review.md`

Boundary:

- `go2_field_distribution_only`
- `thresholds_are_diagnostic`
- `navigation_metric_tuning=false`
- `trace_solver_input=false`
- `final_v23_output_solver_input=false`
- Go2 velocity is not truth.
- Contact-conditioned velocity comparison is not truth error.
- `go2_velocity_prior_enabled=false`
- `go2_yaw_prior_enabled=false`
- `paper_performance_claim=false`
- `fgo=false`
