# AGENTS.md - LegSA-GINS Multi-Agent Working Rules

## 0. Purpose

This repository is used for the LegSA-GINS project: a legged-robot GNSS/INS fusion system with Raw Doppler, source-aware weighting, Go2 proprioceptive observations, legged candidate FGO factors, no-feedback FGO, and FGO-feedback EKF joint filtering.

This file is the persistent project context for Codex multi-agent work. It must prevent repeated context loss, phase confusion, false plot completion, unsafe merges, unsupported claims, and accidental algorithm changes.

The project uses a supervised multi-agent workflow:

- supervisor
- planner
- worker
- reviewer
- human final decision

The human user is the final decision maker for merge, tag, branch deletion, PR closure, and stage transitions.

## 1. Required Multi-Agent Workflow

### 1.1 Supervisor

The supervisor coordinates the task, checks stage boundaries, spawns planner first, approves or rejects worker scope, spawns reviewer after worker finishes, and asks the human before any merge, tag, force push, PR closure, branch deletion, or stage transition.

The supervisor must prevent phase confusion:

- N8K: BY2 formal ablation and ablation plot audit.
- N8K2-N8K6: real plot materialization and plot audit repairs.
- N9A: BY2 normal clean full plot audit.
- N9B: BY2 full degradation matrix.
- N9B1D4: current technical pilot source for deterministic degradation preparation.
- N9B1E: current pilot visual/go-no-go source, passed with the C yaw caution.
- N9B2A/N9B2A1: full-matrix preparation sources.
- N9B2B: path lock stage; locks Windows plus WSL aliases and future by2-huitu output alias.
- N9B2B1: documentation/context update after path lock.
- N9B2C: batch0 smoke plan and optional execution precheck.
- N9B2D: batch0 normal parity smoke.
- N9B2E: batch1 deterministic execution after human approval.
- N9B2F/N9B2F1: batch1 deterministic execution and review.
- N9B2G through N9B2K1: batch2 position-noise review and batch3 position-spike pipeline.
- N9B2L through N9B2M1: batch4 yaw-noise parameter lock, execution, and review.
- N9B2N through N9B2Q1: batch5 core module-disable and batch6 mixed long-pipeline preparation.
- N9B2R: final_v23 external baseline degradation control.
- N9B2S: batch6 selected mixed case definition and parameter lock.
- N9B2T0 through N9C0: batch6 mixed execution, review, and global staged consolidation precheck.
- N9C0A: documentation/context update after global consolidation precheck.
- N9C1: next planned consolidated figure generation stage; not yet run.
- N9C: degradation plotting, case review, and consolidated figure package stages.
- N9D: mathematical / evaluation / filter construction full-chain audit.
- N9E: BY2 paper-level packaging.
- N9F0_TO_N9F2: active nine-factor FGO legged design materialization and context sync; design/package stage only, no representative runs.
- N9F6A_TO_N9F7: source-code forensic audit and active FGO/legged completion review; Step 1 passed from source evidence, Step 2 took design-package-only Path C with no implementation or runs.
- N9F7A_TO_N9G0: Git/PR boundary lock and manual LegSA_9F_FGO_EKF design review; design package complete, implementation not started.
- N9G0A: Git boundary resolution completed; PR #52 head is synced to `9ceba928`.
- N9G1A: current context-lock stage before LegSA_9F_FGO_EKF implementation; documentation and audit reports only.
- N9G1B: planned Phase 1 provider/factor/logger/normal-smoke stage only after approval; no representative degradation or full matrix.
- N9G1C-E: current provider contract resolution, active backend audit, logger connection, and normal-smoke gate; normal smoke blocked by active backend.
- BY3A0_TO_BY3E: current BY3 normal-generalization and BY2 degradation report reorganization stage; BY3A0/A/B are complete, BY3C generated candidate inputs with provider blockers, BY3D/E solver/evaluator execution is blocked, and BY2T/BY2F summaries/archive were generated copy-only.
- BY3A1: current BY3-vs-BY2 parity and provider-gate repair stage; BY3 candidate inputs were repaired to BY2-compatible runtime schemas, BY3 Go2 priors were materialized, Raw Doppler and same-case feedback remain blocked, and solvers/evaluators were not run.
- BY3A2: current historical WSL pipeline recovery and runner-gate repair stage; historical BY2 Raw Doppler/Go2/single/final_v23/feedback chains were recovered, BY3 UBX/RAWX rebuild and accepted Raw Doppler provider materialization succeeded, same-case selected feedback remains blocked, and solvers/evaluators were not run.

