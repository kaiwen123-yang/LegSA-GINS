# Replay Reference Mapping Audit

N4H2D exists because the old N4H2 replay summary reported yaw near 93 deg even though N4H2C-runtime found that actual dual_final_v23 NAV and replay NAV are nearly identical.

This stage reconstructs the official evaluation reference from `DUAL_FINAL_V23_ARTIFACT_ROOT` using official NAV and official error_series, then freshly evaluates the N4H2 replay NAV from `N4H2_ARTIFACTS_ROOT` against that reconstructed reference.

The audit checks whether the old replay summary was stale, mapped to the wrong reference, or otherwise unsuitable as formal evidence.

Boundary:

- trace_solver_input=false
- output_only_correction=false
- solver_output_changed=false
- numerical_performance_claim=false
- no solver output is modified
- no artifact file is committed
