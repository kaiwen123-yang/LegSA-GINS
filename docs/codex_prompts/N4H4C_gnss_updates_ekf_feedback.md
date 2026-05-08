# N4H4C Codex Prompt Summary

Task:
Implement LegSA-v23-core GNSS position, velocity, and yaw updates, EKFUpdate,
stateFeedback, and the `newImuProcess` measurement-update branch.

Hard boundaries:

- Do not implement raw Doppler, raw pseudorange, Go2 prior, LSIM/OIM,
  source-aware weighting, FGO, FGO feedback, or Neural Gate.
- Do not use trace as solver input.
- Do not use final_v23 output as proposed solver input.
- Do not copy or compile `reference/final_v23_repo` source.
- Do not claim final_v23 numerical parity or performance.
- Preserve Chinese comments around critical C++ functions.

Expected evidence:

- `legsa_v23_core_demo --dry-run-update-toy` generates NAV/STD/EVAL_NAV and
  RUN_MANIFEST.
- Manifest has `measurement_update_implemented=true` and
  `state_feedback_implemented=true`.
- Forbidden flags remain false.
- Yaw scheme_C counts are recorded.
- Audit and pytest pass.

Next stage:
N4H4D clean replay parity, still without final_v23 output substitution or
performance claim until independently validated.
