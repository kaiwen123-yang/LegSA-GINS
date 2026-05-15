# N8K Final Merge Review After N8K6

This is the rerun final merge review for PR #48 after the targeted N8K6 A0
feedback applicability blocker fix. It is a review gate only: it does not merge
PR #48, does not create an N8K tag, and does not start N9A or N9B.

## Git State

- PR #48 head commit: `940805deb35e8d18bab358a5e01225a0bcdc8463`
- PR #48 state: open / unmerged
- PR #21 state: open / unmerged
- previous failed review commit: `11bb17a7daf10f51b24c9dc0388c6348dc848403`
- N8K6 blocker fix commit: `940805deb35e8d18bab358a5e01225a0bcdc8463`

## N8K6 Blocker Resolution

- A0 blocker status: resolved
- A0 variant role: `baseline_no_feedback`
- A0 feedback applicable after N8K6: `false`
- A0 raw feedback rows detected: `175`
- A0 raw feedback rows role: diagnostic only
- A0 effective feedback rows for plotting: `0`
- A0 feedback accept/reject: `0/0`
- A0 raw rows ignored: `true`
- A0 raw rows ignored reason: `variant_role_baseline_no_feedback`
- A0 feedback-specific figures: documented not-applicable

Feedback applicability after N8K6:

- applicable variant count: `8`
- not-applicable variant count: `22`
- applicable variants: `A7_feedback_default_gate`, `A8_feedback_selected_conservative_gate`, `B0_reject_all_sanity`, `B1_velocity_only_feedback`, `B2_attitude_only_feedback`, `B3_velocity_attitude_feedback`, `B4_diagnostic_PVA_feedback`, `C0_selected_feedback_full`
- not-applicable variants: `A0_source_backed_ekf_baseline`, `A1_plus_raw_doppler_ekf`, `A2_plus_source_aware_lsim_oim`, `A3_plus_go2_horizontal_velocity`, `A4_plus_go2_proprioceptive_joint`, `A5_plus_legged_candidate_fgo_factors_no_feedback`, `A6_no_feedback_fgo_selected_stack`, `C1_selected_without_raw_doppler`, `C2_selected_without_source_aware`, `C3_selected_without_go2_joint`, `C4_selected_without_legged_candidate_factors`, `C5_selected_without_yawrate_between`, `C6_selected_without_relative_odometry`, `C7_selected_without_foot_kinematic`, `C8_selected_without_contact_aware_weighting`, `C9_selected_without_feedback`, `D0_no_feedback_fgo_default`, `D1_no_feedback_fgo_weak_yaw_smoothness`, `D2_no_feedback_fgo_conservative_policy`, `D3_no_feedback_fgo_raw_receiver_balanced`, `D4_no_feedback_fgo_go2_joint_x2`, `D5_no_feedback_fgo_dual_yaw_x2`

## Direct N8K6 Figure Rescan

- PNG total count: `2850`
- variant count: `30`
- per-variant PNG count: `95` for all 30 variants
- per-variant category directories: `14` for all 30 variants
- same-category exact duplicate count: `0`
- same-variant cross-category exact duplicate count: `0`
- blocking duplicate pairs after: `[]`
- placeholder remaining: `0`
- applicable placeholder remaining: `0`
- semantic mismatch remaining: `0`
- feedback empty-axis remaining: `0`

## Remaining Global Duplicates

- remaining global exact duplicate groups: `8`
- remaining duplicate classification: non-blocking
- verification: all remaining exact duplicate groups are cross-variant-only,
  same-category, same-filename groups.
- not a same-variant duplicate: `true`
- not a cross-category duplicate: `true`
- semantic leakage detected: `false`

These groups represent identical figure filenames shared across variants. They
do not indicate same-variant copy leakage or cross-category semantic leakage.

## Derived Data Labels

- derived data labels count: `20`
- derived/surrogate label: `derived_from_n8k_metrics_and_baseline_nav`
- claim boundary: derived/surrogate visualizations remain labeled and are not
  used for paper performance claims.

## Validation

- N8K6 audits: passed
- N8K5 audits: passed
- N8K4 audits: passed
- N8K3 audits: passed
- N8K2 audits: passed
- N8K audits: passed
- no-trace-solver-input audit: passed
- pytest: `887 passed, 1 warning`
- CMake configure/build: passed

## Hygiene

- no runtime artifacts or generated figures committed
- no local absolute path leak
- `/home/kaiwen/KF-GINS` tracked diff unchanged
- submodule gitlink unchanged
- no algorithm changes
- no degradation matrix run
- no trace/final_v23 tuning
- no paper performance claim
- no outperform final_v23 claim
- worktree clean after review commit

## Decision

- status: `N8K_final_merge_review_passed`
- ready_to_merge: `true`
- ready_to_tag: `true`
- recommended_next_stage: `merge_PR_48_create_N8K_tag_then_start_N9A_BY2_full_plot_audit`
