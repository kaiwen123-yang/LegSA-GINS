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

Current N4H2C-2 runtime probe:

- supplied `ACTUAL_FINAL_V23_CASE_ROOT`: `evidence_missing`
- recovered candidate group: `EXTERNAL_KFGINS_ROOT:10`
- actual candidate input.gnss exists: true
- reconstructed input.gnss exists: true
- actual candidate input.gnss lines: 303
- reconstructed input.gnss lines: 303
- input_diff_status: `yaw_input_matched`
- matched_count: 303
- position_diff_rmse_m: 0.04087297923984076
- height_diff_rmse_m: 2.911876689989946e-07
- velocity_diff_rmse_mps: 0.0
- yaw_diff_rmse_deg: 1.4706893995962274
- yaw_diff_mean_deg: -0.011152765078168928
- yaw_std_diff_mean_deg: 0.0

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

## N4H2C-2 Added Audits

N4H2C-2 adds:

- actual final_v23 artifact recovery
- process_data runtime-parameter audit
- yaw input variant matrix
- runtime yaw update audit
- replay yaw diagnostics

Runtime artifact recovery found a nominal-none candidate group, so the current
tracked blocker is no longer "no candidate input at all." The exact historical
case root supplied to the runner still reports `evidence_missing`, and the
recovered candidate remains runtime evidence only.

Process_data defaults may include disturbance/noise/outage behavior, so nominal
replay must be justified by explicit safe flags or equivalent invocation
evidence.

Trace yaw and auto-best install selected by trace are diagnostic-only. Status
yaw physical sign/offset still needs actual input, process_data invocation, or
physical mounting evidence.

N4H2C-2 runtime observations:

- artifact_groups_found: 71
- actual candidate input recovered: true
- actual candidate summary recovered: true
- process_data `BASE_TIME`: 1772784000.0
- process_data `YAW_SOURCE_MODE`: `status`
- process_data `USE_STATUS_YAW`: true
- process_data `YAW_SIGN`: 1.0
- process_data `YAW_INSTALL_OFFSET_DEG`: 0.0
- process_data `AUTO_APPLY_BEST_INSTALL`: false
- process_data `STATUS_YAW_STD_MODE_DEFAULT`: `fixed_1p5`
- process_data `OUTLIER_MODE_DEFAULT`: `legacy15`
- process_data `YAW_NOISE_STD_DEG`: 1.5
- explicit nominal safe flags found: false
- best status variant: `status_A1_sign-1_offset+90_yawstd_fixed1p5_noise0`
- best status yaw_vs_trace_rmse_deg: 4.9973634253532975
- best trace diagnostic yaw_vs_trace_rmse_deg: 92.93107029020553
- yaw_measurement_loaded: true
- yaw_residual_formula: true
- yaw_wrap_formula: true
- scheme_C_gate_used: true
- replay yaw diagnostic classification: `likely_input_yaw_generation_issue`

Full KF-GINS framework reconstruction is needed later, but yaw input/runtime
parity comes first.

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

`N4H2C_runtime_yaw_update_config_audit`

Current blocking_issues:

- none

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
