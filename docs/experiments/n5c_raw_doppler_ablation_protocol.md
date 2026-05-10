# Stage N5C: Raw Doppler Ablation Protocol

N5C follows the N5B real EKF activation of the RTKLIB-backed raw Doppler velocity factor. The goal is controlled diagnostic evidence, not another interface proof and not a paper result.

## Variants

- `baseline_full`: receiver position, receiver-native velocity, and dual yaw; raw Doppler disabled.
- `baseline_plus_raw_doppler_r1`: baseline plus the RTKLIB-derived raw Doppler auxiliary velocity factor at `R_scale=1.0`; this is the only proposed-candidate diagnostic row.
- `position_yaw_plus_raw_doppler_r1`: receiver-native velocity disabled and raw Doppler enabled; velocity-isolation variants are diagnostic-only.
- `position_yaw_only`: receiver-native velocity disabled and raw Doppler disabled; diagnostic lower reference.
- `baseline_plus_raw_doppler_r0p5/r2/r5`: R_scale screen is diagnostic-only and is not tuning.

## Boundaries

- NAV-PVT velocity is not raw Doppler.
- .gnss vn/ve/vd is not raw Doppler.
- RTKLIB position solution must not be used as LegSA solver input.
- The factor CSV must remain velocity-only and must come from the N5B RTKLIB Doppler provider.
- The dual/final_v23 reference is evaluation-only; final_v23 output is not solver input.
- Trace is evaluation-only and is not used to tune timing or noise.
- paper performance claim: false.
- no outperform final_v23 claim: true.
- No LSIM/OIM, Go2 prior, source-aware weighting, FGO, output-only correction, tuning, or epoch deletion is introduced.
