# N7C Horizontal Velocity Policy

N7C uses only Go2 horizontal velocity as a weak prior:

- `measurement_components = [vn, ve]`
- `base_horizontal_std_mps = 2.0`
- `go2_horizontal_velocity_prior_vertical_disabled: true`
- `go2_horizontal_velocity_prior_mode = horizontal_2d`
- `source_aware_no_R_shrink = true`
- `trace_tuning = false`
- `final_v23_tuning = false`

The Go2 body velocity is source evidence, not truth. The vertical component is
not an effective measurement. Position and yaw priors remain disabled.
