# PROJECT_CONTEXT.md - LegSA-GINS Current Context

LegSA-GINS is a legged-robot GNSS/INS positioning and attitude project with source-backed EKF, Raw Doppler, source-aware weighting, Go2 proprioception, FGO, and FGO-feedback EKF workstreams.

This checkout is the Windows audit workspace, not the default WSL algorithm source repository. Use aliases from `PATH_POLICY.md` in tracked docs.

## Current Stage

- Current implementation/context stage: `N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
- Current BY3/reporting stage: `BY3A3_SELECTED_FEEDBACK_STAGE1_CHAIN_AND_NORMAL_GENERALIZATION_EXECUTION`.
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
- Current BY3 recommended next stage: `BY3B_DEGRADATION_MATRIX_PLANNING_AND_PRECHECK`.
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
ready_for_BY3_solver_evaluator=normal_completed
ready_for_BY3_input_chain=repaired
ready_for_BY3_go2_priors=true
ready_for_BY3_raw_doppler_provider=true
ready_for_BY3_same_case_feedback=true
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

BY3 degradation planning is now ready for a dedicated planning/precheck stage after BY3A3 normal-only solver/evaluator completion. BY3A3 metrics are runtime evidence for review only, not paper claims, final_v23 outperformance claims, or BY3 degradation/full-matrix completion.

## Path Boundary

Tracked docs use aliases only. Actual local paths belong only in ignored `docs/codex_context/DATA_PATHS.local.md`. Runtime roots remain untracked.
