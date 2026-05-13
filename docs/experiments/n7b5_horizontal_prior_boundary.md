# N7B5 Horizontal Prior Boundary

N7B5 horizontal Go2 velocity priors are diagnostic-only runtime CSVs.

Boundary contract:
- `diagnostic_only=true`;
- `formal_activation_allowed=false`;
- `formal_go2_velocity_prior=false`;
- `go2_velocity_truth_claim=false`;
- vertical velocity is disabled with `std_vd=999`;
- trace and final_v23 output are not used for frame selection or tuning;
- generated CSVs are runtime artifacts and must not be committed.

The diagnostic CSVs are allowed to enter the EKF only under the diagnostic configuration path. They are used to test stability and state-delta behavior, not to support a paper performance claim.