### 1.2 Planner

Planner is read-only. It inspects branch, PR, git status, reports, docs, runtime roots, and risks; creates an execution plan; identifies required files, expected outputs, blockers, validation commands, and forbidden actions; and never edits files, creates runtime outputs, or commits.

### 1.3 Worker

Worker executes only the supervisor-approved plan. It edits only approved tracked files, creates runtime reports only in approved runtime folders, never commits raw data or generated artifacts, never changes algorithms unless explicitly approved, never tunes using trace/final_v23, and reports exactly what was done.

### 1.4 Reviewer

Reviewer is read-only. It reviews git diff, checks hard boundaries, checks runtime artifacts were not committed, checks no local path leaks exist, checks claim boundaries, verifies reports match actual outputs, and never edits files.

### 1.5 Human

The human user decides whether to merge, tag, close PRs, delete branches, proceed to the next stage, or authorize N9B2 execution. No agent may bypass the human final decision.

## 2. Global Hard Boundaries

Unless explicitly requested by the human, never do the following:

- Do not merge PR #21 or PR #52.
- Do not close PR #21 or PR #52.
- Do not delete remote branches.
- Do not force push.
- Do not stage, commit, push, merge, tag, or create PRs from worker/reviewer roles.
- Do not commit raw data or `by2.txt`.
- Do not commit NAV / STD / EVAL_NAV / RUN_MANIFEST runtime outputs.
- Do not commit generated figures.
- Do not commit `FGO_FEEDBACK_OBSERVATIONS.csv`.
- Do not commit `FGO_SMOOTHED_NAV.csv`.
- Do not commit `FGO_FACTOR_TABLE.csv`.
- Do not commit generated degradation CSV / summary / case review runtime files.
- Do not write local absolute paths into tracked docs/config/scripts.
- Do not edit `docs/codex_context/DATA_PATHS.local.md` unless explicitly requested.
- Do not modify `<WSL_ALGO_REPO>`.
- Do not run git add / commit / checkout / reset / pull / push inside `<WSL_ALGO_REPO>`.
- Do not compile reference/final_v23 itself.
- Do not use trace as solver input.
- Do not use final_v23 output as solver input.
- Do not tune using trace or final_v23.
- Do not perform output-only correction.
- Do not directly overwrite EKF NAV with FGO output.
- Do not delete bad epochs to pass metrics.
- Do not make paper performance claims unless explicitly approved after multi-dataset evidence.
- Do not claim outperform final_v23.
- Do not treat Go2 position, velocity, contact, or yaw as truth.
- Do not treat GNSS source observations as algorithm estimates.
- Do not treat placeholder PNG generation as successful plotting.
- Do not run more N9B2 execution unless the human defines a new follow-up.
- Do not run N9C1 figure generation until the human explicitly approves N9C1.
- Do not run solvers, evaluators, random generation, degraded-input generation, degradation matrices, or figures during context-only stages such as N9C0A.

## 3. Path And Output Policy

Tracked docs must use aliases only:

- `<WINDOWS_AUDIT_ROOT>`
- `<WSL_AUDIT_ROOT>`
- `<WSL_ALGO_REPO>`
- `<BY2_N9B2_WINDOWS_ROOT>`
- `<BY2_N9B2_WSL_ROOT>`
- `<BY2_N9B2_FULL_MATRIX_ROOT>`
- `<BY2_N9B2_DEFERRED_EXT4_ROOT>`
- `<N9C0_CONSOLIDATED_PRECHECK_ROOT>`
- `<FINALV23_EXTERNAL_BASELINE_ROOT>`

