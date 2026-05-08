# Yaw Input Variant Matrix

N4H2C-2 builds a diagnostic-only yaw input variant matrix from reconstructed
process_data-compatible `.gnss` input.

## Variants

The matrix covers status A1 sign/offset candidates, auto-best diagnostic
candidate, trace-yaw diagnostic candidate, uploaded-script-default candidate,
and nominal-safe candidate.

## Formal Boundary

- trace yaw variant: `formal_allowed=false`
- auto-best install selected by trace: `formal_allowed=false`
- status yaw physical sign/offset still requires process_data invocation,
  actual final_v23 input, or physical mounting evidence

The matrix can identify whether a 90 degree yaw error is plausibly caused by
sign/offset/source-mode, but it is not formal offset selection.

## Runtime Snapshot

The current N4H2C-2 runtime matrix used reconstructed process_data-compatible
input and evaluation-only trace yaw:

- best status variant: `status_A1_sign-1_offset+90_yawstd_fixed1p5_noise0`
- best status yaw_vs_trace_rmse_deg: 4.9973634253532975
- best trace diagnostic variant: `trace_yaw_diagnostic_only`
- trace diagnostic yaw_vs_trace_rmse_deg: 92.93107029020553
- formal_selection_allowed: false

The best status variant is useful diagnostic evidence for a sign/offset
convention problem, but it is not enough to formally select an offset without
process_data invocation evidence or physical antenna-order evidence.
