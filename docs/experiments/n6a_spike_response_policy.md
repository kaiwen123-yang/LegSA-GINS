# N6A Spike Response Policy

N5D1 raw Doppler spike epochs are evaluation-only sentinels. They are read only
after a source-aware run, then matched to nearest raw Doppler rows in
`SOURCE_AWARE_WEIGHT_TRACE.csv`.

The spike times are not hardcoded into C++ policy, Python LSIM/OIM policy, or
runtime configs. The solver reacts only to residuals and source metadata.

中文说明：spike response report 只回答“spike 附近 raw_doppler_velocity 的 OIM/combined
R scale 是否自动升高”，不能作为调参输入。

Runtime-only report:
`N6A_SPIKE_RESPONSE_REPORT.json`.
