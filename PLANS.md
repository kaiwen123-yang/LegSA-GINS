# LegSA-GINS Clean Rebuild Plan

## Current Stage

`PAPER10_CLEAN0_REPOSITORY_LEGACY_FREEZE_DEPENDENCY_DECOUPLING_AND_HARD_RESET`

CLEAN0 froze Git history and legacy protocol knowledge, established the clean code/config/context structure, hash-locked raw inputs, created an independent runner, completed a BY2 clean smoke, physically removed guarded legacy assets, and prepared a clean GPT context and lightweight unmerged review PR.

## CLEAN0 Gates

1. Git refs, open-PR metadata/patches, and an all-refs bundle are frozen and verified.
2. Raw and paper roots are protected; raw files are hash-locked without modification.
3. Active code has no dependency on old experiment, report, provider, or output roots.
4. The paper-rebuild runner reads only explicit local config and writes only below `<CLEAN_ROOT>`.
5. BY2 `basic_dual_yaw_EKF` clean smoke passes with `old_runtime_input_count=0`.
6. Exact-path deletion guards pass before physical legacy deletion.
7. Clean GPT context export passes integrity and denylist scans.
8. Build, clean tests, active-core tests, diff checks, and publish checks pass.

No smoke result is a paper performance claim.

All execution gates above are complete. Legacy unit/audit tests that require retired external stage assets remain classified separately and do not override passing clean tests, active-core tests, or the raw/provider/smoke guards.

## Next Stage

`CLEAN1` is considered only after CLEAN0 supervisor/reviewer closure and explicit human approval. Its candidate scope is a fixed BY2 normal protocol across the four clean methods, followed by manifest, metric, and visual review. It does not automatically authorize classic-18, the 60x9 matrix, DA03/DA05, selected feedback, active 9F FGO, QA fallback, or paper claims.

Detailed rules live in `docs/paper_rebuild/`.