Actual local absolute paths belong only in ignored `docs/codex_context/DATA_PATHS.local.md`.

N9B2B locks the Windows and WSL path aliases and the current BY2/N9 runtime alias root. Future BY2/N9 outputs must use the `BY2_N9B2_*` aliases. N9C0 consolidated precheck artifacts are represented by `<N9C0_CONSOLIDATED_PRECHECK_ROOT>`, under `<BY2_N9B2_FULL_MATRIX_ROOT>`. The old Chinese output root is read-only historical evidence, not the active output root. Native Ubuntu migration is deferred.

Runtime outputs remain untracked. The N9C0A runtime root is represented in tracked docs only by the alias `<BY2_N9B2_WINDOWS_ROOT>/N9C0A_CONTEXT_UPDATE_AFTER_GLOBAL_CONSOLIDATION`.
The N9F6A/N9F7 runtime root is represented in tracked docs only by the alias `<BY2_N9B2_WINDOWS_ROOT>/N9F6A_TO_N9F7_CODEBASE_FORENSIC_AUDIT_AND_ACTIVE_FGO_LEGGED_COMPLETION`.
The N9F7A/N9G0 runtime root is represented in tracked docs only by the alias `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
The N9G0 design package root is represented in tracked docs only by the alias `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_LEGSA_9F_FGO_EKF_DESIGN_PACKAGE`.
The N9G0 export-clean package root is represented in tracked docs only by the alias `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_EXPORT_CLEAN_DESIGN_PACKAGE`.
The N9G1A/N9G1B runtime root is represented in tracked docs only by the alias `<BY2_N9B2_WINDOWS_ROOT>/N9G1A_TO_N9G1B_CONTEXT_LOCK_AND_LEGSA_9F_PHASE1_IMPLEMENTATION`.
The N9G1C-E runtime root is represented in tracked docs only by the alias `<BY2_N9B2_WINDOWS_ROOT>/N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
The BY3A0_TO_BY3E runtime root is represented in tracked docs only by the alias `<BY3_STAGE_ROOT>`.
The BY3A1 runtime/audit root is represented in tracked docs only by the alias `<BY3A1_STAGE_ROOT>`.
The BY3A2 runtime/audit root is represented in tracked docs only by the alias `<BY3A2_STAGE_ROOT>`.
The BY3 full-matrix runtime root is represented in tracked docs only by the alias `<BY3_FULL_MATRIX_ROOT>`.
The BY3 receiver root is represented in tracked docs only by `<BY3_RECEIVER_ROOT>`.
The BY3 Go2 body/high-level source is represented in tracked docs only by `<BY3_GO2_BODY_SOURCE>`.
The BY2 degradation report archive source is represented in tracked docs only by `<BY2_DEGRADATION_ARCHIVE_ROOT>`.

## 4. Data Source Roles

### 4.1 Trace

Role: evaluation-only reference/truth after alignment.

Never: solver input, tuning source, algorithm estimate, feedback correction source.

### 4.2 GNSS Raw And Status

Role: source observations, GNSS observation quality, yaw observation, Raw Doppler source diagnostics.

Never: algorithm estimate, trajectory estimate, direct metric source.

### 4.3 `by2.txt`

Role: Go2 body/high-level source data, Go2 IMU/body state, Go2 velocity/contact/foot/mode/gait diagnostic source.

Never: truth or absolute pose reference.

### 4.4 Receiver IMU Data

Role: diagnostic source unless explicitly approved.

Never: replacement for Go2 body IMU without explicit review.

### 4.5 NAV / EVAL_NAV / STD / RUN_MANIFEST

Role: algorithm outputs, evaluation chain, plot source for estimates/errors/metrics/comparisons.

Trajectory, error, and metric plots must use verified algorithm outputs, not source observations. Final-only metrics rule: reported metrics must come from final algorithm output/evaluation files for the case under review, not intermediate source diagnostics.

