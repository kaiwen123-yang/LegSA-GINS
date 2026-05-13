# N8A1 Decision

N8A1 uses ordered decision rules:

1. Yaw convention or wrap blocker -> `fgo_yaw_convention_blocker`.
2. State/epoch mapping blocker -> `fgo_state_epoch_mapping_blocker`.
3. Diagnostic candidate leakage -> `fgo_candidate_factor_leak_blocker`.
4. Smoothness/yaw factor policy suspect -> `fgo_factor_weight_policy_review_needed`.
5. Large but explained yaw delta with no-feedback boundary intact -> `n8a_foundation_ready_with_yaw_policy_caveat`.
6. Small yaw delta after wrap correction -> `n8a_foundation_ready_metric_wrap_fixed`.

All outcomes preserve:

- no FGO feedback to EKF
- no FGO output substitution for EKF NAV
- no trace/final_v23 solver input
- no output-only correction
- no paper performance claim
- no outperform-final_v23 claim
