# N6A Measurement Policy

`source_aware_max_R_scale=25` is the fixed N6A cap. The default mode is off; the
diagnostic modes are `lsim_only`, `oim_only`, and `lsim_oim`.

No trace tuning is allowed. No final_v23 output is used for weighting. Output correction is forbidden.
N6A does not delete epochs and does not relax yaw
gates for metric passing.

Per-source defaults are enabled for:

- receiver_position
- receiver_velocity
- dual_antenna_yaw
- raw_doppler_velocity

中文说明：每个 source 在 `EKFUpdate` 前构造 metadata 和 innovation，计算 LSIM/OIM
scale，然后把 `R_scaled` 传入 EKF。N6A 默认只保守降权，不缩小 R。
