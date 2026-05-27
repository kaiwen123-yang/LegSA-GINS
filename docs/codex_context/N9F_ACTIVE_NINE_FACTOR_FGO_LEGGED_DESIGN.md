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

## N9F6A/N9F7 Source-Code Audit Update

N9F6A re-audited the real source code from zero and passed reviewer gate. The audit found:

- `LegSA_full_EKF` is defined as an EKF/update/feedback algorithm, not as `LegSA_9F_FGO_EKF`.
- C++ runtime evidence supports active EKF Raw Doppler, source-aware weighting, Go2 weak attitude / horizontal velocity updates, and selected-feedback EKF pseudo-measurement ingestion.
- Python FGO/legged code contains no-feedback, offline, diagnostic, provider, and candidate factor paths for robot kinematics/contact/legged modeling.
- No active production FGO window/factor graph with row-level residual, Jacobian, and cost logging for all nine factors was accepted.

N9F7 therefore followed Path C only:

```text
status=N9F7_substantial_algorithm_design_required
ready_for_algorithm_design_review=true
ready_for_implementation_review=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=manual_algorithm_design_review
```

The current N9F7 package is `<BY2_N9B2_WINDOWS_ROOT>/N9F6A_TO_N9F7_CODEBASE_FORENSIC_AUDIT_AND_ACTIVE_FGO_LEGGED_COMPLETION`. It is not solver evidence and must not be used as paper-claim support.

## N9F7A/N9G0 Manual Design Review Update

N9F7A locked the Git/PR boundary before implementation. It recorded that PR #52 remained open and unmerged and that the local branch had existing unpushed history, including a reporting/test code commit. N9G0A later resolved that Git boundary and synced PR #52 head to `9ceba928`; PR #52 still requires explicit human approval for merge, closure, or tag actions.

N9G0 completed a manual design review for a separate future `LegSA_9F_FGO_EKF` candidate. The design package defines:

- algorithm identity and separation from `LegSA_full_EKF`;
- EKF state and future FGO window policy;
- nine factor residual, Jacobian, covariance, gate, provider, logger, and minimum-test requirements;
- residual/matrix model including `r_i`, `J_i`, `R_i`, `W_i`, whitened residual, `r_i^T W_i r_i`, `J_i^T W_i J_i`, and `J_i^T W_i r_i`;
- provider contracts for GNSS, dual yaw, Raw Doppler, Go2, foot kinematics, yaw-rate, relative odometry, contact/slip, and feedback observations;
- logger schema, roadmap, validation protocol, and risk register.

N9G0 is still design-only:

```text
status=N9G0_design_review_complete_then_N9G0A_git_boundary_resolved
pr_52_head_synced_to=9ceba928
ready_for_N9G1_phase1_implementation=human_decision_required
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION
```

## N9G1A Context Lock Update

N9G1A splits N9G1 into a context-lock stage and a later implementation/smoke stage:

```text
N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION
N9G1B_PHASE1_PROVIDER_FACTOR_LOGGER_NORMAL_SMOKE_ONLY
N9G2_REPRESENTATIVE_VALIDATION
N9G3_FULL_MATRIX
N9G4_REPLOT_AND_REPORT
```

`LegSA_full_EKF` remains the current verified EKF/feedback algorithm. `LegSA_9F_FGO_EKF` is a separate new candidate. N9G1B, if approved later, is limited to Phase 1 provider/factor/logger/normal-smoke work. Representative degradation/full-matrix validation is deferred to N9G2 and later N9G3/N9G4 stages if applicable.

```text
complete_nine_factor_FGO_claim=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

## N9G1B Phase 1 Update

N9G1B created the separate `LegSA_9F_FGO_EKF` candidate identity/config boundary, provider/factor audit helper, active-FGO logger schema, legged diagnostic logger schema, and normal-smoke safety gate. It did not relabel `LegSA_full_EKF`.

Normal smoke was not run. The gate blocks execution because provider contracts are not ready for active factors, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled. No active nine-factor FGO residual/Jacobian/cost rows were produced.

```text
status=N9G1_context_locked_provider_or_factor_blocked
complete_nine_factor_FGO_claim=false
ready_for_N9G2_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=fix_provider_or_factor_model
```
