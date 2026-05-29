# BY3A8 Yaw Error Budget Safe Repair Context

Stage: `BY3A8_YAW_ERROR_BUDGET_AND_SAFE_REPAIR`

Purpose: accept the BY3A7 normal-only IMU preprocessing repair, budget the remaining BY3 dual-yaw normal error, and allow only source-backed non-parameter repairs. BY3A8 did not run BY3 degradation, artificial degradations, solver reruns, official evaluator reruns, gate relaxation, trace-based correction, HDT fallback, long-baseline `rel_pos` fallback, or paper-claim work.

Runtime aliases:

- Stage root: `<BY3A8_STAGE_ROOT>`
- Runtime root: `<BY3_FULL_MATRIX_ROOT>/BY3A8_YAW_ERROR_BUDGET_REPAIR`
- Accepted prior normal root: `<BY3A7_STAGE_ROOT>`
- Accepted A1 yaw source: `<BY3A7_STAGE_ROOT>/repaired_input_or_config`

Final decision:

```text
status=BY3A8_yaw_limited_but_position_up_ready
a1_observation_lower_bound=BY3A8_a1_observation_quality_poor
a1_quality=BY3A8_a1_quality_objective_mask_ready
imu_bias=BY3A8_imu_bias_no_safe_change
time_lag=BY3A8_no_time_lag_issue
yaw_gate=BY3A8_gate_behavior_acceptable
feedback=BY3A8_feedback_worsens_yaw
safe_repair_plan=BY3A8_no_safe_repair_accept_yaw_limit
normal_rerun=BY3A8_normal_rerun_not_run_no_safe_repair
post_stage=BY3A8_yaw_limited_by_A1_observation_quality
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=position_up_with_diagnostic_yaw
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=BY3B_POSITION_UP_WITH_DIAGNOSTIC_YAW_PLANNING
```

Locked findings:

- A1_dual_diff remains the mainline BY3 dual-yaw source, with fixed_1p5 yaw_std and the BY2-compatible sign/lateral policy from BY3A5B/BY3A6/BY3A7. HDT and GNSS status long-baseline `rel_pos_n/e/d` remain rejected as mainline yaw inputs.
- The A1 observation lower-bound audit used the BY3 trace only as evaluation reference. A1 yaw versus trace heading has RMSE about `24.06 deg`, p95 about `31.78 deg`, max about `167.29 deg`, circular mean about `-15.06 deg`, and circular std about `17.17 deg`. This does not support a robust 2 deg normal dual-yaw expectation from the raw A1 observation alone.
- A1 objective invalid-epoch rules remain source-quality based. BY3A8 found 297 A1 epochs, 75 yaw jumps above 15 deg, 19 above 30 deg, 4 above 45 deg, median baseline about 0.383 m, and 6 objective invalid solver-candidate epochs. Trace disagreement is diagnostic only and is not a masking rule.
- BY3A7 pre-motion IMU bias remains the accepted safe IMU preprocessing. BY3A8 checked source-only stationary candidates; the best source-stationary 1000-sample candidate differed from BY3A7 z bias by about `0.001 deg/s`, and no source-backed refinement justified a rerun.
- Time-lag scans were diagnostic only. The A1-vs-trace best diagnostic lag improved RMSE by only about 2.1 percent and had no timestamp metadata support, so no time-shift repair is allowed.
- Yaw gate behavior is acceptable under the current gate policy. Actual gate counts remain high-reject because NAV-vs-A1 residuals are large, but objective-invalid A1 epochs explain only a small share of rejects. Gate thresholds were not relaxed.
- Stage2 selected feedback worsened yaw relative to stage1 in BY3A7 accepted outputs: stage1 yaw RMSE about `4.23 deg` and LegSA_full_EKF yaw RMSE about `5.26 deg`. BY3A8 does not change feedback policy; any feedback repair requires a separate human-approved source-role review.

Boundary after BY3A8:

- BY3 degradation planning is allowed only as position/up with diagnostic yaw unless a later human review broadens yaw scope.
- BY3 yaw claims remain diagnostic-only; paper claims remain false.
- Do not reintroduce HDT, GNSS status long-baseline `rel_pos`, old moving-segment IMU bias, trace-based yaw correction, RMSE-selected epoch deletion, or yaw-gate relaxation.
