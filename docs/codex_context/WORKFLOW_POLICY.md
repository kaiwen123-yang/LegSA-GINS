# WORKFLOW_POLICY.md

## Required Sequence

1. Supervisor reads core context and runtime evidence.
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

## Current N9C0A Boundary

`N9C0A_CONTEXT_UPDATE_AFTER_GLOBAL_CONSOLIDATION` is documentation/context update only.

Allowed:

- Approved tracked docs/context updates.
- Approved runtime report/matrix/summary outputs under `<BY2_N9B2_WINDOWS_ROOT>/N9C0A_CONTEXT_UPDATE_AFTER_GLOBAL_CONSOLIDATION`.
- Read-only validation commands.
- Commit and push tracked docs only after reviewer passes, if the supervisor policy allows it.

Forbidden:

- solver execution.
- official evaluator execution.
- N9B2 execution.
- N9C1 figure generation.
- random generation.
- degraded-input generation.
- final paper figure generation.
- paper claims.
- algorithm math, FGO factor math, feedback policy, final_v23, KF-GINS-Baseline, or `<WSL_ALGO_REPO>` edits.
- `docs/codex_context/DATA_PATHS.local.md` edits or staging.
- `by2-huitu/` staging.
- PR #52 merge, close, or tag creation.

## Current Decision

N9C0A may set:

```text
ready_for_N9C1_consolidated_figure_generation=true
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

It may recommend `human_review_N9C0A_then_N9C1_consolidated_figure_generation`, but it must not run N9C1 or authorize PR #52 merge/tag.
