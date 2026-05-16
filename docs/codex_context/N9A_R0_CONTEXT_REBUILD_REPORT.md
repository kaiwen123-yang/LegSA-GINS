# N9A_R0 Context Rebuild Report

## Scope

Rebuild multi-agent documentation/context only in the Windows audit workspace.

## Implemented

- Rewrote top-level `AGENTS.md` and `PLANS.md` for current N9A_R0/N9A_R3 context.
- Added operational Markdown agent files for supervisor, planner, worker, and reviewer.
- Added current-state, stage-history, data-role, plot-taxonomy, degradation-plan, blocker-history, claim-boundary, runbook, and data-path template context files.
- Refreshed existing context policy files for consistency.

## Files Changed And Purpose

- `AGENTS.md`: top-level operating contract for current state, roles, forbidden actions, data roles, route, plot taxonomy, and claim boundary.
- `PLANS.md`: required planning template plus current route from N9A_R0 through N10C.
- `.codex/agents/supervisor.md`: supervisor responsibilities and handoff checklist.
- `.codex/agents/planner.md`: read-only planner scope and required outputs.
- `.codex/agents/worker.md`: approved-scope execution limits for documentation and future WSL bridge work.
- `.codex/agents/reviewer.md`: read-only review checks for diff, path leaks, artifacts, and claim boundary.
- `docs/codex_context/current_state.md`: verified current PR/stage/next-step state.
- `docs/codex_context/stage_history_N0_to_current.md`: N0 through N9A_R0 history summary.
- `docs/codex_context/data_source_roles.md`: trace/GNSS/by2/final_v23/NAV/EVAL/STD role boundaries.
- `docs/codex_context/plot_taxonomy_01_14.md`: unified plotting categories and permission matrix fields.
- `docs/codex_context/degradation_plan_N9B.md`: N9B plan only; no execution.
- `docs/codex_context/current_blocker_N8K_placeholder_plots.md`: historical N8K placeholder blocker and N8K2-N8K6 resolution.
- `docs/codex_context/claim_boundary.md`: allowed and forbidden claims.
- `docs/codex_context/multi_agent_runbook.md`: supervisor/planner/worker/reviewer operating sequence.
- `docs/codex_context/DATA_PATHS.template.md`: alias-only local path template.
- Existing policy docs: refreshed path, workflow, review, Git, and project context rules.

## Current State Preserved

- PR #48 is merged.
- PR #21 is open/unmerged and untouched.
- PR #49 is open/unmerged and must not be merged/tagged.
- N9A_R2 is incomplete/failure.
- N9A_R3 real output and frame alignment gate is next.
- N9B remains not started.

## Stage Boundaries Written

- N8K is not N9A.
- N8K did not run the full degradation matrix.
- N9B is the degradation-matrix stage and requires explicit user approval.
- N8K placeholder failures were real but are now historical after N8K2-N8K6 and PR #48 merge.
- N9A_R3 is a gate for real output lineage, frame/time alignment, metric sanity, and plot permission.
- No true algorithm output means no trajectory/error/compare figure permission.
- `applicable=True` cannot mean placeholder.
- Trace and final_v23 remain evaluation/reference only, never solver input or tuning source.
- FGO feedback EKF is an EKF pseudo-measurement/update path, not output substitution.
- PR #21 remains open/unmerged and untouched.

## Explicit Non-Actions During Context Editing

- No WSL algorithm work.
- No generated figures.
- No runtime artifacts.
- No degradation matrix.
- No merge or tag.
- No PR #21 or PR #49 action.
- No edits to `DATA_PATHS.local.md`.

Git add/commit/push/PR creation, if performed, is a separate publish step after validation. It must include only the documentation/context files listed in this report.

## Validation Performed

- Required files exist.
- `git diff --check` passed.
- Tracked context docs use aliases instead of local absolute machine paths; scanned tracked Markdown context excluding `DATA_PATHS.local.md`.
- No generated output directories were modified by this task.
- `DATA_PATHS.local.md` remains local-only and unchanged.
- `python3 -m pytest tests` was attempted but could not run because `python3` resolves to the WindowsApps stub and no `tests` directory exists in this checkout.
- `cmake -S cpp -B build/cpp` and `cmake --build build/cpp` were attempted but could not run because `cmake` is not installed in this shell and no `cpp` directory exists in this checkout.

## Reviewer Focus

- Confirm current state is not stale.
- Confirm agent files are narrow and operational.
- Confirm role/data/claim boundaries are consistent.
- Confirm no forbidden artifacts or Git operations occurred.

## Current Next Step

After this documentation context rebuild is reviewed and, if approved, published, the next technical stage is:

```text
N9A_R3_REAL_OUTPUT_AND_FRAME_ALIGNMENT_GATE
```

## Human Confirmation Still Required

- Whether to accept this documentation-only context rebuild.
- Whether to push/open a PR for the R0 context branch.
- Whether and when to start N9A_R3.
- No merge, tag, N9B start, or PR #21 action is authorized by this report.