Current active global metrics source after N9C0: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`. The N9C0 active final-only metrics table has 825 rows. Do not use superseded rows, `historical_nominal_none`, or source diagnostics for current claims.

### 4.6 final_v23 Output

Role: external reference comparison / sanity check only.

Never: solver input, tuning source, hidden target, or performance-claim basis by itself.

## 5. Runner Rules

- Formal execution must use `legsa_v23_port_core_demo` plus `by2_algorithm_runner`.
- `legsa_gins --run-filter-csv` is diagnostic only.
- `selected_feedback` requires same-case feedback.
- Clean feedback cannot be reused for degraded cases.
- EVAL_NAV feedback generation uses state/estimate columns only.
- EVAL_NAV feedback generation must not use trace/error feedback corrections.
- No additional N9B2 execution is allowed unless a later stage explicitly approves it.
- N9C1 is figure generation and package preparation only; it is not paper-claim authorization.

## 6. Baseline Roles

- `single_antenna_gnss1_status_KF_GINS`: GNSS1-status baseline, not raw GNSS.
- `pure_INS_reference_initialized`: fixed/reference baseline.
- `final_v23_dual_antenna_EKF`: `external_reference_baseline` only.
- `true_no_feedback_FGO`: diagnostic unless full comparable output exists.

## 7. Matrix Cautions

- `B_gnss_downsample_2Hz` is invalid and superseded.
- Ratio downsample cases `every2`, `every5`, and `every10` are the active downsample family.
- `C_position_noise` has a yaw caution.
- `H_dual_yaw_noise` has a single-seed caveat.
- C and H require multi-seed treatment in N9B2.
- D position spike multi-seed is recommended.
- Superseded rows must never be used for active conclusions.

## 8. Current Route

Current completed route:

- N9A normal clean completed.
- N9B0, N9B0A, N9B0A1, N9B0A2 completed.
- N9B0B and N9B0C completed.
- N9B1A and N9B1A1 completed.
- N9B1C through N9B1G2 completed.
- N9B1D through N9B1D4 completed.
- N9B1E passed with C yaw caution.
- N9B2A completed.
- N9B2A1 completed.
- N9B2B completed.
- N9B2B1 completed.
- Batch 0 normal smoke completed.
- Batch 1 deterministic completed.
- Batch 2 position noise completed.
- Batch 3 position spike completed.
- Batch 4 yaw noise completed.
- Batch 5 core module-disable completed; module-stress remains deferred.
- Batch 6 selected mixed cases completed.
- final_v23 external baseline completed and integrated.
- N9C0 global staged consolidation precheck completed.
- N9E active nine-factor FGO/legged logger review completed with the logging-blocked decision.
- N9E decision: `complete_nine_factor_FGO_claim=false`; current `LegSA_full_EKF` lacks accepted row-level active FGO residual/cost evidence for all nine factors.
- N9F0_TO_N9F2 active nine-factor FGO legged design materialization and context sync completed.
- N9F6A source-code forensic audit from zero completed and passed reviewer gate.
- N9F7 took Path C only: data-pipeline / substantial algorithm design package; no implementation, solver, evaluator, representative run, full matrix, replot, or figure generation.
- N9F7A Git boundary audit completed: historical publish block documented the existing non-doc ahead commit before human resolution.
- N9G0 manual `LegSA_9F_FGO_EKF` design review completed as design only: algorithm identity, state/window, nine-factor, matrix/residual, provider, logger, roadmap, validation, and risk packages exist.
- N9G0A Git boundary resolution completed: PR #52 head is synced to `9ceba928`; PR #52 remains open/unmerged unless the human explicitly approves merge/closure/tag actions.
- N9G1 is split into `N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION` and later `N9G1B_PHASE1_PROVIDER_FACTOR_LOGGER_NORMAL_SMOKE_ONLY`.
- N9G1A context lock passed reviewer gate and was pushed to PR #52 at `f1e80f1`.
- N9G1B Phase 1 created the separate `LegSA_9F_FGO_EKF` candidate ID, runner/config boundary, provider/factor audit helper, logger schemas, safety gate, and runtime reports.
- N9G1B normal smoke was not run because provider contracts are blocked, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled.
- N9G1C-E resolved the locked normal clean source and core providers for `LegSA_9F_FGO_EKF`; provider contracts are partial accepted.
- N9G1C-E found the active nine-factor FGO backend still unavailable and candidate solver execution still disabled; normal smoke was not run.
- Current operational source of truth: `N9C0_GLOBAL_STAGED_N9B2_CONSOLIDATION_PRECHECK`.
- Current implementation/context stage: `N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
- Current BY3/reporting stage: `BY3A2_HISTORICAL_WSL_PIPELINE_RECOVERY_AND_RUNNER_GATE_REPAIR`; historical BY2 WSL chains were recovered, BY3 Raw Doppler and Go2 priors are materialized, baseline handoff configs are available for review, but same-case selected feedback remains blocked.
- Recommended BY3 next stage: `repair_BY3_stage1_feedback_chain`.
- Recommended active-FGO next stage remains: `implement_active_fgo_backend_or_reframe_scope`.

