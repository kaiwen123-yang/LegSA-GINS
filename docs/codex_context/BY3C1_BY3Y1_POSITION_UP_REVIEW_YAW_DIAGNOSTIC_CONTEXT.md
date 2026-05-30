# BY3C1/BY3Y1 Position Up Review And Yaw Diagnostic Context

## Stage

`BY3C1_TO_BY3Y1_POSITION_UP_GENERALIZATION_REVIEW_AND_YAW_DIAGNOSTIC_EXPLANATION`

## Scope

This stage is reporting/review-only. It reviews existing BY3C Batch0-Batch3 position/up metrics, existing BY3A8 yaw-error-budget evidence, and existing BY2 N9C0D/N9C2B comparison material.

It does not run solvers, evaluators, degraded-input generation, random generation, parameter retuning, trace solver input, final_v23 solver input, PR merge/closure/tag actions, or paper-claim work.

## Runtime Roots

- Stage root: `<BY3C1_STAGE_ROOT>`
- Review package: `<BY3C1_REVIEW_PACKAGE_ROOT>`
- Yaw diagnostic package: `<BY3Y1_STAGE_ROOT>`
- Export-clean package: `<BY3C1_EXPORT_CLEAN_ROOT>`

## Inputs

- BY3C active metrics: `<BY3C_STAGE_ROOT>/matrix/BY3C_ACTIVE_METRICS_BATCH0_TO_BATCH3`
- BY3C approved case matrix: `<BY3C_STAGE_ROOT>/matrix/BY3C_APPROVED_CASE_MATRIX`
- BY3A8 yaw lower-bound evidence: `<BY3A8_STAGE_ROOT>/matrix/BY3A8_A1_OBSERVATION_LOWER_BOUND`
- BY3A8 feedback evidence: `<BY3A8_STAGE_ROOT>/matrix/BY3A8_FEEDBACK_INTERACTION_AUDIT`
- BY2 active metrics with LegSA_full: `<BY2_N9C0D_LEGSA_FULL_ROOT>/matrix/N9C0D_ACTIVE_FINAL_ONLY_METRICS_WITH_LEGSA_FULL`
- BY2 canonical comparison mapping: `<BY2_N9C2B_MAIN_COMPARISON_ROOT>/matrix/N9C2B_CANONICAL_CASE_MAPPING`

## Result

Result integrity passed for 71 BY3 case units and 213 final metric rows across `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, and `final_v23_dual_antenna_EKF`.

BY3 position/up behavior is family-dependent. B downsample is classified as `generalizes_consistently` in the review package. Normal, A outage, E position std, C position noise, and D position spike are same-order or mixed, not paper-ready advantage claims.

BY3 yaw remains diagnostic-only. BY3Y1 explains the current yaw state as follows: wrong-source yaw, stale first-row initatt, and BY3 Go2 IMU moving-segment gyro-bias issues were repaired before BY3C; BY3A8 shows A1 observation quality remains the limiting factor; selected feedback worsens normal diagnostic yaw slightly relative to stage1.

## Decision

```text
status=BY3C1_position_up_review_and_yaw_diagnostic_complete
ready_for_BY3D_or_other_dataset_planning=true_after_human_review
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=human_review_BY3C1_then_BY3D_mixed_position_up_or_other_dataset_planning
```

## Forbidden Claims

- Do not claim BY3 paper-ready performance.
- Do not claim BY3 yaw robustness.
- Do not claim final_v23 outperformance.
- Do not treat BY3C1 review figures as new solver/evaluator evidence.
- Do not treat BY3C1/BY3Y1 as authorization for BY3D execution without explicit human approval.
