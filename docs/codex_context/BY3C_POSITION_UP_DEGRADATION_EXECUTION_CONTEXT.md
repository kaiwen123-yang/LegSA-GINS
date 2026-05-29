# BY3C Position/Up Degradation Execution Context

Stage: `BY3C_POSITION_UP_DEGRADATION_EXECUTION_BATCH0_TO_BATCH3_LONG_PIPELINE`

BY3C executed only the human-approved position/up-primary subset after BY3B:

- Batch 0: normal parity recheck with accepted BY3A7/BY3A8 sources.
- Batch 1: A_outage, B_gnss_downsample_every2/every5/every10, and E_position_std_inflation_x2/x5/x10.
- Batch 2: C_position_noise mild/medium/strong seeds 0..9.
- Batch 3: D_position_spike mild/medium/strong seeds 0..9.

Accepted source locks:

- BY3A7 repaired body IMU.
- BY3A5B/BY3A7 A1_dual_diff 15-column GNSS yaw source.
- BY3A2 Raw Doppler provider.
- BY3 Go2 attitude, horizontal velocity, and joint priors.
- BY3 trace as evaluation-only reference.
- GNSS1-status single-baseline input.
- final_v23 external-baseline config pattern.
- BY3 selected-feedback same-case pattern, used only as a pattern reference.

Execution result:

```text
status=BY3C_batch0_to_batch3_position_up_degradation_complete
case_units_executed=71
final_metric_rows=213
batch1_metric_rows=30
batch2_metric_rows=90
batch3_metric_rows=90
consolidated_figure_rows=12
ready_for_BY3D_diagnostic_yaw_or_mixed_planning=true_after_human_review
ready_for_paper_claims=false
```

Scope boundaries:

- Horizontal/up metrics are primary.
- Yaw columns are diagnostic-only.
- Same-case degraded feedback is generated only from each case's stage1 official EVAL_NAV state/estimate columns.
- Batch 2 and Batch 3 random arrays use approved seed streams and structured hashes.
- H_dual_yaw_noise, E_yaw_std_inflation, mixed cases, module-disable cases, `LegSA_9F_FGO_EKF`, nonredundant FGO extension, and full monolithic BY3 matrix were not executed.
- BY2 feedback and BY3 normal feedback were not reused for degraded cases.
- No paper claims, final_v23 outperformance claims, or yaw robustness claims are authorized.

Tracked docs must refer to outputs through `<BY3C_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3C_POSITION_UP_DEGRADATION_EXECUTION`; local absolute paths belong only in ignored local path docs.
