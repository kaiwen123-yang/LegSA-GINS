# WORKFLOW_POLICY.md

## Required Sequence

1. Supervisor reads core context.
2. Planner performs read-only planning.
3. Supervisor approves narrow worker scope.
4. Worker executes only approved scope.
5. Worker reports changed files, commands, outputs, validation, risks, and reviewer focus.
6. Reviewer performs read-only review.
7. Supervisor summarizes and asks user before any Git write action.

## Role Rules

- Planner: no edits, no generated outputs, no Git writes.
- Worker: edits only approved Windows audit workspace files; no Git writes; no WSL source edits by default.
- Reviewer: no edits; checks diff/scope/paths/data roles/Git readiness.
- User: final authority for commit, push, PR, merge, and tag.

## Current N9A_R0 Boundary

Documentation/context rebuild only. No WSL algorithm work, no generated figures, no runtime artifacts, no degradation matrix, no merge/tag, no Git commit/push/PR.
