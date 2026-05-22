# Multi-Agent Runbook

## Standard Sequence

1. Supervisor reads core context.
2. Planner performs read-only analysis and outputs a plan.
3. Supervisor approves exact worker scope.
4. Worker executes only the approved scope.
5. Worker reports changed files, commands, output files, validation, risks, and reviewer focus.
6. Reviewer performs read-only audit.
7. Supervisor summarizes and asks the human before any Git write action or stage transition.

## Current N9B2B1 Worker Scope

Allowed:

- Update approved documentation/context files in the Windows audit workspace.
- Create approved runtime reports, matrices, and summaries under `<BY2_N9B2_WINDOWS_ROOT>/N9B2B1_CONTEXT_UPDATE_AFTER_PATH_LOCK`.
- Validate conflict markers, path leaks, ignored local path policy, runtime artifact tracking/staging, JSON/CSV parse, git diff check, git status, and changed tracked files.

Forbidden:

- WSL algorithm work.
- final_v23 edits.
- algorithm math, FGO factor math, or feedback policy edits.
- solver execution.
- evaluator execution.
- N9B2 execution.
- random generation.
- degraded-input generation.
- degradation matrix execution.
- figure generation.
- edits to `DATA_PATHS.local.md`.
- Git add/commit/push/PR/merge/tag/checkout/reset/pull.

## WSL Bridge Policy

No WSL commands are approved for N9B2B1. When a later stage explicitly approves WSL execution, use the supervised bridge policy and keep `<WSL_ALGO_REPO>` source read-only unless source edits are explicitly approved.

## Reviewer Focus For N9B2B1

- Current state is not stale N9A_R0/R3/PR49/N9B-not-started text except explicitly historical references.
- PR #52 remains open/unmerged and merge/tag is not authorized.
- Path aliases are used in tracked docs; no local absolute path leaks exist.
- `DATA_PATHS.local.md` was not edited, staged, or tracked.
- Runtime reports are under the approved N9B2B1 runtime root and remain untracked.
- No solver/evaluator/N9B2/random/degraded-input/figure execution occurred.
- Runner rules are preserved.
- Baseline roles are preserved.
- Matrix cautions are preserved.
- Readiness flags are correct:

```text
ready_for_N9B2_preparation=true
ready_for_N9B2_environment_smoke=true
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```
