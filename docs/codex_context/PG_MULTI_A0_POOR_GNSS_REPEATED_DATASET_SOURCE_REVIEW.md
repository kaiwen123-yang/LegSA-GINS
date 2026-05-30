# PG_MULTI_A0 Poor-GNSS Repeated Dataset Source Review

Stage: `PG_MULTI_A0_POOR_GNSS_REPEATED_DATASET_SOURCE_REVIEW_AND_RUNNABILITY_CLASSIFICATION_WITH_LOCKED_XB2_XB3_XB4_BODY_PATHS`

Purpose: review the four repeated poor-GNSS experiments without running solvers, evaluators, degradation generation, random generation, retuning, quality-aware execution, or paper-claim work.

Runtime root: `<PG_MULTI_A0_STAGE_ROOT>`

## Decision

```text
status=PG_MULTI_A0_all_repeats_severe_quality_aware_branch_recommended
pg1_imported_from_XB1A2=true
pg2_pg3_pg4_receiver_roots_registered=true
pg2_pg3_pg4_body_paths_locked=true
pg2_pg3_pg4_body_parseable=true
raw_doppler_provider_feasibility=PG1_ready_PG2_PG3_PG4_likely_ready
a1_relpos_diff=invalid_all_repeats
runnability_classification=quality_aware_branch_candidate_all_repeats
ready_for_selected_PG_normal_run_planning=false
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_paper_claims=false
recommended_next_stage=human_review_PG_MULTI_A0_then_quality_aware_branch_or_position_only_diagnostic_or_stop
```

## Dataset Registration

- PG1/XB1 was imported from XB1A2 through `<XB1A2_STAGE_ROOT>`.
- PG2/XB2 receiver and body sources are represented by `<PG2_XB2_RECEIVER_ROOT>` and `<PG2_XB2_BODY_SOURCE>`.
- PG3/XB3 receiver and body sources are represented by `<PG3_XB3_RECEIVER_ROOT>` and `<PG3_XB3_BODY_SOURCE>`.
- PG4/XB4 receiver and body sources are represented by `<PG4_XB4_RECEIVER_ROOT>` and `<PG4_XB4_BODY_SOURCE>`.

Tracked docs must not contain the concrete PG2/PG3/PG4 local paths. Those belong only in local path files or untracked runtime reports.

## Body Source Lock

The PG2/PG3/PG4 body/high-level files are locked by user-provided mapping. They parsed as `/sportmodestate` logs and overlap the receiver time ranges:

- PG2/XB2: 84436 body rows, about 358.66 s receiver/body overlap.
- PG3/XB3: 80306 body rows, about 346.44 s receiver/body overlap.
- PG4/XB4: 79738 body rows, about 356.18 s receiver/body overlap.

Receiver `imu-data.csv` is diagnostic only and was not used as body IMU.

## A1 Dual-Yaw Audit

The BY2-compatible status relpos-difference path was audited before invalidity decisions: interpolate GNSS2 status rel_pos to GNSS1 time and compute `rel_pos_gnss2 - rel_pos_gnss1`.

Primary `gnss2_minus_gnss1` results:

- PG1/XB1: imported XB1A2 result; 356 rows, 7 physical-band epochs, valid ratio about 0.01966, median about 9.18 m, p95 about 50.96 m, max about 131.70 m.
- PG2/XB2: 330 rows, zero physical-band epochs, median about 14.27 m, p95 about 55.57 m.
- PG3/XB3: 315 rows, zero physical-band epochs, median about 14.84 m, p95 about 107.10 m.
- PG4/XB4: 315 rows, zero physical-band epochs, median about 36.63 m, p95 about 63.52 m.

Single status `rel_pos_n/e/d`, HDT, and absolute LLH difference remain rejected as mainline yaw sources.

## Runnability

All four repeats are classified as `quality_aware_branch_candidate`, with `position_only_fallback_candidate` as a diagnostic secondary tag.

- `single_antenna_gnss1_status_KF_GINS`: possible diagnostic fallback after later human approval.
- `LegSA_full_EKF`: not applicable for frozen dual-yaw mainline because A1 is invalid.
- `final_v23_dual_antenna_EKF`: not applicable without valid dual-yaw input.
- quality-aware branch: planning may be considered after human review; implementation/execution was not performed.

## Boundaries

PG_MULTI_A0 does not authorize frozen dual-yaw mainline runs, solver/evaluator execution, artificial degradation, random arrays, parameter retuning, quality-aware execution, paper claims, PR #52 merge/closure/tag, or poor-GNSS robustness claims.
