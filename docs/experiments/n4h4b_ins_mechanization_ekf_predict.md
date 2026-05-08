# N4H4B INS Mechanization and EKF Predict

N4H4B implements the LegSA-owned v23-core propagation foundation:
Earth/Rotation math, IMU compensation, INS velocity/position/attitude
mechanization, error-state `F/G/Phi/Qd` construction, covariance prediction,
and a propagation toy dry-run.

This stage is prediction only. It does not implement GNSS position update, GNSS
velocity update, GNSS yaw update, `EKFUpdate`, or `stateFeedback`.

## Implemented

- WGS84 Earth utilities for gravity, RM/RN, `DR`, `DRi`, `qne`, BLH recovery,
  earth rotation, and navigation-frame rotation.
- Rotation utilities for skew matrices, quaternions, Euler/rotation matrix
  conversion, and yaw/heading angle wrapping.
- `INSMechanization::insMech` with fixed order:
  `velUpdate -> posUpdate -> attUpdate`.
- IMU compensation using current bias/scale states without any second
  FLU-to-FRD conversion.
- `buildErrorStateMatrices` for 21-state / 18-noise prediction matrices.
- `EKFPredict` for `dx` and covariance propagation.
- `--dry-run-propagation-toy` demo mode.

## Boundary

N4H4B does not chase final_v23 numeric parity, does not run clean replay parity,
does not read final_v23 output as proposed solver input, and does not make a
performance claim. N4H4C is the next stage for GNSS measurement updates,
`EKFUpdate`, and `stateFeedback`.

Clean replay input remains a later N4H4D parity input after propagation and
measurement update stages are separately closed.
