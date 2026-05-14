# N8F1 Decision

N8F1 decision rules:

- Missing or empty required figures lead to `visual_validation_failed_missing_figures`.
- Plot semantic blockers lead to `visual_validation_failed_semantics`.
- Missing factor signal leads to `factor_signal_review_failed`.
- Gross degradation leads to `legged_candidate_stack_not_ready`.
- If all visual, signal, semantic, and sanity checks pass, status is
  `legged_candidate_factor_visual_validation_passed`.

The pass recommendation is
`N8F_merge_tag_then_N8G_feedback_ekf_foundation`, but N8G is not implemented in
N8F1.

Always preserved:

- no paper performance claim
- no FGO feedback
- no output substitution
- no trace/final_v23 solver input or tuning
- no Go2 truth claim

