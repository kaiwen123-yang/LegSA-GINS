# Multi-Agent Runbook

## Standard Sequence

1. Supervisor reads core context.
2. Planner performs read-only analysis and outputs a plan.
3. Supervisor approves exact worker scope.
4. Worker executes only the approved scope.
5. Worker reports changed files, commands, output files, validation, risks, and reviewer focus.
6. Reviewer performs read-only audit.
7. Supervisor summarizes and asks the human before any Git write action or stage transition.

## Current N9F7A/N9G0 Worker Scope

Allowed:

- Update approved documentation/context files in the Windows audit workspace.
- Create approved runtime reports, matrices, and summaries under `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
- Create manual design-review material under `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_LEGSA_9F_FGO_EKF_DESIGN_PACKAGE` and `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_EXPORT_CLEAN_DESIGN_PACKAGE`.
- Validate conflict markers, path leaks, ignored local path policy, runtime artifact tracking/staging, JSON/CSV parse, git diff check, git status, and changed tracked files.
- Commit tracked docs only after reviewer passes and supervisor policy allows it.

Forbidden:

- `LegSA_9F_FGO_EKF` implementation.
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
- pushing PR #52 while the existing non-doc ahead commit boundary remains unresolved.
- PR #52 merge, close, or tag creation.

## WSL Bridge Policy

No WSL execution is approved for N9F7A/N9G0 except read-only validation if explicitly needed. When a later stage explicitly approves WSL execution, use the supervised bridge policy and keep `<WSL_ALGO_REPO>` source read-only unless source edits are explicitly approved.

## Reviewer Focus For N9F7A/N9G0

- Current state is not stale N9C0A/N9F text except explicitly historical references.
- AGENTS, PLANS, README, PHASE_LOG, and `docs/codex_context` reflect N9F7A/N9G0 as current design-review state and `resolve_git_boundary` as next planned stage.
- PR #52 remains open/unmerged and merge/tag is not authorized.
- PR #52 push remains blocked until the existing non-doc ahead commit boundary is resolved.
- Path aliases are used in tracked docs; no local absolute path leaks exist.
- `DATA_PATHS.local.md` was not edited, staged, or tracked.
- Runtime reports are under the approved N9F7A/N9G0 runtime root and remain untracked.
- No implementation/solver/evaluator/N9B2/random/degraded-input/N9C1 figure execution occurred.
- Runner rules are preserved.
- Baseline roles are preserved.
- Matrix cautions are preserved.
- Readiness flags are correct:

```text
design_review_complete=true
ready_for_N9G1_phase1_implementation=human_decision_required
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```
