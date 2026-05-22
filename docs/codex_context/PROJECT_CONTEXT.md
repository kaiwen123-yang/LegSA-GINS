# PROJECT_CONTEXT.md - LegSA-GINS Current Context

LegSA-GINS is a legged-robot GNSS/INS positioning and attitude project with source-backed EKF, Raw Doppler, source-aware weighting, Go2 proprioception, FGO, and FGO-feedback EKF workstreams.

This checkout is the Windows audit workspace, not the default WSL algorithm source repository. Use aliases from `PATH_POLICY.md` in tracked docs.

## Current Stage

- Current documentation task: `N9B2B1_CONTEXT_UPDATE_AFTER_PATH_LOCK`.
- Current technical pilot source: `N9B1D4`.
- Current pilot visual/go-no-go source: `N9B1E`, passed with C yaw caution.
- Full-matrix preparation sources: `N9B2A` and `N9B2A1`.
- Current path-lock source: `N9B2B`.
- Current recommended next stage: `human_review_N9B2B1_then_N9B2C_batch0_smoke_plan`.

## Current Decision Flags

```text
ready_for_N9B2_preparation=true
ready_for_N9B2_environment_smoke=true
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

## Current PR Boundary

- PR #21: open/unmerged historical branch; do not touch.
- PR #52: open/unmerged unless the human explicitly approves merge/tag/closure.

## Current Technical Boundary

N9B2B1 is docs/context update only. Do not run solvers, evaluators, N9B2, random generation, degraded-input generation, degradation matrices, or figures. Do not modify algorithm math, FGO factor math, feedback policy, final_v23, or `<WSL_ALGO_REPO>`.

## Path Boundary

Tracked docs use aliases only. Actual local paths belong only in ignored `docs/codex_context/DATA_PATHS.local.md`.
