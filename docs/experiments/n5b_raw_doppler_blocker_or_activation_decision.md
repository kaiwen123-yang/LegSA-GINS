# N5B Blocker Or Activation Decision

N5B uses a hard activation rule:

- `completed_enabled` requires `RAW_DOPPLER_VELOCITY_FACTORS.csv` and `raw_doppler_update_count > 0`.
- If the factor exists but the update count is zero, the blocker is `activation_failed_update_alignment_or_loader`.
- If helper compilation fails, the blocker is `helper_compile_failed`.
- If the helper runs but produces no velocity rows, the blocker is `helper_compiled_but_no_velocity_output`.
- If velocity covariance is unavailable without a documented conservative policy, the blocker is `covariance_missing`.

The decision report must keep `trace_solver_input=false`, `final_v23_output_solver_input=false`, and `paper_performance_claim=false`.
