# N4H2C Yaw Config Parity Decision

## N4H2 Replay Context

- replay_completed: true
- external_run_status: completed
- output_standardization_status: completed
- evaluation_status: completed
- aligned_count: 56566
- horizontal_rmse_m: 0.3479654209159466
- up_rmse_m: 0.7940101228929531
- yaw_rmse_deg: 93.55731196644105
- roll_rmse_deg: 1.0674301793679788
- pitch_rmse_deg: 1.6712386339103198
- position_replay_gate_pass: true
- yaw_replay_gate_pass: false

## Input Diff Conclusion

N4H2C must probe `ACTUAL_FINAL_V23_CASE_ROOT/input.gnss` and
`N4H2_ARTIFACTS_ROOT/inputs/BY2_PROCESS_DATA_COMPAT.gnss` at runtime. If both
exist, the runner computes position, height, velocity, yaw, yaw-std, and
standard-deviation diffs. If either input is missing, the decision is
`evidence_missing`.

Current N4H2C runtime probe:

- actual input.gnss exists: false
- reconstructed input.gnss exists: true
- input_diff_status: `evidence_missing`
- position_diff_rmse_m: `null`
- height_diff_rmse_m: `null`
- velocity_diff_rmse_mps: `null`
- yaw_diff_rmse_deg: `null`
- yaw_diff_mean_deg: `null`
- yaw_std_diff_mean_deg: `null`

## process_data / Runtime Source Conclusion

The audit must inspect `process_data.py`, run scripts, config candidates,
`GnssFileLoader`, `GIEngine`, and the KF-GINS core flow using read-only path and
line-number evidence.

Current N4H2C runtime probe:

- process_data path role: `EXTERNAL_KF_GINS_ROOT/bin/process_data.py`
- run script candidates: 173
- config candidates: 40
- yaw_source_mode evidence: found
- yaw_std_mode evidence: found
- YAW_SIGN evidence: found
- YAW_INSTALL_OFFSET evidence: found
- GNSS loader 15-column support evidence: found
- engine velocity update evidence: found
- engine yaw update evidence: found
- KF-GINS requested core-flow terms: found
- LegSA framework gaps:
  `newImuProcess`, `isToUpdate`, `imuInterpolate`, `imuCompensate`,
  `F/G/Phi/Qd`, `EKFPredict`, `EKFUpdate`, `stateFeedback`

## Decision Rules

- If actual input is missing:
  `recommended_next_stage=N4H2C_actual_input_artifact_recovery_or_run_script_audit`
- If actual and reconstructed inputs show matched position but large yaw
  mismatch:
  `recommended_next_stage=N4H2C_yaw_input_config_fix`
- If input yaw matches but replay yaw differs:
  `recommended_next_stage=N4H2C_runtime_yaw_update_config_audit`
- If runtime source branch does not support the 15-column velocity/yaw path:
  `recommended_next_stage=N4H2C_runtime_source_branch_parity_audit`
- Full KF-GINS-style EKF reconstruction must wait until input/yaw parity is
  resolved.

Current recommended_next_stage:

`N4H2C_actual_input_artifact_recovery_or_run_script_audit`

Current blocking_issues:

- `actual_final_v23_input_missing`

## Claim Boundary

- N4H2C is diagnostic source/input/runtime audit only.
- N4H2C is not proposed solver implementation.
- trace_solver_input=false
- final_v23_is_proposed=false
- output_only_correction=false
- bad_epoch_deletion_for_metric=false
- raw_data_committed=false
- no formal performance claim
- no trace-based formal yaw-offset selection
