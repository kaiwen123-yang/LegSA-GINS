# PLANS.md - LegSA-GINS Current Plan And Stage Roadmap

## 0. Purpose

This file records the active roadmap, completed stages, readiness flags, future gates, and multi-agent boundaries for the LegSA-GINS project.

This file is not a runtime report, algorithm output, paper claim, or place to store local absolute paths.

## 1. Project Identity

LegSA-GINS is a legged-robot GNSS/INS fusion project with source-backed EKF, Raw Doppler, source-aware weighting, Go2 proprioception, legged FGO candidate factors, no-feedback FGO, and FGO-feedback EKF joint filtering.

Current data focus has expanded to BY3 normal-generalization, position/up degradation gates, cross-dataset review packaging, poor-GNSS repeated-experiment source review plus quality-aware fallback design, and paper-facing evidence organization. BY3A0_TO_BY3E through GEN1 established the BY3 position/up-with-diagnostic-yaw generalization route from existing metrics only. XB1A0-E, XB1A1, and XB1A2 established that PG1/XB1 is severe poor GNSS, Raw Doppler provider materialization is source-backed, and no valid A1 dual-yaw source exists. PG_MULTI_A0 then registered PG2-PG4 receiver/body aliases, audited source quality and status-relpos dual-difference A1 feasibility across PG1-PG4, and classified all repeats as quality-aware branch candidates. PG_QA0 organized BY2/BY3/PG evidence and designed the separate future `LegSA_QA_Fallback_EKF` candidate, while keeping `LegSA_full_EKF` as the frozen mainline and paper claims disabled. PAPER0 then organized the near-term paper evidence package from existing BY2/BY3/PG/QA evidence and kept paper claims disabled.

## 2. Global Working Principles

- Do not confuse source observations with algorithm outputs.
- Do not confuse evaluation reference with solver input.
- Do not confuse PNG existence with valid plotting.
- Do not confuse clean BY2 engineering validation with paper-level performance claims.
- Do not change algorithm code during reporting, context, or audit stages.
- Do not tune using trace or final_v23 output.
- Do not merge, tag, close PRs, delete branches, force push, stage, commit, or push without the correct role and explicit human approval.
- The human user is always the final decision maker.

## 3. Current Roadmap State

Completed or accepted for current planning:

