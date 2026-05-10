# N5A RTKLIB And Ephemeris Readiness

RTKLIB is allowed in N5A as a mature runtime-only provider/tool. Discovery reports may record local executable and ephemeris paths in runtime output, but tracked docs/config/scripts use role aliases and command parameters rather than hardcoded local paths.

The readiness probe searches for `convbin`, `rnx2rtkp`, selected RTKLIB source files, and BY2-date broadcast or precise ephemeris candidates. `rnx2rtkp` diagnostic output is data-availability evidence only; it is not a raw Doppler factor and is not LegSA solver input.

N5A activation requires RAWX plus ephemeris plus a satellite-state or Doppler-velocity export provider. If the provider is missing, the correct result is a blocker with `recommended_next_stage=N5B_rtklib_satellite_state_export_provider`.

No trace solver input. No final_v23 output solver input. No paper performance claim.
