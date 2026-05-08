# N4H4C State Feedback Contract

`stateFeedback` applies the 21-state EKF error estimate to the nominal
navigation state after `EKFUpdate`. It is a solver-internal error-state feedback
step, not output-only correction.

Feedback convention:

- Position: `pos -= DRi(pos) * dx[P_ID]`.
- Velocity: `vel -= dx[V_ID]`.
- Attitude: `qbn = rotvec2quaternion(dx[PHI_ID]) * qbn`.
- Gyro/accelerometer bias: add `dx[BG_ID]` and `dx[BA_ID]`.
- Gyro/accelerometer scale: add `dx[SG_ID]` and `dx[SA_ID]`.
- After feedback, `dx` is reset to zero.

The negative position and velocity signs follow the predicted-minus-observed
measurement residual convention used by N4H4C position and velocity updates.
The additive IMU bias/scale update follows the internal error-parameter
definition used in the LegSA-v23-core state container.

This contract does not claim final_v23 numerical parity. It only establishes
the LegSA-owned closed-loop EKF update skeleton needed before N4H4D clean replay
parity work.