- N9A normal clean completed.
- N9B0, N9B0A, N9B0A1, N9B0A2 completed.
- N9B0B and N9B0C completed.
- N9B1A and N9B1A1 completed.
- N9B1C through N9B1G2 completed.
- N9B1D through N9B1D4 completed.
- N9B1D4 is the current technical pilot source.
- N9B1E passed with the C yaw caution and is the current pilot visual/go-no-go source.
- N9B2A completed.
- N9B2A1 completed.
- N9B2A/N9B2A1 are the full-matrix preparation sources.
- N9B2B completed and locked Windows plus WSL aliases and the future by2-huitu output alias.
- N9B2B1 context update after path lock completed.
- Batch 0 normal smoke completed.
- Batch 1 deterministic completed.
- Batch 2 position noise completed.
- Batch 3 position spike completed.
- Batch 4 yaw noise completed.
- Batch 5 core module-disable completed; module-stress remains deferred.
- Batch 6 selected mixed cases completed.
- final_v23 external baseline completed and integrated.
- N9C0 global staged consolidation precheck completed.
- N9E active nine-factor FGO/legged logger review completed with `complete_nine_factor_FGO_claim=false`.
- N9E outcome: logging blocked for current `LegSA_full_EKF`; no complete active nine-factor FGO claim.
- Current implementation/context stage: `N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
- Current BY3/reporting stage: `GEN1_BY2_BY3_GENERALIZATION_REPORT_AND_BY3_FIGURE_ORGANIZATION`; GEN1 built BY2/BY3 three-scheme inventories and summaries from existing metrics, generated cross-dataset figures from existing metrics only, and created a copy-only BY3 figure organization. Paper claims remain false.
- Current poor-GNSS stage: `PG_QA0_QUALITY_AWARE_FALLBACK_DESIGN_AND_PAPER_MAINLINE_DECISION`; PG_MULTI_A0 remains the source/runnability evidence import. PG_QA0 is design-only and creates no solver/evaluator/degraded/random/retuning evidence. It defines `LegSA_QA_Fallback_EKF` as a separate future quality-aware fallback candidate for severe GNSS and unavailable A1 dual-yaw, while keeping `LegSA_full_EKF` as the current verified mainline for normal/moderate GNSS and BY2/BY3 position-up evidence.
- Current paper-facing evidence stage: `PAPER0_MAINLINE_EVIDENCE_PACKAGE_AND_CLAIM_BOUNDARY_REVIEW`; PAPER0 is complete and supports starting manuscript experiment-section drafting from existing BY2/BY3 evidence while keeping PG/QA as limitation/design extension and `ready_for_paper_claims=false`.
- N9F design materialization completed: current evidence requires a new active nine-factor FGO algorithm design before representative runs.
- N9F6A source-code forensic audit completed from real Windows/WSL source evidence and passed reviewer gate.
- N9F7 followed Path C only: substantial algorithm design package required; no implementation, solver/evaluator execution, representative run, full matrix, or replot was performed.
- N9F7A Git boundary audit completed: the current branch has existing unpushed local history, including a reporting/test code commit that blocks automatic push until human review.
- N9G0 manual `LegSA_9F_FGO_EKF` design review completed as design only.
- N9G0A Git boundary resolution completed; PR #52 head is synced to `9ceba928`.
- N9G1 is split into `N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION` and later `N9G1B_PHASE1_PROVIDER_FACTOR_LOGGER_NORMAL_SMOKE_ONLY`.
- N9G1A context lock passed reviewer gate and was pushed to PR #52 at `f1e80f1`.
- N9G1B Phase 1 created the separate `LegSA_9F_FGO_EKF` candidate identity, runner/config boundary, provider/factor audit helper, logger schemas, safety gate, and runtime decision artifacts.
- N9G1B normal smoke was not run because the gate blocked it: provider contracts are not ready for active factors, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled.
- N9G1C-E resolved the locked normal source and core provider contracts for `LegSA_9F_FGO_EKF` as partial accepted provider evidence, but the active nine-factor FGO backend remains unavailable and candidate solver execution remains disabled.
- N9G1C-E normal smoke was not run because the gate blocked it: active backend unavailable, candidate solver disabled, and no active factor wiring rows.
- BY3A1 extracted the accepted BY2 input chain, repaired BY3 candidate IMU/GNSS files to BY2 runtime conventions, and materialized BY3 Go2 attitude/horizontal/joint priors.
- BY3A2 recovered the historical BY2 WSL Raw Doppler, Go2, single-baseline, final_v23, and selected-feedback chains; BY3 Raw Doppler is now materialized through the accepted N5A/N5B path, while BY3 same-case selected feedback remains unavailable under accepted gates.
- BY3A3 generated BY3 same-case selected feedback from stage1 official-eval state/estimate columns only, ran LegSA_full_EKF stage2, ran the GNSS1-status single baseline and final_v23 external baseline, and completed official normal evaluation without BY3 degradation or paper claims.
- BY3A4A recovered BY2 lateral yaw policy evidence as partial, explicitly encoded that the dual antennas are lateral/perpendicular to robot forward direction, audited +90/-90 and baseline-reversal candidates with existing BY3A3 outputs only, generated common-overlap metrics/diagnostic figures/seed0-9 explanation/context memory, and blocked repaired yaw metrics because no policy passed sanity without RMSE-only selection.
- BY3A4C recovered the historical BY2/N4 yaw-reference fix from git/docs/runtime evidence: N4H2 old yaw around 93 deg was invalidated by N4H2D, N4H2D selected `official_ref_sign_minus`, and fresh replay yaw was about 1.98 deg against the reconstructed dual official reference. Applying recovered and diagnostic profiles to existing BY3A3 outputs did not produce an accepted BY3 yaw reference, so BY3 yaw is `not_evaluable` and original BY3A3/BY3A4A yaw remains historical invalid-reference evidence.
- BY3A5B superseded BY3A5's HDT policy, reconstructed BY3 A1_dual_diff yaw from GNSS1/GNSS2 short-baseline absolute positions, rejected status long-baseline `rel_pos_n/e/d`, generated a fixed_1p5 repaired 15-column GNSS input, and reran BY3 normal only; BY3A6 later superseded readiness by validating trace/evaluator/base_time, repairing initatt, and keeping yaw unresolved.
- BY3A7 superseded the BY3A6 yaw-readiness blocker by confirming the remaining yaw failure was a BY3 Go2 IMU moving-segment gyro-bias preprocessing bug, repairing a BY3A7-local IMU using pre-motion source bias, and rerunning BY3 normal only with LegSA_full_EKF yaw RMSE about 5.26 deg.
- `LegSA_full_EKF` remains the current verified EKF/feedback algorithm.
- `LegSA_9F_FGO_EKF` is a separate new candidate, not a relabeling of `LegSA_full_EKF`.

Immediate next stages:

- Human review of `GEN1_BY2_BY3_GENERALIZATION_REPORT_AND_BY3_FIGURE_ORGANIZATION`
- `PAPER1_MANUSCRIPT_EXPERIMENT_SECTION_DRAFT` from PAPER0 evidence and claim-boundary tables; final figure generation and final claim review remain separate gates.
- QA1 remains optional for a stronger/top-journal route; no PG solver/evaluator/degradation/random/retuning/quality-aware execution is authorized by QA0 or PAPER0.
- `BY3D_MIXED_POSITION_UP_PLANNING`, separate diagnostic-yaw planning, or other-dataset planning only after explicit human approval; GEN1 does not authorize H_dual_yaw_noise, E_yaw_std_inflation, mixed execution, module-disable, LegSA_9F_FGO_EKF, nonredundant-FGO, or full monolithic BY3 matrix execution
- `implement_active_fgo_backend_or_reframe_scope`
- `N9G2_REPRESENTATIVE_VALIDATION` later, only after active backend/provider/factor gaps are fixed and reviewed.
- `N9G3_FULL_MATRIX` and `N9G4_REPLOT_AND_REPORT` later only if applicable and explicitly approved.
- `N9C1_CONSOLIDATED_FIGURE_GENERATION` only after the correct human-approved route confirms the implementation/figure scope.
- `N9C2_FIGURE_VISUAL_REVIEW_AND_REPAIR`
- `N9C3_CONSOLIDATED_CASE_REVIEW_AND_REPORT_PACKAGE`
- `N9D_CLAIM_BOUNDARY_AND_PAPER_WRITING_READINESS_REVIEW`
- Paper-facing claims only after N9D review and explicit human approval.

Do not run more N9B2 execution unless the human defines a new follow-up. N9C1 is consolidated figure generation and package preparation; it is not paper-claim authorization.

## 4. Readiness Flags

```text
ready_for_N9C1_consolidated_figure_generation=true
ready_for_algorithm_design_review=true
ready_for_implementation_review=false
ready_for_N9G1A_context_lock=complete
ready_for_N9G1C_E_provider_backend_normal_smoke=blocked_active_backend
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=position_up_with_diagnostic_yaw
ready_for_BY3C_position_up_degradation_execution=complete_batch0_to_batch3
ready_for_BY3C1_BY3Y1_review=complete
ready_for_GEN1_BY2_BY3_generalization_report_and_BY3_figure_organization=complete
ready_for_XB1_quality_audit=complete
ready_for_XB1_raw_doppler_provider=true
ready_for_XB1_dual_yaw=false
ready_for_XB1_normal_solver=single_baseline_only_completed
ready_for_XB1_quality_aware_branch_planning=true_after_human_review
ready_for_PG_MULTI_A0_review=complete
ready_for_PG_QA0_design=complete
ready_for_PG_QA1_classifier_logging=false_pending_human_review
PG_QA0_paper_mainline_recommendation=Option_B_design_extension_now
PG_QA0_optional_high_tier_route=Option_C_after_QA1_QA2_QA3
ready_for_PAPER0_evidence_package=complete
ready_for_manuscript_drafting=true
ready_for_PAPER10C_R1A_resume_manifest=complete
ready_for_PAPER10C_R1A_runner_execution=false_space_gate
PAPER10C_R1A_BY2_go2_120x6=closed_720_of_720
PAPER10C_R1A_BY3_go2_120x6=partial_543_of_720
PAPER10C_R1A_BY3_go2_missing_rows=169
PAPER10C_R1A_BY3_go2_partial_rows=8
PAPER10C_R1A_go2_claim=bounded_auxiliary_candidate_not_closed_main_innovation
PAPER10C_R1B_BY2_go2_120x6=closed_720_of_720
PAPER10C_R1B_BY3_go2_120x6=closed_720_of_720
PAPER10C_R1B_readiness_lsim=closed_first_class_runtime_metadata
PAPER10C_R1B_go2_claim=bounded_auxiliary_prior_and_metadata_mechanism
PAPER10Y_archive_verified=true
PAPER10Y_verified_wsl_cleanup=true
PAPER10Y_vhdx_compact=pending_windows_manual
ready_for_PAPER10B2_multi_state_quality_management_closure=true_after_human_review
ready_for_QA1=false
ready_for_PG2_or_XB1_degradation_planning=false
ready_for_BY3D_or_other_dataset_planning=true_after_human_review
ready_for_BY3D_diagnostic_yaw_or_mixed_planning=requires_new_human_approval
ready_for_BY3_solver_evaluator=normal_completed
ready_for_BY3_input_chain=repaired
ready_for_BY3_go2_priors=true
ready_for_BY3_raw_doppler_provider=true
ready_for_BY3_same_case_feedback=true
ready_for_BY3_yaw_input_policy=A1_dual_diff_repaired
ready_for_BY3_yaw_reference=diagnostic_only_after_BY3A8_A1_lower_bound
yaw_degradation_claims=diagnostic_only
ready_for_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
```

These flags do not authorize solver/evaluator/N9B2/random/degraded-input execution, paper claims, representative active-nine-factor FGO degradation/full-matrix runs, or N9C1 figure generation from N9G1B Phase 1.

## 5. Path And Runtime Policy

Tracked docs must use aliases only:

- `<WINDOWS_AUDIT_ROOT>`
- `<WSL_AUDIT_ROOT>`
- `<WSL_ALGO_REPO>`
- `<BY2_N9B2_WINDOWS_ROOT>`
- `<BY2_N9B2_WSL_ROOT>`
- `<BY2_N9B2_FULL_MATRIX_ROOT>`
- `<BY2_N9B2_DEFERRED_EXT4_ROOT>`
- `<GEN1_STAGE_ROOT>`
- `<BY3_FIGURE_SUMMARY_ROOT>`
- `<GEN1_EXPORT_CLEAN_ROOT>`
- `<XB1_OUTPUT_ROOT>`
- `<XB1_STAGE_ROOT>`
- `<XB1A1_STAGE_ROOT>`
- `<XB1_FULL_MATRIX_ROOT>`
- `<XB1A1_NORMAL_GATE_ROOT>`
- `<XB1A2_STAGE_ROOT>`
- `<XB1A2_RELPOS_DIFF_REPAIR_ROOT>`
- `<XB1_EXPORT_CLEAN_ROOT>`
- `<XB1_RECEIVER_ROOT>`
- `<XB1_BODY_SOURCE>`
- `<PG_MULTI_REVIEW_ROOT>`
- `<PG_MULTI_A0_STAGE_ROOT>`
- `<PG_QA0_STAGE_ROOT>`
- `<PAPER_EVIDENCE_REVIEW_ROOT>`
- `<PAPER0_STAGE_ROOT>`
- `<PAPER10C_R1_STAGE_ROOT>`
- `<PAPER10C_R1A_STAGE_ROOT>`
- `<PAPER10C_R1A_C_EXPORT_ROOT>`
- `<PAPER10C_R1A_OBSIDIAN_SYNC_ROOT>`
- `<PAPER10C_R1B_STAGE_ROOT>`
- `<PAPER10C_R1B_C_EXPORT_ROOT>`
- `<PAPER10C_R1B_OBSIDIAN_SYNC_ROOT>`
- `<PAPER10B_R2_STAGE_ROOT>`

Actual local absolute paths belong only in ignored `docs/codex_context/DATA_PATHS.local.md`.

N9B2B locks the Windows and WSL path aliases and the future by2-huitu output alias. Future BY2/N9B outputs must use the `BY2_N9B2_*` aliases. Native Ubuntu migration is deferred. The old Chinese output root is read-only historical evidence.

Runtime outputs remain untracked. N9B2B1 runtime reports belong under `<BY2_N9B2_WINDOWS_ROOT>/N9B2B1_CONTEXT_UPDATE_AFTER_PATH_LOCK`.
N9C0A runtime reports belong under `<BY2_N9B2_WINDOWS_ROOT>/N9C0A_CONTEXT_UPDATE_AFTER_GLOBAL_CONSOLIDATION`. N9C0 consolidated precheck artifacts are represented by `<N9C0_CONSOLIDATED_PRECHECK_ROOT>` under `<BY2_N9B2_FULL_MATRIX_ROOT>`.
N9F design/context outputs belong under `<BY2_N9B2_WINDOWS_ROOT>/N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`, with export-clean design material under `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`.
N9F6A/N9F7 source-audit and design-package outputs belong under `<BY2_N9B2_WINDOWS_ROOT>/N9F6A_TO_N9F7_CODEBASE_FORENSIC_AUDIT_AND_ACTIVE_FGO_LEGGED_COMPLETION`.
N9F7A/N9G0 Git-boundary and manual-design-review outputs belong under `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
N9G0 design packages belong under `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_LEGSA_9F_FGO_EKF_DESIGN_PACKAGE` and `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_EXPORT_CLEAN_DESIGN_PACKAGE`.
N9G1A/N9G1B context-lock and Phase 1 outputs belong under `<BY2_N9B2_WINDOWS_ROOT>/N9G1A_TO_N9G1B_CONTEXT_LOCK_AND_LEGSA_9F_PHASE1_IMPLEMENTATION`.
N9G1C-E provider/backend/logger gate outputs belong under `<BY2_N9B2_WINDOWS_ROOT>/N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
BY3A0_TO_BY3E outputs belong under `<BY3_STAGE_ROOT>`.
BY3A1 parity/provider-gate outputs belong under `<BY3A1_STAGE_ROOT>`.
BY3A4A yaw-repair/context-memory outputs belong under `<BY3A4A_STAGE_ROOT>` and the diagnostic runtime root `<BY3_FULL_MATRIX_ROOT>/BY3A4A_YAW_REPAIR`.
BY3A4C yaw-history reconstruction outputs belong under `<BY3A4C_STAGE_ROOT>` and the diagnostic runtime root `<BY3_FULL_MATRIX_ROOT>/BY3A4C_YAW_HISTORY_RECONSTRUCTION`.
BY3A5B A1 dual-diff yaw-input repair outputs belong under `<BY3A5B_STAGE_ROOT>` and the normal-only runtime root `<BY3_FULL_MATRIX_ROOT>/BY3A5B_A1_DUAL_DIFF_REPAIR`.
BY3A6 trace-truth/initatt/gate forensic outputs belong under `<BY3A6_STAGE_ROOT>` and the normal-only runtime root `<BY3_FULL_MATRIX_ROOT>/BY3A6_TRACE_TRUTH_INITATT_GATE_FORENSIC`.
BY3A7 A1 yaw dynamic-quality/IMU gate repair outputs belong under `<BY3A7_STAGE_ROOT>` and the normal-only runtime root `<BY3_FULL_MATRIX_ROOT>/BY3A7_YAW_DYNAMIC_GATE_REPAIR`.
BY3A8 yaw error-budget safe-repair outputs belong under `<BY3A8_STAGE_ROOT>` and the normal-only runtime root `<BY3_FULL_MATRIX_ROOT>/BY3A8_YAW_ERROR_BUDGET_REPAIR`.
BY3B position/up diagnostic-yaw planning outputs belong under `<BY3B_STAGE_ROOT>` and future execution is planned under `<BY3_FULL_MATRIX_ROOT>/BY3B_POSITION_UP_DEGRADATION_MATRIX`.
BY3C execution outputs belong under `<BY3C_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3C_POSITION_UP_DEGRADATION_EXECUTION`.
BY3C1/BY3Y1 review outputs belong under `<BY3C1_STAGE_ROOT>`, with the review package under `<BY3C1_REVIEW_PACKAGE_ROOT>`, the yaw diagnostic package under `<BY3Y1_STAGE_ROOT>`, and the export-clean package under `<BY3C1_EXPORT_CLEAN_ROOT>`.
GEN1 cross-dataset review outputs belong under `<GEN1_STAGE_ROOT>`, with the copy-only BY3 figure organization under `<BY3_FIGURE_SUMMARY_ROOT>` and export-clean material under `<GEN1_EXPORT_CLEAN_ROOT>`.
XB1 / PG1 poor-GNSS bootstrap outputs belong under `<XB1_STAGE_ROOT>`, with normal-bootstrap runtime material under `<XB1_FULL_MATRIX_ROOT>/XB1A_NORMAL_BOOTSTRAP`, export-clean material under `<XB1_EXPORT_CLEAN_ROOT>`, receiver data represented by `<XB1_RECEIVER_ROOT>`, and body/high-level data represented by `<XB1_BODY_SOURCE>`. XB1A1 blocker-triage and normal-gate repair outputs belong under `<XB1A1_STAGE_ROOT>`, with normal-gate runtime material under `<XB1A1_NORMAL_GATE_ROOT>`. XB1A2 A1 relpos-difference re-audit outputs belong under `<XB1A2_STAGE_ROOT>` and `<XB1A2_RELPOS_DIFF_REPAIR_ROOT>`. PG_MULTI_A0 review outputs belong under `<PG_MULTI_A0_STAGE_ROOT>`, PG_QA0 design outputs belong under `<PG_QA0_STAGE_ROOT>`, and PAPER0 evidence-review outputs belong under `<PAPER0_STAGE_ROOT>`.
PAPER10C_R1 interrupted Go2/readiness runtime evidence is represented by `<PAPER10C_R1_STAGE_ROOT>`. PAPER10C_R1A resume outputs are represented by `<PAPER10C_R1A_STAGE_ROOT>`, with export-clean material under `<PAPER10C_R1A_C_EXPORT_ROOT>` and vault notes under `<PAPER10C_R1A_OBSIDIAN_SYNC_ROOT>`. PAPER10C_R1B low-space missing-only resume outputs are represented by `<PAPER10C_R1B_STAGE_ROOT>`, with export-clean material under `<PAPER10C_R1B_C_EXPORT_ROOT>` and vault notes under `<PAPER10C_R1B_OBSIDIAN_SYNC_ROOT>`. Imported PAPER10B_R2 BY3 source-aware material is represented by `<PAPER10B_R2_STAGE_ROOT>`.
BY3 full-matrix placeholders belong under `<BY3_FULL_MATRIX_ROOT>` and do not mean BY3 full matrix was run.
BY3 receiver source is represented by `<BY3_RECEIVER_ROOT>`.
BY3 Go2 body/high-level source is represented by `<BY3_GO2_BODY_SOURCE>`.
BY2 degradation archive evidence is represented by `<BY2_DEGRADATION_ARCHIVE_ROOT>`.

## 6. Runner And Evaluation Rules

- Formal runner: `legsa_v23_port_core_demo` plus `by2_algorithm_runner`.
- `legsa_gins --run-filter-csv` is diagnostic only.
- `selected_feedback` requires same-case feedback.
- Clean feedback cannot be used for degraded cases.
- EVAL_NAV feedback generation uses state/estimate columns only.
- EVAL_NAV feedback generation must not use trace/error feedback corrections.
- Final-only metrics rule: metrics must come from final algorithm output/evaluation files for the same case.
- Current active global metrics source after N9C0: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`.
- The N9C0 active final-only metrics table has 825 rows.
- Do not use superseded rows, `historical_nominal_none`, or `B_gnss_downsample_2Hz` for active conclusions.
- Additional N9B2 execution is forbidden until explicit stage approval.

