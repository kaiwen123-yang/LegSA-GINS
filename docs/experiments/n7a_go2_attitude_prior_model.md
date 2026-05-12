# N7A Go2 attitude prior model

The N7A factor source is `go2_attitude_roll_pitch`.

Measurement:
- roll and pitch from Go2 rpy/quaternion after internal consistency checks.

Residual:
- `dz = current_roll_pitch - go2_roll_pitch`
- roll/pitch residuals are wrapped to `[-pi, pi]`.

Jacobian:
- H maps the residual to the PHI_ID roll/pitch attitude error components.

Covariance:
- default `std_roll_deg = 5.0`
- default `std_pitch_deg = 5.0`
- this is a weak conservative prior, not truth.

The prior enters the C++ EKFUpdate path and then uses the existing stateFeedback sequence. It is not output-only correction. It does not use Go2 position as global truth. It does not use trace or final_v23 output for tuning. No paper performance claim.
