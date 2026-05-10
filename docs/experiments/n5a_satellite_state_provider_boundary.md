# N5A Satellite State Provider Boundary

The satellite-state provider is a necessary condition for raw Doppler activation. RAWX alone is not enough because Doppler residuals require satellite position, satellite velocity, LOS geometry, and clock-drift treatment.

Allowed runtime tools include RTKLIB `convbin`, `rnx2rtkp`, and RTKLIB source functions such as `satposs`, `eph2pos`, `geph2pos`, `seleph`, `readrnx`, `resdop`, or `estvel` when a runtime-only helper can export satellite states or provider-backed Doppler velocity.

If no satellite-state or Doppler-velocity export method is available, N5A must set `satellite_state_provider_status=provider_missing_sat_state_export`, `raw_doppler_solver_activation_allowed=false`, and `recommended_next_stage=N5B_rtklib_satellite_state_export_provider`.

No trace solver input. No final_v23 output solver input. No paper performance claim.
