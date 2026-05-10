# N6A Ablation Protocol

Required clean variants:

- baseline_full_no_raw_no_sourceaware
- baseline_plus_raw_no_sourceaware
- baseline_plus_raw_lsim_only
- baseline_plus_raw_oim_only
- baseline_plus_raw_lsim_oim

Required receiver-velocity stress pairs:

- disabled no_sourceaware vs lsim_oim
- std_scale_5 no_sourceaware vs lsim_oim
- outage_30s no_sourceaware vs lsim_oim
- noise_0p5 no_sourceaware vs lsim_oim

Required spike sentinel:

- baseline_plus_raw_lsim_oim_spike_response_audit

中文说明：stress variants 是 diagnostic_only；不做 paper performance claim，不做
outperform final_v23 claim，不用 trace 调参，不硬编码 spike time。
