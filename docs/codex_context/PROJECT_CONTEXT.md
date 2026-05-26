# PROJECT_CONTEXT.md - LegSA-GINS Current Context

LegSA-GINS is a legged-robot GNSS/INS positioning and attitude project with source-backed EKF, Raw Doppler, source-aware weighting, Go2 proprioception, FGO, and FGO-feedback EKF workstreams.

This checkout is the Windows audit workspace, not the default WSL algorithm source repository. Use aliases from `PATH_POLICY.md` in tracked docs.

## Current Stage

- Current design/context stage: `N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`.
- Current operational source of truth: `N9C0_GLOBAL_STAGED_N9B2_CONSOLIDATION_PRECHECK`.
- Current active nine-factor FGO design package: `<BY2_N9B2_WINDOWS_ROOT>/N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`.
- Current export-clean design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`.
- Current metrics source: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`.
- Active final-only metrics row count: 825.
- N9E completed with a logging-blocked decision and `complete_nine_factor_FGO_claim=false`.
- Current recommended next stage: `N9F6_HUMAN_REVIEW_LEGSA_9F_IMPLEMENTATION_PLAN`.

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
ready_for_implementation_review=true
ready_for_N9C1_consolidated_figure_generation=true
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

## Current PR Boundary

- PR #21: open/unmerged historical branch; do not touch.
- PR #52: open/unmerged unless the human explicitly approves merge/tag/closure.

## Current Technical Boundary

N9F0_TO_N9F2 is design/context sync only. Do not run solvers, official evaluators, N9B2, representative active-nine-factor FGO runs, N9C1 figure generation, random generation, degraded-input generation, final paper figure generation, or paper-claim drafting. Do not modify algorithm math, FGO factor math, feedback policy, final_v23, KF-GINS-Baseline math, or `<WSL_ALGO_REPO>`. Do not relabel `LegSA_full_EKF` as active nine-factor FGO.

## Path Boundary

Tracked docs use aliases only. Actual local paths belong only in ignored `docs/codex_context/DATA_PATHS.local.md`. Runtime roots remain untracked.
