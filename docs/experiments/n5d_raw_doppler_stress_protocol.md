# N5D Raw Doppler Velocity-Stress Protocol

N5D defines receiver-native velocity stress variants to diagnose whether the
RTKLIB-backed raw Doppler factor provides independent velocity constraint when
baseline receiver velocity is disabled, downweighted, interrupted, or perturbed.

Required groups:
- clean core: baseline_full and baseline_plus_raw_doppler_r1;
- velocity isolation: position_yaw_only and position_yaw_plus_raw_doppler_r1;
- receiver velocity stress: disabled, STD-scale 5, 30 s outage, and fixed-seed 0.5 m/s additive noise, each with no_raw and plus_raw variants.

Boundary:
- Receiver velocity stress variants are diagnostic-only.
- R-scale and STD-scale screens are not tuning claims.
- Stress variants do not represent a real sensor fault model.
- Stress variants are not proposed results.
- No output-only correction, no tuning, no epoch deletion.
- No LSIM/OIM, Go2 prior, or FGO implementation in N5D.
- paper performance claim: false.
