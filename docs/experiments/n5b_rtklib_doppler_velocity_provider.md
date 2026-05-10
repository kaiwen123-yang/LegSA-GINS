# Stage N5B: RTKLIB Doppler Velocity Provider

N5A completed the raw Doppler activation path but left real activation blocked by `provider_missing_sat_state_export`.
N5B targets a real Doppler-derived velocity provider backed by RTKLIB source functions, not another interface placeholder.

- The provider uses runtime-only RINEX obs/nav files and a runtime-only helper built from local RTKLIB source.
- The helper calls RTKLIB `pntpos` with a runtime-only patch that restores Doppler velocity estimation when the local source has that call disabled.
- The provider output is velocity-only and is converted to NED before EKF use.
- RTKLIB final position solutions are diagnostic-only and cannot be LegSA solver input.
- NAV-PVT velocity and `.gnss` `vn/ve/vd` remain receiver-native baseline velocity, not raw Doppler.
- `raw_doppler_update_count > 0` is required before N5B can report real activation.
- No LSIM/OIM, Go2 prior, FGO, source-aware weighting, output-only correction, trace tuning, or paper performance claim is introduced.
