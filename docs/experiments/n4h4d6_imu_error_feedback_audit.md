# N4H4D6 IMU Error Feedback Audit

N4H4D6 exists because D5 showed that one-step mechanization is close, measurement residuals are reasonable under an external-state shadow audit, and `pos_vel_only` diagnostic feedback is much more stable than full feedback.

This stage audits IMU error-state feedback, bias/scale coupling, compensation timing, and covariance-unit evidence. It does not tune the solver, delete epochs, use trace as solver input, or claim performance.

Key runtime debug files are `IMU_ERROR_FEEDBACK_TRACE.csv`, `IMU_COMPENSATION_TRACE.csv`, `CROSS_COVARIANCE_TRACE.csv`, and `IMU_ERROR_UNIT_SNAPSHOT.json`. They are runtime-only artifacts and must not be committed.

