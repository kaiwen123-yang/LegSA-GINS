# BY2 frame audit

Status: `CLOSED_MAINTAINED_SOFTWARE_DIRECTION_REAL_BY2_COMPLETE_RECORD_PREFIX`. The immutable raw source is incomplete, while its exact 63,277-record prefix is filter-eligible under `BY2_COMPLETE_RECORD_POLICY_V1`.

The paper contract uses active `R_WB` from body/IMU coordinates to a world-up Hartley gauge. The explicit chain is raw IMU sensor/source axes → corrected robot-body FLU by the frozen installation rotation → Hartley body by identity. The maintained input builder applies `RzRyRx(-1°,0°,0°)` by left-multiplying each IMU vector. The frozen software direction is therefore sensor-to-body active rotation:

```text
[[1, 0, 0],
 [0, 0.9998476951563913,  0.01745240643728351],
 [0,-0.01745240643728351, 0.9998476951563913]]
```

The determinant is `+1`, orthogonality and round-trip Frobenius errors are `0`, and the matrix is right-handed. The known-axis checks map sensor `+Y` to `[0,0.9998476951563913,-0.01745240643728351]` and sensor `+Z` to `[0,0.01745240643728351,0.9998476951563913]`.

`foot_position_body` is already expressed in robot-body FLU and does not receive the IMU installation rotation.

An offline input-only stationary-candidate diagnostic used the 633 lowest stable-sorted scores `gyro_norm/median + max_foot_speed_norm/median` from the 63,277 complete messages. Median gyro norm was `0.006985405045971301 rad/s`; median maximum foot-speed norm was `0.021942319569801246 m/s`. Under a level-body assumption only, the frozen sensor-to-body interpretation produced `0.20591299391339885 m/s²` residual, versus `0.23197377843950862 m/s²` for its inverse. Foot speed is `DIAGNOSTIC_ONLY`, is unavailable online, and cannot affect contact thresholds or states. Low motion does not prove the robot is physically level, so direction is frozen by maintained software semantics, not by this comparison.

For the required stationary cancellation test, corrected mean specific force `[-0.1423245110971291,0.1487915535872073,9.509044229287252] m/s²` initializes roll `0.8964552251045289°` and pitch `0.8573929075977925°`; yaw is arbitrary. Then `R0 f_bar + [0,0,-|f_bar|]` has norm `1.776493855757274e-15 m/s²`.

The world-up → NED-shaped reporting gauge is the proper rotation `diag(1,-1,-1)`. It left-multiplies world components of rotation, velocity, position, and contacts; covariance maps as `T P T^T` with that rotation on spatial error blocks and identity on body-bias blocks. It creates no observed north or heading measurement.

These checks do not recalibrate the installation or create attitude/heading truth. No quaternion, RPY, pose, velocity, yaw, or trace/reference value was materialized.
