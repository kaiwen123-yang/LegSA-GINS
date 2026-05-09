# N4H4R2 GIEngine Port Contract

The R2 `GIEngine` implements the source-backed GNSS/INS backbone functions:

- `initialize`
- `addImuData`
- `addGnssData`
- `newImuProcess`
- `isToUpdate`
- `imuInterpolate`
- `imuCompensate`
- `insPropagation`
- `gnssUpdate`
- `EKFPredict`
- `EKFUpdate`
- `stateFeedback`
- `getNavState`
- `getCovariance`

Special contracts:

- IMU increments are assumed already converted by `process_data`; the port does
  not do a second FLU-to-FRD transform.
- `imuInterpolate` only splits increments. Compensation is applied in
  propagation.
- GNSS position residual is predicted antenna position minus observed GNSS.
- EKF update uses `dx += K * (dz - H * dx)` and Joseph covariance form.
- State feedback subtracts position/velocity error, left-multiplies attitude
  error, adds bias/scale error, and resets `dx`.
- scheme_C yaw gating is retained as a backbone runtime policy, not as a
  proposed factor.

Critical C++ functions carry Chinese comments and provenance headers.
