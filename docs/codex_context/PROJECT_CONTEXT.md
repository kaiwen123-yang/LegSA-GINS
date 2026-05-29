# PROJECT_CONTEXT.md - LegSA-GINS Current Context

LegSA-GINS is a legged-robot GNSS/INS positioning and attitude project with source-backed EKF, Raw Doppler, source-aware weighting, Go2 proprioception, FGO, and FGO-feedback EKF workstreams.

This checkout is the Windows audit workspace, not the default WSL algorithm source repository. Use aliases from `PATH_POLICY.md` in tracked docs.

## Current Stage

- Current implementation/context stage: `N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
- Current BY3/reporting stage: `BY3C_POSITION_UP_DEGRADATION_EXECUTION_BATCH0_TO_BATCH3_LONG_PIPELINE`.
- Current operational source of truth: `N9C0_GLOBAL_STAGED_N9B2_CONSOLIDATION_PRECHECK`.
- Current active nine-factor FGO design package: `<BY2_N9B2_WINDOWS_ROOT>/N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`.
- Current source-code audit and N9F7 design package: `<BY2_N9B2_WINDOWS_ROOT>/N9F6A_TO_N9F7_CODEBASE_FORENSIC_AUDIT_AND_ACTIVE_FGO_LEGGED_COMPLETION`.
- Current N9G0 manual design-review package: `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
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
- Current BY3C position/up Batch0-Batch3 execution root: `<BY3C_STAGE_ROOT>`.
- Current BY3 full-matrix placeholder root: `<BY3_FULL_MATRIX_ROOT>`.
- Current export-clean design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`.
- Current metrics source: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`.
- Active final-only metrics row count: 825.
- N9E completed with a logging-blocked decision and `complete_nine_factor_FGO_claim=false`.
- N9F6A source audit completed from real source evidence; robot kinematics/contact/legged modeling exists mainly as provider, diagnostic, offline no-feedback, or candidate factor code.
- N9F7 followed Path C only and produced a design package; no implementation, solver/evaluator, representative run, full matrix, or figure generation was performed.
- N9G0 manual design review completed for a separate future `LegSA_9F_FGO_EKF` candidate.
- N9G0A completed historical Git boundary resolution; PR #52 remains open/unmerged unless the human explicitly approves otherwise.
- N9G1 is split into N9G1A context lock and later N9G1B Phase 1 provider/factor/logger/normal-smoke only.
- N9G1A context lock passed reviewer gate and was pushed to PR #52 at `f1e80f1`.
- N9G1B created candidate identity/config, provider/factor audit helper, logger schemas, and safety gate, but normal smoke was not run because provider contracts and the active FGO backend are blocked.
- N9G1C-E resolved locked normal and core providers for `LegSA_9F_FGO_EKF`, but active backend and solver execution remain blocked, so normal smoke was not run.
- BY3A0_TO_BY3E completed BY3A0 context lock, BY3A inventory/body IMU audit, BY3B alignment, BY3C candidate input generation, BY2T text summaries, and BY2F copy-only figure archive. BY3D/E were blocked before solver/evaluator execution.
- BY3A1 repaired BY3 input-chain parity where BY2 policy was clear and materialized BY3 Go2 priors.
- BY3A2 recovered the historical BY2 WSL Raw Doppler, Go2, single-baseline, final_v23, and selected-feedback chains; BY3 Raw Doppler is now materialized through the accepted N5A/N5B path.
- BY3A3 generated same-case BY3 selected feedback from stage1 official-eval state/estimate columns only, then completed normal-only LegSA_full_EKF, GNSS1-status single-baseline, and final_v23 external-baseline official evaluation.
- BY3A4A recovered BY2 lateral dual-antenna yaw policy evidence as partial, encoded that lateral antennas are perpendicular to the robot forward/head direction, audited +90/-90 and baseline-reversal policies using existing BY3A3 outputs only, and blocked repaired yaw metrics because no physical/BY2-backed policy passed sanity without RMSE-only selection.
- BY3A4C recovered the historical BY2/N4 yaw-reference repair from git/docs/runtime evidence, including the N4H2D `official_ref_sign_minus` reference mapping that invalidated the old 93 deg yaw result and produced about 1.98 deg fresh replay yaw. Applying recovered and diagnostic profiles to existing BY3A3 outputs did not produce an accepted BY3 yaw reference, so BY3 yaw is `not_evaluable`.
- BY3A5B superseded BY3A5's HDT replacement policy and regenerated BY3 mainline dual yaw from GNSS1/GNSS2 A1_dual_diff short-baseline positions with BY2 lateral conversion and fixed_1p5 yaw_std.
- BY3A6 validated the BY3 trace truth/evaluator/base_time chain, confirmed processed trace lat/lon are unsafe for blind evaluation, repaired stale first-row initatt for stage1/LegSA, and completed a BY3 normal-only rerun. Yaw still failed before BY3A7.
- BY3A7 confirmed the remaining yaw failure came from BY3 Go2 IMU preprocessing: gyro bias was estimated from a moving segment after selected Go2 start. BY3A7 repaired a BY3A7-local IMU using the pre-motion source gyro-bias segment, preserved A1 yaw source and yaw gates, reran BY3 normal only, and dual-yaw yaw sanity passed.
- BY3A8 computed the remaining BY3 yaw error budget and found A1 observation quality is the limiting factor: A1-vs-trace heading RMSE is about 24.06 deg and p95 about 31.78 deg. No safe additional repair passed and no normal rerun was run.
- BY3B imported the BY3A8 scope, locked BY3A7 repaired IMU plus A1_dual_diff as future accepted sources, and created position/up-primary degradation plans with diagnostic yaw only. BY3B did not generate degraded inputs, random arrays, solvers, evaluators, figures, or paper claims.
- BY3C completed the approved Batch0-Batch3 position/up execution subset: normal parity, deterministic A/B/E_position_std, C_position_noise seeds 0..9, and D_position_spike seeds 0..9. It produced 213 final metric rows, figures, case reviews, consolidated review, and final validation; yaw remains diagnostic-only and paper claims remain false.
- Current active-FGO recommended next stage: `implement_active_fgo_backend_or_reframe_scope`.

