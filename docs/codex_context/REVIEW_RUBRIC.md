# REVIEW_RUBRIC.md

Reviewer must lead with findings and then summarize validation and residual risk.

## Required Checks

- Worker followed the approved N9B2B1 planner scope.
- No WSL algorithm source was modified.
- final_v23 was not modified.
- Algorithm math, FGO factor math, and feedback policy were not modified.
- `DATA_PATHS.local.md` was not edited, staged, or tracked.
- No generated figures, NAV/STD/EVAL_NAV/RUN_MANIFEST outputs, degradation outputs, archives, raw data, or large sensor files were created/staged.
- No solver/evaluator/N9B2/random/degraded-input execution occurred.
- Current state is accurate for N9B2B1 after N9B2B path lock.
- PR #52 remains open/unmerged and merge/tag is not authorized.
- N9B2C remains the next recommended stage after human review.
- `ready_for_N9B2_preparation=true`.
- `ready_for_N9B2_environment_smoke=true`.
- `ready_for_N9B2_execution=false`.
- `ready_for_full_N9B_execution=false`.
- Path aliases are used; no tracked-doc local absolute path leaks exist.
- Data source roles are not confused.
- Runner rules are preserved.
- Baseline roles are preserved.
- Matrix cautions are preserved.
- Claims do not exceed verified evidence.

## Required Git Recommendations

State separately:

- Windows audit workspace: whether commit / push / PR / merge is recommended.
- WSL algorithm source repository: whether commit / push / PR / merge is recommended.

Reviewer must not execute Git operations.

## Allowed Conclusions

- pass.
- conditional pass.
- fail.
