# N7A Go2 readiness report

N7A readiness checks are source-integrity gates, not performance claims.

Required checks:
- Go2 body-state parser reports row count, time range, dt stats, and field coverage.
- Quaternion/rpy check selects `wxyz` only when the internal delta is small enough.
- Frame contract treats Go2 body frame as FLU and records sign-candidate diagnostics without trace selection.
- Time alignment uses `aligned_time = stamp - BASE_TIME` and compares overlap with clean replay time. It does not estimate physical clock offset from trace.

Readiness-only sources:
- `go2_yaw_rate_consistency`
- `go2_velocity_frame_readiness`
- `go2_position_odometry_readiness`
- `go2_contact_stationary_readiness`

These readiness sources are not activated as EKF priors in N7A.
