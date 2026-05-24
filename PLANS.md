# PLANS.md - LegSA-GINS Current Plan And Stage Roadmap

## 0. Purpose

This file records the active roadmap, completed stages, readiness flags, future gates, and multi-agent boundaries for the LegSA-GINS project.

This file is not a runtime report, algorithm output, paper claim, or place to store local absolute paths.

## 1. Project Identity

LegSA-GINS is a legged-robot GNSS/INS fusion project with source-backed EKF, Raw Doppler, source-aware weighting, Go2 proprioception, legged FGO candidate factors, no-feedback FGO, and FGO-feedback EKF joint filtering.

Current data focus remains BY2. Later generalization to BY3, indoor-outdoor transition, and poor-GNSS environments requires separate stages and evidence.

## 2. Global Working Principles

- Do not confuse source observations with algorithm outputs.
- Do not confuse evaluation reference with solver input.
- Do not confuse PNG existence with valid plotting.
- Do not confuse clean BY2 engineering validation with paper-level performance claims.
- Do not change algorithm code during reporting, context, or audit stages.
- Do not tune using trace or final_v23 output.
- Do not merge, tag, close PRs, delete branches, force push, stage, commit, or push without the correct role and explicit human approval.
- The human user is always the final decision maker.

## 3. Current Roadmap State

Completed or accepted for current planning:

- N9A normal clean completed.
- N9B0, N9B0A, N9B0A1, N9B0A2 completed.
- N9B0B and N9B0C completed.
- N9B1A and N9B1A1 completed.
- N9B1C through N9B1G2 completed.
- N9B1D through N9B1D4 completed.
- N9B1D4 is the current technical pilot source.
- N9B1E passed with the C yaw caution and is the current pilot visual/go-no-go source.
- N9B2A completed.
- N9B2A1 completed.
- N9B2A/N9B2A1 are the full-matrix preparation sources.
- N9B2B completed and locked Windows plus WSL aliases and the future by2-huitu output alias.
- N9B2B1 context update after path lock completed.
- Batch 0 normal smoke completed.
- Batch 1 deterministic completed.
- Batch 2 position noise completed.
- Batch 3 position spike completed.
- Batch 4 yaw noise completed.
- Batch 5 core module-disable completed; module-stress remains deferred.
- Batch 6 selected mixed cases completed.
- final_v23 external baseline completed and integrated.
- N9C0 global staged consolidation precheck completed.
- Current context-update stage: `N9C0A_CONTEXT_UPDATE_AFTER_GLOBAL_CONSOLIDATION`.

Immediate next stages:

- `human_review_N9C0A_then_N9C1_consolidated_figure_generation`
- `N9C1_CONSOLIDATED_FIGURE_GENERATION`
- `N9C2_FIGURE_VISUAL_REVIEW_AND_REPAIR`
- `N9C3_CONSOLIDATED_CASE_REVIEW_AND_REPORT_PACKAGE`
- `N9D_CLAIM_BOUNDARY_AND_PAPER_WRITING_READINESS_REVIEW`
- Paper-facing claims only after N9D review and explicit human approval.

Do not run more N9B2 execution unless the human defines a new follow-up. N9C1 is consolidated figure generation and package preparation; it is not paper-claim authorization.

## 4. Readiness Flags

```text
ready_for_N9C1_consolidated_figure_generation=true
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

These flags do not authorize solver/evaluator/N9B2/random/degraded-input execution, paper claims, or N9C1 figure generation during N9C0A.

## 5. Path And Runtime Policy

Tracked docs must use aliases only:

- `<WINDOWS_AUDIT_ROOT>`
- `<WSL_AUDIT_ROOT>`
- `<WSL_ALGO_REPO>`
- `<BY2_N9B2_WINDOWS_ROOT>`
- `<BY2_N9B2_WSL_ROOT>`
- `<BY2_N9B2_FULL_MATRIX_ROOT>`
- `<BY2_N9B2_DEFERRED_EXT4_ROOT>`

Actual local absolute paths belong only in ignored `docs/codex_context/DATA_PATHS.local.md`.

N9B2B locks the Windows and WSL path aliases and the future by2-huitu output alias. Future BY2/N9B outputs must use the `BY2_N9B2_*` aliases. Native Ubuntu migration is deferred. The old Chinese output root is read-only historical evidence.

Runtime outputs remain untracked. N9B2B1 runtime reports belong under `<BY2_N9B2_WINDOWS_ROOT>/N9B2B1_CONTEXT_UPDATE_AFTER_PATH_LOCK`.
N9C0A runtime reports belong under `<BY2_N9B2_WINDOWS_ROOT>/N9C0A_CONTEXT_UPDATE_AFTER_GLOBAL_CONSOLIDATION`. N9C0 consolidated precheck artifacts are represented by `<N9C0_CONSOLIDATED_PRECHECK_ROOT>` under `<BY2_N9B2_FULL_MATRIX_ROOT>`.

## 6. Runner And Evaluation Rules

- Formal runner: `legsa_v23_port_core_demo` plus `by2_algorithm_runner`.
- `legsa_gins --run-filter-csv` is diagnostic only.
- `selected_feedback` requires same-case feedback.
- Clean feedback cannot be used for degraded cases.
- EVAL_NAV feedback generation uses state/estimate columns only.
- EVAL_NAV feedback generation must not use trace/error feedback corrections.
- Final-only metrics rule: metrics must come from final algorithm output/evaluation files for the same case.
- Current active global metrics source after N9C0: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`.
- The N9C0 active final-only metrics table has 825 rows.
- Do not use superseded rows, `historical_nominal_none`, or `B_gnss_downsample_2Hz` for active conclusions.
- Additional N9B2 execution is forbidden until explicit stage approval.

