# Writer and Evaluator Contract

## EVAL_NAV Writer

EVAL_NAV is the standardized evaluation navigation output. It contains:

- timestamp
- lat_deg
- lon_deg
- height_m
- vn_mps
- ve_mps
- vd_mps
- roll_deg
- pitch_deg
- yaw_deg
- status
- source_role

timestamp must be convertible to float and monotonically non-decreasing.

status records the row-level state or availability label. source_role records whether the row belongs to a baseline, proposed, diagnostic, or infrastructure output role.

The writer may only write standardized evaluation output. It must not write raw data or large source dumps.

## Evaluator Boundary

Evaluator utilities must not be used as solver input.

trace/reference streams are evaluation-only. They must not be used for solver input or tuning unless a later phase explicitly reopens that boundary.

If required evidence is missing, write:

evidence_missing
