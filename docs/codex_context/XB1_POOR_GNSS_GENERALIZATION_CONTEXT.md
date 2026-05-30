# XB1 Poor-GNSS Generalization Context

## Stage Identity

- Stage: `XB1A0_TO_XB1E_POOR_GNSS_GENERALIZATION_CONTEXT_QUALITY_AUDIT_ALIGNMENT_AND_NORMAL_RUN`
- Engineering alias: `XB1`
- Experiment alias: `PG1_20260105_122513`
- Dataset meaning: first of four poor-GNSS repeated experiments
- Stage root: `<XB1_STAGE_ROOT>`
- Normal-bootstrap runtime root: `<XB1_FULL_MATRIX_ROOT>/XB1A_NORMAL_BOOTSTRAP`
- Export-clean root: `<XB1_EXPORT_CLEAN_ROOT>`

## Source Roles

- `<XB1_BODY_SOURCE>` is the robot body/high-level/body-IMU source.
- Receiver `imu-data.csv` is diagnostic-only and must not be used as robot body IMU.
- Trace is evaluation-only and must not be solver input, tuning source, yaw-sign selector, time-offset selector, or feedback correction source.
- GNSS1/GNSS2 status files are decoded receiver observations and A1 dual-diff yaw candidates, not trajectory estimates.
- Status long-baseline `rel_pos_n/e/d` and HDT are forbidden as mainline yaw sources.
- final_v23 and single-baseline outputs are comparison outputs only and must not be solver inputs.

## Accepted Input-Chain Policy

- Use the BY2/BY3 kick-event alignment strategy: detect the sudden body-IMU impulse in `<XB1_BODY_SOURCE>` and align with GNSS official start / movement onset.
- Use pre-motion stationary gyro bias for body-IMU preprocessing. Do not estimate bias from a moving segment after selected Go2 start.
- Use A1 dual-diff yaw from GNSS1/GNSS2 short-baseline absolute positions with lateral antenna conversion and fixed_1p5 yaw std when and only when the short-baseline gate passes.
- Initatt yaw must be starttime-aligned to the first accepted A1 row at or after solver start.
- Same-case feedback for XB1 may only be generated from XB1 stage1 official EVAL_NAV state/estimate columns.

## XB1 Result Lock

XB1 completed literature criteria, data inventory, GNSS quality profile, kick-event alignment, input generation, provider materialization attempt, quality figures, case review, export-clean material, and Obsidian sync. It did not run artificial degradation, parameter retuning, normal solvers, official evaluators, feedback generation, normal metrics, or paper-claim work.

GNSS quality is classified `severe`. Evidence includes PDOP p95 at the 99.99 sentinel for both receivers, sol_num_sat p05 of 0, large position-accuracy tails, and invalid A1 short-baseline geometry. The A1 short-baseline median length is about 9.14 m with p95 about 51.68 m, so normal dual-yaw input is blocked. Status long-baseline `rel_pos_n/e/d` has median length about 2925.69 m and is rejected.

Kick alignment passed without trace tuning. Recommended algorithm start is about 16.646 s and recommended end is about 390.640 s relative to the body-source time zero.

Input/provider status is partial. Body IMU was generated from `<XB1_BODY_SOURCE>` with pre-motion stationary bias. Go2 attitude, horizontal velocity, and joint priors were materialized. Raw Doppler provider materialization attempted the accepted N5A/N5B RTKLIB/RINEX/helper path, but failed because the RTKLIB Doppler helper compile tool was unavailable in the current Windows runtime.

## Decision

```text
status=XB1_severe_GNSS_quality_mainline_limited
normal_run_status=XB1F_failed_before_solver
normal_run_blockers=inputs_not_ready_for_normal,A1_short_baseline_yaw_gate_blocked,providers_not_ready_for_LegSA_full
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_PG2_or_XB1_degradation_planning=false
ready_for_paper_claims=false
recommended_next_stage=human_review_XB1_then_repair_provider_or_plan_quality_aware_branch
```

## Claim Boundary

Allowed: describe the quality profile, alignment result, source-role policy, input/provider blockers, and quality-aware branch planning need.

Forbidden: paper claims, poor-GNSS robustness claims, final_v23 outperformance claims, artificial degradation, parameter retuning, trace-tuned thresholds, receiver IMU as body IMU, long-relpos/HDT yaw fallback, output-only correction, treating absent normal figures as real result figures, PR #52 merge/closure/tag, or running PG2/degradation/adaptation without explicit human approval.
