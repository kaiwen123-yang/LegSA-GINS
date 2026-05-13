# N7C6 Go2 Proprioceptive Joint Observation Factor

N7C6 evaluates a joint Go2 proprioceptive observation:

`z = [roll_go2, pitch_go2, vN_go2, vE_go2]`

with prediction:

`h(x) = [roll_filter, pitch_filter, vN_filter, vE_filter]`

and residual:

`r = h(x) - z`

The current C++ route uses a sequential-equivalent implementation: roll/pitch
2D update plus horizontal velocity 2D update. The contract still describes the
combined 4D observation. This stage does not enable Go2 position, yaw, or
vertical velocity priors.

Candidate policies scan roll/pitch std values of 5, 3, 1.6, 1, and 0.75 deg,
with horizontal velocity std fixed at 1.0 m/s for the main candidates. The
0.75 deg variants are diagnostic-aggressive.

The output is engineering evidence only and is not a paper performance claim.
