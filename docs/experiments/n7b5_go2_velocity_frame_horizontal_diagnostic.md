# N7B5 Go2 Velocity Frame Horizontal Diagnostic

N7B5 follows N7B4 after the contact probability model became diagnostic-ready but the velocity frame margin remained too small for formal activation.

Scope:
- compare the N7B4 top frames, `go2_velocity_as_body_flu_then_rotate_by_go2_attitude` and `yaw_only_rotation_diagnostic_only`;
- build diagnostic-only horizontal Go2 velocity prior CSVs;
- run full-3D and horizontal-only sensitivity variants;
- decide whether N7C can review a formal horizontal weak prior.

Boundaries:
- Go2 velocity is not truth;
- trace and final_v23 output are not solver input and are not used for frame tuning;
- vertical Go2 velocity is disabled in horizontal-only diagnostic priors by `std_vd=999`;
- formal Go2 velocity prior is disabled in N7B5;
- Go2 yaw prior is disabled;
- no FGO, output-only correction, epoch deletion, paper performance claim, or outperform final_v23 claim.

Runtime inputs are passed by role alias:
- `N7B4_literature_contact_velocity_runtime_report_root`
- `N7A_go2_body_state_runtime_report_root`
- `N5B_raw_doppler_runtime_report_root`
- `N6B_source_aware_policy_runtime_report_root`
- `clean_receiver_velocity_runtime_root`
- `N7B5_runtime_output_root`
- `N7B5_runtime_figure_root`
