# N8H Feedback Gate Review

N8H reviews the N8G gate instead of tuning it.

Inputs:

- accepted/rejected counts;
- correction norm distribution;
- configured gate thresholds;
- conservative residual-proxy covariance policy;
- sliding-window duration, stride, and epoch counts.

Gate classifications:

- `gate_reasonable`
- `gate_too_loose_suspect`
- `gate_too_strict_suspect`
- `gate_needs_N8H2_policy_review`

All accepted feedback can remain acceptable when correction norms stay below
configured caps and visual deltas do not show gross degradation. Trace and
final_v23 outputs are not used to tune the gate.
