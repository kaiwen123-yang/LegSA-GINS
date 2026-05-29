# Current State - BY3C Position/Up Degradation Execution Batch0-Batch3

This file records the current verified operational state for the Windows audit workspace. It supersedes stale N8K, N9A, N9B2B1, and N9B-not-started text except where that text is explicitly historical.

## Verified Current State

- Current implementation/context stage: `N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
- Current BY3/reporting stage: `BY3B_POSITION_UP_WITH_DIAGNOSTIC_YAW_PLANNING`.
- Current operational source of truth for degradation metrics remains `N9C0_GLOBAL_STAGED_N9B2_CONSOLIDATION_PRECHECK`.
- Current active nine-factor FGO design source: `<BY2_N9B2_WINDOWS_ROOT>/N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`.
- Current source-code forensic audit and N9F7 design package: `<BY2_N9B2_WINDOWS_ROOT>/N9F6A_TO_N9F7_CODEBASE_FORENSIC_AUDIT_AND_ACTIVE_FGO_LEGGED_COMPLETION`.
- Current Git-boundary and N9G0 manual design-review package: `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
- Current N9G0 full-matrix design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_LEGSA_9F_FGO_EKF_DESIGN_PACKAGE`.
- Current N9G0 export-clean design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_EXPORT_CLEAN_DESIGN_PACKAGE`.
- Current N9G1A/N9G1B runtime root: `<BY2_N9B2_WINDOWS_ROOT>/N9G1A_TO_N9G1B_CONTEXT_LOCK_AND_LEGSA_9F_PHASE1_IMPLEMENTATION`.
- Current N9G1C-E runtime root: `<BY2_N9B2_WINDOWS_ROOT>/N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
- Current BY3 stage root: `<BY3_STAGE_ROOT>`.
- Current BY3A1 parity/provider-gate root: `<BY3A1_STAGE_ROOT>`.
- Current BY3A2 historical recovery/provider-gate root: `<BY3A2_STAGE_ROOT>`.
- Current BY3A3 selected-feedback/normal execution root: `<BY3A3_STAGE_ROOT>`.
- Current BY3A4A yaw-repair/context-memory root: `<BY3A4A_STAGE_ROOT>`.
- Current BY3A4C yaw-history reconstruction root: `<BY3A4C_STAGE_ROOT>`.
- Current BY3A5B A1 dual-diff yaw-input repair root: `<BY3A5B_STAGE_ROOT>`.
- Current BY3A6 trace-truth/initatt/gate forensic root: `<BY3A6_STAGE_ROOT>`.
- Current BY3A7 A1 yaw dynamic-quality/IMU gate repair root: `<BY3A7_STAGE_ROOT>`.
- Current BY3A8 yaw error-budget safe-repair root: `<BY3A8_STAGE_ROOT>`.
- Current BY3B position/up diagnostic-yaw planning root: `<BY3B_STAGE_ROOT>`.
- Current BY3 full-matrix placeholder root: `<BY3_FULL_MATRIX_ROOT>`.
- Current BY3 receiver source alias: `<BY3_RECEIVER_ROOT>`.
- Current BY3 Go2 body/high-level source alias: `<BY3_GO2_BODY_SOURCE>`.
- Current BY2 degradation report archive alias: `<BY2_DEGRADATION_ARCHIVE_ROOT>`.
- Current export-clean design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`.
- N9C0 consolidated precheck root: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>`.
- N9C0 active metrics source: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`.
- N9C0 active final-only metrics row count: 825.
- N9C1 consolidated figure generation readiness: passed.
- PR #52 remains open/unmerged unless the human explicitly approves otherwise.
- N9G0A Git boundary resolution completed historically; PR #52 remains open/unmerged unless the human explicitly approves otherwise.
- N9E active nine-factor FGO/legged logger review completed with `complete_nine_factor_FGO_claim=false`.
- N9F decision: current evidence requires a new active nine-factor FGO algorithm design; `LegSA_full_EKF` is not accepted as active nine-factor FGO.
- N9F6A decision: source evidence shows active EKF/update/feedback code and offline/candidate FGO/legged code, but no active nine-factor FGO solver.
- N9F7 decision: `N9F7_substantial_algorithm_design_required`; Path C design package only, no implementation or runs.
- N9F7A historical decision: publish was blocked pending human review because the branch contained an existing unpushed non-doc reporting/test commit before the docs lock.
- N9G0 decision: manual design review completed for a separate `LegSA_9F_FGO_EKF` candidate; no implementation or solver/evaluator/figure execution.
- N9G1 split decision: `N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION` is separate from later `N9G1B_PHASE1_PROVIDER_FACTOR_LOGGER_NORMAL_SMOKE_ONLY`.
- N9G1A context lock passed reviewer gate and was pushed to PR #52 at `f1e80f1`.
- N9G1B Phase 1 created the separate `LegSA_9F_FGO_EKF` candidate identity, provider/factor contract audit helpers, logger schemas, safety gate, and runtime decision artifacts.
- N9G1B normal smoke was not run. The gate blocked it because provider contracts are not ready for active factors, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled.
- N9G1C-E resolved the locked normal clean source and core providers for `LegSA_9F_FGO_EKF`.
- N9G1C-E provider decision: `N9G1C_provider_contracts_partial_accepted`.
- N9G1C-E backend decision: `N9G1D_active_backend_blocked`.
- N9G1E normal smoke gate decision: `N9G1E_normal_smoke_gate_blocked`; normal smoke was not run.
- BY3A0 context lock completed as report-only bootstrap.
- BY3A inventory/body IMU audit completed as source inventory only.
- BY3B alignment passed using the BY2 event-normalized kick policy with no trace tuning.
- BY3C candidate Go2 IMU and GNSS status inputs were generated, but runtime configs remain `execution_allowed=false`.
- BY2T text summaries were generated from existing active final-only metrics.
- BY2F reorganization completed as a copy-only archive of existing BY2 figure evidence.
- BY3D/E were blocked before solver/comparison/decision outputs because BY3 raw Doppler/Go2 prior/same-case feedback, single-baseline runner handoff, and final_v23 external-baseline input gates were not satisfied.
- BY3A1 extracted the accepted BY2 input chain and found BY3A0 candidate input mismatches in delimiter/header, IMU column count, single-baseline schema, and original event-normalized time policy.
- BY3A1 repaired BY3 IMU, dual-GNSS, and single-GNSS1 runtime input files to BY2-compatible no-header whitespace numeric conventions using a common BY3 body-source time zero without trace tuning.
- BY3A1 materialized BY3 Go2 attitude, horizontal velocity, and joint prior provider files from the BY3 Go2 body source, with Go2 truth claims disabled.
- BY3A1 did not materialize BY3 Raw Doppler because the accepted BY2 RTKLIB provider logic requires RINEX observation/navigation inputs that were not available in the receiver CSV tree.
- BY3A2 recovered the historical BY2 WSL chains for Raw Doppler, Go2 priors, single-baseline handoff, final_v23 external handoff, and selected-feedback same-case dependency.
- BY3A2 rebuilt BY3 UBX/RAWX evidence and materialized the BY3 Raw Doppler provider through the accepted N5A/N5B RTKLIB/RINEX/helper path.
- BY3A2 validated BY3 Go2 priors and generated single/final_v23 runtime handoff configs for review.
- BY3A2 did not run BY3 solvers, official evaluators, degradation, metrics, or metric figures because same-case selected feedback remains blocked.
- BY3A3 recovered the BY2 selected-feedback stage1 policy and generated BY3 same-case feedback from the stage1 official-eval state/estimate table only.
- BY3A3 completed BY3 normal-only solver/evaluator execution for `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, and `final_v23_dual_antenna_EKF`.
- BY3A3 produced official normal metrics, figures, and a case review under `<BY3A3_STAGE_ROOT>` while keeping trace evaluation-only, final_v23 external-only, and no paper claims.
- BY3A3 did not run BY3 degradation, artificial degradations, LegSA_9F_FGO_EKF, nonredundant FGO extension, branch ablations, parameter retuning, trace tuning, BY2 feedback reuse, output substitution, PR merge/closure, or tag creation.
- BY3A4A recovered BY2 lateral dual-antenna yaw policy evidence as partial and locked the physical rule that the dual antennas are lateral/perpendicular to robot forward direction.
- BY3A4A requires body heading to account for a plus/minus 90 degree correction from antenna-baseline heading depending on antenna direction and coordinate convention; +90/-90 must not be selected by RMSE alone.
- BY3A4A tested current BY3A3, BY2-recovered lateral, plus/minus 90, and baseline-reversal yaw policies using existing BY3A3 solver outputs only. No policy produced sane yaw across all three normal algorithms, so repaired yaw metrics were not accepted.
- BY3A4A recomputed strict common-overlap metrics, regenerated diagnostic figures, generated the seed0-9 explanation files, and updated context/Obsidian memory. It did not run solvers, degradation, parameter retuning, or paper-claim work.
- BY3A4C recovered the historical BY2/N4 yaw-reference repair from git history, tracked docs/source, PR metadata, and runtime evidence.
- BY3A4C verified that N4H2 old yaw around 93 deg was invalidated by N4H2D, that N4H2D selected `official_ref_sign_minus`, and that fresh replay yaw was about 1.98 deg under the reconstructed dual official reference.
- BY3A4C applied recovered and diagnostic yaw profiles to existing BY3A3 outputs only. No BY3 yaw truth/reference profile was accepted, so BY3 yaw is `not_evaluable` and BY3A3/BY3A4A bad yaw metrics remain historical invalid-reference evidence.
- BY3A4C generated diagnostic yaw-source figures, a position-only common-overlap panel, metric policy, case review, context/Obsidian notes, and validation reports. It did not run solvers, degradation, parameter retuning, output correction, RMSE-only yaw policy selection, or paper-claim work.
- BY3A5 confirmed the old BY3 15-column yaw input was wrong-source, but its HDT replacement policy is now diagnostic/rejected/superseded for mainline BY3.
- BY3A5B reconstructed BY3 A1_dual_diff yaw from GNSS1/GNSS2 short-baseline absolute positions. The short-baseline median is about 0.383 m, while GNSS1 status `rel_pos_n/e/d` has median length about 3062.8 m and is rejected as a long-baseline/base-vector source.
- BY3A5B generated `BY3_DUAL_A1_DIFF_15COL_REPAIRED.gnss` with BY2 `gnss2_minus_gnss1`, lateral conversion equivalent to `baseline_heading+90`, and fixed_1p5 yaw_std. HDT was not used as solver input.
- BY3A6 locked the BY3 trace file as the evaluation truth reference, validated evaluator raw numeric field selection/base_time/yaw_truth_mode, and marked processed trace lat/lon fields unsafe for blind evaluation.
- BY3A6 confirmed that BY3A5B A1_dual_diff remains the mainline dual-yaw input with caution: source/schema/starttime coverage are valid, but A1-vs-trace heading and yaw-gate behavior remain unresolved.
- BY3A6 confirmed a stale first-row initatt bug for stage1 and `LegSA_full_EKF`; the safe repair uses the first dual GNSS/A1 yaw row at or after the requested starttime and does not use trace.
- BY3A7 confirmed the remaining yaw failure was dominated by a BY3 Go2 IMU preprocessing bug: gyro bias was estimated from a moving segment after selected Go2 start. BY3A7 repaired a BY3A7-local IMU with pre-motion source gyro bias, kept A1 yaw source/gates unchanged, reran BY3 normal only, and dual-yaw yaw sanity passed.
- BY3A8 accepted BY3A7 and computed the remaining yaw error budget. A1 yaw versus trace heading has RMSE about 24.06 deg and p95 about 31.78 deg, so the raw A1 observation quality does not support a robust 2 deg normal-yaw expectation. No source-backed A1 mask, IMU bias refinement, metadata-backed time-lag fix, yaw-gate change, or feedback change passed the safe repair gate.
- BY3B imported the BY3A8 decision and completed planning/precheck only: accepted-source lock, position/up family scope, case matrix, seed plan, provider/feedback dependency plan, dry-run command templates, evaluator/metric policy, figure/case-review plan, and batch plan. BY3B did not generate degraded inputs, random arrays, solver/evaluator outputs, figures, degradation results, or paper claims.
- BY3C executed the approved Batch0-Batch3 position/up subset only: normal parity, A/B/E_position_std deterministic cases, C_position_noise seeds 0..9, and D_position_spike seeds 0..9. BY3C produced official evaluations, same-case feedback, 213 final metric rows, figures, case reviews, and consolidated review; yaw remains diagnostic-only and paper claims remain false.
- BY3A1 did not materialize same-case selected feedback because no real BY3 stage1 solver and official EVAL_NAV exist.
- BY3A1 did not run BY3 solvers, official evaluators, degradation, metrics, or metric figures.
- `LegSA_full_EKF` remains the current verified EKF/feedback algorithm.
- `LegSA_9F_FGO_EKF` is a separate new candidate.
- `complete_nine_factor_FGO_claim=false`.

## Batch State

- Batch 0 normal smoke: complete.
- Batch 1 deterministic: complete.
- Batch 2 position noise: complete.
- Batch 3 position spike: complete.
- Batch 4 yaw noise: complete.
- Batch 5 core module-disable: complete.
- Batch 5 module-stress: deferred.
- Batch 6 selected mixed cases: complete for `M_mixed_A` through `M_mixed_F`.
- final_v23 external baseline: complete and integrated as `external_reference_baseline`.
- Full monolithic N9B2: not run.

## Current Decision

N9G1C-E is provider contract resolution, active-backend audit, logger schema connection, and normal-smoke gate work only. It does not provide active nine-factor FGO residual/Jacobian/cost rows and did not run solver, official evaluator, representative degradation, full matrix, random/degraded-input generation, figure generation, PR merge/closure, tag creation, or paper claims.

BY3A1 is an input-chain parity and provider-gate repair stage only. It repaired BY3 runtime input format/time conventions and materialized BY3 Go2 priors, but the final decision remains `BY3A1_provider_or_feedback_blocked`.

BY3A3 is a normal-only selected-feedback and comparison execution stage. Its normal comparison completed, but its earlier BY3 degradation-planning readiness is superseded by BY3A4A.

BY3C is the active BY3 execution decision. The final decision is `BY3C_batch0_to_batch3_position_up_degradation_complete`: A1 dual-diff remains mainline with dynamic-quality caution, BY3A7's IMU repair remains accepted, BY3A8 yaw remains diagnostic-only, and only approved Batch0-Batch3 position/up execution is complete. Paper claims remain disabled.

## Next Stage

```text
recommended_next_stage=implement_active_fgo_backend_or_reframe_scope
recommended_BY3_next_stage=human_review_BY3C_then_BY3D_DIAGNOSTIC_YAW_OR_MIXED_PLANNING
```

Planned sequence after human review:

```text
implement_active_fgo_backend_or_reframe_scope
N9G2_REPRESENTATIVE_VALIDATION only after active backend/provider/factor gaps are fixed and reviewed
N9G3_FULL_MATRIX if applicable and explicitly approved
N9G4_REPLOT_AND_REPORT if applicable and explicitly approved
N9C1_CONSOLIDATED_FIGURE_GENERATION
N9C2_FIGURE_VISUAL_REVIEW_AND_REPAIR
N9C3_CONSOLIDATED_CASE_REVIEW_AND_REPORT_PACKAGE
N9D_CLAIM_BOUNDARY_AND_PAPER_WRITING_READINESS_REVIEW
```

## Readiness Flags

```text
ready_for_algorithm_design_review=true
ready_for_implementation_review=false
ready_for_N9G1A_context_lock=complete
ready_for_N9G1C_E_provider_backend_normal_smoke=blocked_active_backend
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=position_up_with_diagnostic_yaw
ready_for_BY3C_position_up_degradation_execution=complete_batch0_to_batch3
ready_for_BY3D_diagnostic_yaw_or_mixed_planning=true_after_human_review
ready_for_BY3_solver_evaluator=normal_completed
ready_for_BY3_input_chain=repaired
ready_for_BY3_go2_priors=true
ready_for_BY3_raw_doppler_provider=true
ready_for_BY3_same_case_feedback=true
ready_for_BY3_yaw_input_policy=A1_dual_diff_repaired
ready_for_BY3_yaw_reference=diagnostic_only_after_BY3A8_A1_lower_bound
yaw_degradation_claims=diagnostic_only
ready_for_BY3_paper_claims=false
ready_for_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