No full monolithic N9B2 was run. Do not run more N9B2 execution unless the human defines a new follow-up. N9C1 consolidated figure generation was ready after N9C0, but N9F evidence review now requires human review of the LegSA active nine-factor FGO implementation plan before representative active nine-factor FGO runs.

## 9. Claim Boundary

Allowed now:

- BY2 FGO-feedback EKF joint filter engineering chain has been validated.
- FGO feedback enters EKF as a controlled update.
- No output substitution, no direct NAV overwrite, no future-data feedback.
- Raw Doppler EKF is active.
- Raw Doppler FGO is active but low marginal value in clean BY2.
- Go2 proprioceptive joint factor is active.
- Legged candidate factors are activated in no-feedback FGO.
- N9B pilot/preparation evidence exists through N9B2B, with cautions recorded above.
- N9B staged execution is complete through N9C0 global consolidated precheck.
- N9C0 active final-only metrics table exists with 825 rows.
- N9C1 consolidated figure generation readiness passed.
- N9E may be cited only as a logging-blocked evidence review and Obsidian sync; it does not support a complete active nine-factor FGO claim.
- N9F design package is complete and concludes that current evidence requires a new active nine-factor FGO algorithm design.
- N9F6A source audit may state that robot kinematics/contact/legged modeling exists in provider, diagnostic, offline no-feedback, and candidate factor code, while active `LegSA_full_EKF` only uses provider-dependent Go2 weak attitude / horizontal velocity EKF updates and selected-feedback EKF pseudo-measurements.
- N9F7 may state that `LegSA_9F_FGO_EKF` still requires a separate active FGO window/factor graph, provider contracts, and row-level residual/Jacobian/cost logging before smoke or representative validation.
- N9G0 may state that a manual design review package exists for a future, separate `LegSA_9F_FGO_EKF` candidate.
- N9G0 may state that `LegSA_full_EKF` remains the verified EKF/feedback algorithm and is not relabeled.
- N9G0A may state that the Git boundary was resolved and PR #52 head is synced to `9ceba928`; merge/closure/tag actions still require explicit human approval.
- N9G1A may state that N9G1 was split into context lock and a later limited Phase 1 implementation/smoke stage.
- N9G1B may state that the separate `LegSA_9F_FGO_EKF` candidate identity/config, provider/factor audit helper, logger schemas, and safety gate exist.
- N9G1B may state that normal smoke was not run because provider/factor contracts and the active nine-factor FGO backend are blocked.
- N9G1C-E may state that locked normal and core providers are resolved with partial provider acceptance.
- N9G1C-E may state that active backend and solver execution remain blocked and normal smoke was not run.
- BY3A0_TO_BY3E may state that BY3A0 context lock, BY3A inventory/body IMU audit, BY3B alignment, BY3C candidate input generation, BY2T text summaries, and BY2F copy-only figure archive are complete.
- BY3A0_TO_BY3E may state that BY3D/E were not executed because BY3 raw Doppler/Go2 prior/same-case feedback, single-baseline runner handoff, and final_v23 external-baseline input gates were not satisfied.
- BY3A1 may state that BY3A0 candidate inputs failed BY2 parity in delimiter/header, IMU column count, single-baseline schema, and original time-normalization policy.
- BY3A1 may state that repaired BY3 IMU, dual-GNSS, and single-GNSS1 inputs now match BY2 runtime file conventions, and that BY3 Go2 attitude/horizontal/joint priors were materialized from the BY3 Go2 body source.
- BY3A1 may state that BY3 Raw Doppler remains blocked under the accepted BY2 RTKLIB/RINEX provider logic, same-case selected feedback remains blocked until a real BY3 stage1 solver/evaluator exists, and no solver/evaluator/figure/degradation run was performed.
- BY3A2 may state that historical BY2 WSL processing chains were recovered and indexed, including N5A/N5B Raw Doppler, N7C6 Go2 priors, R4J single-baseline handoff, final_v23 external-baseline handoff, and selected-feedback same-case policy.
- BY3A2 may state that BY3 raw receiver CSVs rebuild UBX/RAWX evidence and that accepted Raw Doppler provider materialization succeeded only when backed by fresh BY3A2 RINEX/nav/provider factor reports.
- BY3A2 may state that no BY3 solver, official evaluator, degradation matrix, metric figure generation, selected-feedback generation, or paper claim was performed.
- N9G2 may be described as the later representative validation stage.
- N9G3/N9G4 may be described as later full matrix/replot/report stages if applicable.
- `LegSA_full_EKF` is not accepted as active nine-factor FGO and must not be relabeled as such.

