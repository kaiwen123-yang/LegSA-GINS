# N8F Relative Odometry Between Factor

The Go2 relative odometry between factor uses horizontal position increments
only:

`r = (p_state(k+1) - p_state(k)) - delta_p_go2`

Default state blocks:

- `position_k`
- `position_k_plus_1`

Boundary:

- Horizontal N/E only by default.
- No vertical increment by default.
- No Go2 absolute position factor.
- Go2 position increments are proprioceptive odometry evidence, not truth.

