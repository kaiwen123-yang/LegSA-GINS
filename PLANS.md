# PLANS.md - LegSA-GINS Current Plan And Stage Roadmap

## 0. Purpose

This file records the active roadmap, completed stages, readiness flags, future gates, and multi-agent boundaries for the LegSA-GINS project.

This file is not a runtime report, algorithm output, paper claim, or place to store local absolute paths.

## 1. Project Identity

LegSA-GINS is a legged-robot GNSS/INS fusion project with source-backed EKF, Raw Doppler, source-aware weighting, Go2 proprioception, legged FGO candidate factors, no-feedback FGO, and FGO-feedback EKF joint filtering.

Current data focus has expanded to BY3 normal-generalization gates. BY3A0_TO_BY3E created source inventory, alignment reports, candidate BY3 normal inputs, BY2 degradation text summaries, and a copy-only BY2 figure archive. BY3A1 repaired BY3 input-chain parity where BY2 policy was clear and materialized BY3 Go2 priors. BY3A2 recovered the historical BY2 WSL Raw Doppler pipeline and materialized the BY3 Raw Doppler provider. BY3A3 repaired same-case selected feedback and completed the BY3 normal-only comparison for LegSA_full_EKF, the GNSS1-status single baseline, and final_v23 external baseline. BY3A4A then locked the lateral dual-antenna yaw geometry and seed0-9 memory, but found the BY3 yaw reference policy inconclusive. BY3 degradation/full-matrix execution is still not run and is blocked until manual dual-antenna yaw-policy review.

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
- N9E active nine-factor FGO/legged logger review completed with `complete_nine_factor_FGO_claim=false`.
- N9E outcome: logging blocked for current `LegSA_full_EKF`; no complete active nine-factor FGO claim.
- Current implementation/context stage: `N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
- Current BY3/reporting stage: `BY3A4A_LATERAL_DUAL_ANTENNA_YAW_REPAIR_SEED_EXPLANATION_AND_CONTEXT_MEMORY_LOCK`; lateral dual-antenna yaw geometry and seed0-9 memory locked, repaired yaw metrics not accepted.
- N9F design materialization completed: current evidence requires a new active nine-factor FGO algorithm design before representative runs.
- N9F6A source-code forensic audit completed from real Windows/WSL source evidence and passed reviewer gate.
- N9F7 followed Path C only: substantial algorithm design package required; no implementation, solver/evaluator execution, representative run, full matrix, or replot was performed.
- N9F7A Git boundary audit completed: the current branch has existing unpushed local history, including a reporting/test code commit that blocks automatic push until human review.
- N9G0 manual `LegSA_9F_FGO_EKF` design review completed as design only.
- N9G0A Git boundary resolution completed; PR #52 head is synced to `9ceba928`.
- N9G1 is split into `N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION` and later `N9G1B_PHASE1_PROVIDER_FACTOR_LOGGER_NORMAL_SMOKE_ONLY`.
- N9G1A context lock passed reviewer gate and was pushed to PR #52 at `f1e80f1`.
- N9G1B Phase 1 created the separate `LegSA_9F_FGO_EKF` candidate identity, runner/config boundary, provider/factor audit helper, logger schemas, safety gate, and runtime decision artifacts.
- N9G1B normal smoke was not run because the gate blocked it: provider contracts are not ready for active factors, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled.
- N9G1C-E resolved the locked normal source and core provider contracts for `LegSA_9F_FGO_EKF` as partial accepted provider evidence, but the active nine-factor FGO backend remains unavailable and candidate solver execution remains disabled.
- N9G1C-E normal smoke was not run because the gate blocked it: active backend unavailable, candidate solver disabled, and no active factor wiring rows.
- BY3A1 extracted the accepted BY2 input chain, repaired BY3 candidate IMU/GNSS files to BY2 runtime conventions, and materialized BY3 Go2 attitude/horizontal/joint priors.
- BY3A2 recovered the historical BY2 WSL Raw Doppler, Go2, single-baseline, final_v23, and selected-feedback chains; BY3 Raw Doppler is now materialized through the accepted N5A/N5B path, while BY3 same-case selected feedback remains unavailable under accepted gates.
- BY3A3 generated BY3 same-case selected feedback from stage1 official-eval state/estimate columns only, ran LegSA_full_EKF stage2, ran the GNSS1-status single baseline and final_v23 external baseline, and completed official normal evaluation without BY3 degradation or paper claims.
- BY3A4A recovered BY2 lateral yaw policy evidence as partial, explicitly encoded that the dual antennas are lateral/perpendicular to robot forward direction, audited +90/-90 and baseline-reversal candidates with existing BY3A3 outputs only, generated common-overlap metrics/diagnostic figures/seed0-9 explanation/context memory, and blocked repaired yaw metrics because no policy passed sanity without RMSE-only selection.
- `LegSA_full_EKF` remains the current verified EKF/feedback algorithm.
- `LegSA_9F_FGO_EKF` is a separate new candidate, not a relabeling of `LegSA_full_EKF`.

Immediate next stages:

- `manual_review_dual_antenna_yaw_policy`
- `BY3B_DEGRADATION_MATRIX_PLANNING_AND_PRECHECK` only after BY3 yaw-reference policy is resolved and approved
- `implement_active_fgo_backend_or_reframe_scope`
- `N9G2_REPRESENTATIVE_VALIDATION` later, only after active backend/provider/factor gaps are fixed and reviewed.
- `N9G3_FULL_MATRIX` and `N9G4_REPLOT_AND_REPORT` later only if applicable and explicitly approved.
- `N9C1_CONSOLIDATED_FIGURE_GENERATION` only after the correct human-approved route confirms the implementation/figure scope.
- `N9C2_FIGURE_VISUAL_REVIEW_AND_REPAIR`
- `N9C3_CONSOLIDATED_CASE_REVIEW_AND_REPORT_PACKAGE`
- `N9D_CLAIM_BOUNDARY_AND_PAPER_WRITING_READINESS_REVIEW`
- Paper-facing claims only after N9D review and explicit human approval.

Do not run more N9B2 execution unless the human defines a new follow-up. N9C1 is consolidated figure generation and package preparation; it is not paper-claim authorization.

## 4. Readiness Flags

```text
ready_for_N9C1_consolidated_figure_generation=true
ready_for_algorithm_design_review=true
ready_for_implementation_review=false
ready_for_N9G1A_context_lock=complete
ready_for_N9G1C_E_provider_backend_normal_smoke=blocked_active_backend
ready_for_BY3_degradation_matrix_planning=false
ready_for_BY3_solver_evaluator=normal_completed
ready_for_BY3_input_chain=repaired
ready_for_BY3_go2_priors=true
ready_for_BY3_raw_doppler_provider=true
ready_for_BY3_same_case_feedback=true
ready_for_BY3_yaw_policy=manual_review_required
ready_for_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

