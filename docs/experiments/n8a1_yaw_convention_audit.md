# N8A1 Yaw Convention Audit

The yaw convention audit checks whether EKF and FGO yaw columns use degree
units, whether yaw ranges are consistent, whether residuals are wrapped, and
whether a heading-yaw versus math-yaw sign convention mismatch is plausible.

The audit also detects 0/360 discontinuity cases where ordinary arithmetic
smoothing can create artificial yaw values near 120, 180, or 240 degrees.

Key fields:

- `yaw_unit_consistent`
- `yaw_wrap_consistent`
- `heading_math_yaw_mismatch_suspect`
- `yaw_residual_wrap_used`
- `yaw_delta_rmse_raw`
- `yaw_delta_rmse_after_best_wrap`
- `yaw_jump_count`
- `blocker_status`

This is an audit-only module. It does not change solver math, does not tune FGO
weights, and does not use trace/final_v23 output as solver input.
