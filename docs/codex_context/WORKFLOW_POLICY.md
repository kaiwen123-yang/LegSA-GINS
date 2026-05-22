# WORKFLOW_POLICY.md

## Required Sequence

1. Supervisor reads core context.
2. Planner performs read-only planning.
3. Supervisor approves narrow worker scope.
4. Worker executes only approved scope.
5. Worker reports changed files, commands, outputs, validation, risks, and reviewer focus.
6. Reviewer performs read-only audit.
7. Supervisor summarizes and asks the human before any Git write action, PR change, merge, tag, or stage transition.

## Role Rules

- Planner: no edits, no generated outputs, no Git writes.
- Worker: edits only approved Windows audit workspace files; creates only approved runtime reports; no Git writes; no WSL source edits by default.
- Reviewer: no edits; checks diff, scope, paths, data roles, claim boundaries, runtime-artifact boundaries, and Git readiness.
- User: final authority for commit, push, PR, merge, close, tag, and stage approval.

## Current N9B2B1 Boundary

`N9B2B1_CONTEXT_UPDATE_AFTER_PATH_LOCK` is documentation/context update only.

Allowed:

- Approved tracked docs/context updates.
- Approved runtime report/matrix/summary outputs under `<BY2_N9B2_WINDOWS_ROOT>/N9B2B1_CONTEXT_UPDATE_AFTER_PATH_LOCK`.
- Read-only validation commands.

Forbidden:

- solver execution.
- evaluator execution.
- N9B2 execution.
- random generation.
- degraded-input generation.
- degradation matrix execution.
- figure generation.
- algorithm math, FGO factor math, feedback policy, final_v23, or `<WSL_ALGO_REPO>` edits.
- `docs/codex_context/DATA_PATHS.local.md` edits.
- Git add/commit/push/merge/tag/checkout/reset/pull.

## Current Decision

N9B2B1 may set:

```text
ready_for_N9B2_preparation=true
ready_for_N9B2_environment_smoke=true
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

It may recommend `human_review_N9B2B1_then_N9B2C_batch0_smoke_plan`, but it must not authorize N9B2 execution or PR #52 merge/tag.
