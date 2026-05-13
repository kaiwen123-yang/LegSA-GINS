# N7B3 Go2 Contact/Velocity Diagnostic Activation

N7B3 is a diagnostic-only continuation of PR #36. It does not merge PR #36,
does not create a tag, does not open a new PR, and does not implement FGO.

Runtime inputs are provided by role aliases:

- `N7A_go2_body_state_runtime_report_root`
- `N7B_velocity_contact_runtime_report_root`
- `N7B2_contact_threshold_runtime_report_root`
- `N7B2A_metric_contact_runtime_report_root`
- `N5B_raw_doppler_runtime_report_root`
- `N6B_source_aware_policy_runtime_report_root`
- `clean_receiver_velocity_runtime_root`
- `N7B3_runtime_output_root`
- `N7B3_runtime_figure_root`

The runner reviews Go2 velocity frame hypotheses, builds Go2-field-only contact
model candidates, writes diagnostic velocity/yaw-rate prior CSVs, runs
diagnostic EKF variants, generates figures, and writes a decision report.

Boundary:

- Go2 position is not truth.
- Go2 velocity is not truth.
- Cross-source consistency is not truth error.
- Contact thresholds are derived from Go2 fields only.
- Trace/final_v23 outputs are not used for thresholds or frame selection.
- Diagnostic activation is not paper performance.
- Formal Go2 velocity prior is not enabled by N7B3.
- Formal Go2 yaw prior is not enabled by N7B3.
- No output-only correction.
- No FGO claim.
