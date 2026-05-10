# N5A Factor Integration Contract

The C++ factor is disabled by default with `enable_raw_doppler=false`. A valid provider-backed CSV enables `raw_doppler_solver_enabled=true`.

At a matching GNSS/update epoch, the factor applies before `stateFeedback` in the source-backed port loop:

`dz = nav.vel_ned_mps - raw_doppler_velocity_ned`

`H(V_ID) = I`

`R = diag(std_vn^2, std_ve^2, std_vd^2) * raw_doppler_R_scale`

The manifest records `raw_doppler_update_count`, reject count, epoch count, satellite count summary, residual p95, provider status, and toy activation evidence. If provider status is missing, solver activation remains false.

NAV-PVT velocity is not raw Doppler. `.gnss vn/ve/vd` remains baseline receiver-native velocity. No output-only correction is allowed.

No trace solver input. No final_v23 output solver input. No LSIM/OIM, Go2 prior, or FGO claim. No paper performance claim.