These flags do not authorize solver/evaluator/N9B2/random/degraded-input execution, paper claims, representative active-nine-factor FGO degradation/full-matrix runs, or N9C1 figure generation from N9G1B Phase 1.

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
N9F design/context outputs belong under `<BY2_N9B2_WINDOWS_ROOT>/N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`, with export-clean design material under `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`.
N9F6A/N9F7 source-audit and design-package outputs belong under `<BY2_N9B2_WINDOWS_ROOT>/N9F6A_TO_N9F7_CODEBASE_FORENSIC_AUDIT_AND_ACTIVE_FGO_LEGGED_COMPLETION`.
N9F7A/N9G0 Git-boundary and manual-design-review outputs belong under `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
N9G0 design packages belong under `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_LEGSA_9F_FGO_EKF_DESIGN_PACKAGE` and `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_EXPORT_CLEAN_DESIGN_PACKAGE`.
N9G1A/N9G1B context-lock and Phase 1 outputs belong under `<BY2_N9B2_WINDOWS_ROOT>/N9G1A_TO_N9G1B_CONTEXT_LOCK_AND_LEGSA_9F_PHASE1_IMPLEMENTATION`.
N9G1C-E provider/backend/logger gate outputs belong under `<BY2_N9B2_WINDOWS_ROOT>/N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
BY3A0_TO_BY3E outputs belong under `<BY3_STAGE_ROOT>`.
BY3A1 parity/provider-gate outputs belong under `<BY3A1_STAGE_ROOT>`.
BY3A4A yaw-repair/context-memory outputs belong under `<BY3A4A_STAGE_ROOT>` and the diagnostic runtime root `<BY3_FULL_MATRIX_ROOT>/BY3A4A_YAW_REPAIR`.
BY3 full-matrix placeholders belong under `<BY3_FULL_MATRIX_ROOT>` and do not mean BY3 full matrix was run.
BY3 receiver source is represented by `<BY3_RECEIVER_ROOT>`.
BY3 Go2 body/high-level source is represented by `<BY3_GO2_BODY_SOURCE>`.
BY2 degradation archive evidence is represented by `<BY2_DEGRADATION_ARCHIVE_ROOT>`.

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
- N9E logging-blocked review completed with no complete active nine-factor FGO claim.
- N9F design package is complete and requires a new active nine-factor FGO algorithm design.
- N9F6A source audit confirms robot kinematics/contact/legged modeling exists, but mainly as provider, diagnostic, offline no-feedback, or candidate factor code.
- N9F7 design package is complete and requires manual algorithm design review before implementation.
- N9G0 manual design review defines `LegSA_9F_FGO_EKF` as a separate future candidate, not an alias for `LegSA_full_EKF`.
- N9G0A resolved the Git boundary and PR #52 head is synced to `9ceba928`; merge, closure, and tag decisions still require explicit human approval.
- N9G1A locks the context before implementation and does not implement code or run solvers/evaluators/generators.
- N9G1B is limited to Phase 1 provider/factor/logger/normal-smoke work if later approved.
- Current evidence supports provider/update or candidate-only diagnostics, not a complete current active nine-factor FGO claim.

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
- relabeling `LegSA_full_EKF` as active nine-factor FGO.
- representative active-nine-factor FGO runs before human-approved implementation review.
- representative degradation or full-matrix validation in N9G1B.
- treating N9F6A/N9F7 design artifacts as active solver residual/cost evidence.
- treating N9G0 design artifacts as implemented solver evidence.
- treating PR #52 head sync as merge, closure, tag, or paper-claim authorization.

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

