# N8A2 Yaw Residual Contract

All FGO yaw residuals use shortest-angle wrapping.

Contracts:

- DualYawFactor: `wrap(yaw_state - yaw_measurement)`
- YawSmoothnessFactor: `wrap((yaw_next - yaw_prev) - expected_delta_yaw)`
- Go2YawRateBetweenFactor diagnostic: `wrap((yaw_next - yaw_prev) - yaw_rate * dt)`
- FGO-vs-EKF yaw evaluation reports both raw and wrapped RMSE; wrapped RMSE is the primary yaw delta metric.

Unwrapped yaw may be used for plotting continuity only, not residuals.

Trace/final_v23 outputs are not solver inputs.