## 7. Baseline Roles

- `single_antenna_gnss1_status_KF_GINS`: GNSS1-status baseline, not raw GNSS.
- `pure_INS_reference_initialized`: fixed/reference baseline.
- `final_v23_dual_antenna_EKF`: `external_reference_baseline` only.
- `true_no_feedback_FGO`: diagnostic unless full comparable output exists.

## 8. Matrix Cautions

- `B_gnss_downsample_2Hz` is invalid and superseded.
- Ratio downsample cases `every2`, `every5`, and `every10` are the active downsample family.
- `C_position_noise` has a yaw caution.
- `H_dual_yaw_noise` has a single-seed caveat.
- C and H require multi-seed treatment in N9B2.
- D position spike multi-seed is recommended.
- Superseded rows must never be used for active conclusions.

## 9. Claim Boundary

Allowed now:

- BY2 FGO-feedback EKF joint filter engineering chain has been validated.
- FGO feedback enters EKF as a controlled update.
- No output substitution, no direct NAV overwrite, no future-data feedback.
- Raw Doppler EKF is active.
- Raw Doppler FGO is active but low marginal value in clean BY2.
- Go2 proprioceptive joint factor is active.
- Legged candidate factors are activated in no-feedback FGO.
- N9B pilot/preparation evidence exists through N9B2B, with the recorded cautions.
- N9B staged execution is complete through N9C0 global consolidated precheck.
- N9C0 active final-only metrics table exists with 825 rows.
- N9C1 consolidated figure generation readiness passed.
- N9E logging-blocked review completed with no complete active nine-factor FGO claim.
- N9F design package is complete and requires a new active nine-factor FGO algorithm design.
- N9F6A source audit confirms robot kinematics/contact/legged modeling exists, but mainly as provider, diagnostic, offline no-feedback, or candidate factor code.
- N9F7 design package is complete and requires manual algorithm design review before implementation.
- N9G0 manual design review defines `LegSA_9F_FGO_EKF` as a separate future candidate, not an alias for `LegSA_full_EKF`.
- N9G0A resolved the Git boundary and PR #52 head is synced to `9ceba928`; merge, closure, and tag decisions still require explicit human approval.
- N9G1A locks the context before implementation and does not implement code or run solvers/evaluators/generators.
- N9G1B is limited to Phase 1 provider/factor/logger/normal-smoke work if later approved.
- Current evidence supports provider/update or candidate-only diagnostics, not a complete current active nine-factor FGO claim.

Forbidden now:

