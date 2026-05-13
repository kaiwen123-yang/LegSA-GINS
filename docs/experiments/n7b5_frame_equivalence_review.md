# N7B5 Frame Equivalence Review

The frame equivalence review measures whether the two N7B4 top Go2 velocity frame candidates are practically equivalent for horizontal velocity.

Inputs:
- N7B4 frame score report;
- Go2 body-state velocity and attitude fields;
- receiver-native velocity from the clean GNSS stream;
- raw Doppler velocity factor rows.

Computed diagnostics:
- top-candidate horizontal difference RMSE and p95;
- top-candidate vertical difference RMSE and p95;
- horizontal velocity vector angular difference;
- segment breakdown for straight, turning, high roll/pitch, and high yaw-rate epochs;
- receiver/raw cross-source consistency for each candidate.

Decision outputs:
- `frame_equivalent_for_horizontal_only`;
- `vertical_component_ambiguous`;
- `recommended_horizontal_policy`.

The review does not use trace or final_v23 output and does not make a truth claim about Go2 velocity, receiver velocity, or raw Doppler velocity.
