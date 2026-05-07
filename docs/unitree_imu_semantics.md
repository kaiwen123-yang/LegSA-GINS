# Unitree IMU Semantics

N4G treats Unitree `sportmodestate` as a diagnostic body-state source.

- quaternion order is `w, x, y, z`
- gyroscope unit is `rad/s`
- accelerometer unit is `m/s^2`
- accelerometer contains gravity
- RPY order is `roll, pitch, yaw`
- RPY unit is `rad`
- Go2 body frame is `FLU`

The parser checks quaternion-to-RPY consistency and records
`quaternion_rpy_consistency_status`. The Go2 high-level `position` and
`velocity` fields are Go2 odom signals, not GNSS/INS global truth. Foot body
signals remain body-relative diagnostics and are not leg-odometry factors.

Raw accelerometer direct integration is deprecated diagnostic only. The main N4G
candidate uses `gyro_only_zero_dvel`; a second candidate uses
`quaternion_gravity_compensated` as a diagnostic gravity-compensated trial, not
as final mechanization.

