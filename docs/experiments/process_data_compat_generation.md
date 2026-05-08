# N4H1P process_data-compatible input generation

This document records the N4H1P stdlib reimplementation of the uploaded
`process_data` logic.

Purpose:

- Reconstruct a final_v23-style 15-column `.gnss` runtime input.
- Reconstruct a process_imu-style 7-column `.imu` runtime input.
- Generate parity/audit reports for input provenance.
- Generate a coverage report for row-retention parity.

This is not a solver. It is not a raw GNSS solver. It does not solve position
from RAWX, SFRBX, or RTCM. It does not implement raw Doppler factors, Go2
priors, source-aware weighting, LSIM/OIM, FGO, or performance evaluation.

Input mapping:

- The `.gnss` main time axis comes from `gnss1-status.csv`.
- N4H1P2 uses `sys_stamp.secs + sys_stamp.nsecs * 1e-9 - BASE_TIME` for the
  status base table aligned time, matching the uploaded script's base-table
  construction.
- Position comes from `gnss1-status.csv`: `pos_lat`, `pos_lon`, `pos_height`.
- Position standard deviation comes from `gnss1-status.csv`: `pos_acc_h` for
  `std_n/std_e`, and `pos_acc_v` for `std_d`.
- Velocity comes from `gnss1-raw.csv` `UBX-NAV-PVT`: `vn`, `ve`, `vd`, and
  parsed `sAcc`.
- Velocity std follows the uploaded code behavior:
  `velocity_std_policy=fixed_0p05_observed_in_uploaded_code`.
- PVT velocity is a merge-asof auxiliary source. It must not become the output
  time axis.
- Yaw comes from `gnss1-status.csv` plus `gnss2-status.csv` A1 dual difference:
  `rel_n = rel_pos_n(gnss2_interp) - rel_pos_n(gnss1)`,
  `rel_e = rel_pos_e(gnss2_interp) - rel_pos_e(gnss1)`,
  `yaw_baseline_deg = -atan2(rel_e, rel_n)`.
- NED yaw uses `yaw_ned = 90 - yaw_body`.
- Status yaw is a merge-asof auxiliary source. It must not become the output
  time axis.
- The uploaded script fills `vn/ve/vd/sAcc` and yaw fields with
  `ffill().bfill()` after merge-asof. N4H1P2 preserves that row-retention
  behavior before final `dropna`.
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

Coverage contract:

- `.gnss` rows should be close to the `gnss1-status` base-row count in nominal
  generation.
- `.gnss` row count must not be directly limited by the number of PVT rows.
- `PROCESS_DATA_COVERAGE_REPORT.json` records `status_base_row_count`,
  `pvt_velocity_row_count`, `yaw_row_count`, `gnss_output_row_count`,
  merge matches before fill, `dropna_count`, ratios, and `coverage_status`.
- `coverage_status=passed` requires `output_to_status_ratio >= 0.8`.
- If coverage is not passed, the runner may still generate files, but reports
  must carry a warning and must not claim row-retention parity.

Generated `.gnss` and `.imu` files are runtime input reconstruction artifacts
for baseline/parity testing only. They must not be described as proposed
algorithm output or as a numerical performance result.
