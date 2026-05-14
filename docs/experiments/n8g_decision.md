# N8G Decision

Decision statuses:

- `feedback_observation_build_failed`
- `feedback_not_entering_ekf`
- `feedback_gate_too_strict_or_fgo_unstable`
- `fgo_feedback_ekf_foundation_ready`
- `fgo_feedback_policy_not_ready`

The ready status only means the engineering foundation exists: observations are
built, at least one feedback update enters EKF, direct NAV overwrite is absent,
and clean gross degradation is absent under diagnostic checks.

It is not a paper performance claim.
