# N7B4 Diagnostic Activation Boundary

N7B4 may build runtime-only `GO2_VELOCITY_PROBABILITY_WEIGHTED_PRIORS_DIAGNOSTIC.csv` and related diagnostic variant CSVs.

The C++ runtime path is the existing diagnostic-only velocity prior interface:

- `enable_go2_velocity_prior_diagnostic=false` by default;
- runtime configs set `go2_diagnostic_prior_only=true`;
- `formal_go2_velocity_prior=false`;
- Go2 yaw-rate remains report-only unless a valid state model exists.

The diagnostic variants may update the EKF, but their outputs are state-delta diagnostics only. They are not paper performance and not formal proposed priors.

Boundary: `"diagnostic_only": True`, `"paper_performance_claim": False`, `"trace_solver_input": False`, `"final_v23_output_solver_input": False`, `"fgo": False`.
