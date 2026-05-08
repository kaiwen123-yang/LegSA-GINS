# N4R yaw evaluator parity

The N4R yaw evaluator parity check compares:

- direct yaw error from actual final_v23 NAV against the evaluation-only
  reference;
- a transform candidate grid over estimate yaw and reference yaw;
- official summary yaw_rmse_deg;
- official error_series yaw_error_deg.

The grid includes identity, sign flips, plus/minus 90 deg, plus 180 deg,
heading-to-math yaw, and trace-yaw aliases. A candidate is useful only if it
reproduces official summary yaw and, when available, official error_series
yaw_error.

The selected candidate is not a solver yaw offset, not antenna-order evidence,
and not a formal mounting calibration. It is only a diagnostic description of
the evaluator convention needed to reproduce official case-review numbers.

Boundary:

- no trace solver input
- no output-only correction
- no formal yaw offset selection
- no formal numerical performance claim
