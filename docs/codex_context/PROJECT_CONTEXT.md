# PROJECT_CONTEXT.md - LegSA-GINS Current Context

LegSA-GINS is a footed-robot GNSS/INS positioning and attitude project with source-backed EKF, Raw Doppler, source-aware weighting, Go2 proprioception, FGO, and FGO feedback EKF workstreams.

This checkout is the Windows audit workspace, not the default algorithm source repository. Use aliases from `PATH_POLICY.md` in tracked docs.

## Current Stage

- Current documentation task: `N9A_R0_MULTI_AGENT_CONTEXT_REBUILD`.
- Current technical next step: `N9A_R3_REAL_OUTPUT_AND_FRAME_ALIGNMENT_GATE`.
- Current required decision: `ready_for_N9B=false`.

## Current Verified PR State

- PR #48: merged on 2026-05-15.
- PR #21: open/unmerged; do not touch.
- PR #49: open/unmerged; do not merge or tag.

## Current Technical Blocker

N9A_R2 is incomplete/failure. The project must audit true output lineage, frame alignment, time alignment, metric sanity, and plot permission before drawing more BY2_normal_clean formal figures.
