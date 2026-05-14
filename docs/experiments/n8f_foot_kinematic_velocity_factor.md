# N8F Foot Kinematic Velocity Factor

The foot kinematic velocity factor promotes the N7C5 foot-kinematic candidate
to an active no-feedback FGO residual.

Default residual:

`r = [vN_state - vN_footkin, vE_state - vE_footkin]`

Default state blocks:

- `velocity_north`
- `velocity_east`

Boundary:

- Horizontal velocity only by default.
- No vertical Go2 velocity factor.
- No Go2 absolute position factor.
- No absolute yaw factor.
- Go2 foot kinematic velocity is proprioceptive evidence, not truth.

