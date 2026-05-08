# N4R official final_v23 case-review reproduction

N4R reproduces the official final_v23 case-review metrics before any runtime
yaw config audit, full KF-GINS-style EKF reconstruction, or factor stacking.

This stage does not implement the proposed solver. The official summary is
reference context, actual official artifacts remain runtime-only, and trace is
used only for evaluation parity.

The key question is yaw evaluator parity: whether the direct yaw error formula,
the trace yaw convention, or the official error_series definition explains the
gap between replay NAV yaw and official case-review yaw.

If evaluator convention does not close, the project must not enter full EKF
reconstruction, raw Doppler, Go2 priors, source-aware weighting, LSIM/OIM, FGO,
or nine-factor stacking.

Boundary:

- trace_solver_input=false
- output_only_correction=false
- bad_epoch_deletion_for_metric=false
- numerical_performance_claim=false
- official artifacts are not proposed solver outputs
- yaw transforms are evaluator diagnostics only
