# N4H1P process_data-compatible input generation

This document records the N4H1P stdlib reimplementation of the uploaded
`process_data` logic.

Purpose:

- Reconstruct a final_v23-style 15-column `.gnss` runtime input.
- Reconstruct a process_imu-style 7-column `.imu` runtime input.
- Generate parity/audit reports for input provenance.

This is not a solver. It is not a raw GNSS solver. It does not solve position
from RAWX, SFRBX, or RTCM. It does not implement raw Doppler factors, Go2
priors, source-aware weighting, LSIM/OIM, FGO, or performance evaluation.

Input mapping:

- Position comes from `gnss1-status.csv`: `pos_lat`, `pos_lon`, `pos_height`.
- Position standard deviation comes from `gnss1-status.csv`: `pos_acc_h` for
  `std_n/std_e`, and `pos_acc_v` for `std_d`.
- Velocity comes from `gnss1-raw.csv` `UBX-NAV-PVT`: `vn`, `ve`, `vd`, and
  parsed `sAcc`.
- Velocity std follows the uploaded code behavior:
  `velocity_std_policy=fixed_0p05_observed_in_uploaded_code`.
- Yaw comes from `gnss1-status.csv` plus `gnss2-status.csv` A1 dual difference:
  `rel_n = rel_pos_n(gnss2_interp) - rel_pos_n(gnss1)`,
  `rel_e = rel_pos_e(gnss2_interp) - rel_pos_e(gnss1)`,
  `yaw_baseline_deg = -atan2(rel_e, rel_n)`.
- NED yaw uses `yaw_ned = 90 - yaw_body`.
- IMU increments come from BY2 `by2.txt` sportmodestate body IMU fields:
  gyroscope and accelerometer are converted FLU to FRD, optionally corrected by
  install RPY, then integrated as dtheta/dvel increments.

Nominal defaults:

- `yaw_source_mode=status`.
- `enable_outage=false`.
- `outlier_mode=none`.
- `yaw_noise_injection=false`.
- `trace_yaw_for_solver=false`.

Trace yaw mode is diagnostic-only. It must not be used as formal input.

Generated `.gnss` and `.imu` files are runtime input reconstruction artifacts
for baseline/parity testing only. They must not be described as proposed
algorithm output or as a numerical performance result.
