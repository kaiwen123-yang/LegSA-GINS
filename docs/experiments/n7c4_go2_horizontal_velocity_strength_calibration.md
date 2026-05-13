# N7C4 Go2 Horizontal Velocity Strength Calibration

N7C4 performs a controlled diagnostic scan of Go2 horizontal velocity prior
strength for PR #38. It does not change the Go2 horizontal velocity Jacobian:
only row-wise measurement uncertainty and update eligibility vary by variant.

Scanned policies:

- `fixed_std_2p0`: current N7C weak-prior reference
- `fixed_std_1p5`
- `fixed_std_1p0`
- `fixed_std_0p75_aggressive`: diagnostic aggressive variant
- `recalibrated_adaptive`: high `1.0`, medium `1.5`, low `2.5`, invalid skip
- `recalibrated_adaptive_aggressive`: high `0.75`, medium `1.25`, low `2.0`, invalid skip

Boundary:

- Go2 velocity is not truth.
- Vertical Go2 velocity remains disabled.
- Go2 yaw and position priors remain disabled.
- No trace/final_v23 tuning.
- No output-only correction, no epoch deletion, no FGO.
- No paper performance claim and no outperform-final_v23 claim.