## 7. Baseline Roles

- `single_antenna_gnss1_status_KF_GINS`: GNSS1-status baseline, not raw GNSS.
- `pure_INS_reference_initialized`: fixed/reference baseline.
- `final_v23_dual_antenna_EKF`: `external_reference_baseline` only.
- `true_no_feedback_FGO`: diagnostic unless full comparable output exists.

## 8. Matrix Cautions

- `B_gnss_downsample_2Hz` is invalid and superseded.
- Ratio downsample cases `every2`, `every5`, and `every10` are the active downsample family.
- `C_position_noise` has a yaw caution.
- `H_dual_yaw_noise` has a single-seed caveat.
- C and H require multi-seed treatment in N9B2.
- D position spike multi-seed is recommended.
- Superseded rows must never be used for active conclusions.

## 9. Claim Boundary

Allowed now:

- BY2 FGO-feedback EKF joint filter engineering chain has been validated.
- FGO feedback enters EKF as a controlled update.
- No output substitution, no direct NAV overwrite, no future-data feedback.
- Raw Doppler EKF is active.
- Raw Doppler FGO is active but low marginal value in clean BY2.
- Go2 proprioceptive joint factor is active.
- Legged candidate factors are activated in no-feedback FGO.
- N9B pilot/preparation evidence exists through N9B2B, with the recorded cautions.
- N9B staged execution is complete through N9C0 global consolidated precheck.
- N9C0 active final-only metrics table exists with 825 rows.
- N9C1 consolidated figure generation readiness passed.

Forbidden now:

- paper performance improvement claim.
- outperform final_v23 claim.
- Go2 truth claim.
- FGO replaces EKF claim.
- trace/final_v23 tuning claim.
- source observations as algorithm estimates.
- placeholder plots as real figures.
- paper claims before N9C visual review and N9D claim-boundary review.
- active conclusions from superseded rows, `historical_nominal_none`, or `B_gnss_downsample_2Hz`.
- automatic PR #52 merge/tag authorization.

## 10. Multi-Agent Workflow

Future work should use:

```text
supervisor -> planner -> worker -> reviewer -> human final decision
```

Planner is read-only. Worker executes only approved scope. Reviewer is read-only. Human decides merge/tag/PR/stage transitions.

## 11. Required Future Plan Format

Every future plan must include:

- Goal.
- Verified current state.
- Scope.
- Inputs.
- Outputs.
- Execution steps.
- Validation.
- Prohibited actions.
- Risks.
- Completion criteria.
- Final report requirements.

## 12. N9C0A Completion Criteria

N9C0A is complete only when:

- Approved tracked context docs are updated away from stale N8K/N9A/N9B2B1 current-state text.
- No local absolute path leaks exist in tracked docs touched by the stage or core context docs.
- `DATA_PATHS.local.md` remains ignored/local-only and is not staged.
- Runtime reports, matrices, and summaries are created under the approved runtime root.
- No solver/evaluator/N9B2/random/degraded-input/N9C1 figure execution occurred.
- `ready_for_N9C1_consolidated_figure_generation=true`.
- `ready_for_paper_claims=false`.
- `ready_for_N9B2_execution=false`.
- `ready_for_full_N9B_execution=false`.
- Recommended next stage is `human_review_N9C0A_then_N9C1_consolidated_figure_generation`.
