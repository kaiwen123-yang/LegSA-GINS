# PROJECT_CONTEXT.md - LegSA-GINS Current Context

LegSA-GINS is a legged-robot GNSS/INS positioning and attitude project with source-backed EKF, Raw Doppler, source-aware weighting, Go2 proprioception, FGO, and FGO-feedback EKF workstreams.

This checkout is the Windows audit workspace, not the default WSL algorithm source repository. Use aliases from `PATH_POLICY.md` in tracked docs.

## Current Stage

- Current design/context stage: `N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION`.
- Current operational source of truth: `N9C0_GLOBAL_STAGED_N9B2_CONSOLIDATION_PRECHECK`.
- Current active nine-factor FGO design package: `<BY2_N9B2_WINDOWS_ROOT>/N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`.
- Current source-code audit and N9F7 design package: `<BY2_N9B2_WINDOWS_ROOT>/N9F6A_TO_N9F7_CODEBASE_FORENSIC_AUDIT_AND_ACTIVE_FGO_LEGGED_COMPLETION`.
- Current N9G0 manual design-review package: `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
- Current N9G0 export-clean design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_EXPORT_CLEAN_DESIGN_PACKAGE`.
- Current N9G1A/N9G1B runtime root: `<BY2_N9B2_WINDOWS_ROOT>/N9G1A_TO_N9G1B_CONTEXT_LOCK_AND_LEGSA_9F_PHASE1_IMPLEMENTATION`.
- Current export-clean design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`.
- Current metrics source: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`.
- Active final-only metrics row count: 825.
- N9E completed with a logging-blocked decision and `complete_nine_factor_FGO_claim=false`.
- N9F6A source audit completed from real source evidence; robot kinematics/contact/legged modeling exists mainly as provider, diagnostic, offline no-feedback, or candidate factor code.
- N9F7 followed Path C only and produced a design package; no implementation, solver/evaluator, representative run, full matrix, or figure generation was performed.
- N9G0 manual design review completed for a separate future `LegSA_9F_FGO_EKF` candidate.
- N9G0A completed Git boundary resolution; PR #52 head is synced to `9ceba928`.
- N9G1 is split into N9G1A context lock and later N9G1B Phase 1 provider/factor/logger/normal-smoke only.
- Current recommended next stage: human review of N9G1A, then explicit N9G1B decision.

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
ready_for_N9G1A_context_lock=true
ready_for_N9G1B_phase1_provider_factor_logger_normal_smoke=human_decision_required
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
- PR #52 head is synced to `9ceba928` after N9G0A.

## Current Technical Boundary

N9G1A is context-lock only. Do not run solvers, official evaluators, N9B2, representative active-nine-factor FGO runs, N9C1 figure generation, random generation, degraded-input generation, final paper figure generation, implementation, or paper-claim drafting. Do not modify algorithm math, FGO factor math, feedback policy, final_v23, KF-GINS-Baseline math, or `<WSL_ALGO_REPO>`. Do not relabel `LegSA_full_EKF` as active nine-factor FGO. Do not treat PR #52 head sync as merge, closure, tag, or paper-claim authorization.

N9G1B, if later approved, is limited to Phase 1 provider/factor/logger/normal-smoke work. Representative validation is deferred to N9G2. Full matrix, replot, and report stages are deferred to N9G3/N9G4 only if applicable and explicitly approved.

## Path Boundary

Tracked docs use aliases only. Actual local paths belong only in ignored `docs/codex_context/DATA_PATHS.local.md`. Runtime roots remain untracked.
