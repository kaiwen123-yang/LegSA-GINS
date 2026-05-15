# N8K Final Merge Review

This review is the pre-merge gate for PR #48. The original review failed on
the A0 feedback applicability blocker. N8K6 is the targeted follow-up fix for
that blocker; PR #48 still must go through a fresh final merge review before
merge/tag.

## Git State

- PR #48 head commit: `4b4062d22124dff3c51a36026f05f25730f98261`
- PR #48 state: open / unmerged
- PR #21 state: open / unmerged
- N8K5 commit: `4b4062d22124dff3c51a36026f05f25730f98261`

## N8K5 Decision

- N8K5 decision: `BY2_formal_ablation_cross_category_semantic_fix_complete`
- N8K5 recommended next stage: `N8K_final_merge_review_then_N9A_BY2_full_plot_audit`

## Direct Figure Rescan

- PNG total count: `2850`
- variant count: `30`
- per-variant PNG count: `95` for all 30 variants
- per-variant category dirs: `14` for all 30 variants
- same-category exact duplicate count: `0`
- same-variant cross-category exact duplicate count: `0`
- blocking duplicate after count:
  - `03_velocity/velocity_residual_time.png` vs `07_compare/compare_velocity_error.png`: `0`
  - `06_observation_quality/feedback_accept_reject_time.png` vs `07_compare/compare_feedback_delta.png`: `0`

## Remaining Global Duplicates

- global exact duplicate groups after N8K5: `8`
- classification: all 8 are cross-variant-only, same-category, same-filename groups.
- non-blocking explanation: these duplicate groups are identical runtime/derived visualizations across variants with the same figure filename. They are not same-variant duplicates and are not cross-category semantic leakage.

## Plot Semantic Gates

- placeholder remaining: `0`
- applicable placeholder remaining: `0`
- semantic mismatch remaining: `0`
- feedback empty-axis remaining: `0`
- N8K4 semantic filename mismatch after: `0`
- N8K3 same-category duplicate after: `0`
- N8K2 applicable placeholder remaining: `0`

## Not Applicable And Derived Data

- `compare_feedback_delta_not_applicable_count`: `21`
- `feedback_accept_reject_time_not_applicable_count`: `21`
- not-applicable panels must carry explicit reasons. N8K5 records no-feedback reasons for the affected feedback plots.
- derived data labels count: `20`
- derived/surrogate visualizations are labeled as `derived_from_n8k_metrics_and_baseline_nav` where applicable and are not paper performance evidence.

## A0 Feedback Applicability

A0 is a merge blocker in this final review.

Evidence:

- `N8K_BY2_FORMAL_ABLATION_SPEC.json` maps `A0_source_backed_ekf_baseline` to `n8j_source_variant = baseline_no_feedback`.
- The A0 active module list is `source_backed_ekf`.
- `N8K_BY2_FORMAL_ABLATION_METRICS_REPORT.json` records A0 `feedback_accept = 0` and `feedback_reject = 0`.
- `N8K2_REAL_PLOT_DATA_LOAD_REPORT.json` records A0 `feedback_rows_per_variant = 175`, `nav_rows = 56643`, `std_rows = 56643`, `eval_rows = 56643`, and `data_source = n8j_runtime_eval_nav`.
- `N8K5_CROSS_CATEGORY_SEMANTIC_FIX_REPORT.json` treats A0 feedback plots as applicable runtime feedback plots, not documented not-applicable panels.

Conclusion: A0 appears to be a no-feedback baseline by design, but the N8K2 to
N8K5 plot pipeline classifies it as feedback-applicable. This must be resolved
before merge.

## Validation

- N8K5 audits: passed
- N8K4/N8K3/N8K2/N8K regression audits: passed
- no-trace-solver-input audit: passed
- pytest: `874 passed, 1 warning`
- CMake configure/build: passed

## Hygiene

- no runtime artifacts or generated figures committed
- no local absolute path leak
- `/home/kaiwen/KF-GINS` unchanged
- submodule gitlink unchanged
- no algorithm changes
- no degradation matrix run
- no trace/final_v23 tuning
- no paper performance claim

## Decision

- status: `N8K_final_merge_review_failed`
- ready_to_merge: `false`
- ready_to_tag: `false`
- recommended_next_stage: `targeted_fix_only_if_blocker_is_real`

## N8K6 Targeted Follow-Up

N8K6 resolves the A0 feedback applicability classification error without
changing algorithms or runtime results:

- A0 variant role: `baseline_no_feedback`
- A0 raw feedback rows detected: `175`
- A0 effective feedback rows for plotting after fix: `0`
- A0 feedback accept/reject: `0/0`
- A0 raw rows ignored reason: `variant_role_baseline_no_feedback`
- A0 feedback-specific figures are documented not-applicable
- N8K6 decision: `A0_feedback_applicability_fix_complete`
- N8K6 recommended next stage: `rerun_N8K_final_merge_review`

This document remains the record of the failed review; the merge/tag readiness
booleans should only be set by the rerun final review.
