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
- Current stage: `N9B2B1_CONTEXT_UPDATE_AFTER_PATH_LOCK`.

Immediate next stages:

- `human_review_N9B2B1_then_N9B2C_batch0_smoke_plan`
- `N9B2C_BATCH0_SMOKE_PLAN_AND_OPTIONAL_EXECUTION_PRECHECK`
- `N9B2D_BATCH0_NORMAL_PARITY_SMOKE`
- `N9B2E_BATCH1_DETERMINISTIC_EXECUTION` after human approval
- N9B2 full execution only after staged batch reviews and explicit human approval

## 4. Readiness Flags

```text
ready_for_N9B2_preparation=true
ready_for_N9B2_environment_smoke=true
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

These flags do not authorize solver/evaluator/N9B2/random/degraded-input execution during N9B2B1.

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

## 6. Runner And Evaluation Rules

- Formal runner: `legsa_v23_port_core_demo` plus `by2_algorithm_runner`.
- `legsa_gins --run-filter-csv` is diagnostic only.
- `selected_feedback` requires same-case feedback.
- Clean feedback cannot be used for degraded cases.
- EVAL_NAV feedback generation uses state/estimate columns only.
- EVAL_NAV feedback generation must not use trace/error feedback corrections.
- Final-only metrics rule: metrics must come from final algorithm output/evaluation files for the same case.
- N9B2 execution is forbidden until explicit stage approval.

## 7. Baseline Roles

- `single_antenna_gnss1_status_KF_GINS`: GNSS1-status baseline, not raw GNSS.
- `pure_INS_reference_initialized`: fixed/reference baseline.
- `final_v23_dual_antenna_EKF`: reference/comparison only.
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

Forbidden now:

- paper performance improvement claim.
- outperform final_v23 claim.
- Go2 truth claim.
- FGO replaces EKF claim.
- trace/final_v23 tuning claim.
- source observations as algorithm estimates.
- placeholder plots as real figures.
- degradation generalization before full approved N9B/N10 evidence.
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

## 12. N9B2B1 Completion Criteria

N9B2B1 is complete only when:

- Approved tracked context docs are updated away from stale N9A_R0/R3/PR49/N9B-not-started current-state text.
- No local absolute path leaks exist in tracked docs touched by the stage or core context docs.
- `DATA_PATHS.local.md` remains ignored/local-only and is not staged.
- Runtime reports, matrices, and summaries are created under the approved runtime root.
- No solver/evaluator/N9B2/random/degraded-input/figure execution occurred.
- `ready_for_N9B2_preparation=true`.
- `ready_for_N9B2_environment_smoke=true`.
- `ready_for_N9B2_execution=false`.
- `ready_for_full_N9B_execution=false`.
- Recommended next stage is `human_review_N9B2B1_then_N9B2C_batch0_smoke_plan`.
