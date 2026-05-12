# N7B Go2 Velocity Quality

Go2 velocity is not truth.

N7B compares Go2 velocity with receiver-native velocity and raw Doppler
velocity as cross-source consistency evidence. Cross-source velocity comparison
is not truth error. Receiver-native velocity is not raw Doppler, and raw Doppler
remains the RTKLIB Doppler-provider velocity factor.

Reported fields include:

- aligned count to receiver velocity
- aligned count to raw Doppler
- velocity diff RMSE to receiver
- velocity diff RMSE to raw Doppler
- body-or-NED component bias
- norm correlation
- contact-conditioned velocity stats
- moving-vs-standing velocity consistency
- `velocity_prior_activation_recommended`

`velocity_prior_activation_recommended` is a future-stage readiness flag. N7B
itself keeps `go2_velocity_prior_enabled=false`, `trace_solver_input=false`,
`final_v23_output_solver_input=false`, `paper_performance_claim=false`, and
`fgo=false`.
