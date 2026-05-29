# BY3A7 A1 Yaw Dynamic Quality IMU Gate Context

Stage: `BY3A7_A1_YAW_DYNAMIC_QUALITY_IMU_SIGN_AND_GATE_REPAIR`

Purpose: accept BY3A6 trace/base-time/initatt findings, audit why BY3 yaw still diverged after a correct start, check A1 yaw dynamic quality, BY3 Go2 IMU yaw-rate preprocessing, yaw update gate residuals, and yaw update code, then apply only a safe non-parameter normal-only repair if gated.

Runtime aliases:

- Stage root: `<BY3A7_STAGE_ROOT>`
- Normal runtime root: `<BY3_FULL_MATRIX_ROOT>/BY3A7_YAW_DYNAMIC_GATE_REPAIR`
- Prior trace/initatt forensic root: `<BY3A6_STAGE_ROOT>`
- A1 dual-diff input source: `<BY3A6_STAGE_ROOT>/repaired_input_generation`

Final decision:

```text
status=BY3A7_yaw_salvaged_ready_for_full_BY3_degradation
a1_yaw_quality=BY3A7_a1_yaw_quality_acceptable_with_mask
imu_sign_axis=BY3A7_imu_sign_axis_bug_confirmed
yaw_gate=BY3A7_gate_reject_caused_by_IMU_prediction_drift
yaw_update_code=BY3A7_yaw_update_code_valid
repair_plan=BY3A7_safe_repair_ready
repair=BY3A7_repair_ready
normal_rerun=BY3A7_normal_rerun_completed
post_repair=BY3A7_yaw_sanity_passed
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=full_after_human_review
ready_for_paper_claims=false
recommended_next_stage=BY3B_DEGRADATION_MATRIX_PLANNING_AND_PRECHECK
```

Locked findings:

- BY3A6 trace truth, evaluator parser/base_time, and starttime-aligned initatt findings remain accepted. Trace is evaluation-only and was not used for solver input, initatt, masking, or tuning.
- BY3A5B/BY3A6 A1_dual_diff remains the mainline dual-yaw source. It is source-valid with dynamic-quality caution: 75 yaw jumps above 15 deg, 19 above 30 deg, 4 above 45 deg, fixed_1p5 yaw_std, and 6 objective invalid solver-candidate epochs from source-quality criteria. Trace/HDT disagreement is diagnostic only.
- The BY3 yaw failure after BY3A6 was primarily a BY3 Go2 IMU preprocessing issue: BY3A0 estimated gyro bias from the first 1000 samples after the selected Go2 motion start, which was a moving segment. The old dynamic z bias was about `-8.58 deg/s`; the pre-motion source segment z bias was about `-0.074 deg/s`.
- BY3A7 regenerated a BY3A7-local IMU input using the same FLU-to-FRD conversion and the pre-motion source gyro-bias segment. It did not change yaw gate thresholds, A1 yaw source, A1 yaw_std, final_v23 math, or solver parameters.
- BY3A7 normal-only rerun completed for `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, and `final_v23_dual_antenna_EKF`. No BY3 degradation, artificial degradation, trace solver input, final_v23 solver input, HDT solver input, gate relaxation, output substitution, or paper claim was performed.
- Post-repair normal yaw sanity passed for dual-yaw algorithms: `LegSA_full_EKF` yaw RMSE is about `5.26 deg` and `final_v23_dual_antenna_EKF` yaw RMSE is about `4.30 deg`. The single-antenna baseline yaw remains poor, as expected for no dual-yaw source.

Hard boundary after BY3A7:

- BY3 degradation planning is allowed only after human review, and paper claims remain false.
- BY3A7 does not authorize PR #52 merge, PR #52 closure, tag creation, or paper performance claims.
- Do not use BY3A7 to claim final_v23 outperformance.
- Do not reuse HDT or GNSS status long-baseline `rel_pos_n/e/d` as mainline yaw input.
- Do not relax yaw gates or tune parameters from BY3A7 metrics.
