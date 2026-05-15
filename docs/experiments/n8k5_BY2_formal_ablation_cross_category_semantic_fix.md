# N8K5 BY2 Formal Ablation Cross-Category Semantic Fix

N8K5 continues PR #48 on the existing N8K branch. It is not N9A, not N9B, and
not merge review.

The stage fixes same-variant cross-category exact duplicate plots that remained
after N8K4:

- `03_velocity/velocity_residual_time.png` must not be reused as
  `07_compare/compare_velocity_error.png`.
- `06_observation_quality/feedback_accept_reject_time.png` must not be reused
  as `07_compare/compare_feedback_delta.png`.

N8K5 keeps the solver and feedback policy fixed. It does not run the full
degradation matrix, does not use trace/final_v23 for tuning, and does not make a
paper performance claim.

Runtime output roots are passed as command-line role-specific inputs only. The
tracked repository stores only code, audits, tests, and documentation.
