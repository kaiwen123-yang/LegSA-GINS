# N9F Active Nine-Factor FGO Legged Design

N9F0_TO_N9F2 materialized the active nine-factor FGO design package and synced context boundaries.

## Decision

```text
status=N9F_legsa_9f_design_package_complete
ready_for_implementation_review=true
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=N9F6_HUMAN_REVIEW_LEGSA_9F_IMPLEMENTATION_PLAN
```

## Evidence Boundary

Evidence sources:

- `<BY2_N9B2_WINDOWS_ROOT>/N9E_ACTIVE_NINE_FACTOR_FGO_LEGGED_LOGGER_AND_OBSIDIAN_SYNC`
- `<BY2_N9B2_WINDOWS_ROOT>/N9C1F_TO_N9C3_FGO_LEGGED_EVIDENCE_REPAIR_AND_REPORT_PACKAGE`
- `<BY2_N9B2_WINDOWS_ROOT>/N9C0D_LEGSA_FULL_ALGORITHM_FULL_MATRIX_EXPANSION`

The current evidence does not prove all nine factors are active row-level FGO solver factors with residual, Jacobian, and cost logging in the current `LegSA_full_EKF` runtime. Provider/update counts and candidate/no-feedback rows are not sufficient for a complete active nine-factor FGO claim.

## Required Design Direction

- Define an active nine-factor FGO algorithm path distinct from `LegSA_full_EKF`.
- Add solver-visible row-level factor rows, residual time series, Jacobian/nonzero counts, and cost contribution logs for every active factor.
- Keep trace and final_v23 as evaluation/reference only.
- Keep Go2 position, velocity, contact, and yaw as observations or diagnostics, not truth.
- Block representative runs until human-approved implementation review.

## Runtime Package

- Runtime design package: `<BY2_N9B2_WINDOWS_ROOT>/N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`
- Export-clean design package: `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`

No solver, evaluator, degradation, random generation, representative active-nine-factor run, or figure generation is authorized by this design package.
