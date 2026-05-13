# N7C3 Soft-Gating Policy

N7C3 uses soft-gating for valid bounded confidence rows:

- high confidence: update with `1.0 m/s`
- medium confidence: update with `1.5 m/s`
- low confidence: update with `2.5` or `4.0 m/s`
- invalid confidence: skip with `update_flag=false`

Hard gating is reserved for invalid confidence or explicit `update_flag=false`.
Low confidence is not discarded by default; it is weakened through bounded
measurement uncertainty.

The report `GO2_HORIZONTAL_VELOCITY_SOFT_GATING_REPORT.json` records high,
medium, low, invalid, update, skip, hard-skip, and soft-gated counts.

Boundary:

- Vertical velocity remains disabled.
- Go2 yaw and position priors remain disabled.
- No trace/final_v23 tuning.
- No paper performance claim.
