# N5B Next Stage Plan

If N5B reaches `completed_enabled`, N5C can define a raw Doppler ablation protocol.

If N5B is blocked, the next stage is selected from the concrete blocker:

- `N5B2_rtklib_helper_compile_fix`;
- `N5B2_rtklib_velocity_output_fix`;
- `N5B2_doppler_velocity_covariance_model`;
- `N5B2_raw_doppler_time_alignment_fix`;
- `N5B2_data_availability_recheck`.

N5C remains not started until activation is stable or a blocker-specific follow-up has been completed.
