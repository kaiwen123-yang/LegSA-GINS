# Current State - After N9F Active Nine-Factor FGO Design Materialization

This file records the current verified operational state for the Windows audit workspace. It supersedes stale N8K, N9A, N9B2B1, and N9B-not-started text except where that text is explicitly historical.

## Verified Current State

- Current design/context stage: `N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`.
- Current operational source of truth for degradation metrics remains `N9C0_GLOBAL_STAGED_N9B2_CONSOLIDATION_PRECHECK`.
- Current active nine-factor FGO design source: `<BY2_N9B2_WINDOWS_ROOT>/N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`.
- Current export-clean design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`.
- N9C0 consolidated precheck root: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>`.
- N9C0 active metrics source: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`.
- N9C0 active final-only metrics row count: 825.
- N9C1 consolidated figure generation readiness: passed.
- PR #52 remains open/unmerged unless the human explicitly approves otherwise.
- N9E active nine-factor FGO/legged logger review completed with `complete_nine_factor_FGO_claim=false`.
- N9F decision: current evidence requires a new active nine-factor FGO algorithm design; `LegSA_full_EKF` is not accepted as active nine-factor FGO.

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

N9F0_TO_N9F2 is design materialization and context sync only. It does not authorize solver execution, official evaluator execution, N9B2 execution, representative active-nine-factor FGO runs, N9C1 figure generation, random generation, degraded-input generation, final paper figure generation, or paper claims.

## Next Stage

```text
recommended_next_stage=N9F6_HUMAN_REVIEW_LEGSA_9F_IMPLEMENTATION_PLAN
```

Planned sequence after human review:

```text
N9F6_HUMAN_REVIEW_LEGSA_9F_IMPLEMENTATION_PLAN
N9F_IMPLEMENTATION_REVIEW_AND_APPROVAL
N9C1_CONSOLIDATED_FIGURE_GENERATION
N9C2_FIGURE_VISUAL_REVIEW_AND_REPAIR
N9C3_CONSOLIDATED_CASE_REVIEW_AND_REPORT_PACKAGE
N9D_CLAIM_BOUNDARY_AND_PAPER_WRITING_READINESS_REVIEW
```

## Readiness Flags

```text
ready_for_implementation_review=true
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
