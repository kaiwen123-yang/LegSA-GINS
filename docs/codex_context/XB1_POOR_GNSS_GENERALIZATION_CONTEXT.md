# XB1 Poor-GNSS Generalization Context

## Stage Identity

- Stage: `XB1A0_TO_XB1E_POOR_GNSS_GENERALIZATION_CONTEXT_QUALITY_AUDIT_ALIGNMENT_AND_NORMAL_RUN`
- Follow-on triage stage: `XB1A1_BLOCKER_TRIAGE_RAW_DOPPLER_A1_YAW_AND_MAINLINE_NORMAL_GATE`
- Correction stage: `XB1A2_A1_DUAL_DIFF_RELPOS_DIFFERENCE_REAUDIT_AND_NORMAL_RERUN`
- Engineering alias: `XB1`
- Experiment alias: `PG1_20260105_122513`
- Dataset meaning: first of four poor-GNSS repeated experiments
- Stage root: `<XB1_STAGE_ROOT>`
- XB1A1 stage root: `<XB1A1_STAGE_ROOT>`
- XB1A2 stage root: `<XB1A2_STAGE_ROOT>`
- Normal-bootstrap runtime root: `<XB1_FULL_MATRIX_ROOT>/XB1A_NORMAL_BOOTSTRAP`
- XB1A1 normal-gate runtime root: `<XB1A1_NORMAL_GATE_ROOT>`
- XB1A2 relpos-diff runtime root: `<XB1A2_RELPOS_DIFF_REPAIR_ROOT>`
- Export-clean root: `<XB1_EXPORT_CLEAN_ROOT>`

## Source Roles

- `<XB1_BODY_SOURCE>` is the robot body/high-level/body-IMU source.
- Receiver `imu-data.csv` is diagnostic-only and must not be used as robot body IMU.
- Trace is evaluation-only and must not be solver input, tuning source, yaw-sign selector, time-offset selector, or feedback correction source.
- GNSS1/GNSS2 status files are decoded receiver observations and A1 dual-diff yaw candidates, not trajectory estimates.
- A single status `rel_pos_n/e/d` row may be a long RTK base vector and must not be used directly as antenna heading.
- A1 invalid conclusions must audit the actual dual-difference construction first: BY2/process_data-compatible status yaw uses `rel_pos_gnss2 - rel_pos_gnss1` after GNSS2 interpolation to GNSS1 time, while BY3A5B used GNSS1/GNSS2 absolute positions for its BY3-specific repair.
- HDT is forbidden as a mainline yaw source.
- final_v23 and single-baseline outputs are comparison outputs only and must not be solver inputs.

## Accepted Input-Chain Policy

- Use the BY2/BY3 kick-event alignment strategy: detect the sudden body-IMU impulse in `<XB1_BODY_SOURCE>` and align with GNSS official start / movement onset.
- Use pre-motion stationary gyro bias for body-IMU preprocessing. Do not estimate bias from a moving segment after selected Go2 start.
- Use A1 dual-diff yaw only when the chosen source's physical short-baseline gate passes. For XB1A2, both BY2 status relpos-difference and BY3A5B absolute-position candidates fail this gate.
- Initatt yaw must be starttime-aligned to the first accepted A1 row at or after solver start.
- Same-case feedback for XB1 may only be generated from XB1 stage1 official EVAL_NAV state/estimate columns.

## XB1 Result Lock

XB1 completed literature criteria, data inventory, GNSS quality profile, kick-event alignment, input generation, provider materialization attempt, quality figures, case review, export-clean material, and Obsidian sync. It did not run artificial degradation, parameter retuning, normal solvers, official evaluators, feedback generation, normal metrics, or paper-claim work.

GNSS quality is classified `severe`. Evidence includes PDOP p95 at the 99.99 sentinel for both receivers, sol_num_sat p05 of 0, large position-accuracy tails, and invalid A1 short-baseline geometry. The A1 short-baseline median length is about 9.14 m with p95 about 51.68 m, so normal dual-yaw input is blocked. Status long-baseline `rel_pos_n/e/d` has median length about 2925.69 m and is rejected.

Kick alignment passed without trace tuning. Recommended algorithm start is about 16.646 s and recommended end is about 390.640 s relative to the body-source time zero.

XB1A0-E input/provider status was partial. Body IMU was generated from `<XB1_BODY_SOURCE>` with pre-motion stationary bias. Go2 attitude, horizontal velocity, and joint priors were materialized. Raw Doppler provider materialization attempted the accepted N5A/N5B RTKLIB/RINEX/helper path, but failed because the RTKLIB Doppler helper compile tool was unavailable in that Windows runtime before XB1A1 repaired the environment/toolchain path.

