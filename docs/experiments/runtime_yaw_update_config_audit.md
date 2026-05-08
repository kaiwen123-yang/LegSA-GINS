# Runtime Yaw Update Config Audit

N4H2C-runtime exists because N4R3 locked the official dual_final_v23 evaluator profile as `direct_identity`, while the N4H2 replay still has a large direct yaw error even though horizontal and up errors are close to the dual_final_v23 context.

This stage is diagnostic only. It compares runtime evidence from `DUAL_FINAL_V23_ARTIFACT_ROOT`, `N4H2_ARTIFACTS_ROOT`, and read-only `EXTERNAL_KFGINS_ROOT`. It does not implement proposed solver logic, raw Doppler, Go2 priors, source-aware weighting, FGO, LSIM/OIM, or a full EKF.

The audit checks:

- actual dual input yaw versus replay input yaw
- actual dual NAV yaw versus replay NAV yaw
- input-to-NAV yaw relation for actual and replay
- runtime config evidence such as `initatt`, `initattstd`, `antlever`, yaw std, yaw gate, and source/executable hints
- current KF-GINS yaw update source and yaw update history

Boundary:

- trace_solver_input=false
- output_only_correction=false
- solver_output_changed=false
- numerical_performance_claim=false
- external KF-GINS source remains read-only
- yaw above the strict 2 deg gate is not a pass
