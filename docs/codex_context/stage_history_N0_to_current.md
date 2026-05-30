# Stage History N0 To Current

## N0-N3: Boundary And Source Policy

Established that LegSA-GINS is not a simple plotting task. The project builds a source-backed GNSS/INS/legged fusion chain while keeping trace truth and final_v23 out of solver inputs.

Key boundaries:

- trace is evaluation-only.
- final_v23/KF-GINS is reference/sanity/evaluation boundary only.
- BY2 is the current primary dataset.
- Windows audit workspace and WSL algorithm source repository are separate.

## N4: Source-Backed EKF Backbone

Built and audited the EKF backbone:

- IMU mechanization.
- state and covariance propagation.
- GNSS position update.
- receiver velocity update where valid.
- dual yaw update.
- state feedback.
- NAV / STD / EVAL_NAV / RUN_MANIFEST outputs.
- provenance and no-trace/no-final_v23 input boundary checks.

## N5: Raw Doppler EKF Factor

Activated RTKLIB-backed Raw Doppler source. Raw Doppler is not NAV-PVT receiver velocity and not the 15-column `.gnss` velocity proxy. It became a real nonzero EKF frontend factor.

## N6: Source-Aware Weighting

Introduced source-aware LSIM/OIM weighting. The conservative policy is acceptable as an R-scaling layer, with stress evidence limited.

## N7: Go2 Proprioceptive Joint Factor

Mature factor definition:

```text
Go2 proprioceptive joint factor = Go2 roll/pitch + Go2 horizontal velocity
```

Not allowed as truth: Go2 absolute position, Go2 yaw, Go2 vertical velocity, and contact truth.

## N8A-N8E: No-Feedback FGO Backend

Built FGO dataset, factor registry, yaw wrap fix, smoothness policy review, Raw Doppler FGO, Go2 joint FGO, and formal engineering ablation.

Important fixes:

- N8A1/N8A2: yaw wrap bug found and fixed.
- N8C2/N8C3: Raw Doppler FGO solver injection bug found and fixed.
- N8D/N8E: weight review and formal engineering ablation with caveats.

## N8F: Legged Candidate Factors

Activated candidate legged factors:

- contact-aware weighting.
- foot kinematic velocity factor.
- Go2 yaw-rate between factor.
- Go2 relative odometry between factor.

These are source/candidate factors, not truth.

## N8G-N8J: FGO Feedback EKF

Selected policy:

```text
mode=horizontal_velocity_attitude_feedback
gate=combined_conservative_gate
covariance=inflation_auto_from_residual_proxy
window=5.0s/1.0s
position_feedback=disabled
feedback_type=EKF pseudo-measurement / error-state update
selected_feedback accepted/rejected=151/24
observations=175
```

Conclusion: engineering closure is demonstrated on BY2 clean, but performance improvement is small. Claims must be limited.

## N8K-N8K6: Formal Ablation Plot Audit

N8K produced many formal ablation figures, but applicable=True figures had placeholder, low-information, duplicate-template, semantic mismatch, and applicability problems.

Resolution chain:

- N8K2: remove applicable placeholders.
- N8K3: fix same-category duplicate semantic plots.
- N8K4: fix semantic filename alignment.
- N8K5: fix same-variant cross-category duplicates.
- N8K6: fix A0 feedback applicability blocker.

Final state:

- `status=N8K_final_merge_review_passed`.
- PR #48 merged.
- Tag `N8K-v0.1-BY2-formal-ablation-plot-audit` exists.

## N9A: BY2 Normal Clean

N9A completed the BY2 normal clean audit route after earlier failed attempts exposed output lineage, frame alignment, metric sanity, zero-line, feedback/contact, and yaw convention risks.

## N9B0-N9B0C: Degradation Groundwork

N9B0, N9B0A, N9B0A1, N9B0A2, N9B0B, and N9B0C completed the initial degradation preparation route.

## N9B1A-N9B1G2: Pilot And Preparation Route

Completed:

- N9B1A and N9B1A1.
- N9B1C through N9B1G2.
- N9B1D through N9B1D4.

Current pilot sources:

- N9B1D4 is the current technical pilot source.
- N9B1E passed with C yaw caution and is the current pilot visual/go-no-go source.