## Active Rules

- Use N9C0 final-only metrics for current global metric tables.
- Do not use superseded rows, `historical_nominal_none`, or `B_gnss_downsample_2Hz` for active conclusions.
- `single_antenna_gnss1_status_KF_GINS` is a GNSS1-status baseline, not raw GNSS.
- `final_v23_dual_antenna_EKF` is an external reference baseline only.
- `selected_feedback` requires same-case feedback; clean feedback is forbidden for degraded cases.
- Trace, final_v23 output, and LegSA output must not be solver inputs.
- Runtime roots remain untracked.
- Tracked docs use aliases only; concrete local paths belong only in ignored `docs/codex_context/DATA_PATHS.local.md`.
- Do not relabel `LegSA_full_EKF` as active nine-factor FGO.
- Do not treat provider/update counts or historical candidate no-feedback rows as current active FGO residual/cost evidence.
- Do not treat N9F6A/N9F7 design-package artifacts as active solver residual/cost evidence.
- Do not treat N9G0 design artifacts as implemented solver evidence.
- Do not treat PR #52 head sync as merge, closure, tag, or paper-claim authorization.
- Do not run representative degradation or full-matrix validation in N9G1B.
## BY3A5/BY3A5B Dual Yaw Input Source Repair

BY3A5 remains historical wrong-source evidence. It correctly confirmed the old BY3 15-column yaw input was not a valid short-baseline dual-antenna yaw source, but its HDT replacement policy is diagnostic/rejected/superseded for mainline BY3.

