# N7B Go2 Contact-State Definition

Contact labels:

- `standing_contact`
- `walking_contact`
- `swing_or_uncertain`
- `low_confidence`
- `invalid`

Inputs:

- `foot_force[4]`
- `foot_speed_body[12]`
- `foot_position_body[12]`
- `gait_type`
- `mode`
- `body_height`

The foot-force threshold is a diagnostic default, not trace tuned and not
derived from final_v23 output. Foot-speed body norm is used as a consistency
check. Mode and gait type separate standing from walking evidence when present.

The contact report is readiness evidence only. It sets
`go2_contact_prior_enabled=false`, `go2_velocity_prior_enabled=false`,
`go2_yaw_prior_enabled=false`, `trace_solver_input=false`, and
`final_v23_output_solver_input=false`.

There is no paper performance claim and no FGO claim.
