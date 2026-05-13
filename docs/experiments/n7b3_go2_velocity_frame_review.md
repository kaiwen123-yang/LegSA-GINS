# N7B3 Go2 Velocity Frame Review

The velocity frame review compares diagnostic Go2 velocity candidates against
receiver-native velocity and raw Doppler velocity. The comparison namespace is
`cross-source consistency`, not truth error.

Frame hypotheses:

- `go2_velocity_as_world_enu_or_ned_direct`
- `go2_velocity_as_body_flu_then_rotate_by_go2_attitude`
- `go2_velocity_flu_to_frd_then_rotate`
- `sign_flip_y`
- `sign_flip_z`
- `xy_swap_diagnostic_only`
- `yaw_only_rotation_diagnostic_only`

The selected frame is only a recommended frame for diagnostic prior attempts.
It must not be described as ground truth. The review writes
`GO2_VELOCITY_FRAME_REVIEW_REPORT.json` with `no_truth_claim=true`,
`trace_solver_input=false`, and `final_v23_output_solver_input=false`.
