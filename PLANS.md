# PLANS.md - LegSA-GINS planning template

Every non-trivial LegSA-GINS task must be planned before execution and reviewed after execution. For this workspace, planner is read-only, worker follows the approved plan, and reviewer is read-only.

## Current Route

Verified current documentation stage:

```text
N9A_R0_MULTI_AGENT_CONTEXT_REBUILD
```

Current technical blocker after R0:

```text
N9A_R3_REAL_OUTPUT_AND_FRAME_ALIGNMENT_GATE
```

Historical prompt fragments may still describe N8K2 as the next step. That was true when N8K applicable figures still contained placeholder, low-information, duplicate, and applicability errors. The verified current state is that N8K2-N8K6 repaired that chain and PR #48 is merged.

## Completed Stage Summary

- N0-N3: project boundaries, data roles, solver input policy, Windows/WSL workspace separation.
- N4: source-backed EKF backbone.
- N5: Raw Doppler EKF factor.
- N6: source-aware LSIM/OIM weighting.
- N7: Go2 roll/pitch and horizontal velocity joint factor.
- N8A-N8E: no-feedback FGO backend, yaw wrap fix, Raw Doppler solver injection fix, formal engineering ablation.
- N8F: legged candidate factors.
- N8G-N8J: conservative FGO feedback EKF closure.
- N8K-N8K6: formal BY2 ablation plot audit and placeholder/duplicate/applicability repair, merged in PR #48.

## Next Planned Stages

- N9A_R3: audit real algorithm output lineage, frame/time alignment, metric sanity, source roles, and plot permission. Do not draw formal figures. Keep `ready_for_N9B=false`.
- N9A_R4: draw only BY2 normal figures with `allowed_to_plot=true`; mark all others missing or documented not-applicable.
- N9A final review: decide whether N9A can merge/tag and whether N9B can be proposed.
- N9B: run the full BY2 degradation matrix only after explicit user approval.
- N9C: convert real degradation outputs into 01-14 figures and case review.
- N9D: audit math, output evaluation, and filter-chain construction.
- N9E: package BY2 paper-grade results with claim limits.
- N10A: BY3 same-scenario replication.
- N10B: indoor-outdoor transition.
- N10C: poor-GNSS environment validation.

## Required Plan Sections

### 1. Task Goal

State the exact target stage and outcome. Distinguish documentation/context rebuilds from algorithm runs, figure generation, audits, or Git operations.

### 2. Verified Current State

List the branch, relevant PR/tag status, current stage, known blocker, and whether any statements are historical/stale. Do not rely only on prior memory when live verification is cheap.

### 3. Scope

List:

- Windows audit workspace files that may be modified.
- Windows audit workspace files/directories that are read-only.
- WSL algorithm repository access level.
- Whether `DATA_PATHS.local.md` may be read.
- Explicitly forbidden files, outputs, and Git actions.

### 4. Execution Steps

For each step, specify input files, commands, expected changed files, and validation method. WSL commands, if approved, must use:

```powershell
.\scripts\run_wsl_legsa.ps1 -Task status -Distro Ubuntu-22.04
.\scripts\run_wsl_legsa.ps1 -Task check-output-roots -Distro Ubuntu-22.04
.\scripts\run_wsl_legsa.ps1 -Task bash -Command "<command>" -Distro Ubuntu-22.04
```

### 5. Validation

Explain how to verify:

- Required files exist.
- No forbidden generated outputs were created.
- `DATA_PATHS.local.md` was not edited or staged.
- WSL algorithm source was not modified, if WSL was touched.
- Git write actions were not performed.
- Stage conclusions preserve `ready_for_N9B=false` unless explicitly approved otherwise.

### 6. Risks

Call out risks such as stale PR state, path leakage, data role confusion, generated artifact leakage, false plot completeness, frame/time alignment failure, metric sanity failure, and accidental WSL source edits.

### 7. Completion Criteria

Define done/not done. For N9A_R0 context rebuild, done means documentation context is coherent and current, but no algorithm output is validated and no plotting permission is granted.
