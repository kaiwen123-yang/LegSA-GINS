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
- N9C: degradation plotting and case review.
- N9D: mathematical / evaluation / filter construction full-chain audit.
- N9E: BY2 paper-level packaging.

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
- Do not run N9B2 execution until explicit stage approval.
- Do not run solvers, evaluators, random generation, degraded-input generation, degradation matrices, or figures during N9B2B1.

## 3. Path And Output Policy

Tracked docs must use aliases only:

- `<WINDOWS_AUDIT_ROOT>`
- `<WSL_AUDIT_ROOT>`
- `<WSL_ALGO_REPO>`
- `<BY2_N9B2_WINDOWS_ROOT>`
- `<BY2_N9B2_WSL_ROOT>`
- `<BY2_N9B2_FULL_MATRIX_ROOT>`
- `<BY2_N9B2_DEFERRED_EXT4_ROOT>`

Actual local absolute paths belong only in ignored `docs/codex_context/DATA_PATHS.local.md`.

N9B2B locks the Windows and WSL path aliases and the future by2-huitu output alias. Future BY2/N9B outputs must use the `BY2_N9B2_*` aliases. The old Chinese output root is read-only historical evidence, not the future output root. Native Ubuntu migration is deferred.

Runtime outputs remain untracked. The N9B2B1 runtime root is represented in tracked docs only by the alias `<BY2_N9B2_WINDOWS_ROOT>/N9B2B1_CONTEXT_UPDATE_AFTER_PATH_LOCK`.

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

### 4.6 final_v23 Output

Role: reference comparison / sanity check only.

Never: solver input, tuning source, hidden target, or performance-claim basis by itself.

## 5. Runner Rules

- Formal execution must use `legsa_v23_port_core_demo` plus `by2_algorithm_runner`.
- `legsa_gins --run-filter-csv` is diagnostic only.
- `selected_feedback` requires same-case feedback.
- Clean feedback cannot be reused for degraded cases.
- EVAL_NAV feedback generation uses state/estimate columns only.
- EVAL_NAV feedback generation must not use trace/error feedback corrections.
- No N9B2 execution is allowed until a later stage explicitly approves it.

## 6. Baseline Roles

- `single_antenna_gnss1_status_KF_GINS`: GNSS1-status baseline, not raw GNSS.
- `pure_INS_reference_initialized`: fixed/reference baseline.
- `final_v23_dual_antenna_EKF`: reference/comparison only.
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
- Current stage: `N9B2B1_CONTEXT_UPDATE_AFTER_PATH_LOCK`.
- Recommended next stage: `human_review_N9B2B1_then_N9B2C_batch0_smoke_plan`.

N9B2 full execution is not approved. N9B2 full execution may occur only after staged batch reviews and explicit human approval.

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

Forbidden now:

- paper performance improvement claim.
- outperform final_v23 claim.
- Go2 truth claim.
- FGO replaces EKF claim.
- trace/final_v23 tuning claim.
- source observations as algorithm estimates.
- placeholder plots as real figures.
- degradation generalization before N9B/N10 evidence.
- automatic PR #52 merge/tag authorization.

## 10. N9B2B1 Decision Lock

N9B2B1 is documentation/context update only.

Expected decision if validation passes:

```text
status=N9B2B1_context_update_after_path_lock_complete
ready_for_N9B2_preparation=true
ready_for_N9B2_environment_smoke=true
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=human_review_N9B2B1_then_N9B2C_batch0_smoke_plan
```