## Current Batch State

- Batch 0 normal smoke complete.
- Batch 1 deterministic complete.
- Batch 2 position noise complete.
- Batch 3 position spike complete.
- Batch 4 yaw noise complete.
- Batch 5 core module-disable complete; module-stress deferred.
- Batch 6 selected mixed cases complete.
- final_v23 external baseline complete and integrated.
- No full monolithic N9B2 was run.

## Current Decision Flags

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
ready_for_N9C1_consolidated_figure_generation=true
complete_nine_factor_FGO_claim=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

## Current PR Boundary

- PR #21: open/unmerged historical branch; do not touch.
- PR #52: open/unmerged unless the human explicitly approves merge/tag/closure.
- PR #52 remains open/unmerged; merge, closure, and tag actions require explicit human approval.

## Current Technical Boundary

N9G1C-E is provider contract resolution, active-backend audit, logger schema connection, and normal-smoke gate work only. It did not run solvers, official evaluators, N9B2, representative active-nine-factor FGO runs, N9C1 figure generation, random generation, degraded-input generation, final paper figure generation, or paper-claim drafting. Do not modify algorithm math, feedback policy, final_v23, KF-GINS-Baseline math, or `<WSL_ALGO_REPO>` without a later explicit stage. Do not relabel `LegSA_full_EKF` as active nine-factor FGO. Do not treat PR #52 head sync as merge, closure, tag, or paper-claim authorization.

N9G2 representative validation is blocked until provider/factor and active FGO backend gaps are fixed and reviewed. Full matrix, replot, and report stages are deferred to N9G3/N9G4 only if applicable and explicitly approved.

