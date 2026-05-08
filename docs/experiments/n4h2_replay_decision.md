# N4H2 Replay Decision

## Replay Status

- replay_completed: true
- external_run_status: completed
- external_run_evidence_status: executed_no_oracle_claim
- output_standardization_status: completed
- output_standardization_evidence_status: output_standardized_no_oracle_claim
- evaluation_status: completed
- evaluation_evidence_status: diagnostic_aligned
- aligned_count: 56566

## Summary Metrics

- horizontal_rmse_m: 0.3479654209159466
- horizontal_p95_m: 0.5609978710111065
- up_rmse_m: 0.7940101228929531
- yaw_rmse_deg: 93.55731196644105
- yaw_p95_deg: 147.05664026037135
- roll_rmse_deg: 1.0674301793679788
- pitch_rmse_deg: 1.6712386339103198

## Reference Context

- dual_final_v23 horizontal_rmse_m: 0.353
- dual_final_v23 up_rmse_m: 0.818
- dual_final_v23 yaw_rmse_deg: 1.814

## Target Gates

- horizontal <= 2 m
- up <= 3 m
- yaw <= 2 deg
- roll/pitch strict <= 1 deg
- roll/pitch relaxed <= 1.6 deg

## Decision

- metrics_available: true
- position_replay_gate_pass: true
- yaw_replay_gate_pass: false
- roll_pitch_strict_gate_pass: false
- roll_pitch_relaxed_gate_pass: false
- replay_close_to_final_v23_context: false
- replay_ready_for_full_ekf: false
- yaw_config_issue: true
- replay_config_or_init_issue: false
- blocking_issue: none

The replay completed, the external run returned successfully, the outputs were
standardized, and evaluation-only metrics are available. Position is close to
the dual_final_v23 reference context, but yaw is not. This supports merging N4H2
as a baseline replay/reporting stage while routing the next stage to yaw
configuration and convention parity, not to full EKF implementation.

## Recommended Next Stage

recommended_next_stage = N4H2C_yaw_config_parity_audit

## Claim Boundary

- N4H2 replay metrics are diagnostic baseline replay metrics.
- They are not LegSA proposed solver performance.
- trace is evaluation-only.
- no formal performance claim is made.
- trace_solver_input: false
- trace_evaluation_only: true
- output_only_correction: false
- bad_epoch_deletion_for_metric: false
- numerical_performance_claim: false
- raw_data_committed: false
