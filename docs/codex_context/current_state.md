# Current State - N9G1B Phase 1 Blocked Before Normal Smoke

This file records the current verified operational state for the Windows audit workspace. It supersedes stale N8K, N9A, N9B2B1, and N9B-not-started text except where that text is explicitly historical.

## Verified Current State

- Current implementation/context stage: `N9G1B_PHASE1_PROVIDER_FACTOR_LOGGER_NORMAL_SMOKE_ONLY`.
- Current operational source of truth for degradation metrics remains `N9C0_GLOBAL_STAGED_N9B2_CONSOLIDATION_PRECHECK`.
- Current active nine-factor FGO design source: `<BY2_N9B2_WINDOWS_ROOT>/N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`.
- Current source-code forensic audit and N9F7 design package: `<BY2_N9B2_WINDOWS_ROOT>/N9F6A_TO_N9F7_CODEBASE_FORENSIC_AUDIT_AND_ACTIVE_FGO_LEGGED_COMPLETION`.
- Current Git-boundary and N9G0 manual design-review package: `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
- Current N9G0 full-matrix design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_LEGSA_9F_FGO_EKF_DESIGN_PACKAGE`.
- Current N9G0 export-clean design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_EXPORT_CLEAN_DESIGN_PACKAGE`.
- Current N9G1A/N9G1B runtime root: `<BY2_N9B2_WINDOWS_ROOT>/N9G1A_TO_N9G1B_CONTEXT_LOCK_AND_LEGSA_9F_PHASE1_IMPLEMENTATION`.
- Current export-clean design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`.
- N9C0 consolidated precheck root: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>`.
- N9C0 active metrics source: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`.
- N9C0 active final-only metrics row count: 825.
- N9C1 consolidated figure generation readiness: passed.
- PR #52 remains open/unmerged unless the human explicitly approves otherwise.
- N9G0A Git boundary resolution completed: PR #52 head is synced to `9ceba928`.
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

N9G1B Phase 1 is candidate identity/config, provider/factor/logger schema, audit, and safety-gate work only. It does not provide active nine-factor FGO residual/Jacobian/cost rows and did not run solver, official evaluator, representative degradation, full matrix, random/degraded-input generation, figure generation, PR merge/closure, tag creation, or paper claims.

## Next Stage

```text
recommended_next_stage=fix_provider_or_factor_model
```

Planned sequence after human review:

```text
fix_provider_or_factor_model
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
ready_for_N9G1B_phase1_provider_factor_logger_normal_smoke=blocked_provider_or_factor_model
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
