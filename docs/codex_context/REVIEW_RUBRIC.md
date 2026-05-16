# REVIEW_RUBRIC.md

Reviewer must lead with findings and then summarize validation and residual risk.

## Required Checks

- Worker followed the approved planner scope.
- No WSL algorithm source was modified unless explicitly approved.
- final_v23 was not modified.
- `DATA_PATHS.local.md` was not edited or staged unless explicitly approved.
- No generated figures, runtime artifacts, degradation outputs, archives, raw data, or large sensor files were created/staged.
- Current state is accurate: PR #48 merged, PR #21 open/unmerged, PR #49 open/unmerged.
- N9A_R2 is not represented as complete.
- N9A_R3 remains the next technical gate.
- `ready_for_N9B=false`.
- Data source roles are not confused.
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
