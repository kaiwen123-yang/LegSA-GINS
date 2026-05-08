# N4H1P process_data-compatible generation prompt

Task:

Implement a stdlib-only process_data-compatible input generator in LegSA-GINS.

Scope:

- Generate `BY2_PROCESS_DATA_COMPAT.gnss`.
- Generate `BY2_PROCESS_DATA_COMPAT.imu`.
- Generate process_data compatibility, status yaw, and IMU reports.
- Update final_v23 input source audit to distinguish historical input evidence
  from reconstructed runtime input availability.

Hard boundaries:

- Do not commit raw data.
- Do not commit generated `.gnss` or `.imu` real-data outputs.
- Do not write local BY2 absolute paths into tracked docs/config.
- Do not modify or copy external KF-GINS source.
- Do not implement raw Doppler, Go2 prior, source-aware weighting, LSIM/OIM,
  FGO, or full EKF.
- Do not use trace as solver input.
- Do not make numerical performance claims.

Expected report facts:

- `velocity_std_policy=fixed_0p05_observed_in_uploaded_code`.
- `trace_solver_input=false`.
- `trace_yaw_for_solver=false`.
- `enable_outage=false`.
- `outlier_mode=none`.
- `yaw_noise_injection=false`.
