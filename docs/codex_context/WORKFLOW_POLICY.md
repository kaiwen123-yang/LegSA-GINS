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

## Current N9G1A Boundary

`N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION` is context lock only.

Allowed:

- Approved tracked docs/context updates.
- Approved runtime report/matrix/summary outputs under `<BY2_N9B2_WINDOWS_ROOT>/N9G1A_TO_N9G1B_CONTEXT_LOCK_AND_LEGSA_9F_PHASE1_IMPLEMENTATION`.
- Read-only validation commands.
- Public Obsidian notes using aliases only, with private local paths confined to `99_LOCAL_PATHS.private.md`.

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
- staging, committing, pushing, checkout, reset, pull, or PR creation from the worker role.
- PR #52 merge, close, or tag creation.
- representative degradation or full-matrix validation during N9G1B.

## Current Decision

N9G1A may set:

```text
status=N9G1A_context_lock_complete
git_boundary_resolved=true
pr_52_head_synced_to=9ceba928
complete_nine_factor_FGO_claim=false
ready_for_N9G1B_phase1_provider_factor_logger_normal_smoke=human_decision_required
ready_for_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

It may recommend human review of N9G1A, then explicit N9G1B decision. It must not implement N9G1B or authorize PR #52 merge/tag/closure.
