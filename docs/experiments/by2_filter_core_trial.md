# Stage N4F: BY2 Filter-Core Diagnostic Trial

Stage N4F runs the current LegSA-GINS C++ filter core on BY2 real-data inputs and
generates diagnostic evaluation artifacts. It answers whether the current filter
core can complete a BY2 runtime and produce `LegSA_NAV.nav`, `LegSA_STD.csv`,
`EVAL_NAV.csv`, `RUN_MANIFEST.json`, `error_series.csv`, `summary.json`, and a
case-review-style `case_review.md`.

This trial is diagnostic only. It does not make a performance claim and it does
not tune to the final_v23 nominal reference context.

## Input Roles

- Go2 body-state gyro/accel is converted into diagnostic IMU increments for
  propagation input.
- The Go2 body / IMU source frame is FLU; the adapter applies FLU to FRD exactly
  once and writes `IMU_FRD_COMPATIBLE`.
- Receiver `imu-data.csv` is not used as body IMU.
- Receiver-native GNSS status is used as the trial measurement source.
- `gnss2-status` is selected by default when it has position rows; otherwise the
  trial falls back to `gnss1-status`.
- Trace is evaluation-only and is read only after C++ runtime output exists.

## Explicit Non-Goals

- no raw Doppler
- no Go2 yaw-rate prior
- no Go2 attitude prior
- no support-foot factor
- no LSIM/OIM
- no source-aware weighting
- no FGO smoother
- no output-only correction
- no bad-epoch deletion for metrics
- no final_v23 output substitution

## Benchmark Context

The report carries these user-provided reference values as context only:

- dual_final_v23 horizontal_rmse_m = 0.353
- dual_final_v23 up_rmse_m = 0.818
- dual_final_v23 yaw_rmse_deg = 1.814
- dual_final_v23 roll_rmse_deg = 1.025
- dual_final_v23 pitch_rmse_deg = 1.524
- single_antenna horizontal_rmse_m = 38.947
- single_antenna yaw_rmse_deg = 41.375
- pure_ins horizontal_rmse_m = 59240.252

## Classification Rules

- `runtime_pass`: all runtime outputs exist and contain no NaN marker.
- `comparable_generated`: aligned trace/eval count is greater than 100.
- `single_antenna_better_than_legsa` or `legsa_better_than_single_antenna`:
  based on horizontal RMSE relative to 38.947 m.
- `final_v23_close`: horizontal RMSE <= 2.0 m and yaw RMSE <= 2.5 deg.
- `final_v23_oracle_level`: horizontal RMSE <= 0.5 m and yaw RMSE <= 2.0 deg.

Even if a threshold is met, N4F remains a diagnostic trial until later review.