- paper performance improvement claim.
- outperform final_v23 claim.
- Go2 truth claim.
- FGO replaces EKF claim.
- trace/final_v23 tuning claim.
- source observations as algorithm estimates.
- placeholder plots as real figures.
- paper claims before N9C visual review and N9D claim-boundary review.
- active conclusions from superseded rows, `historical_nominal_none`, or `B_gnss_downsample_2Hz`.
- automatic PR #52 merge/tag authorization.
- relabeling `LegSA_full_EKF` as active nine-factor FGO.
- representative active-nine-factor FGO runs before human-approved implementation review.
- representative degradation or full-matrix validation in N9G1B.
- treating N9F6A/N9F7 design artifacts as active solver residual/cost evidence.
- treating N9G0 design artifacts as implemented solver evidence.
- treating PR #52 head sync as merge, closure, tag, or paper-claim authorization.

## 10. Multi-Agent Workflow

Future work should use:

```text
supervisor -> planner -> worker -> reviewer -> human final decision
```

Planner is read-only. Worker executes only approved scope. Reviewer is read-only. Human decides merge/tag/PR/stage transitions.

## 11. Required Future Plan Format

Every future plan must include:

- Goal.
- Verified current state.
- Scope.
- Inputs.
- Outputs.
- Execution steps.
- Validation.
- Prohibited actions.
- Risks.
- Completion criteria.
- Final report requirements.

## 12. N9F Completion Criteria

N9F0_TO_N9F2 is complete only when:

- Runtime reports/matrices/summaries exist under `<BY2_N9B2_WINDOWS_ROOT>/N9F0_TO_N9F2_ACTIVE_NINE_FACTOR_FGO_LEGGED_DESIGN_MATERIALIZATION_AND_CONTEXT_SYNC`.
- Design and export-clean packages exist under `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_ACTIVE_FGO_LEGGED_DESIGN_AND_EVIDENCE` and `<BY2_N9B2_FULL_MATRIX_ROOT>/N9F_EXPORT_CLEAN_DESIGN_PACKAGE`.
- Obsidian public notes use aliases only, with private paths confined to `99_LOCAL_PATHS.private.md`.
- No solver/evaluator/degradation/random/figure execution occurred.
- `ready_for_implementation_review=true`.
- `ready_for_paper_claims=false`.
- `ready_for_N9B2_execution=false`.
- `ready_for_full_N9B_execution=false`.
- Recommended next stage is `N9F6_HUMAN_REVIEW_LEGSA_9F_IMPLEMENTATION_PLAN`.

## 13. N9F6A/N9F7 Completion Criteria

N9F6A/N9F7 is complete only when:

- Source-root discovery, source inventory, runner mapping, EKF/FGO/legged/selected-feedback audits, evidence matrices, and decision reports exist under `<BY2_N9B2_WINDOWS_ROOT>/N9F6A_TO_N9F7_CODEBASE_FORENSIC_AUDIT_AND_ACTIVE_FGO_LEGGED_COMPLETION`.
- Step 1 reviewer passes before Step 2 begins.
- Step 2 follows only the Step 1 decision path.
- For the current Path C decision, no implementation, solver, evaluator, degradation generation, representative run, full matrix, or figure generation occurs.
- Robot kinematics/contact modeling is classified from source evidence as provider, diagnostic, offline no-feedback, candidate, EKF-update, or missing.
- Public docs and Obsidian notes use aliases only.
- `ready_for_algorithm_design_review=true`.
- `ready_for_implementation_review=false`.
- `ready_for_paper_claims=false`.
- `ready_for_N9B2_execution=false`.
- `ready_for_full_N9B_execution=false`.
- Recommended next stage is `manual_algorithm_design_review`.

## 14. N9F7A/N9G0 Completion Criteria

N9F7A/N9G0 is complete only when:

- Git status, ahead commit, PR #52, publish safety, protected-root, staging, and path-leak audits exist under `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
- Manual `LegSA_9F_FGO_EKF` design reports exist for algorithm identity, state/window, nine factors, matrix/residual model, provider contracts, logger schema, implementation roadmap, validation protocol, and risk register.
- `LegSA_full_EKF` remains the current verified EKF/feedback algorithm.
- `LegSA_9F_FGO_EKF` remains design-only until a later human-approved implementation stage.
- No implementation, solver, evaluator, random generation, degraded-input generation, N9B2 execution, representative validation, full matrix, figure generation, paper claim, PR merge, PR closure, or tag creation occurs.
- `ready_for_N9G1_phase1_implementation=human_decision_required`.
- `ready_for_paper_claims=false`.
- `ready_for_N9B2_execution=false`.
- `ready_for_full_N9B_execution=false`.
- Recommended next stage is `resolve_git_boundary`.

Historical supersession: N9G0A later resolved this Git boundary and synced PR #52 head to `9ceba928`. The historical `resolve_git_boundary` recommendation must not be read as current after N9G0A/N9G1A; current state and next-step guidance are in the N9G1A section and `docs/codex_context/current_state.md`.

## 15. Historical N9C0A Completion Criteria

N9C0A is complete only when:

- Approved tracked context docs are updated away from stale N8K/N9A/N9B2B1 current-state text.
- No local absolute path leaks exist in tracked docs touched by the stage or core context docs.
- `DATA_PATHS.local.md` remains ignored/local-only and is not staged.
- Runtime reports, matrices, and summaries are created under the approved runtime root.
- No solver/evaluator/N9B2/random/degraded-input/N9C1 figure execution occurred.
- `ready_for_N9C1_consolidated_figure_generation=true`.
- `ready_for_paper_claims=false`.
- `ready_for_N9B2_execution=false`.
- `ready_for_full_N9B_execution=false`.
- Recommended next stage is `human_review_N9C0A_then_N9C1_consolidated_figure_generation`.

## 16. N9G1A Completion Criteria

N9G1A is complete only when:

- Approved tracked context docs record N9G0A completion and PR #52 head sync to `9ceba928`.
- Approved tracked context docs record the N9G1 split into context lock and later Phase 1 provider/factor/logger/normal-smoke only.
- `LegSA_full_EKF` remains the current verified EKF/feedback algorithm.
- `LegSA_9F_FGO_EKF` remains a separate new candidate.
- Runtime reports, matrices, summaries, and validation records exist under `<BY2_N9B2_WINDOWS_ROOT>/N9G1A_TO_N9G1B_CONTEXT_LOCK_AND_LEGSA_9F_PHASE1_IMPLEMENTATION`.
- Public Obsidian notes use aliases only; private local paths are confined to `99_LOCAL_PATHS.private.md`.
- No implementation, solver execution, evaluator execution, generator execution, degradation generation, full matrix, figure generation, staging, commit, or push occurs.
- `complete_nine_factor_FGO_claim=false`.
- `ready_for_paper_claims=false`.
- `ready_for_representative_validation=false`.
- Recommended next stage is human review of N9G1A, then explicit decision on N9G1B.

N9G1A completion alone does not authorize implementation. N9G1B may start only when a human request explicitly authorizes it and the N9G1A reviewer gate passes.

## 17. BY3A0_TO_BY3E Completion Criteria

BY3A0_TO_BY3E is complete only when:

- tracked context docs use aliases only and record BY3 as normal-generalization gate work;
- `<BY3_STAGE_ROOT>` contains BY3A inventory/body IMU audit reports, BY3B alignment reports, BY3C candidate input generation reports, BY2T text summary reports, BY2F copy-only archive manifests, gate matrices, summaries, and validation manifests;
- `<BY3_FULL_MATRIX_ROOT>` records that BY3 degradation/full matrix was not run;
- public Obsidian BY3 notes use aliases only, while private local paths remain in an untracked private note;
- BY3D/E are marked blocked if solver/evaluator readiness is not genuinely established.

Completion does not authorize BY3 solver/evaluator execution, BY3 degradation/full matrix, figures, representative validation, paper claims, or final_v23/algorithm changes.

## 18. BY3A1 Completion Criteria

BY3A1 is complete only when:

- accepted BY2 input-chain references are extracted from current evidence;
- BY3A0 candidate inputs are audited against BY2 delimiter/header/schema/time policy;
- BY3 input repair is limited to BY2-compatible file conventions and no trace-tuned offset search;
- BY3 Go2 priors are materialized only from the BY3 Go2 body source and marked as non-truth observations;
- BY3 Raw Doppler provider and selected-feedback dependency are either materially generated from accepted logic or explicitly blocked;
- solver/evaluator execution remains blocked unless parity, provider, feedback, and runner gates all pass;
- no BY3 degradation matrix, artificial degradation, figure-from-metric package, parameter retuning, final_v23 mutation, or paper claim is produced;
- runtime outputs and Obsidian notes remain untracked.

Current BY3A1 decision:

```text
status=BY3A1_provider_or_feedback_blocked
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_providers_or_feedback
```

## 19. BY3A2 Completion Criteria

BY3A2 is complete only when:

- historical BY2 WSL chains for Raw Doppler, Go2 priors, single-baseline handoff, final_v23 handoff, and selected-feedback same-case dependency are recovered from real artifacts;
- BY3 Raw Doppler provider materialization uses the accepted N5A/N5B logic or records a concrete blocker;
- BY3 Go2 priors remain source observations, not truth;
- single-baseline and final_v23 handoffs are validated as runtime configs/commands only unless all solver gates pass;
- selected-feedback remains blocked unless a real same-case BY3 stage1 official EVAL_NAV exists;
- no BY3 degradation matrix, artificial degradation, parameter retuning, trace tuning, final_v23 algorithm change, fabricated output, metric figure package, or paper claim is produced;
- runtime outputs and Obsidian notes remain untracked.

