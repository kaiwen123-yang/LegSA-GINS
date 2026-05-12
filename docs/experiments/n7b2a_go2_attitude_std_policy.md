# N7B2A Go2 Attitude Std Policy

N7B2A reviews the N7A Go2 roll/pitch weak-prior standard-deviation policy.

The current roll/pitch standard deviation is 5 deg. It is a weak-prior
measurement uncertainty, not a gate threshold.

Policy notes:

- `current_roll_pitch_std_deg=5.0`
- `is_gate_or_threshold=false`
- `is_measurement_std=true`
- Go2 RPY/quaternion consistency is internal consistency, not absolute truth.
- Go2 attitude is not truth.
- Absolute truth for Go2 attitude is not available.
- Future diagnostic screens may review `[1.0, 1.6, 3.0, 5.0]`.
- Future std screens must not use trace tuning or final_v23 output tuning.

Recommended policy:

- `keep_5deg_for_N7A_safety`
- `review_1p6_or_3deg_in_future_N7C_if_activation_needed`

N7B2A does not activate Go2 velocity prior, does not activate Go2 yaw prior,
does not implement FGO, and makes no paper performance claim.