## 12. N9F Completion Criteria

N9F0_TO_N9F2 is complete only when:

- Runtime reports/matrices/summaries exist under `<BY2_N9B2_WINDOWS_ROOT>/N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`.
- Design and export-clean packages exist under `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_ACTIVE_FGO_LEGGED_DESIGN_AND_EVIDENCE` and `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`.
- Obsidian public notes use aliases only, with private paths confined to `99_LOCAL_PATHS.private.md`.
- No solver/evaluator/degradation/random/figure execution occurred.
- `ready_for_implementation_review=true`.
- `ready_for_paper_claims=false`.
- `ready_for_N9B2_execution=false`.
- `ready_for_full_N9B_execution=false`.
- Recommended next stage is `N9F6_HUMAN_REVIEW_LEGSA_9F_IMPLEMENTATION_PLAN`.

## 13. N9F6A/N9F7 Completion Criteria

N9F6A/N9F7 is complete only when:

- Source-root discovery, source inventory, runner mapping, EKF/FGO/legged/selected-feedback audits, evidence matrices, and decision reports exist under `<BY2_N9B2_WINDOWS_ROOT>/N9F6A_TO_N9F7_CODEBASE_FORENSIC_AUDIT_AND_ACTIVE_FGO_LEGGED_COMPLETION`.
- Step 1 reviewer passes before Step 2 begins.
- Step 2 follows only the Step 1 decision path.
- For the current Path C decision, no implementation, solver, evaluator, degradation generation, representative run, full matrix, or figure generation occurs.
- Robot kinematics/contact modeling is classified from source evidence as provider, diagnostic, offline no-feedback, candidate, EKF-update, or missing.
- Public docs and Obsidian notes use aliases only.
- `ready_for_algorithm_design_review=true`.
- `ready_for_implementation_review=false`.
- `ready_for_paper_claims=false`.
- `ready_for_N9B2_execution=false`.
- `ready_for_full_N9B_execution=false`.
- Recommended next stage is `manual_algorithm_design_review`.

## 14. N9F7A/N9G0 Completion Criteria

N9F7A/N9G0 is complete only when:

- Git status, ahead commit, PR #52, publish safety, protected-root, staging, and path-leak audits exist under `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
- Manual `LegSA_9F_FGO_EKF` design reports exist for algorithm identity, state/window, nine factors, matrix/residual model, provider contracts, logger schema, implementation roadmap, validation protocol, and risk register.
- `LegSA_full_EKF` remains the current verified EKF/feedback algorithm.
- `LegSA_9F_FGO_EKF` remains design-only until a later human-approved implementation stage.
- No implementation, solver, evaluator, random generation, degraded-input generation, N9B2 execution, representative validation, full matrix, figure generation, paper claim, PR merge, PR closure, or tag creation occurs.
- `ready_for_N9G1_phase1_implementation=human_decision_required`.
- `ready_for_paper_claims=false`.
- `ready_for_N9B2_execution=false`.
- `ready_for_full_N9B_execution=false`.
- Recommended next stage is `resolve_git_boundary`.

