# N7A ablation protocol

N7A uses runtime-only variants:

- `baseline_plus_raw_sourceaware_n6b_no_go2`
- `baseline_plus_raw_sourceaware_n6b_go2_attitude_weak_prior`
- `baseline_plus_raw_no_sourceaware_go2_attitude_weak_prior`
- `raw_doppler_stress_plus_sourceaware_no_go2`
- `raw_doppler_stress_plus_sourceaware_go2_attitude_weak_prior`
- `attitude_prior_std_3deg`
- `attitude_prior_std_5deg`
- `attitude_prior_std_10deg`

The default candidate is the 5 degree roll/pitch weak prior. The 3 degree and 10 degree variants are diagnostic-only screens, not trace-tuned policy selection.

No trace/final_v23 output is used for Go2 prior construction. Go2 position and velocity priors are disabled by default in N7A. Go2 yaw prior is disabled in N7A. No paper performance claim. No FGO.
