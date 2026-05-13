# N7C Ablation Protocol

Required variants:

- `baseline_no_go2_horizontal_velocity`
- `go2_horizontal_velocity_weak_prior_main`
- `go2_horizontal_velocity_probability_weighted`
- `go2_horizontal_velocity_contact_weighted`
- `go2_horizontal_velocity_high_confidence_only`
- `receiver_velocity_stress_no_go2`
- `receiver_velocity_stress_plus_go2_horizontal`
- `raw_doppler_stress_no_go2`
- `raw_doppler_stress_plus_go2_horizontal`

Only `go2_horizontal_velocity_weak_prior_main` is the controlled N7C activation
candidate. Stress variants are diagnostic-only. The protocol does not select a
policy by trace or final_v23 output.
