# N5A Raw Doppler Factor Activation

N5A is the first proposed factor integration attempt after the source-backed backbone parity work.

The factor name is `raw_doppler_auxiliary_factor`, the factor family is `raw_gnss`, and the first implementation form is a raw-Doppler-derived velocity auxiliary factor. It must enter the EKF update chain when and only when a provider-backed velocity factor exists.

NAV-PVT velocity is not raw Doppler. `.gnss vn/ve/vd` remains baseline receiver-native velocity. Raw Doppler must come from satellite-level observations such as UBX-RXM-RAWX `doMes`, and it needs satellite position, satellite velocity, LOS, and clock-drift handling.

If RAWX, ephemeris, and RTKLIB exist but the satellite-state provider is missing, N5A must mark `provider_missing_sat_state_export` and must not report the factor as applied.

No trace solver input. No final_v23 output solver input. No output-only correction. No LSIM/OIM, Go2 prior, or FGO claim. No paper performance claim. No outperform final_v23 claim.