Forbidden now:

- paper performance improvement claim.
- outperform final_v23 claim.
- Go2 truth claim.
- FGO replaces EKF claim.
- trace/final_v23 tuning claim.
- source observations as algorithm estimates.
- placeholder plots as real figures.
- paper claims before N9C visual review and N9D claim-boundary review.
- using superseded rows, `historical_nominal_none`, or `B_gnss_downsample_2Hz` for active conclusions.
- automatic PR #52 merge/tag authorization.
- representative active nine-factor FGO degradation/full-matrix runs during N9G1A or N9G1B.
- treating N9G1B schema/gate outputs as active nine-factor FGO residual/Jacobian/cost evidence.
- treating N9G1C-E provider resolution as active nine-factor FGO residual/Jacobian/cost evidence.
- treating N9G1E as normal-smoke pass evidence.
- treating the N9F6A/N9F7 design package as active solver implementation.
- treating the N9G0 design package as implementation or active factor evidence.
- treating PR #52 head sync as merge, tag, or closure authorization.
- treating provider/update counts or historical candidate no-feedback rows as current active nine-factor FGO residual/cost evidence.
- treating BY3 source inventory, BY3B alignment reports, or BY3C candidate inputs as BY3 solver/evaluator performance evidence.
- treating BY3A1 repaired input files or materialized BY3 Go2 priors as BY3 solver/evaluator performance evidence.
- treating BY3A2 historical pipeline recovery, UBX/RAWX rebuild evidence, or baseline handoff configs as BY3 solver/evaluator performance evidence.
- claiming BY3 degradation/full-matrix completion before explicit BY3 execution approval.

## 10. Historical N9C0A Decision Lock

N9C0A was documentation/context update only. This historical lock remains for provenance and does not supersede the current N9F decision lock.

Expected decision if validation passes:

```text
status=N9C0A_context_update_after_global_consolidation_complete
ready_for_N9C1_consolidated_figure_generation=true
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=human_review_N9C0A_then_N9C1_consolidated_figure_generation
```

## 11. N9F Decision Lock

N9F0_TO_N9F2 is design materialization and context sync only. It does not authorize solver execution, evaluator execution, degradation generation, figure generation, representative active-nine-factor runs, paper claims, or relabeling `LegSA_full_EKF` as active nine-factor FGO.

Expected decision if validation passes:

```text
status=N9F_legsa_9f_design_package_complete
ready_for_implementation_review=true
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=N9F6_HUMAN_REVIEW_LEGSA_9F_IMPLEMENTATION_PLAN
```

