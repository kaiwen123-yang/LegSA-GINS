# N7C6 Factor Jacobian Contract

Joint residual dimension: 4.

State dimension: 21.

Nonzero state blocks:

- `attitude_roll`
- `attitude_pitch`
- `velocity_north`
- `velocity_east`

Zero state blocks:

- position
- yaw
- vertical velocity
- IMU biases

`R = diag(std_roll^2, std_pitch^2, std_vn^2, std_ve^2)`.

The toy finite-difference check verifies derivative 1 for roll, pitch, vN, and
vE residuals, and derivative 0 for position, yaw, and vertical velocity.
