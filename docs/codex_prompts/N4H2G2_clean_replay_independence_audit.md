# N4H2G2 Prompt Contract

Task: audit clean replay independence, cache/staleness, and yaw-input sensitivity before N4H3.

Runtime role aliases:

- `DUAL_FINAL_V23_ARTIFACT_ROOT`
- `N4H2_ARTIFACTS_ROOT`
- `N4H2G_CLEAN_ROOT`
- `N4H2G2_OUTPUT_ROOT`
- `EXTERNAL_KFGINS_ROOT`

Required boundaries:

- no solver modification
- no tuning
- no epoch deletion
- no output-only correction
- no generated artifact commits
- no trace solver input
- no performance claim
- noisy historical artifact must not be relabeled as clean nominal

Required outputs:

- `CLEAN_REPLAY_INDEPENDENCE_REPORT.json`
- `CLEAN_REPLAY_ARTIFACT_HASH_REPORT.json`
- `CLEAN_REPLAY_FRESH_SUMMARY_AUDIT.json`
- `YAW_INPUT_SENSITIVITY_PROBE_REPORT.json`
- `N4H2G2_DECISION_REPORT.json`