Current BY3A2 decision:

```text
status=BY3A2_selected_feedback_blocked
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_stage1_feedback_chain
```
## BY3A5/BY3A5B Dual Yaw Input Source Repair

BY3A5 audits the BY3 dual-yaw input source and correctly confirms the old BY3 15-column yaw was wrong-source. Its HDT replacement policy is diagnostic/rejected/superseded for mainline BY3 and must not be reused as solver yaw input.

BY3A5B is the accepted mainline input repair: BY3 dual yaw is regenerated from GNSS1/GNSS2 A1_dual_diff short-baseline absolute positions with BY2 sign/lateral conversion and fixed_1p5 yaw_std. Status long-baseline `rel_pos_n/e/d` and NMEA HDT are rejected as mainline solver yaw sources. BY3A6 validated trace truth/evaluator/base_time and repaired stale first-row initatt. BY3A7 then repaired the remaining BY3 Go2 IMU moving-segment gyro-bias preprocessing bug. BY3A8 found the remaining yaw error is limited by A1 observation quality; `ready_for_BY3_degradation_matrix_planning=true` only with `scope=position_up_with_diagnostic_yaw`, and `ready_for_paper_claims=false`.

## BY3A7 A1 Yaw Dynamic Quality IMU Gate Repair

BY3A7 is complete when:

- A1_dual_diff yaw dynamic quality is audited with source-quality invalid criteria, not RMSE-selected epoch deletion;
- BY3 Go2 IMU sign/axis/yaw-rate preprocessing is audited against BY3 source timing and frame contracts;
- yaw gate residuals and yaw update code are audited without gate relaxation;
- any repair is BY3A7-local, non-parameter, and does not use trace/final_v23/solver output as solver input;
- BY3 normal-only rerun completes if and only if the repair gate passes;
- no BY3 degradation, artificial degradation, paper claim, PR merge/closure, or tag occurs.

Current BY3A7 decision:

```text
status=BY3A7_yaw_salvaged_ready_for_full_BY3_degradation
root_cause=BY3_Go2_IMU_moving_segment_gyro_bias_preprocessing
repair=BY3A7_static_pre_motion_gyro_bias_IMU_input
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=full_after_human_review
ready_for_paper_claims=false
recommended_next_stage=BY3B_DEGRADATION_MATRIX_PLANNING_AND_PRECHECK
```

## BY3A8 Yaw Error Budget Safe Repair

BY3A8 is complete when:

- A1 observation lower-bound audit is computed using trace as evaluation-only reference;
- A1 quality, IMU bias, time-lag, yaw gate, and feedback interaction are audited without trace-based repair or RMSE-selected policy;
- no solver/evaluator/degradation rerun occurs unless a source-backed repair passes the gate;
- no HDT/long-relpos fallback, yaw-gate relaxation, parameter retuning, paper claim, PR merge/closure, or tag occurs.

Current BY3A8 decision:

```text
status=BY3A8_yaw_limited_but_position_up_ready
a1_observation_lower_bound=BY3A8_a1_observation_quality_poor
a1_observation_yaw_rmse_about_deg=24.06
safe_repair_plan=BY3A8_no_safe_repair_accept_yaw_limit
normal_rerun=BY3A8_normal_rerun_not_run_no_safe_repair
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=position_up_with_diagnostic_yaw
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=BY3B_POSITION_UP_WITH_DIAGNOSTIC_YAW_PLANNING
```

## BY3B Position Up With Diagnostic Yaw Planning

BY3B is complete only when:

- BY3A8's `position_up_with_diagnostic_yaw` decision is imported;
- BY3A7 repaired IMU and BY3A5B/BY3A7 A1_dual_diff yaw input are locked for future BY3 execution;
- family scope, case matrix, seed plan, provider/feedback dependency plan, dry-run command templates, evaluator/metric policy, figure/case-review plan, and batch plan exist under `<BY3B_STAGE_ROOT>`;
- all future command templates have `execute_now=false` and `dry_run_only=true`;
- no degraded inputs, random arrays, solvers, evaluators, figures, degradation outputs, paper claims, PR merge/closure, or tag are produced;
- yaw metrics remain diagnostic-only because BY3A8 found A1 observation quality is limiting.

Current BY3B decision:

```text
status=BY3B_position_up_diagnostic_yaw_plan_complete
case_seed_units_total=118
position_up_primary_units=75
diagnostic_yaw_units=43
solver_rows_planned=311
ready_for_BY3C_position_up_degradation_execution=true
human_final_decision_required_before_execution=true
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=BY3C_POSITION_UP_DEGRADATION_EXECUTION_BATCH0_TO_BATCH3_LONG_PIPELINE
```

## BY3C Position Up Degradation Execution Batch0-Batch3

BY3C is complete only for the human-approved subset:

- Batch 0: BY3 normal parity recheck with accepted BY3A7/BY3A8 sources.
- Batch 1: A_outage, B_gnss_downsample_every2/every5/every10, and E_position_std_inflation_x2/x5/x10.
- Batch 2: C_position_noise mild/medium/strong seeds 0..9.
- Batch 3: D_position_spike mild/medium/strong seeds 0..9.
- Source locks preserve BY3A7 repaired IMU, BY3A5B/BY3A7 A1_dual_diff yaw, BY3A2 Raw Doppler, BY3 Go2 priors, trace as evaluation-only reference, and same-case feedback policy.
- Metrics, figures, and case reviews are position/up-primary; yaw remains diagnostic-only.

Current BY3C decision:

```text
status=BY3C_batch0_to_batch3_position_up_degradation_complete
case_units_executed=71
final_metric_rows=213
consolidated_figure_rows=12
batch2_case_review_rows=30
batch3_case_review_rows=30
ready_for_BY3D_diagnostic_yaw_or_mixed_planning=true_after_human_review
ready_for_paper_claims=false
recommended_next_stage=human_review_BY3C_then_BY3D_DIAGNOSTIC_YAW_OR_MIXED_PLANNING
```

## BY3C1/BY3Y1 Position/Up Review And Yaw Diagnostic Explanation

BY3C1/BY3Y1 is complete as a review-only stage. It audited the existing BY3C Batch0-Batch3 result integrity, built BY3 three-scheme position/up comparison tables, compared overlapping BY2/BY3 families through active BY2 N9C0D/N9C2B material, generated review figures from existing metrics only, and wrote a BY3Y1 yaw diagnostic explanation from BY3A5B-BY3A8 evidence.

Current BY3C1/BY3Y1 decision:

```text
status=BY3C1_position_up_review_and_yaw_diagnostic_complete
case_units_reviewed=71
final_metric_rows_reviewed=213
ready_for_BY3D_or_other_dataset_planning=true_after_human_review
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=human_review_BY3C1_then_BY3D_mixed_position_up_or_other_dataset_planning
```

## GEN1 BY2-BY3 Generalization Report And BY3 Figure Organization

GEN1 is complete as a cross-dataset reporting, review, and figure-organization stage. It built BY2 and BY3 metric inventories with 213 rows each across 71 comparable case units for the three schemes, created canonical mapping, generated cross-dataset summary tables and figures from existing metrics only, inventoried existing BY3 figures, copied 874 unique nonempty figure files into `<BY3_FIGURE_SUMMARY_ROOT>`, created export-clean material, and synced local Obsidian notes.

Current GEN1 decision:

```text
status=GEN1_cross_dataset_report_and_BY3_figure_organization_complete
ready_for_next_stage=true_after_human_review
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=human_review_GEN1_then_decide_BY3D_or_other_dataset
```

## XB1 Poor-GNSS Generalization Bootstrap

XB1A0_TO_XB1E_POOR_GNSS_GENERALIZATION_CONTEXT_QUALITY_AUDIT_ALIGNMENT_AND_NORMAL_RUN is complete as the first poor-GNSS repeated-experiment bootstrap for XB1 / PG1_20260105_122513. It generated literature-backed quality criteria, receiver/body inventory, GNSS quality profile, kick-event alignment, input/provider reports, quality figures, case review, Obsidian notes, and export-clean material. It did not run artificial degradation, parameter retuning, paper-claim work, or normal solvers/evaluators.

Current XB1 decision:

```text
status=XB1_severe_GNSS_quality_mainline_limited
quality_class=severe
alignment_status=XB1D_alignment_passed
input_status=XB1E_inputs_ready_providers_partial
normal_run_status=XB1F_failed_before_solver
normal_run_blockers=inputs_not_ready_for_normal,A1_short_baseline_yaw_gate_blocked,providers_not_ready_for_LegSA_full
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_PG2_or_XB1_degradation_planning=false
ready_for_paper_claims=false
recommended_next_stage=human_review_XB1_then_repair_provider_or_plan_quality_aware_branch
```

## XB1A1 Blocker Triage And Normal Gate