## XB1A1 Blocker Triage Result

XB1A1 imported the severe XB1A0-E GNSS quality result and triaged the normal-run blockers. The Raw Doppler blocker was repairable: the provider now builds/runs through a WSL gcc/helper bridge when native Windows gcc is unavailable, while preserving the accepted RTKLIB/RINEX/helper chain and source-role boundaries. The resulting XB1 Raw Doppler factor provider is schema-valid with 1809 rows.

A1 dual yaw remained invalid after XB1A1, but XB1A1 did not audit the BY2/process_data-compatible status relpos-difference path, so its source-provenance conclusion is suspended/superseded by XB1A2. The XB1A1 absolute-position short-baseline gate had about 1.95 percent objective valid epochs, with nonphysical baseline length for the robot antennas: median about 9.14 m, p95 about 51.68 m, and max about 120.50 m.

Normal algorithm applicability is partial. `LegSA_full_EKF` is blocked because forcing it without valid A1 dual yaw would change the current algorithm identity. `final_v23_dual_antenna_EKF` is not applicable without valid dual-yaw input. `single_antenna_gnss1_status_KF_GINS` completed normal official evaluation as a diagnostic baseline only. No artificial degradation, retuning, quality-aware execution, trace solver input, fabricated provider, fabricated A1 yaw, or paper-claim work was performed.

## XB1A2 Relpos-Difference Reaudit Result

XB1A2 recovered two implementation families and audited both for XB1:

- BY2/process_data-compatible status relpos-difference: `rel_pos_gnss2 - rel_pos_gnss1` after GNSS2 interpolation to GNSS1 time, `yaw_baseline=-atan2(rel_e,rel_n)`, `yaw_ned=90-yaw_body`, fixed_1p5 yaw_std.
- BY3A5B absolute-position repair: GNSS1/GNSS2 absolute-position short baseline projected to local ENU, used for BY3 because BY3 status rel_pos direct was a long-base vector.

The BY2 status relpos-difference candidate is nonphysical for XB1: 356 rows, 7 physical-band epochs, valid ratio about 0.0197, median length about 9.18 m, p95 about 50.96 m, and max about 131.70 m. The BY3A5B-style absolute-position candidate is also nonphysical for XB1: median about 9.14 m and p95 about 51.70 m. Single status rel_pos direct remains rejected as a long RTK base-vector source, and HDT remains diagnostic-only.

No repaired dual-yaw input was generated. XB1A2 did not run dual-yaw normal solvers, degradation, retuning, trace tuning, quality-aware adaptation, or paper-claim work.

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

XB1A1 follow-on decision:

```text
status=XB1A1_partial_baseline_only_completed
raw_doppler_provider=XB1A1_raw_doppler_provider_ready
a1_dual_yaw=XB1A1_A1_dual_yaw_invalid_due_GNSS_quality
normal_run_status=XB1A1_normal_partial_completed
legsa_full_status=blocked_dual_yaw_invalid
final_v23_status=not_applicable_dual_yaw_invalid
single_baseline_status=completed_normal_official_eval
quality_aware_branch=XB1A1_quality_aware_branch_recommended
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_XB1_degradation_or_PG2_planning=false
ready_for_paper_claims=false
recommended_next_stage=human_review_XB1A1_then_quality_aware_branch_or_PG2_source_review
```

XB1A2 follow-on decision:

```text
status=XB1A2_no_valid_A1_source_quality_aware_recommended
by2_status_relpos_diff=XB1A2_relpos_diff_invalid
absolute_position_candidate=nonphysical
normal_run_status=XB1A2_normal_blocked
quality_aware_branch=quality_aware_recommended_due_no_valid_A1
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_XB1_degradation_or_PG2_planning=false
ready_for_paper_claims=false
recommended_next_stage=human_review_XB1A2_then_quality_aware_branch_or_PG2_source_review
```

## Claim Boundary

Allowed: describe the quality profile, alignment result, source-role policy, input/provider blockers, XB1A2 relpos-difference re-audit, and quality-aware branch planning need.

Forbidden: paper claims, poor-GNSS robustness claims, final_v23 outperformance claims, artificial degradation, parameter retuning, trace-tuned thresholds, receiver IMU as body IMU, single-relpos/long-relpos/HDT yaw fallback, output-only correction, forcing dual-yaw normal runs without valid A1, treating absent normal figures as real result figures, PR #52 merge/closure/tag, or running PG2/degradation/adaptation without explicit human approval.
