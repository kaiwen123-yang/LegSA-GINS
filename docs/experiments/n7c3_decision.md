# N7C3 Decision

N7C3 decision rules:

- if max std is greater than `5 m/s`: `policy_failed_physical_bound`
- if adaptive update count is zero: `adaptive_activation_failed`
- if clean run degrades relative to fixed std: `adaptive_policy_not_ready`
- if clean is neutral and stress is neutral or improved:
  `bounded_adaptive_policy_ready_for_N8A`
- if fixed std is sufficient and bounded adaptive adds no benefit:
  `fixed_std_policy_sufficient_bounded_adaptive_optional`

Always false:

- `paper_performance_claim`
- `go2_velocity_truth_claim`
- `trace_solver_input`
- `final_v23_output_solver_input`
- `fgo`

Always disabled:

- Go2 vertical velocity prior
- Go2 yaw prior
- Go2 position prior