XB1A1_BLOCKER_TRIAGE_RAW_DOPPLER_A1_YAW_AND_MAINLINE_NORMAL_GATE is complete as a blocker-triage and safe mainline-gate repair stage after XB1A0-E. The Raw Doppler blocker was repaired as an environment/toolchain issue by using WSL gcc/helper execution while preserving the accepted N5A/N5B RTKLIB/RINEX/helper provider chain. The XB1 Raw Doppler factor provider is schema-valid with 1809 rows and is source-backed.

The A1 short-baseline yaw blocker remains. Objective valid A1 epochs are about 1.95 percent, and short-baseline length remains nonphysical for the robot antennas: median about 9.14 m, p95 about 51.68 m, and max about 120.50 m. Status long-baseline `rel_pos_n/e/d` and HDT remain rejected as mainline yaw sources.

Algorithm applicability is partial. `LegSA_full_EKF` and `final_v23_dual_antenna_EKF` were not forced because valid dual-yaw input is unavailable and forcing those runs would change algorithm identity or violate the baseline contract. `single_antenna_gnss1_status_KF_GINS` completed normal official evaluation as a diagnostic baseline only. No degradation matrix, parameter retuning, quality-aware execution, trace solver input, fabricated provider, fabricated A1 yaw, PR #52 merge/closure/tag, or paper-claim work was performed.

Current XB1A1 decision:

```text
status=XB1A1_partial_baseline_only_completed
raw_doppler_provider=XB1A1_raw_doppler_provider_ready
a1_dual_yaw=XB1A1_A1_dual_yaw_invalid_due_GNSS_quality
normal_run_status=XB1A1_normal_partial_completed
legsa_full_status=blocked_dual_yaw_invalid
final_v23_status=not_applicable_dual_yaw_invalid
single_baseline_status=completed_normal_official_eval
quality_aware_branch=XB1A1_quality_aware_branch_recommended
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_XB1_degradation_or_PG2_planning=false
ready_for_paper_claims=false
recommended_next_stage=human_review_XB1A1_then_quality_aware_branch_or_PG2_source_review
```

## XB1A2 A1 Relpos-Difference Reaudit

XB1A2_A1_DUAL_DIFF_RELPOS_DIFFERENCE_REAUDIT_AND_NORMAL_RERUN is complete as a correction stage after XB1A1. It suspends the XB1A1 A1 source-provenance conclusion because XB1A1 used the absolute-position A1 audit path and did not audit the BY2/process_data-compatible status rel_pos dual-difference path.

Recovered implementation evidence now distinguishes two families:

- BY2/process_data-compatible status yaw: interpolate GNSS2 status to GNSS1 time, compute `rel_pos_gnss2 - rel_pos_gnss1`, then `yaw_baseline=-atan2(rel_e,rel_n)`, `yaw_ned=90-yaw_body`, and fixed_1p5 yaw_std.
- BY3A5B repair: use GNSS1/GNSS2 absolute-position short baseline projected to local ENU because BY3 status rel_pos was rejected as a long-base vector.

XB1A2 audited both families for XB1. The BY2 relpos-difference candidate remains nonphysical with 356 rows, 7 physical-band epochs, valid epoch ratio about 0.0197, median length about 9.18 m, p95 about 50.96 m, and max about 131.70 m. The absolute-position candidate also remains nonphysical with median about 9.14 m and p95 about 51.70 m. Single rel_pos direct remains rejected as a long RTK base-vector source, and HDT remains diagnostic-only.

Current XB1A2 decision:

```text
status=XB1A2_no_valid_A1_source_quality_aware_recommended
xb1a1_a1_source_provenance=suspended_or_superseded
by2_status_relpos_diff=XB1A2_relpos_diff_invalid
absolute_position_candidate=nonphysical
repaired_dual_input=XB1A2_repaired_dual_input_blocked
normal_run_status=XB1A2_normal_blocked
quality_aware_branch=quality_aware_recommended_due_no_valid_A1
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_XB1_degradation_or_PG2_planning=false
ready_for_paper_claims=false
recommended_next_stage=human_review_XB1A2_then_quality_aware_branch_or_PG2_source_review
```

## PG_MULTI_A0 Poor-GNSS Multi-Repeat Source Review

PG_MULTI_A0_POOR_GNSS_REPEATED_DATASET_SOURCE_REVIEW_AND_RUNNABILITY_CLASSIFICATION_WITH_LOCKED_XB2_XB3_XB4_BODY_PATHS is complete as a review-only stage. It imported PG1/XB1 from XB1A2, registered the PG2/PG3/PG4 receiver roots through aliases, locked the user-provided PG2/PG3/PG4 body/high-level sources through aliases, inventoried receiver files, parsed body logs, built GNSS quality profiles, audited Raw Doppler provider feasibility, and audited the BY2-compatible status relpos-difference A1 path for PG2/PG3/PG4.

No solver, official evaluator, degraded input generation, random array generation, parameter retuning, quality-aware branch implementation, figure generation, or paper-claim work was performed in PG_MULTI_A0.

Relpos-diff A1 results:

- PG1/XB1: imported from XB1A2; 356 rows, 7 physical-band epochs, valid ratio about 0.01966, median about 9.18 m, p95 about 50.96 m, max about 131.70 m.
- PG2/XB2: 330 `gnss2_minus_gnss1` relpos-diff rows, zero physical-band epochs, median about 14.27 m, p95 about 55.57 m.
- PG3/XB3: 315 `gnss2_minus_gnss1` relpos-diff rows, zero physical-band epochs, median about 14.84 m, p95 about 107.10 m.
- PG4/XB4: 315 `gnss2_minus_gnss1` relpos-diff rows, zero physical-band epochs, median about 36.63 m, p95 about 63.52 m.

Body/high-level lock results:

- PG2/XB2: locked body source `<PG2_XB2_BODY_SOURCE>` parsed with 84436 rows and about 358.66 s receiver/body overlap.
- PG3/XB3: locked body source `<PG3_XB3_BODY_SOURCE>` parsed with 80306 rows and about 346.44 s receiver/body overlap.
- PG4/XB4: locked body source `<PG4_XB4_BODY_SOURCE>` parsed with 79738 rows and about 356.18 s receiver/body overlap.

Current PG_MULTI_A0 decision:

```text
status=PG_MULTI_A0_all_repeats_severe_quality_aware_branch_recommended
pg1_imported_from_XB1A2=true
pg2_pg3_pg4_receiver_roots_registered=true
pg2_pg3_pg4_body_paths_locked=true
pg2_pg3_pg4_body_parseable=true
raw_doppler_provider_feasibility=PG1_ready_PG2_PG3_PG4_likely_ready
a1_relpos_diff=invalid_all_repeats
runnability_classification=quality_aware_branch_candidate_all_repeats
ready_for_selected_PG_normal_run_planning=false
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_paper_claims=false
recommended_next_stage=human_review_PG_MULTI_A0_then_quality_aware_branch_or_position_only_diagnostic_or_stop
```

## PG_QA0 Quality-Aware Fallback Design And Paper Mainline Decision

PG_QA0_QUALITY_AWARE_FALLBACK_DESIGN_AND_PAPER_MAINLINE_DECISION is complete as a design-only follow-on after PG_MULTI_A0 and XB1A2. It imported BY2 full-metric evidence, BY3 position/up-with-diagnostic-yaw evidence, and PG1-PG4 severe GNSS source/runnability evidence. It did not implement a quality-aware branch, run solvers, run evaluators, generate degraded inputs, generate random arrays, retune parameters, or create paper claims.

Algorithm identity is locked:

- `LegSA_full_EKF`: current frozen verified mainline for normal/moderate GNSS and BY2/BY3 position-up evidence.
- `LegSA_QA_Fallback_EKF`: separate design-only future candidate for severe GNSS, unavailable A1 dual-yaw, poor GNSS position quality, Raw Doppler availability, and IMU+Go2 bridge operation.

QA0 designed the fallback state machine S0-S6, measurement enable/disable policy, R-scale and threshold-source policy, Raw Doppler retention policy, Go2 bridge policy, logging schema, validation protocol, implementation roadmap, risk register, and paper-mainline decision matrix. Trace RMSE, final_v23 output, future information, and final-metric-only labels are forbidden as online threshold sources.

Current PG_QA0 decision:

```text
status=PG_QA0_design_complete_human_review_before_QA1
paper_mainline_recommendation=Option_B_design_extension_now
optional_high_tier_route=Option_C_after_QA1_QA2_QA3
ready_for_QA1=false
ready_for_paper_claims=false
recommended_next_stage=human_review_PG_QA0_then_keep_future_work_or_approve_PG_QA1
```

## PAPER0 Mainline Evidence Package And Claim Boundary

PAPER0_MAINLINE_EVIDENCE_PACKAGE_AND_CLAIM_BOUNDARY_REVIEW is complete as a paper-facing organization stage after PG_QA0. It uses BY2 as the full-metric main dataset, BY3 as independent position/up generalization with diagnostic-only yaw, PG1-PG4 as severe-GNSS boundary and QA motivation, and PG_QA0 as a design extension. It generated evidence summaries, paper table drafts, figure recommendations, narrative outline, claim-boundary matrix, journal-positioning notes, missing-work decision, export-clean material, validation reports, and local Obsidian notes from existing evidence only.

