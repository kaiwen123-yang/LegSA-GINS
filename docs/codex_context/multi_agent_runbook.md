# Multi-Agent Runbook

## Standard Sequence

1. Supervisor reads core context.
2. Planner performs read-only analysis and outputs a plan.
3. Supervisor approves exact worker scope.
4. Worker executes only the approved scope.
5. Worker reports changed files, commands, output files, validation, risks, and reviewer focus.
6. Reviewer performs read-only audit.
7. Supervisor summarizes and asks the human before any Git write action or stage transition.

## Current N9G1C-E Worker Scope

Allowed:

- Update approved `LegSA_9F_FGO_EKF` provider/backend/logger gate helpers, focused tests, and documentation/context files in the Windows audit workspace.
- Create approved runtime reports, matrices, and summaries under `<BY2_N9B2_WINDOWS_ROOT>/N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
- Create public Obsidian notes with aliases only, with private local paths confined to `99_LOCAL_PATHS.private.md`.
- Validate conflict markers, path leaks, ignored local path policy, runtime artifact tracking/staging, JSON/CSV parse, git diff check, git status, and changed tracked files.

Forbidden:

- WSL algorithm work.
- final_v23 edits.
- KF-GINS-Baseline edits.
- algorithm math, FGO factor math, or feedback policy edits.
- solver execution.
- official evaluator execution.
- N9B2 execution.
- N9C1 figure generation.
- random generation.
- degraded-input generation.
- final paper figure generation.
- paper claims.
- edits to `DATA_PATHS.local.md`.
- staging `by2-huitu/`.
- staging `obsidian_knowledge/` or `.obsidian/`.
- staging, committing, pushing, checkout, reset, pull, PR creation, merge, or tag operations from the worker role.
- PR #52 merge, close, or tag creation.
- representative degradation or full-matrix validation during N9G1C-E.

## WSL Bridge Policy

No WSL solver/evaluator execution is approved for N9G1C-E when the normal-smoke gate is blocked. When a later stage explicitly approves WSL execution, use the supervised bridge policy and keep `<WSL_ALGO_REPO>` source read-only unless source edits are explicitly approved.

## Reviewer Focus For N9G1C-E

- Current state reflects N9G1C-E as locked normal/core provider resolution plus active-backend blocked normal-smoke gate.
- AGENTS, PLANS, README, PHASE_LOG, and `docs/codex_context` reflect N9G1C-E blocked-before-smoke status and N9G2 not-ready state.
- PR #52 remains open/unmerged and merge/tag is not authorized.
- PR #52 head sync is not treated as merge, closure, tag, or paper-claim authorization.
- Path aliases are used in tracked docs; no local absolute path leaks exist.
- `DATA_PATHS.local.md` was not edited, staged, or tracked.
- Runtime reports are under the approved N9G1C-E runtime root and remain untracked.
- Public Obsidian notes use aliases only; local paths are confined to `99_LOCAL_PATHS.private.md`.
- No solver/evaluator/generator/N9B2/random/degraded-input/N9C1 figure execution occurred.
- `LegSA_9F_FGO_EKF` is separate from `LegSA_full_EKF`; no relabeling occurred.
- No candidate-only factor is marked active without residual/Jacobian/cost rows.
- N9G2 is later representative validation; N9G3/N9G4 are later full matrix/replot/report if applicable.
- Runner rules are preserved.
- Baseline roles are preserved.
- Matrix cautions are preserved.
- Readiness flags are correct:

```text
status=N9G1E_active_backend_blocked
provider_contract_decision=N9G1C_provider_contracts_partial_accepted
normal_smoke_status=N9G1E_normal_smoke_not_run_blocked_by_gate
complete_nine_factor_FGO_claim=false
ready_for_N9G2_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```
