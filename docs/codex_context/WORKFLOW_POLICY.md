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

## Current N9F7A/N9G0 Boundary

`N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW` is Git-boundary and manual design-review only.

Allowed:

- Approved tracked docs/context updates.
- Approved runtime report/matrix/summary outputs under `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
- Manual design-review material under `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_LEGSA_9F_FGO_EKF_DESIGN_PACKAGE` and `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_EXPORT_CLEAN_DESIGN_PACKAGE`.
- Read-only validation commands.
- Commit tracked docs only after reviewer passes, if the supervisor policy allows it.

Forbidden:

- implementation of `LegSA_9F_FGO_EKF`.
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
- `obsidian_knowledge/` or `.obsidian/` staging.
- PR #52 push while the existing non-doc ahead commit boundary remains unresolved.
- PR #52 merge, close, or tag creation.

## Current Decision

N9G0 may set:

```text
design_review_complete=true
ready_for_N9G1_phase1_implementation=human_decision_required
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

It may recommend `resolve_git_boundary`, but it must not implement N9G1 or authorize PR #52 push/merge/tag without the required reviewer and human boundary decision.
