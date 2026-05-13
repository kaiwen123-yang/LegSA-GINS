# N7C5A Decision

Decision statuses:

- `n7c5_visual_blocker`: required plot coverage, figure generation, time-axis,
  or sanity checks fail. Stop before N7C6.
- `n7c5_visual_review_passed`: visual review has no blocker and N7C6 can run.

Always true:

- Go2 observations are not truth.
- Go2 position/yaw/vertical velocity priors remain disabled.
- No trace/final_v23 solver input or tuning.
- No FGO activation.
- No paper performance claim.
