# BY2 Go2 Body-State Contract

N4E parses `by2.txt` as Go2 body-state diagnostic data from `/sportmodestate` text. It does not create Go2 yaw-rate priors, attitude priors, support-foot factors, LSIM/OIM, or source-aware weighting.

## Frame Policy

- Go2 body / IMU frame: `FLU`.
- `sportmodestate.imu_state` is body/IMU data.
- `sportmodestate.position` and `sportmodestate.velocity` belong to Go2 odom and are not navigation NED measurements.
- `foot_position_body` and `foot_speed_body` are body-relative.
- `body_state_requires_frame_adapter: true`.

Before any later estimator use, Go2 body-state data must pass a frame adapter and role-specific validation.

## Diagnostic Output

N4E writes a diagnostic CSV with timestamp, raw quaternion slots, gyroscope, accelerometer, RPY, yaw speed, gait/mode fields, foot force, foot body-position, and foot body-speed fields.

Quaternion order is not asserted in N4E. The CSV keeps `quat_0`, `quat_1`, `quat_2`, and `quat_3` instead of reordering to `w/x/y/z`.

Evidence status:

- `evidence_missing: quaternion_order_needs_validation`
- `trace_solver_input: false`
- `receiver_imu_as_body_imu: false`
