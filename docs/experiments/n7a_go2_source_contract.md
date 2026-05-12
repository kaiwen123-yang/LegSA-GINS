# N7A Go2 source contract

Go2 `/sportmodestate` / `by2.txt` may contain stamp, `imu_state.quaternion`, `imu_state.gyroscope`, `imu_state.accelerometer`, `imu_state.rpy`, temperature, mode, gait type, position, velocity, yaw speed, foot force, foot position body, and foot speed body.

Go2 body-state is not truth. Position and velocity are Go2 internal odometry/high-level state, not RTK truth, not trace, and not final_v23 output. RPY/quaternion are not high-precision absolute truth. They can only be used as weak priors after source, time, and frame checks.

N7A activates only roll/pitch weak attitude prior. Go2 position and velocity priors are disabled by default in N7A. Go2 yaw prior is disabled in N7A. Yaw speed, body velocity, position, foot force, gait type, and mode are readiness/future source-aware metadata only.

No trace/final_v23 output is used for Go2 prior construction. No paper performance claim. No FGO.
