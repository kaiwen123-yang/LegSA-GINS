# N8F Yaw-Rate Between Factor

The Go2 yaw-rate between factor uses yaw speed as an incremental constraint:

`r = wrap((yaw_{k+1} - yaw_k) - yaw_speed * dt)`

Jacobian contract:

- `dr/dyaw_k = -1`
- `dr/dyaw_{k+1} = +1`

Boundary:

- This is not an absolute Go2 yaw truth factor.
- Wrapped residuals use the N8A2 yaw convention.
- No trace/final_v23 tuning.
- No feedback/substitution.