BY3A5B remains the current mainline yaw-input repair. It uses GNSS1/GNSS2 A1_dual_diff short-baseline absolute positions, BY2 sign/lateral conversion, and fixed_1p5 yaw_std. Status long-baseline `rel_pos_n/e/d` and NMEA HDT are rejected as solver yaw sources.

## BY3A6 Trace Truth Initatt Gate Forensic

BY3A6 remains the accepted trace/evaluator/base-time/initatt forensic reference. It locked the trace file as evaluation truth, verified evaluator raw-field/base_time behavior, confirmed processed trace lat/lon are unsafe for blind evaluation, audited A1_dual_diff input, confirmed and repaired stale first-row initatt in stage1/LegSA, and reran BY3 normal only. The BY3A6 yaw failure is historical pre-BY3A7 evidence.

## BY3A7 A1 Yaw Dynamic Quality IMU Gate Repair

BY3A7 is the accepted IMU repair decision. It audited A1 yaw jumps/baseline quality, BY3 Go2 IMU sign-axis and yaw-rate propagation, yaw gate residuals, and yaw update code. The safe repair was BY3A7-local IMU preprocessing only: use pre-motion source gyro bias instead of the moving-segment bias after selected Go2 start. BY3A7 normal-only rerun produced about 5.26 deg LegSA yaw RMSE and about 4.30 deg final_v23 yaw RMSE.

