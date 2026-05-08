# N4H4D2 Update Feedback Variant Matrix

N4H4D2 adds diagnostic-only model variants for residual signs, position
H_phi coupling, yaw H sign, EKF innovation sign, and stateFeedback signs/sides.

Each variant runs only when diagnostic mode is explicitly enabled and is written
to RUN_MANIFEST with `diagnostic_only=true` and
`not_for_performance_claim=true`.

Variant results are not paper results, not tuning, and not a permanent solver
fix. They only identify which formula branch should be fixed in a later stage.

