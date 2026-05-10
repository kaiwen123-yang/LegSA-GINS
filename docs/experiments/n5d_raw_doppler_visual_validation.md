# N5D Raw Doppler Visual Validation

N5D adds runtime-only visual checks after N5C raw Doppler ablation.

Scope:
- clean visual validation for baseline_full and baseline_plus_raw_doppler_r1;
- raw Doppler velocity, residual proxy, satellite count, STD/covariance, and update timeline plots;
- diagnostic review for yaw wrap, velocity jumps, and update mismatch.

Boundary:
- NAV-PVT velocity is not raw Doppler.
- .gnss vn/ve/vd is not raw Doppler.
- RTKLIB position solution must not be used as LegSA solver input.
- final_v23 output is not proposed solver input.
- trace remains evaluation-only.
- paper performance claim: false.
- no outperform final_v23 claim.

Generated figures are temporary inspection artifacts and must stay runtime-only.
