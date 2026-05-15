# N8K6 A0 Feedback Applicability Fix

N8K6 is a targeted blocker fix for PR #48 after the N8K final merge review.
N8K5 had already completed the cross-category semantic fix; the final review
left only the A0 feedback applicability conflict. This is not N9A, not N9B,
not a merge/tag stage, and not a broad plot-system redesign.

## Blocker

`A0_source_backed_ekf_baseline` is the formal source-backed EKF baseline. Its
semantic role is `baseline_no_feedback`, and its N8K metrics record feedback
accept/reject as `0/0`.

The previous plot data path detected raw feedback rows for A0 and classified
A0 as feedback-applicable. That was a reporting/plot classification error:
raw detected rows are not equivalent to feedback applicability for a
no-feedback baseline.

The reproduced blocker values are:

- raw feedback rows detected: `175`
- effective feedback rows for plotting before fix: `175`
- effective feedback rows for plotting after fix: `0`
- feedback accept/reject: `0/0`

## Fix

N8K6 separates raw detected rows from effective plotting rows:

- `raw_feedback_rows_detected` remains recorded for audit.
- `effective_feedback_rows_for_plotting` is `0` for `baseline_no_feedback`.
- A0 feedback-specific plots are documented not-applicable.
- A0 raw feedback rows are ignored for feedback plotting with reason
  `variant_role_baseline_no_feedback`.

The fix is limited to reporting and plot data classification. It does not
modify solver math, feedback policy, runtime NAV/STD/EVAL artifacts, or any
formal ablation result.

## Boundaries

- no algorithm change
- no feedback policy tuning
- no degradation matrix run
- no trace/final_v23 tuning
- no output substitution
- no paper performance claim
- no outperform final_v23 claim

After N8K6, the correct next step is to rerun the N8K final merge review.