## 12. N9F6A/N9F7 Decision Lock

N9F6A_TO_N9F7 completed a source-code forensic audit and then followed Path C only. It does not authorize code implementation, solver execution, evaluator execution, degradation generation, representative validation, full matrix execution, figure generation, paper claims, or relabeling `LegSA_full_EKF` as active nine-factor FGO.

Expected decision if validation passes:

```text
status=N9F7_substantial_algorithm_design_required
ready_for_algorithm_design_review=true
ready_for_implementation_review=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=manual_algorithm_design_review
```

## 13. N9F7A/N9G0 Decision Lock

N9F7A_TO_N9G0 completed a Git boundary audit and manual `LegSA_9F_FGO_EKF` design review. It does not authorize implementation, solver execution, evaluator execution, random generation, degraded-input generation, N9B2 execution, representative validation, full matrix execution, figure generation, paper claims, PR #52 merge, PR #52 closure, or tag creation.

This lock is historical after N9G0A. N9G0A resolved the Git boundary and synced PR #52 head to `9ceba928`; it did not authorize PR merge, PR closure, tag creation, paper claims, representative validation, or full matrix execution.

Expected decision if validation passes:

```text
status=N9G0_publish_blocked_by_git_boundary
design_review_complete=true
ready_for_N9G1_phase1_implementation=human_decision_required
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=resolve_git_boundary
```

## 14. N9G1A Decision Lock

N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION is context lock only. It records that N9G0A resolved the Git boundary and PR #52 head is synced to `9ceba928`. N9G1A by itself does not authorize implementation, solver execution, evaluator execution, random generation, degraded-input generation, representative validation, full matrix execution, figure generation, paper claims, PR #52 merge, PR #52 closure, or tag creation. N9G1B may start only when a human request explicitly authorizes it and the N9G1A reviewer gate passes.

Expected decision if validation passes:

```text
status=N9G1A_context_lock_complete
git_boundary_resolved=true
pr_52_head_synced_to=9ceba928
n9g1_split=N9G1A_context_lock_then_N9G1B_phase1_provider_factor_logger_normal_smoke_only
legsa_full_ekf_role=current_verified_EKF_feedback_algorithm
legsa_9f_fgo_ekf_role=separate_new_candidate
complete_nine_factor_FGO_claim=false
ready_for_N9G1B_phase1_provider_factor_logger_normal_smoke=human_decision_required
ready_for_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=human_review_N9G1A_then_decide_N9G1B
```

## 15. N9G1B Decision Lock

N9G1B_PHASE1_PROVIDER_FACTOR_LOGGER_NORMAL_SMOKE_ONLY created a separate `LegSA_9F_FGO_EKF` candidate identity/config boundary, provider/factor audit helper, active-FGO logger schema, legged diagnostic logger schema, and normal-smoke safety gate. It does not authorize representative validation, full matrix execution, figure generation, paper claims, PR #52 merge, PR #52 closure, or tag creation.

N9G1B did not run normal smoke because the safety gate blocked execution: provider contracts are not ready for active factors, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled. No active nine-factor FGO residual/Jacobian/cost rows were produced.

Expected decision if validation passes:

```text
status=N9G1_context_locked_provider_or_factor_blocked
legsa_9f_fgo_ekf_role=separate_new_candidate
normal_smoke_status=N9G1B_normal_smoke_not_run_blocked_by_gate
complete_nine_factor_FGO_claim=false
ready_for_N9G2_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=fix_provider_or_factor_model
```

## 16. N9G1C-E Decision Lock

N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE resolved the locked normal clean source and core provider contracts for the separate `LegSA_9F_FGO_EKF` candidate. It created provider, backend, factor wiring, logger, normal-smoke gate, validation, and decision reports. It does not authorize representative validation, full matrix execution, figure generation, paper claims, PR #52 merge, PR #52 closure, or tag creation.

N9G1C-E did not run normal smoke because the safety gate blocked execution: the active nine-factor FGO backend remains unavailable, candidate solver execution remains disabled, and no active factor wiring rows exist. No active nine-factor FGO residual/Jacobian/cost rows were produced.

