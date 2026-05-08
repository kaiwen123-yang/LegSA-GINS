# Yaw Input Sensitivity Probe

The N4H2G2 yaw sensitivity probe is a diagnostic smoke test. It creates a temporary `.gnss` variant by shifting only the yaw column by +30 degrees while preserving all other columns and yaw standard deviation.

The shifted input is used only in a repository-external replay under `N4H2G2_OUTPUT_ROOT`. It is not a proposed solver input, not a factor experiment, and not performance evidence.

Probe interpretation:

- If shifted input yaw changes by about 30 degrees and NAV yaw changes by more than 5 degrees, runtime yaw input is clearly active.
- If shifted input yaw changes by about 30 degrees and NAV yaw changes by less than 0.5 degrees, yaw input has low runtime effect or the update is rejected/gated.
- Intermediate NAV yaw differences are reported as bounded runtime effect.

Boundary:

- trace_solver_input=false
- output_only_correction=false
- solver_output_changed=false
- bad_epoch_deletion_for_metric=false
- numerical_performance_claim=false
- shifted yaw replay must not be reported as an algorithm result