Historical supersession: N9G0A later resolved this Git boundary and synced PR #52 head to `9ceba928`. The historical `resolve_git_boundary` recommendation must not be read as current after N9G0A/N9G1A; current state and next-step guidance are in the N9G1A section and `docs/codex_context/current_state.md`.

## 15. Historical N9C0A Completion Criteria

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

## 16. N9G1A Completion Criteria

N9G1A is complete only when:

- Approved tracked context docs record N9G0A completion and PR #52 head sync to `9ceba928`.
- Approved tracked context docs record the N9G1 split into context lock and later Phase 1 provider/factor/logger/normal-smoke only.
- `LegSA_full_EKF` remains the current verified EKF/feedback algorithm.
- `LegSA_9F_FGO_EKF` remains a separate new candidate.
- Runtime reports, matrices, summaries, and validation records exist under `<BY2_N9B2_WINDOWS_ROOT>/N9G1A_TO_N9G1B_CONTEXT_LOCK_AND_LEGSA_9F_PHASE1_IMPLEMENTATION`.
- Public Obsidian notes use aliases only; private local paths are confined to `99_LOCAL_PATHS.private.md`.
- No implementation, solver execution, evaluator execution, generator execution, degradation generation, full matrix, figure generation, staging, commit, or push occurs.
- `complete_nine_factor_FGO_claim=false`.
- `ready_for_paper_claims=false`.
- `ready_for_representative_validation=false`.
- Recommended next stage is human review of N9G1A, then explicit decision on N9G1B.

N9G1A completion alone does not authorize implementation. N9G1B may start only when a human request explicitly authorizes it and the N9G1A reviewer gate passes.

## 17. BY3A0_TO_BY3E Completion Criteria

BY3A0_TO_BY3E is complete only when:

- tracked context docs use aliases only and record BY3 as normal-generalization gate work;
- `<BY3_STAGE_ROOT>` contains BY3A inventory/body IMU audit reports, BY3B alignment reports, BY3C candidate input generation reports, BY2T text summary reports, BY2F copy-only archive manifests, gate matrices, summaries, and validation manifests;
- `<BY3_FULL_MATRIX_ROOT>` records that BY3 degradation/full matrix was not run;
- public Obsidian BY3 notes use aliases only, while private local paths remain in an untracked private note;
- BY3D/E are marked blocked if solver/evaluator readiness is not genuinely established.

Completion does not authorize BY3 solver/evaluator execution, BY3 degradation/full matrix, figures, representative validation, paper claims, or final_v23/algorithm changes.

## 18. BY3A1 Completion Criteria

BY3A1 is complete only when:

- accepted BY2 input-chain references are extracted from current evidence;
- BY3A0 candidate inputs are audited against BY2 delimiter/header/schema/time policy;
- BY3 input repair is limited to BY2-compatible file conventions and no trace-tuned offset search;
- BY3 Go2 priors are materialized only from the BY3 Go2 body source and marked as non-truth observations;
- BY3 Raw Doppler provider and selected-feedback dependency are either materially generated from accepted logic or explicitly blocked;
- solver/evaluator execution remains blocked unless parity, provider, feedback, and runner gates all pass;
- no BY3 degradation matrix, artificial degradation, figure-from-metric package, parameter retuning, final_v23 mutation, or paper claim is produced;
- runtime outputs and Obsidian notes remain untracked.

Current BY3A1 decision:

```text
status=BY3A1_provider_or_feedback_blocked
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_providers_or_feedback
```

## 19. BY3A2 Completion Criteria

BY3A2 is complete only when:

- historical BY2 WSL chains for Raw Doppler, Go2 priors, single-baseline handoff, final_v23 handoff, and selected-feedback same-case dependency are recovered from real artifacts;
- BY3 Raw Doppler provider materialization uses the accepted N5A/N5B logic or records a concrete blocker;
- BY3 Go2 priors remain source observations, not truth;
- single-baseline and final_v23 handoffs are validated as runtime configs/commands only unless all solver gates pass;
- selected-feedback remains blocked unless a real same-case BY3 stage1 official EVAL_NAV exists;
- no BY3 degradation matrix, artificial degradation, parameter retuning, trace tuning, final_v23 algorithm change, fabricated output, metric figure package, or paper claim is produced;
- runtime outputs and Obsidian notes remain untracked.

Current BY3A2 decision:

```text
status=BY3A2_selected_feedback_blocked
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_stage1_feedback_chain
```
