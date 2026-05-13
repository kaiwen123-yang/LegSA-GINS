# N7C2 Factor Jacobian Contract

N7C2 documents active measurement/update factor contracts without changing the C++ solver.

Covered factors:

- `receiver_position`
- `receiver_velocity`
- `dual_antenna_yaw`
- `raw_doppler_velocity`
- `source_aware_scaling`
- `go2_attitude_roll_pitch_weak_prior`
- `go2_horizontal_velocity_weak_prior`

The Go2 horizontal velocity weak-prior contract is:

- residual: `[nav.vn - go2.vn, nav.ve - go2.ve]`
- residual dimension: 2
- nonzero state blocks: `velocity_north`, `velocity_east`
- H shape: `2 x 21`
- R shape: `2 x 2`
- vertical velocity disabled
- Go2 velocity is a weak prior, not truth

Toy finite-difference checks cover linear velocity factors and confirm that the Go2 horizontal velocity residual derivative is one for `vn/ve` and zero for `vd`.

Trace and final_v23 outputs are not solver inputs.
