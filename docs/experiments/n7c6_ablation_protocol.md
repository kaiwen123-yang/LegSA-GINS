# N7C6 Ablation Protocol

Required variants:

- `baseline_no_go2_proprioceptive`
- `horizontal_only_fixed_1p0`
- `rollpitch_only_5deg`
- `rollpitch_only_3deg`
- `rollpitch_only_1p6deg`
- `rollpitch_only_1deg`
- `joint_rp3deg_hv1p0`
- `joint_rp1p6deg_hv1p0`
- `joint_rp1deg_hv1p0`
- `joint_rp0p75_hv1p0_diagnostic`
- `joint_rp1p6deg_hv0p75_diagnostic`
- `joint_rp1p6deg_hv1p0_sourceaware_off`
- `receiver_velocity_stress_baseline`
- `receiver_velocity_stress_joint`
- `raw_doppler_stress_baseline`
- `raw_doppler_stress_joint`

The ablation reports clean/stress deltas, update/reject counts, source-aware
trace summaries, and NIS proxies. These are diagnostic engineering checks, not
paper performance claims or final_v23 outperform claims.
