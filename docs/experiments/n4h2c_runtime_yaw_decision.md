# N4H2C Runtime Yaw Decision

N4R3 confirmed the dual_final_v23 artifact and locked the official evaluator profile as `direct_identity`. Therefore the N4H2 replay yaw failure under direct identity should be treated as a runtime/config/source-version parity issue, not as a formal evaluator convention patch.

N4H2C-runtime records:

- actual dual official summary
- N4H2 replay summary
- actual input versus replay input yaw and motion differences
- actual NAV versus replay NAV yaw and attitude differences
- actual input-to-NAV and replay input-to-NAV yaw relation
- runtime config parity evidence
- current yaw update source evidence
- yaw update source history evidence

Decision categories include:

- `N4H2C_input_generation_fix`
- `N4H2C_replay_config_parity_fix`
- `N4H2C_source_version_parity_replay`
- `N4H2C_actual_runtime_source_recovery`
- `N4H2C_actual_config_recovery_needed`
- `N4H2C_yaw_update_instrumentation_required`

Boundary:

- runtime yaw audit is diagnostic only
- no solver output is modified
- external KF-GINS source is not modified
- no formal performance claim is made
- yaw above 2 deg is not relaxed
- full KF-GINS-style framework work remains future work until runtime/config parity is resolved
