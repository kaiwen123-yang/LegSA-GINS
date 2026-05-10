# N6A Decision

The decision report is runtime-only:
`N6A_SOURCE_AWARE_DECISION_REPORT.json`.

Decision statuses:

- `not_activated`
- `needs_policy_fix`
- `ready_for_go2_weak_prior_or_extended_source_weighting`
- `ready_with_spike_response_caveat`
- `ready_with_weak_stress_evidence`
- `needs_lsim_oim_threshold_review`

Always false:

- paper_performance_claim
- proposed_factor_claim
- output_only_correction
- trace_tuning
- bad_epoch_deletion_for_metric
- go2_prior
- fgo

中文说明：N6A 只输出工程诊断结论；是否进入 N6B 或 N7A 由 clean/stress/spike
证据共同决定。