## BY3A8 Yaw Error Budget Safe Repair

BY3A8 is the accepted yaw error-budget decision. It computed the A1 observation lower bound against the BY3 trace as evaluation-only reference and found A1-vs-trace heading RMSE about 24.06 deg, p95 about 31.78 deg, max about 167.29 deg, and circular mean about -15.06 deg. A1 objective source-quality checks found only 6 invalid solver-candidate epochs, so an objective mask would not repair the broad observation error. BY3A8 found no safe IMU bias refinement, no metadata-backed time-lag repair, and no yaw-gate repair. Feedback worsened yaw relative to stage1 and is left for a separate human-approved review. Current BY3 planning scope is `position_up_with_diagnostic_yaw`; `ready_for_paper_claims=false`.

## BY3B Position Up With Diagnostic Yaw Planning

BY3B is the historical BY3 planning state. It locked future BY3 degradation execution to the BY3A7 repaired IMU and the BY3A5B/BY3A7 A1_dual_diff yaw input. It planned 118 case-seed units: 75 position/up-primary units and 43 diagnostic-yaw units, with 311 future solver rows if later human-approved. BY3B itself did not generate random arrays, degraded inputs, solver outputs, evaluator outputs, figures, or paper claims.

## BY3C Position Up Degradation Execution

BY3C is the current BY3 execution state. It completed only the human-approved Batch0-Batch3 position/up subset: 1 normal parity case, 10 deterministic A/B/E_position_std cases, 30 C_position_noise case-seed units, and 30 D_position_spike case-seed units. It used BY3A7 repaired IMU, BY3A5B/BY3A7 A1_dual_diff yaw, BY3A2 Raw Doppler, BY3 Go2 priors, same-case degraded feedback from each stage1 official EVAL_NAV state/estimate table, and trace as evaluation-only reference. It produced 213 final metric rows, figures, case reviews, consolidated metrics, and final validation. It did not run H_dual_yaw_noise, E_yaw_std_inflation, mixed, module-disable, LegSA_9F_FGO_EKF, nonredundant-FGO, or full monolithic BY3 matrix cases. Current decision: `BY3C_batch0_to_batch3_position_up_degradation_complete`; `ready_for_BY3D_diagnostic_yaw_or_mixed_planning=true_after_human_review`; `ready_for_paper_claims=false`.
