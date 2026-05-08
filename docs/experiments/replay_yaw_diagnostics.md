# Replay Yaw Diagnostics

N4H2C-2 compares:

- reconstructed input yaw vs trace-derived yaw
- replay NAV yaw vs trace-derived yaw
- reconstructed input yaw vs replay NAV yaw

Trace-derived yaw comes from evaluation artifacts only. It is never solver
input.

## Diagnostic Classifications

- `likely_runtime_yaw_update_or_initialization_issue`
- `likely_input_yaw_generation_issue`
- `likely_yaw_convention_offset_issue`
- `yaw_diagnostics_inconclusive`
- `evidence_missing`

## Runtime Snapshot

Using N4H2 replay artifacts and evaluation-only trace-derived yaw:

- input_yaw_vs_trace_rmse: 92.93107029020553
- replay_nav_yaw_vs_trace_rmse: 93.55116160331568
- input_yaw_vs_replay_nav_rmse: 5.105864733805185
- likely_issue_classification: `likely_input_yaw_generation_issue`

This diagnostic is intentionally conservative: it does not correct the replay
output and does not use trace as solver input.

## Boundary

No output-only correction, no epoch deletion, and no formal performance claim.
