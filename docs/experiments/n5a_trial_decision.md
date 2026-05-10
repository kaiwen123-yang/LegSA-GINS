# N5A Trial Decision

N5A runs a baseline replay path and a raw Doppler diagnostic path only when readiness reports activation allowed. If activation is blocked, the trial report must say which blocker applies and must not enable the solver.

Valid blockers include `rawx_missing`, `ephemeris_missing`, `rtklib_missing`, and `provider_missing_sat_state_export`. If RAWX, ephemeris, and RTKLIB are all available but solver activation is false, `blocking_issue` must be explicit.

If solver activation is true, `raw_doppler_update_count` must be greater than zero. If it is zero, the trial is a failed real activation, not an applied factor.

NAV-PVT velocity is not raw Doppler. `.gnss vn/ve/vd` remains baseline receiver-native velocity.

No trace solver input. No final_v23 output solver input. No paper performance claim. No outperform final_v23 claim.
