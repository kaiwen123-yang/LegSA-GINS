# BY3A5B A1 Dual-Diff Yaw Input Repair Context

Stage: `BY3A5B_A1_DUAL_DIFF_YAW_INPUT_REPAIR_AND_NORMAL_RERUN`

Runtime aliases:

- Stage root: `<BY3A5B_STAGE_ROOT>`
- Normal runtime root: `<BY3_FULL_MATRIX_ROOT>/BY3A5B_A1_DUAL_DIFF_REPAIR`
- Receiver source: `<BY3_RECEIVER_ROOT>`

## Decision

```text
status=BY3A5B_a1_dual_diff_input_repaired_but_yaw_reference_issue_remains
by3a5_hdt_policy=diagnostic_rejected_superseded
yaw_input_source=A1_dual_diff_short_baseline_from_GNSS1_GNSS2_absolute_positions
status_rel_pos_policy=rejected_long_baseline_base_vector
yaw_std_policy=fixed_1p5
normal_rerun_status=completed
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=position_up_only
yaw_degradation_claims=false
ready_for_paper_claims=false
recommended_next_stage=human_review_yaw_reference_or_position_only_BY3B
```

## Evidence Summary

- BY3A5 remains valid as wrong-source evidence: the old BY3 15-column yaw input was not a valid short-baseline dual-antenna yaw source.
- BY3A5 HDT repaired-input policy is diagnostic/rejected/superseded for mainline BY3 generalization.
- BY3A5B reconstructs a short GNSS1/GNSS2 baseline from absolute position fields. The median short-baseline length is about 0.383 m.
- GNSS1 status `rel_pos_n/e/d` has median length about 3062.8 m and is rejected as a long-baseline/base-vector source.
- Repaired BY3 dual yaw uses BY2 A1 logic: GNSS2 interpolated to GNSS1 epoch, `gnss2_minus_gnss1`, lateral conversion equivalent to `baseline_heading+90`, and fixed_1p5 yaw_std.
- BY3 normal-only rerun completed for `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, and `final_v23_dual_antenna_EKF`.

## Claim Boundary

- Do not use NMEA HDT as mainline BY3 solver yaw input.
- Do not use GNSS status long-baseline `rel_pos_n/e/d` as antenna heading.
- Do not choose antenna order or lateral sign by yaw RMSE minimization.
- Do not treat BY3A5B as repaired official BY3 yaw-reference evidence. The yaw input is repaired; the official yaw reference/evaluator remains unresolved.
- Do not run BY3 degradation or make paper claims without explicit human approval.