BY3C executed only the human-approved position/up-primary Batch0-Batch3 subset with diagnostic yaw. BY3 yaw input remains A1_dual_diff short baseline, stale first-row initatt was repaired in BY3A6, BY3A7 repaired a BY3-local IMU preprocessing bias bug without changing yaw gates or tuning parameters, and BY3A8 found the remaining yaw error is limited by A1 observation quality with no safe additional repair. BY3A3/BY3A4A/BY3A5/BY3A5B/BY3A6 yaw metrics remain historical bad-input, invalid-reference, or pre-BY3A7 evidence and must not support paper claims or final_v23 outperformance. BY3C does not authorize H_dual_yaw_noise, E_yaw_std_inflation, mixed, module-disable, LegSA_9F_FGO_EKF, nonredundant-FGO, or full monolithic BY3 matrix execution.

## Path Boundary

Tracked docs use aliases only. Actual local paths belong only in ignored `docs/codex_context/DATA_PATHS.local.md`. Runtime roots remain untracked.
## BY3A5/BY3A5B Dual Yaw Input Source Repair

BY3A5 correctly confirms the old BY3 15-column yaw input was wrong-source, but its HDT repaired-input policy is diagnostic/rejected/superseded for mainline BY3.

BY3A5B repairs the mainline yaw input with A1_dual_diff short-baseline yaw from GNSS1/GNSS2 absolute positions, BY2 sign/lateral conversion, and fixed_1p5 yaw_std. GNSS status long-baseline `rel_pos_n/e/d` and NMEA HDT are rejected as mainline solver yaw sources.

## BY3A6 Trace Truth Initatt Gate Forensic

BY3A6 locks the trace file as evaluation truth, validates evaluator raw numeric fields/base_time/yaw_truth_mode, rejects blind use of processed trace lat/lon fields, audits A1_dual_diff input, confirms and repairs stale first-row initatt for stage1/LegSA, and reruns BY3 normal only. Its post-repair yaw failure is superseded by BY3A7 for current BY3 readiness.

## BY3A7 A1 Yaw Dynamic Quality IMU Gate Repair

BY3A7 audits A1 yaw dynamic quality, BY3 Go2 IMU sign-axis/yaw propagation, yaw gate residuals, and yaw update code. It confirms a BY3 IMU preprocessing bug: dynamic gyro bias was estimated from a moving segment after selected Go2 start. The repair is BY3A7-local static pre-motion source-bias IMU input only; A1 yaw source, fixed_1p5 yaw_std, yaw gates, trace/evaluator policy, and solver parameters are unchanged.

## BY3A8 Yaw Error Budget Safe Repair

BY3A8 accepts the BY3A7 normal-only outputs and budgets the remaining 4-5 deg dual-yaw error. It finds that A1_dual_diff observation quality does not support a robust 2 deg normal-yaw expectation without additional modeling: A1-vs-trace heading RMSE is about 24.06 deg, p95 about 31.78 deg, and max about 167.29 deg. Source-quality-only checks identify 6 objective invalid A1 epochs, not enough to explain the broad observation error. BY3A8 finds no safe IMU bias, time-lag, yaw-gate, or continuity repair and does not run a normal rerun. Feedback worsens yaw relative to stage1 but remains unchanged pending a separate review. Current BY3 planning scope is `position_up_with_diagnostic_yaw`, and `ready_for_paper_claims=false`.

## BY3B Position Up With Diagnostic Yaw Planning

BY3B completed planning/precheck only. It locked future BY3 degradation execution to BY3A7 repaired IMU and BY3A5B/BY3A7 A1_dual_diff yaw source, defined 75 position/up-primary case-seed units plus 43 diagnostic-yaw units, preserved same-seed fairness, required same-case degraded feedback generation for LegSA, and wrote dry-run command templates with `execute_now=false`.

## BY3C Position Up Degradation Execution

BY3C completed only approved Batch0-Batch3 position/up execution. It used BY3A7 repaired IMU, BY3A5B/BY3A7 A1_dual_diff yaw, BY3A2 Raw Doppler, BY3 Go2 priors, trace as evaluation-only reference, and same-case degraded feedback generated from each case's stage1 official EVAL_NAV state/estimate columns. It produced 71 executed case units, 213 final metric rows, 12 consolidated figure rows, and batch/case-review packages. Current decision is `BY3C_batch0_to_batch3_position_up_degradation_complete`; `ready_for_BY3D_diagnostic_yaw_or_mixed_planning=true_after_human_review`; `ready_for_paper_claims=false`.
