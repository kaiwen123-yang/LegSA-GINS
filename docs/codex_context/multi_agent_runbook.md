# Multi-Agent Runbook

## Standard Sequence

1. Supervisor reads core context.
2. Planner performs read-only analysis and outputs a plan.
3. Supervisor approves exact worker scope.
4. Worker executes only the approved scope.
5. Worker reports changed files, commands, validation, risks, and reviewer focus.
6. Reviewer performs read-only audit.
7. Supervisor summarizes and asks user before any Git write action.

## Current N9A_R0 Worker Scope

Allowed:

- Update documentation/context files in the Windows audit workspace.
- Create missing `.md` agent and `docs/codex_context` files.
- Validate file presence and scan for forbidden path/artifact leakage.

Forbidden:

- WSL algorithm work.
- generated figures.
- runtime artifacts.
- degradation matrix.
- edits to `DATA_PATHS.local.md`.
- Git add/commit/push/PR/merge/tag.

## WSL Bridge Policy

When WSL execution is approved, use only:

```powershell
.\scripts\run_wsl_legsa.ps1 -Task status -Distro Ubuntu-22.04
.\scripts\run_wsl_legsa.ps1 -Task check-output-roots -Distro Ubuntu-22.04
.\scripts\run_wsl_legsa.ps1 -Task bash -Command "<command>" -Distro Ubuntu-22.04
```

Do not edit `<WSL_ALGO_REPO>` source by default.

## Reviewer Focus For N9A_R0

- Current state is not stale.
- PR #48 is merged, not open.
- PR #21 and PR #49 remain untouched.
- No local absolute data paths were added to tracked docs.
- `DATA_PATHS.local.md` was not edited.
- Agent files are operational and narrow.
- N9A_R3 is next and `ready_for_N9B=false`.
