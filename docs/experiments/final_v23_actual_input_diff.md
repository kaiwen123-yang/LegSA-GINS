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

- actual input exists: false
- reconstructed input exists: true
- input_diff_status: `evidence_missing`
- position_diff_rmse_m: `null`
- height_diff_rmse_m: `null`
- velocity_diff_rmse_mps: `null`
- yaw_diff_rmse_deg: `null`
- yaw_diff_mean_deg: `null`
- yaw_std_diff_mean_deg: `null`

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
