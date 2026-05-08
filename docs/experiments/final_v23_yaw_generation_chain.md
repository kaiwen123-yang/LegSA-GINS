# final_v23 Yaw Generation Chain

Stage N4H1 audits final_v23 status-yaw generation candidates.

## A1 Dual-Difference Formula

The A1 dual-difference baseline is:

- `b_n = rel_pos_n(gnss2) - rel_pos_n(gnss1)`
- `b_e = rel_pos_e(gnss2) - rel_pos_e(gnss1)`
- `yaw = -atan2(b_e, b_n)`

The audit compares this formula and related diagnostic candidates against the final_v23 15-column `.gnss` yaw column.

## Diagnostic Candidates

The candidates include:

- `a1_dual_diff`
- `a1_dual_diff_plus90`
- `a1_dual_diff_minus90`
- `reverse_dual_diff`
- `reverse_plus90`
- `reverse_minus90`
- `heading_direct_atan2_e_n`
- `yaw_math_candidate`

All candidates are diagnostic-only. A formal heading offset cannot be selected until antenna order and process_data yaw offset semantics are confirmed from source evidence.

## Boundary

Trace may be used only for evaluation-only yaw diagnostics. It must not be used as solver input or as the basis for formal heading-offset selection.

This stage does not make a numerical performance claim and does not implement any proposed solver feature.
