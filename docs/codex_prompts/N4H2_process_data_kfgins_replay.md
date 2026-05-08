# N4H2 process_data-compatible KF-GINS replay prompt

Task:

Run the N4H1P2 process_data-compatible `.gnss` / `.imu` inputs through the
external KF-GINS executable, parse outputs, evaluate against trace in
evaluation-only mode, and write a replay report.

Scope:

- Create an N4H2 branch from merged and tagged N4H1 `main`.
- Generate real BY2 process_data-compatible `.gnss` / `.imu` artifacts.
- Write a replay YAML outside the external KF-GINS source tree.
- Run external KF-GINS without modifying or copying its source.
- Parse `KF_GINS_Navresult.nav`, `KF_GINS_STD.txt`, and
  `KF_GINS_IMU_ERR.txt`.
- Evaluate parsed NAV against trace after replay only.
- Commit scripts and small reports only.

Hard boundaries:

- Do not commit raw data, generated real `.gnss` / `.imu`, NAV, STD, IMU_ERR,
  or error-series CSV files.
- Do not write local BY2 absolute paths into tracked docs/config.
- Do not modify or vendor `/home/kaiwen/KF-GINS`.
- Do not use trace/reference/user_io/tf outputs as solver input.
- Do not perform output-only correction.
- Do not delete bad epochs for metrics.
- Do not implement raw Doppler, Go2 priors, source-aware weighting, LSIM/OIM,
  FGO, or a new proposed solver stage.
- Do not claim final_v23 parity or proposed-method performance.
- Do not merge or tag N4H2.

Expected report facts:

- `replay_success=true`.
- `parse_success=true`.
- `evaluation_success=true`.
- `formal_performance_claim_allowed=false`.
- `trace_solver_input=false`.
- `output_only_correction=false`.
- replay output rows are reported for NAV / STD / IMU_ERR.
