# N8K6 A0 Feedback Applicability Fix Prompt

Use this prompt when continuing the targeted N8K6 blocker fix.

The stage is not N9A, not N9B, not merge/tag, and not a broad plot repair.
N8K5 already completed the cross-category semantic fix. The only remaining
final-review blocker is A0 feedback applicability:

- `A0_source_backed_ekf_baseline` is `baseline_no_feedback`.
- A0 metrics feedback accept/reject are `0/0`.
- Raw feedback rows may be detected, and the reproduced count is `175`; they
  are diagnostic-only for A0.
- Effective feedback rows for A0 plotting must be `0`.
- A0 feedback-specific figures must be documented not-applicable.

Do not change algorithms, tune feedback policy, run degradation matrices, use
trace/final_v23 for tuning, or make paper performance claims.