## N9B2A-N9B2B: Full-Matrix Preparation And Path Lock

- N9B2A completed.
- N9B2A1 completed.
- N9B2A/N9B2A1 are full-matrix preparation sources.
- N9B2B completed path lock.
- N9B2B locks Windows plus WSL aliases and the future by2-huitu output alias.
- Native Ubuntu migration is deferred.
- Old Chinese output root is read-only historical evidence.
- Future BY2/N9B outputs use `BY2_N9B2_*` aliases.

## N9B2B1-N9C0: Staged N9B Execution And Global Consolidation

N9B2B1 completed the documentation/context update after path lock.

The staged N9B route then completed through N9C0:

- Batch 0 normal smoke complete.
- Batch 1 deterministic complete.
- Batch 2 position noise complete.
- Batch 3 position spike complete.
- Batch 4 yaw noise complete.
- Batch 5 core module-disable complete; module-stress remains deferred.
- Batch 6 selected mixed cases complete.
- final_v23 external baseline complete and integrated.
- N9C0 global staged consolidation precheck complete.

N9C0 active final-only metrics table:

```text
source=<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE
rows=825
```

No full monolithic N9B2 was run. `B_gnss_downsample_2Hz` remains invalid and superseded.

## Historical N9C0A: Context Update After Global Consolidation

`N9C0A_CONTEXT_UPDATE_AFTER_GLOBAL_CONSOLIDATION` updated tracked docs/context and wrote audit reports only. It did not authorize solver, evaluator, N9B2, random generation, degraded-input generation, N9C1 figure generation, or paper claims. Its immediate next-stage recommendation is historical after the later N9E/N9F evidence review.

Readiness after pass:

```text
ready_for_N9C1_consolidated_figure_generation=true
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

Recommended next stage:

```text
human_review_N9C0A_then_N9C1_consolidated_figure_generation
```

## N9E: Active Nine-Factor FGO/Legged Logger Review

N9E reviewed active nine-factor FGO and legged logger evidence after the N9C figure/evidence repair route. It completed with a blocked-logger decision:

```text
N9E_logging_blocked_report_and_obsidian_sync_complete
complete_nine_factor_FGO_claim=false
ready_for_paper_claims=false
```

N9E did not authorize relabeling `LegSA_full_EKF` as active nine-factor FGO. It found aggregate/provider/candidate/missing evidence classes that require a new reviewed algorithm design before complete active evidence claims.

## N9F0_TO_N9F2: Active Nine-Factor FGO Legged Design Materialization

N9F0_TO_N9F2 reviewed N9E, N9C1F, N9C0D, and code-context evidence for active nine-factor FGO claims. The stage produced runtime-only design matrices and an export-clean design package.

Decision:

```text
status=N9F_legsa_9f_design_package_complete
ready_for_implementation_review=true
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=N9F6_HUMAN_REVIEW_LEGSA_9F_IMPLEMENTATION_PLAN
```

N9F did not run solvers, evaluators, degradation generation, random generation, representative active-nine-factor runs, or figure generation. It did not modify algorithm source, math, or config wiring. The central conclusion is that `LegSA_full_EKF` must not be relabeled as active nine-factor FGO; current evidence requires a new active nine-factor FGO algorithm design and implementation review before representative runs.

## N9F6A_TO_N9F7: Source-Code Forensic Audit And Design Package

N9F6A re-audited the real Windows/WSL source code from zero and passed reviewer gate before Step 2. The audit distinguished code existence, provider existence, config enablement, runner mapping, solver instantiation, factor/update rows, and residual/cost/log evidence.

Decision:

```text
status=N9F7_substantial_algorithm_design_required
ready_for_algorithm_design_review=true
ready_for_implementation_review=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=manual_algorithm_design_review
```

The source answer is that robot kinematics/contact/legged modeling exists, but mainly as provider, diagnostic, offline no-feedback, or candidate factor code. Active `LegSA_full_EKF` uses provider-dependent Go2 weak attitude / horizontal velocity EKF updates and selected-feedback EKF pseudo-measurements; it does not instantiate a complete active nine-factor FGO solver with row-level residual, Jacobian, and cost logs. N9F7 therefore produced a Path C design/data-provider package only and did not implement code, run solvers/evaluators, generate figures, run representative cases, or run a full matrix.

## N9F7A_TO_N9G0: Git Boundary And Manual LegSA 9F FGO EKF Design Review

N9F7A audited the then-current Git/PR publication boundary. The local branch was ahead of the PR #52 remote head and included an existing unpushed reporting/test code commit before the docs lock. Runtime roots and Obsidian roots remained untracked. Current-stage docs were alias-only, and PR push was blocked until the human resolved the non-doc ahead commit boundary.

N9G0 produced a manual design package for the future `LegSA_9F_FGO_EKF` candidate. It distinguishes the current verified `LegSA_full_EKF` EKF/feedback algorithm from a separate active-FGO candidate and defines the state/window design, nine-factor design, matrix/residual model, provider contracts, logger schema, implementation roadmap, validation protocol, and risk register.

Decision:

```text
status=N9G0_publish_blocked_by_git_boundary
design_review_complete=true
ready_for_N9G1_phase1_implementation=human_decision_required
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=resolve_git_boundary
```

N9G0 did not implement `LegSA_9F_FGO_EKF`, run solvers, run evaluators, generate random or degraded inputs, run N9B2, generate figures, merge or close PR #52, create tags, or make paper claims.

## N9G0A: Git Boundary Resolution

N9G0A resolved the Git boundary recorded by N9F7A/N9G0. PR #52 head is synced to `9ceba928`. PR #52 remains open/unmerged unless the human explicitly approves merge, closure, or tag actions.

Decision:

```text
status=N9G0A_git_boundary_resolved
pr_52_head_synced_to=9ceba928
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION
```

## N9G1A: Context Lock Before LegSA 9F Implementation

N9G1A locks the context before any `LegSA_9F_FGO_EKF` implementation. It splits N9G1 into `N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION` and later `N9G1B_PHASE1_PROVIDER_FACTOR_LOGGER_NORMAL_SMOKE_ONLY`.

`LegSA_full_EKF` remains the current verified EKF/feedback algorithm. `LegSA_9F_FGO_EKF` is a separate new candidate. `complete_nine_factor_FGO_claim=false` and `ready_for_paper_claims=false` remain locked.

N9G1B, if approved later, is limited to Phase 1 provider/factor/logger/normal-smoke work. Representative validation is deferred to N9G2. Full matrix, replot, and report stages are deferred to N9G3/N9G4 if applicable.

Decision:

```text
status=N9G1A_context_lock_complete_after_validation
ready_for_N9G1B_phase1_provider_factor_logger_normal_smoke=human_decision_required
ready_for_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=human_review_N9G1A_then_decide_N9G1B
```

## N9G1B: LegSA 9F Phase 1 Provider/Factor/Logger

N9G1B created a separate `LegSA_9F_FGO_EKF` candidate identity/config boundary, provider/factor audit helper, active-FGO logger schema, legged diagnostic logger schema, safety gate, and runtime reports.

Normal smoke was not run. The gate blocks execution because provider contracts are not ready for active factors, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled. `LegSA_full_EKF` remains the current verified EKF/feedback algorithm and is not relabeled.

Decision:

```text
status=N9G1_context_locked_provider_or_factor_blocked
normal_smoke_status=N9G1B_normal_smoke_not_run_blocked_by_gate
complete_nine_factor_FGO_claim=false
ready_for_N9G2_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=fix_provider_or_factor_model
```

## N9G1C-E: Provider Contract Resolution, Backend Audit, Normal-Smoke Gate

N9G1C-E resolved the locked normal clean source and core provider contracts for the separate `LegSA_9F_FGO_EKF` candidate. The provider contract decision is partial accepted: GNSS position/velocity/yaw, Raw Doppler, Go2 joint/attitude/horizontal velocity, and same-case feedback observations are resolved. Foot kinematic velocity, yaw-rate, relative odometry, contact probability, and slip risk remain candidate-only or aggregate evidence and are not active factor claims.

The active backend audit found only offline/no-feedback/candidate FGO support. The active nine-factor FGO backend remains unavailable, candidate solver execution remains disabled, no factor wiring rows are active, and normal smoke was not run.

Decision:

```text
status=N9G1E_active_backend_blocked
provider_contract_decision=N9G1C_provider_contracts_partial_accepted
backend_decision=N9G1D_active_backend_blocked
normal_smoke_status=N9G1E_normal_smoke_not_run_blocked_by_gate
complete_nine_factor_FGO_claim=false
ready_for_N9G2_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=implement_active_fgo_backend_or_reframe_scope
```

## BY3A4C: Git-History Yaw Reference Reconstruction

BY3A4C recovered the historical BY2/N4 yaw-reference repair from git history, tracked docs/source, PR metadata, and runtime evidence. It verified that N4H2 old yaw around 93 deg was invalidated by N4H2D, that N4H2D selected `official_ref_sign_minus`, and that fresh replay yaw was about 1.98 deg against the reconstructed dual official reference.

Recovered and diagnostic profiles were applied to existing BY3A3 outputs only. No BY3 yaw truth/reference profile was accepted, so BY3 yaw is `not_evaluable`; BY3A3/BY3A4A yaw metrics remain historical invalid-reference evidence. Position/up metrics may support position/up-only planning, with yaw degradation claims disabled.

Decision:

```text
status=BY3A4C_yaw_not_evaluable_position_only_generalization_ready
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=position_up_only
yaw_degradation_claims=false
ready_for_paper_claims=false
recommended_next_stage=BY3B_POSITION_ONLY_DEGRADATION_PLANNING_OR_HUMAN_REVIEW
```
## BY3A5/BY3A5B Dual Yaw Input Source Repair

BY3A5 audits the BY3 dual-yaw input source and correctly confirms the old BY3 15-column yaw was wrong-source. BY3A5's HDT replacement policy is diagnostic/rejected/superseded for mainline BY3 and must not be reused as solver yaw input.

BY3A5B supersedes BY3A5 for mainline yaw input repair. It reconstructs BY3 dual yaw from GNSS1/GNSS2 A1_dual_diff short-baseline absolute positions, rejects GNSS status long-baseline `rel_pos_n/e/d`, applies BY2 sign/lateral conversion equivalent to `baseline_heading+90`, and uses fixed_1p5 yaw_std.

BY3A5B normal-only rerun completed for LegSA_full_EKF, single_antenna_gnss1_status_KF_GINS, and final_v23_dual_antenna_EKF. The final decision was:

```text
status=BY3A5B_a1_dual_diff_input_repaired_but_yaw_reference_issue_remains
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=position_up_only
yaw_degradation_claims=false
ready_for_paper_claims=false
recommended_next_stage=human_review_yaw_reference_or_position_only_BY3B
```

BY3A5B is superseded by BY3A6/BY3A7 for current BY3 readiness.

## BY3A6 Trace Truth Initatt Gate Forensic

BY3A6 locked the trace file as the BY3 evaluation truth reference, confirmed the evaluator uses raw numeric trace fields rather than unsafe processed trace lat/lon fields, validated base_time alignment, audited BY3A5B A1_dual_diff input, confirmed stale first-row initatt in stage1/LegSA, and repaired initatt to use the first dual GNSS/A1 yaw at or after the requested starttime.

BY3A6 reran BY3 normal only for LegSA_full_EKF, single_antenna_gnss1_status_KF_GINS, and final_v23_dual_antenna_EKF. No degradation, artificial degradation, parameter retuning, trace solver input, output substitution, or paper-claim work was performed. Yaw still fails after initatt repair, while position/up remains sane.

The BY3A6 decision was:

```text
status=BY3A6_position_up_ready_yaw_issue_remaining
ready_for_BY3_degradation_matrix_planning=false
ready_for_BY3_degradation_matrix_planning_scope=none_pending_human_review
yaw_degradation_claims=false
ready_for_paper_claims=false
recommended_next_stage=human_review_yaw_issue_or_position_only_BY3B
```

## BY3A7 A1 Yaw Dynamic Quality IMU Gate Repair

BY3A7 accepted BY3A6 trace/evaluator/base_time/initatt findings and audited the remaining yaw failure. A1_dual_diff remained source-valid with dynamic-quality caution. Yaw update code/wrap/gate configuration was valid; the confirmed root cause was BY3 Go2 IMU preprocessing, where gyro bias was estimated from a moving segment after selected Go2 start.

BY3A7 repaired a BY3A7-local IMU input using pre-motion source gyro bias, preserved the existing FLU-to-FRD conversion, A1 yaw source, fixed_1p5 yaw_std, yaw gate thresholds, and solver parameters, and reran BY3 normal only. LegSA_full_EKF yaw RMSE was about 5.26 deg and final_v23_dual_antenna_EKF yaw RMSE was about 4.30 deg. No BY3 degradation, trace solver input, HDT solver input, final_v23 solver input, gate relaxation, parameter retuning, output substitution, PR merge/closure, tag, or paper claim was performed.

The current BY3 decision is:

```text
status=BY3A7_yaw_salvaged_ready_for_full_BY3_degradation
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=full_after_human_review
ready_for_paper_claims=false
recommended_next_stage=BY3B_DEGRADATION_MATRIX_PLANNING_AND_PRECHECK
```

## BY3A8 Yaw Error Budget Safe Repair

BY3A8 accepted BY3A7 and audited the remaining 4-5 deg dual-yaw normal error. The A1 observation lower-bound audit used the BY3 trace as evaluation-only reference and found A1-vs-trace heading RMSE about 24.06 deg, p95 about 31.78 deg, max about 167.29 deg, and circular mean about -15.06 deg. Source-quality-only checks found 6 objective invalid A1 solver-candidate epochs, so an objective mask cannot explain or repair the broad observation error.

BY3A8 found no safe additional repair: BY3A7 pre-motion IMU bias remains accepted, no metadata-backed time-lag issue was found, yaw gate behavior is acceptable under unchanged thresholds, yaw continuity/code was not identified as a bug, and feedback worsened yaw relative to stage1 but requires a separate human-approved review. No BY3 normal rerun, solver/evaluator run, degradation, trace solver input, HDT/long-relpos fallback, gate relaxation, parameter retuning, PR merge/closure, tag, or paper claim was performed.

Current BY3A8 decision:

```text
status=BY3A8_yaw_limited_but_position_up_ready
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=position_up_with_diagnostic_yaw
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=BY3B_POSITION_UP_WITH_DIAGNOSTIC_YAW_PLANNING
```

## BY3B Position Up With Diagnostic Yaw Planning

BY3B imported the BY3A8 decision and completed the BY3 degradation planning/precheck stage. It locked BY3A7 repaired IMU preprocessing and the BY3A5B/BY3A7 A1_dual_diff short-baseline yaw input for future BY3 execution; HDT, GNSS status long-baseline `rel_pos_n/e/d`, old BY3 IMU, BY2 feedback, and BY3 normal feedback reuse remain forbidden.

BY3B planned 118 case-seed units: 75 position/up-primary units and 43 diagnostic-yaw units, with 311 future solver rows if a later human-approved execution stage runs them. It created family scope, case matrix, seed plan, provider/feedback dependency plan, dry-run command templates, evaluator/metric policy, figure/case-review plan, batch plan, context updates, and Obsidian notes. It did not run degradation, generate degraded inputs, generate random arrays, run solvers, run evaluators, generate figures, retune parameters, make paper claims, merge PR #52, close PR #52, or create a tag.

Current BY3B decision:

```text
status=BY3B_position_up_diagnostic_yaw_plan_complete
ready_for_BY3C_position_up_degradation_execution=true
human_final_decision_required_before_execution=true
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=BY3C_POSITION_UP_DEGRADATION_EXECUTION_BATCH0_TO_BATCH3_LONG_PIPELINE
```

## BY3C Position Up Degradation Execution Batch0-Batch3

BY3C executed the human-approved position/up-primary degradation subset after BY3B. It locked BY3A7 repaired IMU preprocessing, BY3A5B/BY3A7 A1_dual_diff short-baseline yaw input, BY3A2 Raw Doppler provider, BY3 Go2 priors, trace as evaluation-only reference, single-baseline input, final_v23 external-baseline pattern, and selected-feedback same-case policy.

BY3C completed Batch 0 normal parity, Batch 1 deterministic A_outage/B_ratio_downsample/E_position_std_inflation, Batch 2 C_position_noise mild/medium/strong seeds 0..9, and Batch 3 D_position_spike mild/medium/strong seeds 0..9. It produced degraded inputs, approved random arrays for Batch 2/3 only, solver outputs, official evaluations, same-case feedback, 213 final metric rows, figures, case reviews, consolidated review, context updates, and Obsidian notes. It did not execute H_dual_yaw_noise, E_yaw_std_inflation, mixed cases, module-disable cases, `LegSA_9F_FGO_EKF`, nonredundant FGO extension, or a full monolithic BY3 matrix.

Current BY3C decision:

```text
status=BY3C_batch0_to_batch3_position_up_degradation_complete
ready_for_BY3D_diagnostic_yaw_or_mixed_planning=true_after_human_review
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=human_review_BY3C_then_BY3D_DIAGNOSTIC_YAW_OR_MIXED_PLANNING
```

## BY3C1/BY3Y1 Position Up Review And Yaw Diagnostic Explanation

BY3C1/BY3Y1 reviewed existing BY3C Batch0-Batch3 evidence only. It audited result integrity, built BY3 three-scheme position/up tables, compared overlapping BY2/BY3 families using active BY2 N9C0D/N9C2B material, generated review figures from existing metrics only, wrote family and case-review packages, produced export-clean summaries, and explained BY3 yaw as diagnostic-only from BY3A5B-BY3A8 evidence.

The stage did not run solvers, evaluators, degraded-input generation, random generation, parameter retuning, trace/final_v23 solver input, PR merge/closure/tag actions, or paper-claim work. Result integrity passed for 71 BY3 case units and 213 final metric rows. BY3C1 classified B downsample as `generalizes_consistently`; normal, A outage, E position std, C position noise, and D position spike remained same-order or mixed. BY3Y1 preserved the yaw diagnostic boundary: wrong-source yaw, stale initatt, and moving-segment IMU bias had been repaired, while A1 observation quality remained the main limitation.

Current BY3C1/BY3Y1 decision:

```text
status=BY3C1_position_up_review_and_yaw_diagnostic_complete
ready_for_BY3D_or_other_dataset_planning=true_after_human_review
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=human_review_BY3C1_then_BY3D_mixed_position_up_or_other_dataset_planning
```

## GEN1 BY2-BY3 Generalization Report And BY3 Figure Organization

GEN1 reviewed existing BY2 and BY3 metric/figure evidence only. It built BY2 and BY3 metric inventories with 213 comparable rows each across 71 case units, mapped normal/A/B/E/C/D families, produced cross-dataset three-scheme family/case/delta summaries, generated cross-dataset figures from existing metrics only, inventoried existing BY3 figures, and created a copy-only organized BY3 figure summary.

The stage copied 874 unique nonempty BY3 figure files into `<BY3_FIGURE_SUMMARY_ROOT>` while preserving original runtime figures. It also created export-clean tables/reports and local Obsidian notes. BY3 yaw remained diagnostic-only throughout.

Current GEN1 decision:

```text
status=GEN1_cross_dataset_report_and_BY3_figure_organization_complete
ready_for_next_stage=true_after_human_review
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=human_review_GEN1_then_decide_BY3D_or_other_dataset
```

## XB1A0-E Poor-GNSS Bootstrap, XB1A1 Blocker Triage, And XB1A2 A1 Reaudit

XB1A0_TO_XB1E completed the first poor-GNSS repeated-experiment bootstrap for XB1 / PG1_20260105_122513. It generated literature criteria, data inventory, GNSS quality profile, kick-event alignment, body IMU from `<XB1_BODY_SOURCE>`, Go2 priors, input/provider reports, figures, case review, Obsidian notes, and export-clean material. XB1 GNSS quality was classified severe, and A1 dual-yaw plus Raw Doppler/provider gates blocked normal solver/evaluator execution.

XB1A1_BLOCKER_TRIAGE_RAW_DOPPLER_A1_YAW_AND_MAINLINE_NORMAL_GATE then repaired the Raw Doppler provider blocker through the accepted RTKLIB/RINEX/helper path using WSL gcc/helper execution. The source-backed provider is schema-valid with 1809 rows. A1 short-baseline dual yaw remained invalid due GNSS quality/geometry, with about 1.95 percent objective valid epochs and nonphysical short-baseline length. `LegSA_full_EKF` and `final_v23_dual_antenna_EKF` normal runs remained blocked/not applicable; `single_antenna_gnss1_status_KF_GINS` completed normal official evaluation as a diagnostic baseline only.

XB1A2_A1_DUAL_DIFF_RELPOS_DIFFERENCE_REAUDIT_AND_NORMAL_RERUN then corrected the A1 source-provenance issue. XB1A1 had not audited the BY2/process_data-compatible status `rel_pos_gnss2-rel_pos_gnss1` dual-difference path. XB1A2 recovered that BY2 status path and the BY3A5B absolute-position repair path, audited both for XB1, and found both nonphysical. The BY2 relpos-difference candidate had 356 rows, 7 physical-band epochs, valid ratio about 1.97 percent, median length about 9.18 m, p95 about 50.96 m, and max about 131.70 m. No repaired dual-yaw input was generated, and no dual-yaw normal rerun was forced.

Current XB1A1 decision:

```text
status=XB1A1_partial_baseline_only_completed
raw_doppler_provider=XB1A1_raw_doppler_provider_ready
a1_dual_yaw=XB1A1_A1_dual_yaw_invalid_due_GNSS_quality
normal_run_status=XB1A1_normal_partial_completed
quality_aware_branch=XB1A1_quality_aware_branch_recommended
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_XB1_degradation_or_PG2_planning=false
ready_for_paper_claims=false
recommended_next_stage=human_review_XB1A1_then_quality_aware_branch_or_PG2_source_review
```

Current XB1A2 decision:

```text
status=XB1A2_no_valid_A1_source_quality_aware_recommended
by2_status_relpos_diff=XB1A2_relpos_diff_invalid
absolute_position_candidate=nonphysical
normal_run_status=XB1A2_normal_blocked
quality_aware_branch=quality_aware_recommended_due_no_valid_A1
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_XB1_degradation_or_PG2_planning=false
ready_for_paper_claims=false
recommended_next_stage=human_review_XB1A2_then_quality_aware_branch_or_PG2_source_review
```

## PG_MULTI_A0 Poor-GNSS Multi-Repeat Source Review

PG_MULTI_A0_POOR_GNSS_REPEATED_DATASET_SOURCE_REVIEW_AND_RUNNABILITY_CLASSIFICATION_WITH_LOCKED_XB2_XB3_XB4_BODY_PATHS completed a review-only four-repeat source audit. PG1/XB1 was imported from XB1A2. PG2/XB2, PG3/XB3, and PG4/XB4 receiver roots were registered by alias, and their body/high-level source paths were locked by alias and parsed successfully. The stage generated data inventory, role classification, GNSS quality profiles, A1 dual-yaw availability audits, provider/body feasibility reviews, runnability classification, recommendation, validation, context updates, and untracked Obsidian notes. No solvers, evaluators, degraded inputs, random arrays, retuning, quality-aware branch implementation, or paper claims were run or produced.

The A1 audit used the BY2 status-yaw rule requiring relpos dual difference before invalidity decisions. PG2/XB2 through PG4/XB4 all had zero physical-band epochs in the primary `gnss2.rel_pos_interp - gnss1.rel_pos` audit, while PG1/XB1 retained the XB1A2 result of 7 physical-band epochs out of 356. Direct single rel_pos, long-relpos, HDT, absolute-LLH-only fallback, receiver IMU as body IMU, trace, final_v23 output, and solver output remain rejected as mainline yaw/body sources.

Current PG_MULTI_A0 decision:

```text
status=PG_MULTI_A0_all_repeats_severe_quality_aware_branch_recommended
pg1_imported_from_XB1A2=true
pg2_pg3_pg4_receiver_roots_registered=true
pg2_pg3_pg4_body_paths_locked=true
pg2_pg3_pg4_body_parseable=true
a1_relpos_diff=invalid_all_repeats
runnability_classification=quality_aware_branch_candidate_all_repeats
ready_for_selected_PG_normal_run_planning=false
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_paper_claims=false
recommended_next_stage=human_review_PG_MULTI_A0_then_quality_aware_branch_or_position_only_diagnostic_or_stop
```
