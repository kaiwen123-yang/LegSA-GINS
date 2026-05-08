# final_v23 Actual Input Diff

This document describes the N4H2C runtime input diff. It avoids local absolute
paths and stores real diff artifacts outside git.

## Path Status

- actual input role: `ACTUAL_FINAL_V23_CASE_ROOT/input.gnss`
- reconstructed input role: `N4H2_ARTIFACTS_ROOT/inputs/BY2_PROCESS_DATA_COMPAT.gnss`
- actual path committed: false
- reconstructed path committed: false

## Diff Metrics

The runner writes `FINAL_V23_INPUT_DIFF_REPORT.json` when both runtime inputs
exist. Required fields are:

- `position_diff_rmse_m`
- `height_diff_rmse_m`
- `velocity_diff_rmse_mps`
- `yaw_diff_rmse_deg`
- `yaw_diff_mean_deg`
- `yaw_std_diff_mean_deg`
- `input_diff_status`

Current N4H2C runtime probe:

- supplied actual case root input exists: false
- recovered actual candidate input exists: true
- reconstructed input exists: true
- recovered candidate group: `EXTERNAL_KFGINS_ROOT:10`
- matched_count: 303
- input_diff_status: `yaw_input_matched`
- position_diff_rmse_m: 0.04087297923984076
- height_diff_rmse_m: 2.911876689989946e-07
- velocity_diff_rmse_mps: 0.0
- yaw_diff_rmse_deg: 1.4706893995962274
- yaw_diff_mean_deg: -0.011152765078168928
- yaw_std_diff_mean_deg: 0.0

## Yaw Diff Analysis

Decision labels:

- `input_position_matched_but_yaw_mismatch`: position agrees while yaw differs
  by more than 10 degrees.
- `yaw_input_matched`: input yaw agrees within 2 degrees.
- `evidence_missing`: fewer than 10 matched rows or one input is unavailable.

## Boundary

- trace_solver_input=false
- output_only_correction=false
- no formal performance claim
- no local absolute path leakage