Expected decision if validation passes:

```text
status=N9G1E_active_backend_blocked
provider_contract_decision=N9G1C_provider_contracts_partial_accepted
backend_decision=N9G1D_active_backend_blocked
normal_smoke_status=N9G1E_normal_smoke_not_run_blocked_by_gate
complete_nine_factor_FGO_claim=false
ready_for_N9G2_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=implement_active_fgo_backend_or_reframe_scope
```

## 17. BY3A0_TO_BY3E Decision Lock

BY3A0_TO_BY3E_GENERALIZATION_AND_BY2_DEGRADATION_REPORT_REORG completed as a partial normal-generalization gate and BY2 report/archive organization stage. It updated context boundaries, created BY3A inventory/body IMU audit reports, created BY3B alignment reports using the BY2 event-normalized kick policy without trace tuning, generated BY3C candidate Go2 IMU and GNSS status inputs, generated BY2T text summaries from existing active final-only metrics, and reorganized BY2 degradation figures as a copy-only archive.

BY3D and BY3E did not run because solver/evaluator gates remained blocked. No BY3 solver, official evaluator, degradation generation, full matrix, random generation, degraded-input generation, BY3 normal metric figure package, or paper claim was produced.

Expected decision if validation passes:

```text
status=BY3_solver_or_evaluator_blocked
by3a0_context_lock=complete
by3a_inventory=complete_read_only_inventory
by3b_alignment=BY3B_alignment_passed_no_trace_tuning
by3c_input_generation=partial_with_provider_blockers
by2t_text_summaries=complete_from_active_final_only_metrics
by2f_archive=complete_copy_only
ready_for_BY3_degradation_full_matrix=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_solver_or_evaluator
```

## 18. BY3A1 Decision Lock

BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR completed a strict BY3-vs-BY2 input-chain parity audit after BY3A0_TO_BY3E was blocked. It extracted the accepted BY2 input-chain reference, audited BY3A0 candidate inputs, found parity mismatches, repaired BY3 IMU/GNSS runtime file conventions where the BY2 policy was clear, materialized BY3 Go2 priors from the BY3 Go2 body source, and recorded remaining provider/feedback/runner blockers.

BY3A1 did not run BY3 solvers, official evaluators, artificial degradation, BY3 degradation matrix, figure generation from metrics, parameter retuning, trace tuning, final_v23 config mutation, or paper-claim work.

Expected decision if validation passes:

```text
status=BY3A1_provider_or_feedback_blocked
by2_reference_chain=extracted
by3_input_parity=partial_repaired
by3_repaired_inputs_ready=true
by3_go2_priors_materialized=true
by3_raw_doppler_provider=blocked_missing_accepted_BY2_RTKLIB_inputs
by3_same_case_feedback=blocked_until_stage1_solver_eval
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_providers_or_feedback
```

## 19. BY3A2 Decision Lock

BY3A2_HISTORICAL_WSL_PIPELINE_RECOVERY_AND_RUNNER_GATE_REPAIR completed a strict historical BY2 WSL pipeline recovery after BY3A1. It recovered the accepted BY2 Raw Doppler N5A/N5B chain, Go2 N7C6 prior chain, R4J single-baseline handoff, final_v23 external-baseline handoff, and selected-feedback same-case dependency policy.

BY3A2 did not run BY3 solvers, official evaluators, artificial degradation, BY3 degradation matrix, metric figure generation, parameter retuning, trace tuning, final_v23 algorithm mutation, selected-feedback generation, or paper-claim work.

Expected decision if validation passes:

```text
status=BY3A2_selected_feedback_blocked
historical_pipeline_recovered=true
by3_raw_ubx_rebuild=true
by3_raw_doppler_provider=materialized_accepted_N5A_N5B_chain
by3_go2_priors_validated=true
single_baseline_handoff=ready_for_review_not_run
finalv23_handoff=ready_for_review_not_run
by3_same_case_feedback=blocked_until_stage1_solver_eval
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_stage1_feedback_chain
```
