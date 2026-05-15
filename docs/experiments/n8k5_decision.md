# N8K5 Decision

Decision statuses:

- `cross_category_semantic_fix_failed`: blocking cross-category duplicates
  remain.
- `cross_category_semantic_fix_failed_empty_feedback_axes`: non-feedback
  variants still contain empty feedback axes.
- `cross_category_semantic_fix_failed_semantic_mismatch`: semantic roles remain
  inconsistent with filenames.
- `BY2_formal_ablation_cross_category_semantic_fix_complete`: all blocking
  cross-category duplicates are fixed and no semantic/placeholder regression is
  present.

The passing recommendation is
`N8K_final_merge_review_then_N9A_BY2_full_plot_audit`.

This is a plotting-audit decision only. It does not change algorithm math,
feedback gate, covariance, window, mode, or any solver input boundary.
