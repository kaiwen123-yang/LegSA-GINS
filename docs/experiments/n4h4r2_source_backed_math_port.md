# N4H4R2 Source-Backed Math Port

N4H4R2 completes the mathematical backbone port inside
`cpp/legsa_v23_port_core`. The port is source-backed by the final_v23/KF-GINS
reference commit `5a4471efd4fcfcdc31e258a677af354c652ff16f` and remains a
backbone implementation, not paper novelty.

Implemented scope:

- Earth and Rotation utilities.
- GINS options, IMU/GNSS/NavState types, 21-state and 18-noise indices.
- Config unit conversions for position, attitude, IMU error, noise, and
  correlation time.
- 7-column IMU loader and 15-column loose-coupled GNSS loader.
- INS mechanization in velocity, position, attitude order.
- GIEngine flow for `newImuProcess`, `imuInterpolate`, `imuCompensate`,
  `insPropagation`, `gnssUpdate`, `EKFPredict`, `EKFUpdate`, and
  `stateFeedback`.
- NAV, STD, EVAL_NAV, and RUN_MANIFEST writers.

N4H4R2 does not run real clean replay parity and does not make a performance
claim. R2 synthetic math output is a smoke artifact only. N4H4R3 is required for
the first honest clean replay parity pass/fail report.