No solver, official evaluator, degraded input generation, random array generation, QA1 implementation, parameter retuning, metric alteration, final figure generation, or paper-claim work was performed in PAPER0.

Current PAPER0 decision:

```text
status=PAPER0_evidence_package_complete_ready_for_manuscript_drafting
ready_for_manuscript_drafting=true
ready_for_QA1=false
ready_for_paper_claims=false
recommended_next_stage=PAPER1_MANUSCRIPT_EXPERIMENT_SECTION_DRAFT
```

## PAPER10X Git Context Cleanup And Next Experiment Direction Freeze

Active stage:

```text
PAPER10X_GIT_CONTEXT_CLEANUP_AND_COMMIT
```

PAPER10X is a Git hygiene, context-doc, claim-boundary, Obsidian sync, and next-experiment planning stage. It must not run solvers, evaluators, degradation generation, DA, LC, GINav, MATLAB, RTKLIB, contact-aided experiments, complete FGO, or any PAPER10B_R2 continuation.

PAPER10X deliverables:

- classify tracked and untracked dirty files;
- keep `.legsa_runtime/` and `qa_fallback_review/` untracked or ignored;
- update `.gitignore` for runtime/raw/archive/figure/core payloads;
- update AGENTS, PLANS, PHASE_LOG, README, CLAIM_BOUNDARY, and `docs/codex_context`;
- summarize current algorithm, module, dataset, experiment, and claim status;
- sync the correct project Obsidian vault;
- create lightweight C export;
- stage only safe context docs and commit locally without push.

Current evidence baseline:

```text
main_algorithm=LegSA_full_EKF
strong_baseline=final_v23_dual_antenna_EKF
source_aware_status=BY2_120x5_closed; BY3_120x5_closed_with_yaw_diagnostic_only
go2_status=weak_prior_evidence_requires_PAPER10C_freeze
fgo_status=selected_feedback_bounded; complete_nine_factor_FGO_forbidden
qa_fallback_status=future_candidate_not_main_algorithm
ready_for_paper_claims=false
```

Recommended steady submission route:

```text
PAPER10C_GO2_HIGH_LEVEL_PRIOR_EVIDENCE_FREEZE
PAPER10E_FINAL_PROPOSED_METHOD_MATRIX_AND_COMPARISON_FREEZE
PAPER10F_FIGURE_TABLE_AND_MANUSCRIPT_EXPERIMENT_SECTION
```

Recommended stronger innovation route:

```text
PAPER10C_GO2_HIGH_LEVEL_PRIOR_EVIDENCE_FREEZE
PAPER10B2_MULTI_STATE_QUALITY_MANAGEMENT_CLOSURE
PAPER10D_SELECTED_FGO_FEEDBACK_EVIDENCE_FREEZE_optional
PAPER10E_FINAL_PROPOSED_METHOD_MATRIX_AND_COMPARISON_FREEZE
PAPER10F_FIGURE_TABLE_AND_MANUSCRIPT_EXPERIMENT_SECTION
```

PAPER10C is mandatory before final method freezing. PAPER10B2 is only recommended if the manuscript keeps a multi-state quality-management contribution. PAPER10D is optional and should not outrank Go2 and final proposed-method closure.

## PAPER4A Write-Ready Evidence Package And Context Sync

Active/consolidated stage:

```text
PAPER4A_WRITE_READY_EVIDENCE_PACKAGE_AND_CONTEXT_SYNC
```

PAPER4A consolidates completed evidence; it does not close body-yaw, exact reproduction, or same-evaluator superiority.

PAPER4A output root is represented in tracked docs by `<PAPER4A_STAGE_ROOT>`. It contains only lightweight reports, evidence ledgers, writing scaffold, figure/table planning, git-safety notes, reviewer/supervisor reports, and context-sync summaries.

PAPER4A input policy:

- PAPER1F direct files may be marked `MISSING_DIRECT_WITH_SECONDARY_PROOF` if only PAPER2B evidence is available.
- PAPER2A and PAPER2B are the governing QA and consolidation sources.
- PAPER3A-R1 and PAPER3B are governing frame-gap/physical-closure sources.
- PAPER3D-R2 through PAPER3I are provider/backend/literature-module evidence sources, with PAPER3I as the latest provider v4 boundary.

PAPER4A classification policy:

```text
MAIN_TEXT_ALLOWED=dataset protocol; BY2 120 canonical case design; PAPER2A QA behavior and coverage; RTKLIB/RINEX/DDLOS provider construction; provider v4 GPS+BDS residual-ready evidence; evidence classification matrix; forbidden-claim boundary table
APPENDIX_ALLOWED=PAPER2A row-level QA; PAPER3E/F/G/H/I native/proxy/backend-level literature-module diagnostics; LAMBDA/MLAMBDA helper evidence; provider v4 system/frequency blockers; internal baseline coverage
DIAGNOSTIC_ONLY=PAPER1F adapters; yaw transform sensitivity; baseline-heading diagnostics; RTKLIB moving-base diagnostics; BY3 yaw; XB/PG severe-GNSS stress; Pavlasek IEKF and Wu EQKF diagnostics
BLOCKED_WITH_PROOF=physical body-yaw frame; same-evaluator superiority; non-GPS provider closure; direct PAPER1F source if no path is found
FORBIDDEN_CLAIM=body-yaw RMSE; yaw superiority; exact reproduction; five faithful external dual-antenna algorithms; final_v23/LegSA superiority; BY3 yaw generalization; XB severe-GNSS high-precision proof; trace online; receiver IMU as Go2 body IMU; full contact/joint-foot claim
```

PAPER4A does not authorize solver/evaluator execution, degraded-input generation, random arrays, figure rendering, retuning, algorithm changes, RTKLIB source modification, external-code modification, runtime/raw/RINEX/UBX/RTCM staging, final paper figures, final paper claims, PR merge/closure/tag, or push.

## PAPER4B_R2 Physical Frame Close And Yaw Reevaluation

Active/completed stage:

```text
PAPER4B_R2_PHYSICAL_FRAME_CLOSE_AND_YAW_REEVALUATION
```

PAPER4B_R2 closes the physical antenna-to-body frame using user-confirmed installation evidence. It does not close exact reproduction, full faithful external algorithms, same-evaluator superiority, BY3 yaw generalization, XB severe-GNSS high-precision proof, or final paper claims.

PAPER4B_R2 output roots are represented in tracked docs by `<PAPER4B_R2_STAGE_ROOT>` and `<PAPER4B_R2_EXPORT_ROOT>`. The stage keeps full derived epoch payloads in the runtime root and exports only lightweight reports, summary CSVs, render-QA outputs, figure/table indices, and context summaries.

PAPER4B_R2 accepted frame policy:

```text
physical_geometry_status=PHYSICAL_BASELINE_GEOMETRY_CLOSED
body_frame=Go2_FLU
GNSS1=robot_right_y_negative
GNSS2=robot_left_y_positive
GNSS1_to_GNSS2=body_plus_Y_left
fixed_transform=body_yaw_NED_deg = wrap360(baseline_heading_NED_deg + 90 deg)
trace_used_online=false
receiver_imu_data_as_body_imu=false
```

PAPER4B_R2 reevaluation policy:

- PAPER3F/PAPER3G/PAPER3H rows with explicit native `atan2(E,N)` baseline-heading semantics may be reevaluated offline as derived body-yaw metrics.
- PAPER3I Wu EQKF DD/LOS row headings and Pavlasek IEKF innovation diagnostics remain diagnostic/blocked unless a later stage provides case-level baseline-state epoch outputs.
- The +90 deg transform is fixed by physical installation evidence and cannot be selected, varied, or tuned by trace/RMSE.

Recommended next actions:

- Use PAPER4B_R2 summaries as appendix or boundary-safe evidence unless the manuscript needs a dedicated yaw-frame subsection.
- Keep PAPER3I diagnostic outputs out of main-text body-yaw metric claims.
- Do not introduce superiority claims without a separate same-evaluator internal-baseline join and reviewer approval.

## PAPER4G Yaw Boundary Freeze And Native Metrics Write Package

Completed stage:

```text
PAPER4G_YAW_BOUNDARY_FREEZE_NATIVE_METRICS_WRITE_PACKAGE
```

PAPER4G freezes the external-method body-yaw boundary after PAPER4F_R2. The user-declared BY2 minimal-export reference policy `trace_body_yaw_NED_deg = wrap360(trace_yaw_deg + 90 deg)` was evaluated on all 2160 PAPER3F/PAPER3G/PAPER3H vector-closed method-case rows, but the systematic 90 deg-class discrepancy remained. Therefore, body-yaw RMSE and yaw-superiority claims stay diagnostic-only.

Current paper route:

- report physical GNSS1-right/GNSS2-left frame closure as an accepted setup fact;
- keep trace yaw source and Fixposition output-frame audits in the appendix;
- use native DD/LOS baseline, residual, ambiguity, provider-readiness, ratio/ADOP, and fix-rate-proxy evidence for external literature method discussion;
- keep PAPER4F_R2 row-level body-yaw reevaluation as diagnostic-only evidence.

