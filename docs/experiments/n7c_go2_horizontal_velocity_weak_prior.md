# N7C Go2 Horizontal Velocity Weak Prior

N7C activates a controlled Go2 horizontal velocity weak prior after N7B5 showed
that the top Go2 velocity frame candidates are equivalent for horizontal-only
use.

- Policy: `n7c_go2_horizontal_velocity_weak_prior`
- Frame: `go2_velocity_as_body_flu_then_rotate_by_go2_attitude`
- Components: `vn`, `ve`
- Go2 vertical velocity prior: disabled
- Go2 position prior: disabled
- Go2 yaw prior: disabled
- Go2 velocity is not truth.
- Trace and final_v23 output are not solver input and are not used for tuning.
- FGO is not implemented in N7C.
- paper_performance_claim: false
- no_outperform_final_v23_claim: true

The main candidate is `go2_horizontal_velocity_weak_prior_main`. Probability,
contact-weighted, high-confidence, receiver-velocity stress, and raw-Doppler
stress variants are diagnostic engineering evidence only.