Recommended next actions:

- draft the experiment section around native DD/LOS evidence and dataset-role-aware protocol;
- avoid main-text external-method body-yaw RMSE plots;
- use `PAPER4G_NATIVE_DDLOS_METRICS_LEDGER.csv` and `PAPER4G_EXTERNAL_LITERATURE_METHOD_STATUS.csv` as the method-status source for Teunissen/Liu/Yang/Wu/Pavlasek/RTKLIB discussion.

## PAPER10C Go2 High-Level Prior Evidence Freeze

Completed stage:

```text
PAPER10C_GO2_HIGH_LEVEL_PRIOR_EVIDENCE_FREEZE
```

PAPER10C froze Go2 high-level state as a bounded auxiliary weak-prior line, not a full contact-aided or truth-source line. It audited the code path, imported N7C6 provider evidence, ran BY2 normal smoke and BY2 120 Go2 ablation under fixed `SA04_N6B_POLICY`, and produced blocked proof for unsupported readiness metadata and missing BY3 Go2 provider evidence.

Current route decision:

- `PAPER10B2_MULTI_STATE_QUALITY_MANAGEMENT_CLOSURE` is recommended only if readiness/motion-state LSIM metadata must be claimed as multi-state quality management.
- `PAPER10E_FINAL_PROPOSED_METHOD_MATRIX_AND_COMPARISON_FREEZE` can proceed if Go2 is kept as a bounded auxiliary weak-prior module.
- `PAPER10D_SELECTED_FGO_FEEDBACK_EVIDENCE_FREEZE` remains optional and should not be required before PAPER10E unless the manuscript makes selected-feedback a visible contribution.

PAPER10C does not authorize BY3 ordinary yaw generalization, Go2 truth claims, full contact-aided InEKF, complete nine-factor FGO, external DA/LC reruns, trace online use, final_v23/LegSA output solver input, per-case tuning, or push.

## PAPER10C_R1A Interrupted Go2 BY3 Matrix Resume

Completed recovery stage:

```text
PAPER10C_R1A_RESUME_INTERRUPTED_GO2_BY3_MATRIX_AND_COMPLETE_STAGE
```

PAPER10C_R1A resumes the interrupted `PAPER10C_R1_BY3_GO2_PROVIDER_AND_READINESS_LSIM_CLOSURE` stage without restarting the full matrix. It generated a resume manifest, audited BY3 Go2 providers, preserved completed outputs, and created a missing-only wrapper. Runner execution was not performed because the Windows E free-space gate failed.

Current R1A evidence:

- BY2 Go2 120x6 is closed: 720/720 completed-evaluable.
- BY3 Go2 120x6 is partial: 543/720 completed-evaluable, 169 missing, 8 partial/corrupted.
- BY3 Go2 roll/pitch, horizontal velocity, and readiness/motion-state providers are present and generated from BY3 `by3.txt`, not BY2.
- G03/G05 readiness metadata has first-class LSIM evidence in completed rows, but readiness modes are not globally closed until missing/partial BY3 rows are resumed.
- BY3 yaw remains diagnostic-only.

Next route:

- `PAPER10C_R1B_CLEAR_SPACE_AND_RUN_MISSING_ONLY_GO2_BY3_ROWS` after the human clears the space gate and confirms missing-only execution.
- `PAPER10B2_MULTI_STATE_QUALITY_MANAGEMENT_CLOSURE` only if the manuscript keeps multi-state quality management as a contribution.
- Do not use R1A to claim full BY2/BY3 Go2 closure, full contact-aided InEKF, full leg odometry, universal superiority, Go2 truth, or completed PAPER10B2.

## PAPER10C_R1B Low-Space BY3 Missing-Only Resume

Completed recovery/execution stage:

```text
PAPER10C_R1B_LOW_SPACE_BY3_MISSING_ONLY_RESUME
```

PAPER10C_R1B used the human-approved low-space policy to lower the Windows E hard-stop to 5 GB and WSL root hard-stop to 20 GB. It imported the R1A resume manifest, quarantined only the 8 partial/corrupted BY3 rows, and reran only the 169 missing plus 8 partial/corrupted BY3 rows.

Current R1B evidence:

- BY2 Go2 120x6 remains closed: 720/720 completed-evaluable.
- BY3 Go2 120x6 is closed: 720/720 completed-evaluable.
- R1B selected-row runtime: 177/177 completed-evaluable, 0 runtime failures.
- Completed rows were not overwritten.
- BY3 Go2 providers remain generated from BY3 `by3.txt`, not BY2.
- Readiness/motion-state is resolved as first-class LSIM metadata for G03/G05.
- BY3 yaw remains diagnostic-only.

Next route:

- `PAPER10B2_MULTI_STATE_QUALITY_MANAGEMENT_CLOSURE` is recommended only if the manuscript needs a multi-state quality-management contribution beyond bounded Go2 auxiliary priors.
- `PAPER10E_FINAL_PROPOSED_METHOD_MATRIX_AND_COMPARISON_FREEZE` can proceed if Go2 is kept as a bounded supporting mechanism.
- Do not use R1B to claim universal superiority, BY3 ordinary yaw generalization, Go2 position/yaw truth, full contact-aided InEKF, full leg odometry, complete nine-factor FGO, trace online use, final_v23/LegSA solver input, or per-case tuning.

## PAPER10Y Post-R1B Git Archive And WSL Space Cleanup

Completed maintenance stage:

```text
PAPER10Y_POST_R1B_GIT_ARCHIVE_AND_WSL_SPACE_CLEANUP
```

PAPER10Y is a maintenance-only closeout after PAPER10C_R1B. It rechecked the R1B evidence package, generated current-content and next-direction summaries, created tar.xz archives for selected completed WSL runtime/worktree material, verified those archives, deleted only verified WSL source directories or clean verified worktrees, and generated a Windows-side VHDX compact script.

Current PAPER10Y evidence:

- R1B remains accepted: BY2 Go2 120x6 and BY3 Go2 120x6 are both closed at 720/720.
- Archive verification passed for all selected tar.xz packages under `<PAPER10Y_ARCHIVE_ROOT>`.
- Verified WSL cleanup released about 67.1 GB of WSL internal space.
- `fstrim` was attempted but sudo required a password; VHDX compact remains a Windows Administrator PowerShell manual step.
- No solver/evaluator, DA, LC, GINav, MATLAB, RTKLIB, contact-aided reproduction, complete FGO, PAPER10B2, or PAPER10E execution was run.
- No raw data, C/G project data, main repo, C export, Obsidian vault, by2.txt, by3.txt, or trace source was deleted.

Next route:

- `PAPER10B2_MULTI_STATE_QUALITY_MANAGEMENT_CLOSURE` is recommended if the manuscript keeps multi-state quality management as one of the three main innovations.
- `PAPER10E_FINAL_PROPOSED_METHOD_MATRIX_AND_COMPARISON_FREEZE` remains the conservative route if multi-state quality management is downgraded.

## PAPER10B2 Multi-State Quality Management Closure

Conditional hard-stop stage:

```text
PAPER10B2_MULTI_STATE_QUALITY_MANAGEMENT_CLOSURE
```

PAPER10B2 implemented a real source-level multi-state QM layer above `SA04_N6B` source-aware LSIM/OIM and Go2 `G05_FULL_AUX` readiness/motion-state metadata. The fixed states are `NORMAL`, `DOWNWEIGHT`, `REJECT`, `HOLD`, `RECOVERY`, and `FALLBACK`; sources keep independent state/action/recovery traces. The mechanism is default-off under `QM00_OFF`.

Current evidence:

- Targeted PAPER10B2 unit/integration tests passed and `legsa_v23_port_core_demo` built successfully.
- BY2 QM matrix completed 600/600 rows.
- BY3 QM matrix stopped at 579/600 rows because `E_DRIVE_HARD_STOP` triggered at the user-defined 10 GB threshold.
- Missing-only BY3 resume manifest contains 21 rows: 16 mixed rows and 5 normal rows.
- BY3 yaw remains diagnostic-only.
- No external DA/LC/GINav/MATLAB/RTKLIB/contact-aided/complete FGO, trace online, final_v23/LegSA solver input, per-case tuning, output substitution, or Go2 position/yaw truth was used.

Current route decision:

- Final status: `CONDITIONAL_PASS_QM_RUNTIME_STOPPED_BY_10GB_HARD_STOP`.
- QM evidence enum: `QM_MECHANISM_READY_PERFORMANCE_MIXED`.
- Do not promote QM to `QM_MAIN_INNOVATION_READY` until BY3 missing-only rows are resumed and the mixed BY2/BY3 effects are reviewed.

Recommended next actions:

- Restore E drive free space above the hard-stop margin.
- Run only the BY3 missing-only resume manifest; do not overwrite completed rows.
- Re-run export QA and update the final claim decision.
- Enter `PAPER10E_FINAL_PROPOSED_METHOD_MATRIX_AND_COMPARISON_FREEZE` only after human review of the hard-stop boundary and QM wording.
