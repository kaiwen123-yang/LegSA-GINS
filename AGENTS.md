# AGENTS.md - LegSA-GINS Multi-Agent Working Rules

## 0. Purpose

This repository is used for the LegSA-GINS project: a legged-robot GNSS/INS fusion system with Raw Doppler, source-aware weighting, Go2 proprioceptive observations, legged candidate FGO factors, no-feedback FGO, and FGO-feedback EKF joint filtering.

This file is the persistent project context for Codex multi-agent work. It must prevent repeated context loss, phase confusion, false plot completion, unsafe merges, unsupported claims, and accidental algorithm changes.

The project uses a supervised multi-agent workflow:

- supervisor
- planner
- worker
- reviewer
- human final decision

The human user is the final decision maker for merge, tag, branch deletion, PR closure, and stage transitions.

## 1. Required Multi-Agent Workflow

### 1.1 Supervisor

The supervisor coordinates the task, checks stage boundaries, spawns planner first, approves or rejects worker scope, spawns reviewer after worker finishes, and asks the human before any merge, tag, force push, PR closure, branch deletion, or stage transition.

The supervisor must prevent phase confusion:

- N8K: BY2 formal ablation and ablation plot audit.
- N8K2-N8K6: real plot materialization and plot audit repairs.
- N9A: BY2 normal clean full plot audit.
- N9B: BY2 full degradation matrix.
- N9B1D4: current technical pilot source for deterministic degradation preparation.
- N9B1E: current pilot visual/go-no-go source, passed with the C yaw caution.
- N9B2A/N9B2A1: full-matrix preparation sources.
- N9B2B: path lock stage; locks Windows plus WSL aliases and future by2-huitu output alias.
- N9B2B1: documentation/context update after path lock.
- N9B2C: batch0 smoke plan and optional execution precheck.
- N9B2D: batch0 normal parity smoke.
- N9B2E: batch1 deterministic execution after human approval.
- N9B2F/N9B2F1: batch1 deterministic execution and review.
- N9B2G through N9B2K1: batch2 position-noise review and batch3 position-spike pipeline.
- N9B2L through N9B2M1: batch4 yaw-noise parameter lock, execution, and review.
- N9B2N through N9B2Q1: batch5 core module-disable and batch6 mixed long-pipeline preparation.
- N9B2R: final_v23 external baseline degradation control.
- N9B2S: batch6 selected mixed case definition and parameter lock.
- N9B2T0 through N9C0: batch6 mixed execution, review, and global staged consolidation precheck.
- N9C0A: documentation/context update after global consolidation precheck.
- N9C1: next planned consolidated figure generation stage; not yet run.
- N9C: degradation plotting, case review, and consolidated figure package stages.
- N9D: mathematical / evaluation / filter construction full-chain audit.
- N9E: BY2 paper-level packaging.
- N9F0_TO_N9F2: active nine-factor FGO legged design materialization and context sync; design/package stage only, no representative runs.
- N9F6A_TO_N9F7: source-code forensic audit and active FGO/legged completion review; Step 1 passed from source evidence, Step 2 took design-package-only Path C with no implementation or runs.
- N9F7A_TO_N9G0: Git/PR boundary lock and manual LegSA_9F_FGO_EKF design review; design package complete, implementation not started.
- N9G0A: Git boundary resolution completed; PR #52 head is synced to `9ceba928`.
- N9G1A: current context-lock stage before LegSA_9F_FGO_EKF implementation; documentation and audit reports only.
- N9G1B: planned Phase 1 provider/factor/logger/normal-smoke stage only after approval; no representative degradation or full matrix.
- N9G1C-E: current provider contract resolution, active backend audit, logger connection, and normal-smoke gate; normal smoke blocked by active backend.
- BY3A0_TO_BY3E: current BY3 normal-generalization and BY2 degradation report reorganization stage; BY3A0/A/B are complete, BY3C generated candidate inputs with provider blockers, BY3D/E solver/evaluator execution is blocked, and BY2T/BY2F summaries/archive were generated copy-only.
- BY3A1: current BY3-vs-BY2 parity and provider-gate repair stage; BY3 candidate inputs were repaired to BY2-compatible runtime schemas, BY3 Go2 priors were materialized, Raw Doppler and same-case feedback remain blocked, and solvers/evaluators were not run.
- BY3A2: current historical WSL pipeline recovery and runner-gate repair stage; historical BY2 Raw Doppler/Go2/single/final_v23/feedback chains were recovered, BY3 UBX/RAWX rebuild and accepted Raw Doppler provider materialization succeeded, same-case selected feedback remains blocked, and solvers/evaluators were not run.
- BY3A3: current BY3 selected-feedback stage1 chain and normal-generalization execution stage; BY3 same-case stage1 solver/evaluator/feedback generation, LegSA_full_EKF stage2, single baseline, final_v23 external baseline, official evaluation, figures, and case review completed for normal BY3 only.
- BY3A4A: BY3 lateral dual-antenna yaw repair and context-memory-lock stage; BY2 lateral yaw policy was recovered as partial, lateral antenna geometry was encoded, existing BY3A3 outputs were audited without solver rerun, and no physically/BY2-backed yaw policy passed sanity.
- BY3A4C: current BY3 git-history yaw-reference reconstruction and visual-validation stage; the historical N4H2C/N4H2D/N4R/N4R2/N4R3 yaw-reference fix was recovered from git/docs/runtime evidence, BY2 `official_ref_sign_minus` direct-reference logic was verified, BY3 yaw remains `not_evaluable`, and any BY3 degradation planning is position/up-only until yaw source mapping is confirmed.
- BY3A5: historical BY3 dual-yaw input source audit; it correctly confirmed the old BY3 15-column yaw was wrong-source, but its HDT replacement policy is superseded for mainline BY3.
- BY3A5B: historical BY3 A1 dual-diff yaw-input repair and normal rerun stage; BY3 dual yaw is generated from GNSS1/GNSS2 short-baseline position difference with BY2 sign/lateral conversion and fixed_1p5 yaw std. Normal rerun completed, but official yaw remained unresolved.
- BY3A6: historical BY3 trace-truth, initatt, and yaw-gate forensic repair stage; trace truth/parser/base_time were validated, stage1/LegSA stale first-row initatt was repaired to starttime-aligned A1 yaw, BY3 normal-only rerun completed, and yaw still failed before BY3A7.
- BY3A7: historical BY3 A1 yaw dynamic-quality, IMU sign-axis, and yaw-gate repair stage; A1 remains valid with dynamic-quality caution, BY3 Go2 IMU preprocessing bias from a moving segment was confirmed and repaired with a pre-motion source-bias BY3A7-local IMU, and BY3 normal-only rerun passed yaw sanity for dual-yaw algorithms.
- BY3A8: current BY3 yaw error-budget and safe-repair stage; A1 observation lower-bound RMSE is about 24.06 deg versus trace as evaluation-only reference, no source-backed additional repair passed, no normal rerun/degradation was run, and BY3 degradation planning is position/up with diagnostic yaw only. Paper claims remain false.
- BY3B: historical BY3 position/up degradation planning and precheck stage; BY3A8 position/up-with-diagnostic-yaw scope was imported, BY3A7 repaired IMU and BY3A5B A1_dual_diff yaw were locked for future execution, case/seed/provider/command/evaluator/figure/batch plans were created only, and no degraded inputs, random arrays, solvers, evaluators, figures, or paper claims were produced.
- BY3C: current BY3 position/up degradation execution stage for approved Batch 0 through Batch 3 only; normal parity, deterministic A/B/E_position_std, C_position_noise seed0-9, and D_position_spike seed0-9 completed with official evaluations, same-case feedback, figures, case reviews, and consolidated review. H/yaw-std/mixed/module/full-matrix/LegSA_9F/nonredundant cases were not executed; yaw remains diagnostic-only and paper claims remain false.
- BY3C1_TO_BY3Y1: current review-only BY3 position/up generalization and yaw diagnostic explanation stage; it audited BY3C Batch0-Batch3 results, built three-scheme BY3 and overlapping BY2-vs-BY3 summaries, generated review figures from existing metrics only, explained BY3 yaw as diagnostic-only from existing BY3A5B-BY3A8 evidence, and ran no solvers/evaluators/degraded-input/random-generation work.
- GEN1_BY2_BY3_GENERALIZATION_REPORT_AND_BY3_FIGURE_ORGANIZATION: current cross-dataset report and BY3 figure-organization stage; it built BY2/BY3 three-scheme inventories and summaries from existing metrics, generated cross-dataset figures from existing metrics only, created a copy-only BY3 figure summary view, and preserved BY3 yaw as diagnostic-only with `ready_for_paper_claims=false`.
- XB1A0_TO_XB1E_POOR_GNSS_GENERALIZATION_CONTEXT_QUALITY_AUDIT_ALIGNMENT_AND_NORMAL_RUN: completed first poor-GNSS repeated-experiment bootstrap for engineering alias XB1 / experiment alias PG1_20260105_122513; context, literature criteria, inventory, GNSS quality profile, kick alignment, input/provider gates, export-clean, and review package were created under `<XB1_STAGE_ROOT>`, but normal solver/evaluator execution was blocked by severe GNSS quality/input/provider gates.
- XB1A1_BLOCKER_TRIAGE_RAW_DOPPLER_A1_YAW_AND_MAINLINE_NORMAL_GATE: historical XB1 blocker-triage stage; Raw Doppler provider materialization was repaired through the accepted RTKLIB/RINEX/helper path using the WSL gcc/helper bridge, A1 short-baseline dual yaw was reported invalid, LegSA_full_EKF and final_v23 dual-yaw normal runs remained blocked/not applicable, and only the GNSS1-status single baseline completed normal official evaluation. No degradation, retuning, quality-aware execution, or paper claim was performed.
- XB1A2_A1_DUAL_DIFF_RELPOS_DIFFERENCE_REAUDIT_AND_NORMAL_RERUN: current XB1 correction stage; it suspends/supersedes XB1A1's A1 source-provenance conclusion, recovers both the BY2/process_data-compatible status `rel_pos_gnss2-rel_pos_gnss1` path and the BY3A5B absolute-position repair path, audits both for XB1, and finds no valid A1 source. The accepted BY2 rel_pos-difference candidate remains nonphysical for XB1 with about 1.97 percent physical-band epochs, median length about 9.18 m, and p95 about 50.96 m. Dual-yaw normal remains blocked; quality-aware diagnostic branch planning is recommended after human review. No degradation, retuning, quality-aware execution, dual-yaw solver forcing, or paper claim was performed.
- PG_MULTI_A0_POOR_GNSS_REPEATED_DATASET_SOURCE_REVIEW_AND_RUNNABILITY_CLASSIFICATION_WITH_LOCKED_XB2_XB3_XB4_BODY_PATHS: current poor-GNSS multi-repeat source review; PG1/XB1 was imported from XB1A2, PG2/PG3/PG4 receiver roots and user-locked body/high-level paths were registered, GNSS quality profiles/body feasibility/provider feasibility were audited, and the BY2-compatible status relpos-difference A1 path was audited for all repeats. PG2/PG3/PG4 all have nonphysical relpos-diff A1 baselines, so PG1-PG4 are classified as `quality_aware_branch_candidate` with position-only fallback as diagnostic only. No solvers, evaluators, degraded inputs, random arrays, retuning, quality-aware branch implementation, or paper claims were performed.
- PG_QA0_QUALITY_AWARE_FALLBACK_DESIGN_AND_PAPER_MAINLINE_DECISION: current poor-GNSS design-only follow-on after PG_MULTI_A0 and XB1A2; it organizes BY2, BY3, and PG1-PG4 evidence, defines the separate future candidate `LegSA_QA_Fallback_EKF`, designs quality-state, measurement, R-scale, Raw Doppler, Go2 bridge, logging, validation, and paper-positioning policies, and recommends Option B for the near-term paper with Option C only after human-reviewed QA1/QA2/QA3 work. No implementation, solver, evaluator, degraded input, random array, retuning, quality-aware execution, or paper claim was performed.
- PAPER0_MAINLINE_EVIDENCE_PACKAGE_AND_CLAIM_BOUNDARY_REVIEW: current paper-facing evidence package after PG_QA0; it organizes BY2 as the full-metric main dataset, BY3 as independent position/up generalization with diagnostic-only yaw, PG1-PG4 as severe-GNSS boundary/QA motivation, and PG_QA0 as design extension. It generated paper table drafts, figure recommendations, narrative outline, journal-positioning notes, missing-work decision, export-clean material, and claim-boundary matrices from existing evidence only. No solver, evaluator, degraded input, random array, QA1 implementation, retuning, metric alteration, final figure, or final paper claim was performed.
- PAPER10C_R1A_RESUME_INTERRUPTED_GO2_BY3_MATRIX_AND_COMPLETE_STAGE: current interrupted-stage recovery for PAPER10C_R1. It recovered BY3 Go2 provider evidence and a resume manifest, preserved completed rows, found BY2 720/720 closed and BY3 543/720 completed-evaluable, identified 169 missing and 8 partial/corrupted BY3 rows, created a missing-only wrapper, but did not execute it because Windows E free space failed the runner gate. No completed output was overwritten, no trace-online/per-case tuning/DA/LC/GINav/MATLAB/RTKLIB/contact-aided/complete FGO was run, and BY3 yaw remains diagnostic-only.
- PAPER10M1R2D_R1_V2_BY2_INTERNAL_ABLATION_MATRIX_EXECUTION_4869ROWS: completed BY2 yaw-corrected internal ablation matrix execution source with 9 x 541 rows; it used only M1R2B2 yaw-corrected provider-ready cases and treated M1R2C_R1 as full-algorithm reference only.
- PAPER10M1R2E_BY2_RESULT_REVIEW_FIGURE_PACKAGE_AND_CLAIM_BOUNDARY_FREEZE: current BY2 result-review, figure-candidate, Chinese-summary, and claim-boundary freeze stage. It is review-only: no solver/evaluator, provider generation, degradation/random generation, BY3, XB/PG, PAPER10H, or horizontal comparison. M1R2C_R1 and M1R2D_R1 are the current valid BY2 evidence sources; old M1R2C yaw-invalid metrics are forbidden. Module contribution claims require M1R2E classification, and weak/no-effect/alias modules must not be inflated into claims.
- PAPER10Q1_QM_DEGRADED_ACTION_EVIDENCE_AND_FIGURE_PACKAGE: current QM evidence-strengthening and figure-review package. It is review/plot-only from frozen M1R2C_R1/M1R2D_R1 evidence; generated PNG/PDF figures stay outside Git. QM/source-aware claims must be family-specific, legacy `bad_a1_consumed_count` is deprecated, and BY3/XB/PAPER10H/horizontal comparison remain not run.

### 1.2 Planner

Planner is read-only. It inspects branch, PR, git status, reports, docs, runtime roots, and risks; creates an execution plan; identifies required files, expected outputs, blockers, validation commands, and forbidden actions; and never edits files, creates runtime outputs, or commits.

### 1.3 Worker

Worker executes only the supervisor-approved plan. It edits only approved tracked files, creates runtime reports only in approved runtime folders, never commits raw data or generated artifacts, never changes algorithms unless explicitly approved, never tunes using trace/final_v23, and reports exactly what was done.

### 1.4 Reviewer

Reviewer is read-only. It reviews git diff, checks hard boundaries, checks runtime artifacts were not committed, checks no local path leaks exist, checks claim boundaries, verifies reports match actual outputs, and never edits files.

### 1.5 Human

The human user decides whether to merge, tag, close PRs, delete branches, proceed to the next stage, or authorize N9B2 execution. No agent may bypass the human final decision.

## 2. Global Hard Boundaries

Unless explicitly requested by the human, never do the following:

- Do not merge PR #21 or PR #52.
- Do not close PR #21 or PR #52.
- Do not delete remote branches.
- Do not force push.
- Do not stage, commit, push, merge, tag, or create PRs from worker/reviewer roles.
- Do not commit raw data or `by2.txt`.
- Do not commit NAV / STD / EVAL_NAV / RUN_MANIFEST runtime outputs.
- Do not commit generated figures.
- Do not commit `FGO_FEEDBACK_OBSERVATIONS.csv`.
- Do not commit `FGO_SMOOTHED_NAV.csv`.
- Do not commit `FGO_FACTOR_TABLE.csv`.
- Do not commit generated degradation CSV / summary / case review runtime files.
- Do not write local absolute paths into tracked docs/config/scripts.
- Do not edit `docs/codex_context/DATA_PATHS.local.md` unless explicitly requested.
- Do not modify `<WSL_ALGO_REPO>`.
- Do not run git add / commit / checkout / reset / pull / push inside `<WSL_ALGO_REPO>`.
- Do not compile reference/final_v23 itself.
- Do not use trace as solver input.
- Do not use final_v23 output as solver input.
- Do not tune using trace or final_v23.
- Do not perform output-only correction.
- Do not directly overwrite EKF NAV with FGO output.
- Do not delete bad epochs to pass metrics.
- Do not make paper performance claims unless explicitly approved after multi-dataset evidence.
- Do not claim outperform final_v23.
- Do not treat Go2 position, velocity, contact, or yaw as truth.
- Do not treat GNSS source observations as algorithm estimates.
- Do not treat placeholder PNG generation as successful plotting.
- Do not run more N9B2 execution unless the human defines a new follow-up.
- Do not run N9C1 figure generation until the human explicitly approves N9C1.
- Do not run solvers, evaluators, random generation, degraded-input generation, degradation matrices, or figures during context-only stages such as N9C0A.

## 3. Path And Output Policy

Tracked docs must use aliases only:

- `<WINDOWS_AUDIT_ROOT>`
- `<WSL_AUDIT_ROOT>`
- `<WSL_ALGO_REPO>`
- `<BY2_N9B2_WINDOWS_ROOT>`
- `<BY2_N9B2_WSL_ROOT>`
- `<BY2_N9B2_FULL_MATRIX_ROOT>`
- `<BY2_N9B2_DEFERRED_EXT4_ROOT>`
- `<N9C0_CONSOLIDATED_PRECHECK_ROOT>`
- `<FINALV23_EXTERNAL_BASELINE_ROOT>`
- `<BY3C1_STAGE_ROOT>`
- `<BY3C1_REVIEW_PACKAGE_ROOT>`
- `<BY3Y1_STAGE_ROOT>`
- `<BY3C1_EXPORT_CLEAN_ROOT>`
- `<GEN1_STAGE_ROOT>`
- `<BY3_FIGURE_SUMMARY_ROOT>`
- `<GEN1_EXPORT_CLEAN_ROOT>`
- `<XB1_OUTPUT_ROOT>`
- `<XB1_STAGE_ROOT>`
- `<XB1A1_STAGE_ROOT>`
- `<XB1A2_STAGE_ROOT>`
- `<XB1_FULL_MATRIX_ROOT>`
- `<XB1A1_NORMAL_GATE_ROOT>`
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
- `<PAPER10Y_STAGE_ROOT>`
- `<PAPER10Y_C_EXPORT_ROOT>`
- `<PAPER10Y_ARCHIVE_ROOT>`
- `<PAPER10Y_OBSIDIAN_SYNC_ROOT>`
- `<PAPER10B_R2_STAGE_ROOT>`
- `<PAPER10G_R2A_STAGE_ROOT>`
- `<PAPER10G_R2A_C_EXPORT_ROOT>`
- `<PAPER10G_R2A_OBSIDIAN_SYNC_ROOT>`
- `<PAPER10E0_STAGE_ROOT>`
- `<PAPER10E0_C_EXPORT_ROOT>`
- `<PAPER10E0_OBSIDIAN_SYNC_ROOT>`
- `<PAPER10M1R2D_R1_STAGE_ROOT>`
- `<PAPER10M1R2D_R1_RUNTIME_ROOT>`
- `<PAPER10M1R2D_R1_C_EXPORT_ROOT>`
- `<PAPER10M1R2E_STAGE_ROOT>`
- `<PAPER10M1R2E_LOCAL_REVIEW_ROOT>`
- `<PAPER10M1R2E_C_EXPORT_ROOT>`
- `<PAPER10Q1_STAGE_ROOT>`
- `<PAPER10Q1_FIGURE_ROOT>`
- `<PAPER10Q1_C_EXPORT_ROOT>`
- `<PG2_XB2_RECEIVER_ROOT>`
- `<PG2_XB2_BODY_SOURCE>`
- `<PG3_XB3_RECEIVER_ROOT>`
- `<PG3_XB3_BODY_SOURCE>`
- `<PG4_XB4_RECEIVER_ROOT>`
- `<PG4_XB4_BODY_SOURCE>`

Actual local absolute paths belong only in ignored `docs/codex_context/DATA_PATHS.local.md`.

N9B2B locks the Windows and WSL path aliases and the current BY2/N9 runtime alias root. Future BY2/N9 outputs must use the `BY2_N9B2_*` aliases. N9C0 consolidated precheck artifacts are represented by `<N9C0_CONSOLIDATED_PRECHECK_ROOT>`, under `<BY2_N9B2_FULL_MATRIX_ROOT>`. The old Chinese output root is read-only historical evidence, not the active output root. Native Ubuntu migration is deferred.

Runtime outputs remain untracked. The N9C0A runtime root is represented in tracked docs only by the alias `<BY2_N9B2_WINDOWS_ROOT>/N9C0A_CONTEXT_UPDATE_AFTER_GLOBAL_CONSOLIDATION`.
The N9F6A/N9F7 runtime root is represented in tracked docs only by the alias `<BY2_N9B2_WINDOWS_ROOT>/N9F6A_TO_N9F7_CODEBASE_FORENSIC_AUDIT_AND_ACTIVE_FGO_LEGGED_COMPLETION`.
The N9F7A/N9G0 runtime root is represented in tracked docs only by the alias `<BY2_N9B2_WINDOWS_ROOT>/N9F7A_TO_N9G0_GIT_BOUNDARY_AND_MANUAL_LEGSA_9F_FGO_EKF_DESIGN_REVIEW`.
The N9G0 design package root is represented in tracked docs only by the alias `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_LEGSA_9F_FGO_EKF_DESIGN_PACKAGE`.
The N9G0 export-clean package root is represented in tracked docs only by the alias `<BY2_N9B2_FULL_MATRIX_ROOT>/N9G0_EXPORT_CLEAN_DESIGN_PACKAGE`.
The N9G1A/N9G1B runtime root is represented in tracked docs only by the alias `<BY2_N9B2_WINDOWS_ROOT>/N9G1A_TO_N9G1B_CONTEXT_LOCK_AND_LEGSA_9F_PHASE1_IMPLEMENTATION`.
The N9G1C-E runtime root is represented in tracked docs only by the alias `<BY2_N9B2_WINDOWS_ROOT>/N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
The BY3A0_TO_BY3E runtime root is represented in tracked docs only by the alias `<BY3_STAGE_ROOT>`.
The BY3A1 runtime/audit root is represented in tracked docs only by the alias `<BY3A1_STAGE_ROOT>`.
The BY3A2 runtime/audit root is represented in tracked docs only by the alias `<BY3A2_STAGE_ROOT>`.
The BY3A3 runtime/audit root is represented in tracked docs only by the alias `<BY3A3_STAGE_ROOT>`.
The BY3A4A runtime/audit root is represented in tracked docs only by the alias `<BY3A4A_STAGE_ROOT>`.
The BY3A4C runtime/audit root is represented in tracked docs only by the alias `<BY3A4C_STAGE_ROOT>`.
The BY3A5B runtime/audit root is represented in tracked docs only by the alias `<BY3A5B_STAGE_ROOT>`, with execution artifacts under `<BY3_FULL_MATRIX_ROOT>/BY3A5B_A1_DUAL_DIFF_REPAIR`.
The BY3A6 runtime/audit root is represented in tracked docs only by the alias `<BY3A6_STAGE_ROOT>`, with execution artifacts under `<BY3_FULL_MATRIX_ROOT>/BY3A6_TRACE_TRUTH_INITATT_GATE_FORENSIC`.
The BY3A7 runtime/audit root is represented in tracked docs only by the alias `<BY3A7_STAGE_ROOT>`, with execution artifacts under `<BY3_FULL_MATRIX_ROOT>/BY3A7_YAW_DYNAMIC_GATE_REPAIR`.
The BY3A8 runtime/audit root is represented in tracked docs only by the alias `<BY3A8_STAGE_ROOT>`, with execution artifacts under `<BY3_FULL_MATRIX_ROOT>/BY3A8_YAW_ERROR_BUDGET_REPAIR`.
The BY3B runtime/audit root is represented in tracked docs only by the alias `<BY3B_STAGE_ROOT>`, with planning artifacts under `<BY3_FULL_MATRIX_ROOT>/BY3B_POSITION_UP_DEGRADATION_MATRIX`.
The BY3C runtime/audit root is represented in tracked docs only by the alias `<BY3C_STAGE_ROOT>`, with executed Batch0-Batch3 artifacts under `<BY3_FULL_MATRIX_ROOT>/BY3C_POSITION_UP_DEGRADATION_EXECUTION`.
The BY3C1/BY3Y1 review runtime root is represented in tracked docs only by `<BY3C1_STAGE_ROOT>`, with the review package under `<BY3C1_REVIEW_PACKAGE_ROOT>`, yaw diagnostic package under `<BY3Y1_STAGE_ROOT>`, and export-clean package under `<BY3C1_EXPORT_CLEAN_ROOT>`.
The GEN1 cross-dataset review runtime root is represented in tracked docs only by `<GEN1_STAGE_ROOT>`, with the copy-only BY3 figure organization under `<BY3_FIGURE_SUMMARY_ROOT>` and the export-clean package under `<GEN1_EXPORT_CLEAN_ROOT>`.
The XB1 / PG1 poor-GNSS generalization bootstrap is represented in tracked docs only by `<XB1_STAGE_ROOT>`, with normal bootstrap runtime material under `<XB1_FULL_MATRIX_ROOT>/XB1A_NORMAL_BOOTSTRAP`, export-clean material under `<XB1_EXPORT_CLEAN_ROOT>`, receiver data under `<XB1_RECEIVER_ROOT>`, and body/high-level data under `<XB1_BODY_SOURCE>`.
The XB1A1 blocker-triage and normal-gate repair stage is represented in tracked docs only by `<XB1A1_STAGE_ROOT>`, with its normal-gate runtime material under `<XB1A1_NORMAL_GATE_ROOT>`.
The XB1A2 rel_pos-difference A1 re-audit stage is represented in tracked docs only by `<XB1A2_STAGE_ROOT>`, with its relpos-diff repair runtime material under `<XB1A2_RELPOS_DIFF_REPAIR_ROOT>`.
The PG multi-repeat poor-GNSS review root is represented in tracked docs only by `<PG_MULTI_REVIEW_ROOT>`, with the PG_MULTI_A0 runtime reports under `<PG_MULTI_A0_STAGE_ROOT>` and the PG_QA0 design package under `<PG_QA0_STAGE_ROOT>`. PG2/PG3/PG4 receiver and body/high-level sources are represented only by `<PG2_XB2_RECEIVER_ROOT>`, `<PG2_XB2_BODY_SOURCE>`, `<PG3_XB3_RECEIVER_ROOT>`, `<PG3_XB3_BODY_SOURCE>`, `<PG4_XB4_RECEIVER_ROOT>`, and `<PG4_XB4_BODY_SOURCE>`.
The paper-facing evidence review root is represented in tracked docs only by `<PAPER_EVIDENCE_REVIEW_ROOT>`, with PAPER0 runtime material under `<PAPER0_STAGE_ROOT>`.
The PAPER10C_R1 interrupted Go2/LSIM recovery source is represented in tracked docs only by `<PAPER10C_R1_STAGE_ROOT>`.
The PAPER10C_R1A resume stage is represented in tracked docs only by `<PAPER10C_R1A_STAGE_ROOT>`, with export-clean material under `<PAPER10C_R1A_C_EXPORT_ROOT>` and vault notes under `<PAPER10C_R1A_OBSIDIAN_SYNC_ROOT>`.
The PAPER10C_R1B low-space missing-only resume stage is represented in tracked docs only by `<PAPER10C_R1B_STAGE_ROOT>`, with export-clean material under `<PAPER10C_R1B_C_EXPORT_ROOT>` and vault notes under `<PAPER10C_R1B_OBSIDIAN_SYNC_ROOT>`.
The PAPER10Y post-R1B maintenance/archive stage is represented in tracked docs only by `<PAPER10Y_STAGE_ROOT>`, with lightweight export material under `<PAPER10Y_C_EXPORT_ROOT>`, archive bodies under `<PAPER10Y_ARCHIVE_ROOT>`, and vault notes under `<PAPER10Y_OBSIDIAN_SYNC_ROOT>`.
The PAPER10G_R2A LSE method-distinctness audit and recompute gate is represented in tracked docs only by `<PAPER10G_R2A_STAGE_ROOT>`, with export-clean material under `<PAPER10G_R2A_C_EXPORT_ROOT>` and vault notes under `<PAPER10G_R2A_OBSIDIAN_SYNC_ROOT>`.
The PAPER10E0 Basic Dual-Yaw EKF baseline freeze is represented in tracked docs only by `<PAPER10E0_STAGE_ROOT>`, with lightweight export material under `<PAPER10E0_C_EXPORT_ROOT>` and vault notes under `<PAPER10E0_OBSIDIAN_SYNC_ROOT>`.
The PAPER10M1R2D_R1 BY2 internal ablation matrix is represented in tracked docs only by `<PAPER10M1R2D_R1_STAGE_ROOT>`, with runtime material under `<PAPER10M1R2D_R1_RUNTIME_ROOT>` and export-clean material under `<PAPER10M1R2D_R1_C_EXPORT_ROOT>`.
The PAPER10M1R2E BY2 result-review and claim-boundary freeze package is represented in tracked docs only by `<PAPER10M1R2E_STAGE_ROOT>`, with lightweight local review material under `<PAPER10M1R2E_LOCAL_REVIEW_ROOT>` and export-clean material under `<PAPER10M1R2E_C_EXPORT_ROOT>`.
The PAPER10Q1 QM degraded-action evidence package is represented in tracked docs only by `<PAPER10Q1_STAGE_ROOT>`, with review-only PNG/PDF figures outside Git under `<PAPER10Q1_FIGURE_ROOT>` and export-clean text material under `<PAPER10Q1_C_EXPORT_ROOT>`.
Prior BY3 source-aware source material imported by PAPER10C_R1 is represented only by `<PAPER10B_R2_STAGE_ROOT>`.
The BY3 full-matrix runtime root is represented in tracked docs only by the alias `<BY3_FULL_MATRIX_ROOT>`.
The BY3 receiver root is represented in tracked docs only by `<BY3_RECEIVER_ROOT>`.
The BY3 Go2 body/high-level source is represented in tracked docs only by `<BY3_GO2_BODY_SOURCE>`.
The BY2 degradation report archive source is represented in tracked docs only by `<BY2_DEGRADATION_ARCHIVE_ROOT>`.
The BY2 degradation text-summary root is represented in tracked docs only by `<BY2_DEGRADATION_TEXT_SUMMARY_ROOT>`.

## 4. Data Source Roles

### 4.1 Trace

Role: evaluation-only reference/truth after alignment.

Never: solver input, tuning source, algorithm estimate, feedback correction source.

### 4.2 GNSS Raw And Status

Role: source observations, GNSS observation quality, yaw observation, Raw Doppler source diagnostics.

Never: algorithm estimate, trajectory estimate, direct metric source.

A1 dual-yaw invalid conclusions must audit the actual dual-difference construction before rejection. For BY2/process_data-compatible status yaw this means auditing `rel_pos_gnss2 - rel_pos_gnss1` after GNSS2 interpolation to GNSS1 time; a single status `rel_pos_n/e/d` row may be a long RTK base vector and must not be used directly as antenna heading. BY3A5B's accepted BY3 repair used GNSS1/GNSS2 absolute-position short baseline because BY3 status rel_pos was rejected as a long-base vector. XB1A2 audited both families for XB1 and found both nonphysical, so no dual-yaw fallback is authorized.

### 4.3 `by2.txt`

Role: Go2 body/high-level source data, Go2 IMU/body state, Go2 velocity/contact/foot/mode/gait diagnostic source.

Never: truth or absolute pose reference.

### 4.4 Receiver IMU Data

Role: diagnostic source unless explicitly approved.

Never: replacement for Go2 body IMU without explicit review.

### 4.5 NAV / EVAL_NAV / STD / RUN_MANIFEST

Role: algorithm outputs, evaluation chain, plot source for estimates/errors/metrics/comparisons.

Trajectory, error, and metric plots must use verified algorithm outputs, not source observations. Final-only metrics rule: reported metrics must come from final algorithm output/evaluation files for the case under review, not intermediate source diagnostics.

Current active global metrics source after N9C0: `<N9C0_CONSOLIDATED_PRECHECK_ROOT>/matrix/N9C0_ACTIVE_FINAL_ONLY_METRICS_TABLE`. The N9C0 active final-only metrics table has 825 rows. Do not use superseded rows, `historical_nominal_none`, or source diagnostics for current claims.

### 4.6 final_v23 Output

Role: external reference comparison / sanity check only.

Never: solver input, tuning source, hidden target, or performance-claim basis by itself.

## 5. Runner Rules

- Formal execution must use `legsa_v23_port_core_demo` plus `by2_algorithm_runner`.
- `legsa_gins --run-filter-csv` is diagnostic only.
- `selected_feedback` requires same-case feedback.
- Clean feedback cannot be reused for degraded cases.
- EVAL_NAV feedback generation uses state/estimate columns only.
- EVAL_NAV feedback generation must not use trace/error feedback corrections.
- No additional N9B2 execution is allowed unless a later stage explicitly approves it.
- N9C1 is figure generation and package preparation only; it is not paper-claim authorization.

## 6. Baseline Roles

- `single_antenna_gnss1_status_KF_GINS`: GNSS1-status baseline, not raw GNSS.
- `pure_INS_reference_initialized`: fixed/reference baseline.
- `final_v23_dual_antenna_EKF`: `external_reference_baseline` only.
- `true_no_feedback_FGO`: diagnostic unless full comparable output exists.

## 7. Matrix Cautions

- `B_gnss_downsample_2Hz` is invalid and superseded.
- Ratio downsample cases `every2`, `every5`, and `every10` are the active downsample family.
- `C_position_noise` has a yaw caution.
- `H_dual_yaw_noise` has a single-seed caveat.
- C and H require multi-seed treatment in N9B2.
- D position spike multi-seed is recommended.
- Superseded rows must never be used for active conclusions.

## 8. Current Route

Current completed route:

- N9A normal clean completed.
- N9B0, N9B0A, N9B0A1, N9B0A2 completed.
- N9B0B and N9B0C completed.
- N9B1A and N9B1A1 completed.
- N9B1C through N9B1G2 completed.
- N9B1D through N9B1D4 completed.
- N9B1E passed with C yaw caution.
- N9B2A completed.
- N9B2A1 completed.
- N9B2B completed.
- N9B2B1 completed.
- Batch 0 normal smoke completed.
- Batch 1 deterministic completed.
- Batch 2 position noise completed.
- Batch 3 position spike completed.
- Batch 4 yaw noise completed.
- Batch 5 core module-disable completed; module-stress remains deferred.
- Batch 6 selected mixed cases completed.
- final_v23 external baseline completed and integrated.
- N9C0 global staged consolidation precheck completed.
- N9E active nine-factor FGO/legged logger review completed with the logging-blocked decision.
- N9E decision: `complete_nine_factor_FGO_claim=false`; current `LegSA_full_EKF` lacks accepted row-level active FGO residual/cost evidence for all nine factors.
- N9F0_TO_N9F2 active nine-factor FGO legged design materialization and context sync completed.
- N9F6A source-code forensic audit from zero completed and passed reviewer gate.
- N9F7 took Path C only: data-pipeline / substantial algorithm design package; no implementation, solver, evaluator, representative run, full matrix, replot, or figure generation.
- N9F7A Git boundary audit completed: historical publish block documented the existing non-doc ahead commit before human resolution.
- N9G0 manual `LegSA_9F_FGO_EKF` design review completed as design only: algorithm identity, state/window, nine-factor, matrix/residual, provider, logger, roadmap, validation, and risk packages exist.
- N9G0A Git boundary resolution completed: PR #52 head is synced to `9ceba928`; PR #52 remains open/unmerged unless the human explicitly approves merge/closure/tag actions.
- N9G1 is split into `N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION` and later `N9G1B_PHASE1_PROVIDER_FACTOR_LOGGER_NORMAL_SMOKE_ONLY`.
- N9G1A context lock passed reviewer gate and was pushed to PR #52 at `f1e80f1`.
- N9G1B Phase 1 created the separate `LegSA_9F_FGO_EKF` candidate ID, runner/config boundary, provider/factor audit helper, logger schemas, safety gate, and runtime reports.
- N9G1B normal smoke was not run because provider contracts are blocked, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled.
- N9G1C-E resolved the locked normal clean source and core providers for `LegSA_9F_FGO_EKF`; provider contracts are partial accepted.
- N9G1C-E found the active nine-factor FGO backend still unavailable and candidate solver execution still disabled; normal smoke was not run.
- Current operational source of truth: `N9C0_GLOBAL_STAGED_N9B2_CONSOLIDATION_PRECHECK`.
- Current implementation/context stage: `N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE`.
- Current BY3/reporting stage: `GEN1_BY2_BY3_GENERALIZATION_REPORT_AND_BY3_FIGURE_ORGANIZATION`; GEN1 built BY2/BY3 metric inventories, canonical family mapping, three-scheme cross-dataset summaries, existing-metric cross-dataset figures, a BY3 figure inventory, and a copy-only BY3 figure organization without solver/evaluator/degradation/random execution.
- Current poor-GNSS stage: `PG_QA0_QUALITY_AWARE_FALLBACK_DESIGN_AND_PAPER_MAINLINE_DECISION`; PG_MULTI_A0 remains the source/runnability evidence import, and QA0 is design-only. QA0 keeps `LegSA_full_EKF` as the frozen verified mainline for normal/moderate GNSS and defines `LegSA_QA_Fallback_EKF` as a separate future candidate for severe GNSS, unavailable A1 dual-yaw, degraded position quality, Raw Doppler availability, and short IMU+Go2 bridge intervals. No implementation, solver, evaluator, degraded-input generation, random arrays, retuning, quality-aware execution, or paper claim was performed.
- Current paper-facing evidence stage: `PAPER0_MAINLINE_EVIDENCE_PACKAGE_AND_CLAIM_BOUNDARY_REVIEW`; it supports starting manuscript experiment-section drafting from existing BY2/BY3 evidence while keeping PG/QA as limitation/design extension and keeping `ready_for_paper_claims=false`.
- Current Go2 recovery status: `PAPER10C_R1B_LOW_SPACE_BY3_MISSING_ONLY_RESUME` passed after missing-only BY3 resume. BY2 and BY3 Go2 120x6 are both closed at 720/720, BY3 providers are `by3.txt` derived, readiness/motion-state LSIM metadata is first-class for G03/G05 runtime evidence, and BY3 yaw remains diagnostic-only.
- Current maintenance status: `PAPER10Y_POST_R1B_GIT_ARCHIVE_AND_WSL_SPACE_CLEANUP` archived verified completed WSL runtime/worktree material, deleted only verified WSL sources, generated a Windows compact script, and recommended PAPER10B2 if the paper kept multi-state quality management as a contribution.
- Current QM status: `PAPER10B2_R1_MISSING_ONLY_RESUME_AND_FINAL_QM_CLOSURE` closed the remaining BY3 QM missing-only rows. BY2 remains 600/600, BY3 is now 600/600, 7 unindexed complete artifacts were harvested, 14 missing-only rows were executed with jobs=8 and E/WSL emergency stops of 2GB/20GB, and final status is `CONDITIONAL_PASS_QM_FULL_MATRIX_COMPLETED_PERFORMANCE_MIXED`.
- Current BY2 result-review status: `PAPER10M1R2E_BY2_RESULT_REVIEW_FIGURE_PACKAGE_AND_CLAIM_BOUNDARY_FREEZE` is the active review-only stage after M1R2C_R1 and M1R2D_R1. Old M1R2B providers and old M1R2C yaw-invalid results are forbidden. M1R2C_R1 is the valid full-algorithm evidence source; M1R2D_R1 is the valid internal-ablation evidence source. Runtime outputs, generated figures, NAV/STD/EVAL_NAV/RUN_MANIFEST, provider payloads, and export zips must not be committed.
- Recommended BY3 next stage: human review of GEN1, then decide `BY3D_MIXED_POSITION_UP_PLANNING`, separate diagnostic-yaw planning, or another-dataset planning only if explicitly approved; GEN1 does not authorize paper claims, PR #52 merge/tag/closure, or additional yaw/mixed/module/full-matrix execution.
- Recommended paper next stage: `PAPER1_MANUSCRIPT_EXPERIMENT_SECTION_DRAFT`. QA1 remains optional for a stronger secondary-contribution route and is not required before starting the near-term Option B manuscript. PAPER0 does not authorize frozen mainline execution on PG1-PG4, quality-aware implementation, solver/evaluator execution, artificial degradation, random arrays, retuning, final paper figures, paper claims, PR #52 merge/closure/tag, or poor-GNSS robustness claims.
- Recommended active-FGO next stage remains: `implement_active_fgo_backend_or_reframe_scope`.

No full monolithic N9B2 was run. Do not run more N9B2 execution unless the human defines a new follow-up. N9C1 consolidated figure generation was ready after N9C0, but N9F evidence review now requires human review of the LegSA active nine-factor FGO implementation plan before representative active nine-factor FGO runs.

## 9. Claim Boundary

Allowed now:

- BY2 FGO-feedback EKF joint filter engineering chain has been validated.
- FGO feedback enters EKF as a controlled update.
- No output substitution, no direct NAV overwrite, no future-data feedback.
- Raw Doppler EKF is active.
- Raw Doppler FGO is active but low marginal value in clean BY2.
- Go2 proprioceptive joint factor is active.
- Go2 high-level roll/pitch, horizontal-velocity weak-prior, and readiness/motion-state LSIM metadata evidence is bounded and closed for BY2/BY3 Go2 120x6 after PAPER10C_R1B; Go2 remains a supporting mechanism, not Go2 position/yaw truth, full contact-aided InEKF, full leg odometry, universal superiority, or complete nine-factor FGO.
- Legged candidate factors are activated in no-feedback FGO.
- N9B pilot/preparation evidence exists through N9B2B, with cautions recorded above.
- N9B staged execution is complete through N9C0 global consolidated precheck.
- N9C0 active final-only metrics table exists with 825 rows.
- N9C1 consolidated figure generation readiness passed.
- N9E may be cited only as a logging-blocked evidence review and Obsidian sync; it does not support a complete active nine-factor FGO claim.
- N9F design package is complete and concludes that current evidence requires a new active nine-factor FGO algorithm design.
- N9F6A source audit may state that robot kinematics/contact/legged modeling exists in provider, diagnostic, offline no-feedback, and candidate factor code, while active `LegSA_full_EKF` only uses provider-dependent Go2 weak attitude / horizontal velocity EKF updates and selected-feedback EKF pseudo-measurements.
- N9F7 may state that `LegSA_9F_FGO_EKF` still requires a separate active FGO window/factor graph, provider contracts, and row-level residual/Jacobian/cost logging before smoke or representative validation.
- N9G0 may state that a manual design review package exists for a future, separate `LegSA_9F_FGO_EKF` candidate.
- N9G0 may state that `LegSA_full_EKF` remains the verified EKF/feedback algorithm and is not relabeled.
- N9G0A may state that the Git boundary was resolved and PR #52 head is synced to `9ceba928`; merge/closure/tag actions still require explicit human approval.
- N9G1A may state that N9G1 was split into context lock and a later limited Phase 1 implementation/smoke stage.
- N9G1B may state that the separate `LegSA_9F_FGO_EKF` candidate identity/config, provider/factor audit helper, logger schemas, and safety gate exist.
- N9G1B may state that normal smoke was not run because provider/factor contracts and the active nine-factor FGO backend are blocked.
- N9G1C-E may state that locked normal and core providers are resolved with partial provider acceptance.
- N9G1C-E may state that active backend and solver execution remain blocked and normal smoke was not run.
- BY3A0_TO_BY3E may state that BY3A0 context lock, BY3A inventory/body IMU audit, BY3B alignment, BY3C candidate input generation, BY2T text summaries, and BY2F copy-only figure archive are complete.
- BY3A0_TO_BY3E may state that BY3D/E were not executed because BY3 raw Doppler/Go2 prior/same-case feedback, single-baseline runner handoff, and final_v23 external-baseline input gates were not satisfied.
- BY3A1 may state that BY3A0 candidate inputs failed BY2 parity in delimiter/header, IMU column count, single-baseline schema, and original time-normalization policy.
- BY3A1 may state that repaired BY3 IMU, dual-GNSS, and single-GNSS1 inputs now match BY2 runtime file conventions, and that BY3 Go2 attitude/horizontal/joint priors were materialized from the BY3 Go2 body source.
- BY3A1 may state that BY3 Raw Doppler remains blocked under the accepted BY2 RTKLIB/RINEX provider logic, same-case selected feedback remains blocked until a real BY3 stage1 solver/evaluator exists, and no solver/evaluator/figure/degradation run was performed.
- BY3A2 may state that historical BY2 WSL processing chains were recovered and indexed, including N5A/N5B Raw Doppler, N7C6 Go2 priors, R4J single-baseline handoff, final_v23 external-baseline handoff, and selected-feedback same-case policy.
- BY3A2 may state that BY3 raw receiver CSVs rebuild UBX/RAWX evidence and that accepted Raw Doppler provider materialization succeeded only when backed by fresh BY3A2 RINEX/nav/provider factor reports.
- BY3A2 may state that no BY3 solver, official evaluator, degradation matrix, metric figure generation, selected-feedback generation, or paper claim was performed.
- BY3A3 may state that BY3 same-case selected feedback was generated from the BY3 stage1 official-eval state/estimate table only, with no BY2 feedback reuse and no trace/error/final_v23 columns used.
- BY3A3 may state that BY3 normal LegSA_full_EKF, single_antenna_gnss1_status_KF_GINS, and final_v23_dual_antenna_EKF official evaluations completed, and may report BY3A3 normal metrics as runtime evidence only.
- BY3A3 may state that its own normal comparison completed, but its earlier `ready_for_BY3_degradation_matrix_planning=true` is superseded by BY3A4A.
- BY3A4A may state that BY2 lateral yaw policy evidence was recovered as partial, dual antennas are lateral/perpendicular to robot forward direction, body heading requires a plus/minus 90 degree correction from antenna-baseline heading depending on antenna order/frame convention, and +90/-90 must not be selected by RMSE alone.
- BY3A4A may state that existing BY3A3 outputs were used for yaw-policy candidate tests, common-overlap metrics, diagnostic figures, seed0-9 explanation, and context/Obsidian memory updates, with no solver rerun, no degradation matrix, no retuning, and no paper claims.
- BY3A4A may state that no tested physically meaningful yaw policy was accepted; therefore repaired yaw metrics are blocked, `ready_for_BY3_degradation_matrix_planning=false`, and `recommended_next_stage=manual_review_dual_antenna_yaw_policy`.
- BY3A4C may state that the historical BY2/N4 yaw repair was recovered from git/docs/runtime evidence: N4H2 old yaw around 93 deg was invalidated by N4H2D, N4H2D selected `official_ref_sign_minus`, and the fresh replay yaw RMSE was about 1.98 deg under the reconstructed dual official reference.
- BY3A4C may state that BY3A3/BY3A4A yaw metrics are preserved as historical invalid-reference evidence, BY3 yaw is `not_evaluable` under current evidence, and position/up normal metrics may support position/up-only planning.
- BY3A4C may set `ready_for_BY3_degradation_matrix_planning=true` only with `scope=position_up_only`, `yaw_degradation_claims=false`, and `ready_for_paper_claims=false`.
- BY3A5B may state that BY3A5 correctly confirmed the old BY3 15-column yaw input was wrong-source, while BY3A5's HDT replacement policy is diagnostic/rejected/superseded for mainline BY3.
- BY3A5B may state that GNSS1/GNSS2 absolute positions reconstruct a physically plausible short baseline with median length about 0.383 m, while GNSS1 status `rel_pos_n/e/d` is a long-baseline/base-vector source with median length about 3062.8 m and is rejected.
- BY3A5B may state that repaired BY3 dual yaw uses A1_dual_diff short-baseline yaw with BY2 accepted `gnss2_minus_gnss1`, lateral conversion equivalent to `baseline_heading+90`, and fixed_1p5 yaw_std.
- BY3A5B may state that BY3 normal-only rerun completed for LegSA_full_EKF, single_antenna_gnss1_status_KF_GINS, and final_v23_dual_antenna_EKF with no degradation, no trace/final_v23/solver-output input, and no parameter retuning.
- BY3A5B may state that the A1 input was repaired but official yaw remained unresolved before BY3A6.
- BY3A6 may state that the BY3 trace file is the evaluation truth reference, that evaluator field selection/base_time/yaw_truth_mode were validated, and that processed trace lat/lon fields are unsafe for blind evaluation.
- BY3A6 may state that stage1 and LegSA_full_EKF initatt used stale first-row A1 yaw before repair, while the safe repair uses the first dual GNSS/A1 yaw row at or after the requested starttime and does not use trace for initatt.
- BY3A6 may state that the BY3 normal-only rerun after initatt repair completed with no degradation, no trace/final_v23/solver-output input, and no parameter retuning.
- BY3A6 may state that position/up sanity remains acceptable, but yaw still fails and likely requires a separate yaw-gate/A1-dynamics review; `ready_for_BY3_degradation_matrix_planning=false`, `yaw_degradation_claims=false`, and `ready_for_paper_claims=false`.
- BY3A7 may state that A1_dual_diff remains the mainline short-baseline yaw source with dynamic-quality caution; invalid-epoch criteria are based on source baseline/jump quality, not RMSE.
- BY3A7 may state that the BY3A0/BY3A1 Go2 IMU input used a gyro bias estimated from a moving segment after selected Go2 start; BY3A7 repairs this by using a pre-motion BY3 source-bias segment while preserving the FLU-to-FRD conversion and all yaw gate parameters.
- BY3A7 may state that BY3 normal-only rerun with the BY3A7-local static-bias IMU completed; `LegSA_full_EKF` yaw RMSE is about 5.26 deg and `final_v23_dual_antenna_EKF` yaw RMSE is about 4.30 deg, while the single-antenna baseline yaw remains poor.
- BY3A7 may set `ready_for_BY3_degradation_matrix_planning=true` only with `scope=full_after_human_review`; `ready_for_paper_claims=false` always remains in force.
- BY3A8 may state that the remaining dual-yaw error is limited by A1 observation quality: A1-vs-trace heading RMSE about 24.06 deg, p95 about 31.78 deg, and max about 167.29 deg in an evaluation-only lower-bound audit.
- BY3A8 may state that no safe additional repair passed: objective A1 mask is insufficient, BY3A7 IMU bias remains accepted, time-lag scans lack metadata support, yaw gate behavior is acceptable under unchanged thresholds, and feedback policy changes require a separate review.
- BY3A8 may set `ready_for_BY3_degradation_matrix_planning=true` only with `scope=position_up_with_diagnostic_yaw`; `yaw_claim_scope=diagnostic_only` and `ready_for_paper_claims=false` always remain in force.
- BY3B may state that BY3 position/up degradation planning/precheck is complete with 75 position/up-primary case-seed units and 43 diagnostic-yaw units, dry-run command templates, same-seed fairness rules, same-case feedback dependencies, and no generated degraded inputs, random arrays, solvers, evaluators, figures, or paper claims.
- BY3B may set `ready_for_BY3C_position_up_degradation_execution=true` only as a human-review-gated planning readiness flag; `yaw_claim_scope=diagnostic_only` and `ready_for_paper_claims=false` remain in force.
- BY3C may state that Batch0-Batch3 position/up-primary execution completed for 71 case units and 213 final metric rows across `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, and `final_v23_dual_antenna_EKF`, using BY3A7 repaired IMU, BY3A5B/BY3A7 A1_dual_diff yaw, BY3A2 Raw Doppler, BY3 Go2 priors, and same-case feedback generated from each case's stage1 official EVAL_NAV state/estimate columns.
- BY3C may state that Batch 2 and Batch 3 random arrays were generated only for approved C_position_noise and D_position_spike seeds 0..9 with structured hashes and same-seed fairness. BY3C may set `ready_for_BY3D_diagnostic_yaw_or_mixed_planning=true` only as a human-review-gated planning readiness flag; `yaw_claim_scope=diagnostic_only` and `ready_for_paper_claims=false` remain in force.
- BY3C1/BY3Y1 may state that review integrity passed for 71 BY3 case units and 213 final metric rows, that BY3 position/up behavior is family-dependent, that B downsample is the only overlapping family classified as `generalizes_consistently`, and that normal/A/E/C/D are `same_order_no_clear_advantage` or mixed rather than paper-ready wins.
- BY3C1/BY3Y1 may state that BY3 yaw is diagnostic-only: prior wrong-source yaw, stale initatt, and IMU bias issues were repaired, but BY3A8 shows A1 observation quality remains the main limitation and selected feedback worsens normal diagnostic yaw slightly versus stage1.
- GEN1 may state that BY2 and BY3 inventories each contain 213 comparable final metric rows across 71 case units for the three schemes, with BY2 final_v23 rows sourced from the accepted external-baseline review table where needed.
- GEN1 may state that BY3 already has normal and degradation figure material, that the organized BY3 figure view is copy-only, and that 874 unique nonempty figure files were copied into `<BY3_FIGURE_SUMMARY_ROOT>` while original runtime figures remained untouched.
- GEN1 may state that BY3 figure classification is partial rather than fully paper-facing, because diagnostic yaw and audit-sanity figures remain separate from position/up-primary review material.
- PG_QA0 may state that BY2/BY3 position-up generalization remains the main proven line, BY3 yaw remains diagnostic-only and should not block the paper, and PG1-PG4 severe GNSS data motivate a future quality-aware fallback branch.
- PG_QA0 may state that `LegSA_QA_Fallback_EKF` is a separate design-only candidate, not a relabeling of `LegSA_full_EKF` or final_v23.
- PG_QA0 may state that the fallback design includes states S0 through S6, disables A1 dual-yaw when relpos-diff geometry is nonphysical, downweights or rejects poor GNSS position by online source-quality indicators, retains Raw Doppler only when provider/residual quality is acceptable, and uses IMU+Go2 bridge mode only as a low-confidence short-interval fallback.
- PG_QA0 may state that the near-term paper recommendation is Option B: keep `LegSA_full_EKF` as the mainline and describe QA as a design/limitation extension with no QA performance claim. Option C requires later human-approved QA1/QA2/QA3 implementation and validation.
- PAPER0 may state that a paper-facing evidence package is complete and that manuscript drafting can begin from existing BY2/BY3 evidence while keeping PG/QA as limitation/design extension.
- PAPER0 may state that BY2 is the full-metric main dataset, BY3 is position/up generalization with diagnostic-only yaw, PG1-PG4 are severe-GNSS boundary datasets, and PG_QA0 is design-only.
- PAPER0 must keep `ready_for_manuscript_drafting=true`, `ready_for_QA1=false`, and `ready_for_paper_claims=false`.
- N9G2 may be described as the later representative validation stage.
- N9G3/N9G4 may be described as later full matrix/replot/report stages if applicable.
- `LegSA_full_EKF` is not accepted as active nine-factor FGO and must not be relabeled as such.

Forbidden now:

- paper performance improvement claim.
- outperform final_v23 claim.
- Go2 truth claim.
- FGO replaces EKF claim.
- trace/final_v23 tuning claim.
- source observations as algorithm estimates.
- placeholder plots as real figures.
- paper claims before N9C visual review and N9D claim-boundary review.
- using superseded rows, `historical_nominal_none`, or `B_gnss_downsample_2Hz` for active conclusions.
- automatic PR #52 merge/tag authorization.
- representative active nine-factor FGO degradation/full-matrix runs during N9G1A or N9G1B.
- treating N9G1B schema/gate outputs as active nine-factor FGO residual/Jacobian/cost evidence.
- treating N9G1C-E provider resolution as active nine-factor FGO residual/Jacobian/cost evidence.
- treating N9G1E as normal-smoke pass evidence.
- treating the N9F6A/N9F7 design package as active solver implementation.
- treating the N9G0 design package as implementation or active factor evidence.
- treating PR #52 head sync as merge, tag, or closure authorization.
- treating provider/update counts or historical candidate no-feedback rows as current active nine-factor FGO residual/cost evidence.
- treating BY3 source inventory, BY3B alignment reports, or BY3C candidate inputs as BY3 solver/evaluator performance evidence.
- treating BY3A1 repaired input files or materialized BY3 Go2 priors as BY3 solver/evaluator performance evidence.
- treating BY3A2 historical pipeline recovery, UBX/RAWX rebuild evidence, or baseline handoff configs as BY3 solver/evaluator performance evidence.
- treating BY3A3 normal-only metrics as paper claims, final_v23 outperformance claims, BY3 degradation/full-matrix completion, or active nine-factor FGO evidence.
- treating BY3A4A diagnostic figures or common-overlap metrics as repaired yaw metrics, paper claims, BY3 degradation readiness, or final_v23 outperformance evidence.
- choosing BY3/BY2 lateral dual-antenna +90/-90 yaw conversion only by lowest yaw RMSE.
- treating BY3A4C diagnostic yaw-source figures or position-only planning readiness as repaired BY3 yaw metrics or yaw degradation readiness.
- claiming BY3 yaw degradation or yaw generalization while `yaw_status=not_evaluable`.
- treating BY3A5 HDT as mainline BY3 solver yaw input.
- using GNSS status long-baseline `rel_pos_n/e/d` as BY3 antenna heading.
- treating BY3A5B's A1 input repair as repaired official BY3 yaw-reference metrics or yaw degradation readiness.
- treating BY3A6 initatt repair as repaired BY3 yaw metrics, BY3 degradation readiness, paper readiness, or proof that trace/A1/evaluator/gate are fully solved.
- treating BY3A7 normal yaw sanity as paper-ready evidence, final_v23 outperformance, PR #52 merge/tag/closure authorization, or completed BY3 degradation/full-matrix execution.
- treating BY3A7 A1 dynamic-quality masks as RMSE-selected epoch deletion; any invalid epoch policy must stay source-quality based.
- treating BY3A8 diagnostic yaw scope as a paper yaw claim, full yaw degradation readiness, trace-based correction permission, feedback-policy authorization, or permission to relax yaw gates.
- treating BY3B planning artifacts as degraded inputs, random arrays, solver/evaluator execution, generated figures, completed BY3 degradation/full-matrix evidence, yaw robustness evidence, paper claims, PR #52 merge/tag/closure authorization, or permission to reuse BY2/normal feedback.
- treating BY3C Batch0-Batch3 position/up results as yaw robustness evidence, paper-ready performance evidence, final_v23 outperformance evidence, full monolithic BY3 matrix completion, or authorization for H_dual_yaw_noise, E_yaw_std_inflation, mixed, module-disable, LegSA_9F_FGO_EKF, or nonredundant-FGO execution.
- treating BY3C1/BY3Y1 review tables or diagnostic-yaw figures as new solver/evaluator evidence, paper performance claims, yaw robustness claims, or authorization for BY3D execution without explicit human approval.
- treating GEN1 cross-dataset reports, organized figure folders, copied figures, or export-clean tables as new solver/evaluator evidence, paper performance claims, BY3 yaw success, final_v23 outperformance, or authorization for BY3D execution without explicit human approval.
- claiming BY3 full-matrix completion before explicit full-matrix execution approval.
- treating PG_QA0 as quality-aware implementation, solver/evaluator evidence, PG robustness evidence, paper-ready QA performance evidence, trace-tuned threshold approval, relabeling approval for `LegSA_full_EKF`, or authorization to start QA1 without human review.
- treating PAPER0 as final paper-claim authorization, final figure authorization, QA1 authorization, BY3 yaw main-claim support, PG performance proof, or comprehensive final_v23 superiority support.

## 10. Historical N9C0A Decision Lock

N9C0A was documentation/context update only. This historical lock remains for provenance and does not supersede the current N9F decision lock.

Expected decision if validation passes:

```text
status=N9C0A_context_update_after_global_consolidation_complete
ready_for_N9C1_consolidated_figure_generation=true
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=human_review_N9C0A_then_N9C1_consolidated_figure_generation
```

## 11. N9F Decision Lock

N9F0_TO_N9F2 is design materialization and context sync only. It does not authorize solver execution, evaluator execution, degradation generation, figure generation, representative active-nine-factor runs, paper claims, or relabeling `LegSA_full_EKF` as active nine-factor FGO.

Expected decision if validation passes:

```text
status=N9F_legsa_9f_design_package_complete
ready_for_implementation_review=true
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=N9F6_HUMAN_REVIEW_LEGSA_9F_IMPLEMENTATION_PLAN
```

## 12. N9F6A/N9F7 Decision Lock

N9F6A_TO_N9F7 completed a source-code forensic audit and then followed Path C only. It does not authorize code implementation, solver execution, evaluator execution, degradation generation, representative validation, full matrix execution, figure generation, paper claims, or relabeling `LegSA_full_EKF` as active nine-factor FGO.

Expected decision if validation passes:

```text
status=N9F7_substantial_algorithm_design_required
ready_for_algorithm_design_review=true
ready_for_implementation_review=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=manual_algorithm_design_review
```

## 13. N9F7A/N9G0 Decision Lock

N9F7A_TO_N9G0 completed a Git boundary audit and manual `LegSA_9F_FGO_EKF` design review. It does not authorize implementation, solver execution, evaluator execution, random generation, degraded-input generation, N9B2 execution, representative validation, full matrix execution, figure generation, paper claims, PR #52 merge, PR #52 closure, or tag creation.

This lock is historical after N9G0A. N9G0A resolved the Git boundary and synced PR #52 head to `9ceba928`; it did not authorize PR merge, PR closure, tag creation, paper claims, representative validation, or full matrix execution.

Expected decision if validation passes:

```text
status=N9G0_publish_blocked_by_git_boundary
design_review_complete=true
ready_for_N9G1_phase1_implementation=human_decision_required
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=resolve_git_boundary
```

## 14. N9G1A Decision Lock

N9G1A_CONTEXT_LOCK_BEFORE_LEGSA_9F_IMPLEMENTATION is context lock only. It records that N9G0A resolved the Git boundary and PR #52 head is synced to `9ceba928`. N9G1A by itself does not authorize implementation, solver execution, evaluator execution, random generation, degraded-input generation, representative validation, full matrix execution, figure generation, paper claims, PR #52 merge, PR #52 closure, or tag creation. N9G1B may start only when a human request explicitly authorizes it and the N9G1A reviewer gate passes.

Expected decision if validation passes:

```text
status=N9G1A_context_lock_complete
git_boundary_resolved=true
pr_52_head_synced_to=9ceba928
n9g1_split=N9G1A_context_lock_then_N9G1B_phase1_provider_factor_logger_normal_smoke_only
legsa_full_ekf_role=current_verified_EKF_feedback_algorithm
legsa_9f_fgo_ekf_role=separate_new_candidate
complete_nine_factor_FGO_claim=false
ready_for_N9G1B_phase1_provider_factor_logger_normal_smoke=human_decision_required
ready_for_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=human_review_N9G1A_then_decide_N9G1B
```

## 15. N9G1B Decision Lock

N9G1B_PHASE1_PROVIDER_FACTOR_LOGGER_NORMAL_SMOKE_ONLY created a separate `LegSA_9F_FGO_EKF` candidate identity/config boundary, provider/factor audit helper, active-FGO logger schema, legged diagnostic logger schema, and normal-smoke safety gate. It does not authorize representative validation, full matrix execution, figure generation, paper claims, PR #52 merge, PR #52 closure, or tag creation.

N9G1B did not run normal smoke because the safety gate blocked execution: provider contracts are not ready for active factors, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled. No active nine-factor FGO residual/Jacobian/cost rows were produced.

Expected decision if validation passes:

```text
status=N9G1_context_locked_provider_or_factor_blocked
legsa_9f_fgo_ekf_role=separate_new_candidate
normal_smoke_status=N9G1B_normal_smoke_not_run_blocked_by_gate
complete_nine_factor_FGO_claim=false
ready_for_N9G2_representative_validation=false
ready_for_paper_claims=false
ready_for_N9B2_execution=false
ready_for_full_N9B_execution=false
recommended_next_stage=fix_provider_or_factor_model
```

## 16. N9G1C-E Decision Lock

N9G1C_TO_N9G1E_PROVIDER_CONTRACT_RESOLUTION_ACTIVE_FGO_BACKEND_AND_NORMAL_SMOKE resolved the locked normal clean source and core provider contracts for the separate `LegSA_9F_FGO_EKF` candidate. It created provider, backend, factor wiring, logger, normal-smoke gate, validation, and decision reports. It does not authorize representative validation, full matrix execution, figure generation, paper claims, PR #52 merge, PR #52 closure, or tag creation.

N9G1C-E did not run normal smoke because the safety gate blocked execution: the active nine-factor FGO backend remains unavailable, candidate solver execution remains disabled, and no active factor wiring rows exist. No active nine-factor FGO residual/Jacobian/cost rows were produced.

Expected decision if validation passes:

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

## 17. BY3A0_TO_BY3E Decision Lock

BY3A0_TO_BY3E_GENERALIZATION_AND_BY2_DEGRADATION_REPORT_REORG completed as a partial normal-generalization gate and BY2 report/archive organization stage. It updated context boundaries, created BY3A inventory/body IMU audit reports, created BY3B alignment reports using the BY2 event-normalized kick policy without trace tuning, generated BY3C candidate Go2 IMU and GNSS status inputs, generated BY2T text summaries from existing active final-only metrics, and reorganized BY2 degradation figures as a copy-only archive.

BY3D and BY3E did not run because solver/evaluator gates remained blocked. No BY3 solver, official evaluator, degradation generation, full matrix, random generation, degraded-input generation, BY3 normal metric figure package, or paper claim was produced.

Expected decision if validation passes:

```text
status=BY3_solver_or_evaluator_blocked
by3a0_context_lock=complete
by3a_inventory=complete_read_only_inventory
by3b_alignment=BY3B_alignment_passed_no_trace_tuning
by3c_input_generation=partial_with_provider_blockers
by2t_text_summaries=complete_from_active_final_only_metrics
by2f_archive=complete_copy_only
ready_for_BY3_degradation_full_matrix=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_solver_or_evaluator
```

## 18. BY3A1 Decision Lock

BY3A1_BY2_PARITY_AUDIT_AND_PROVIDER_GATE_REPAIR completed a strict BY3-vs-BY2 input-chain parity audit after BY3A0_TO_BY3E was blocked. It extracted the accepted BY2 input-chain reference, audited BY3A0 candidate inputs, found parity mismatches, repaired BY3 IMU/GNSS runtime file conventions where the BY2 policy was clear, materialized BY3 Go2 priors from the BY3 Go2 body source, and recorded remaining provider/feedback/runner blockers.

BY3A1 did not run BY3 solvers, official evaluators, artificial degradation, BY3 degradation matrix, figure generation from metrics, parameter retuning, trace tuning, final_v23 config mutation, or paper-claim work.

Expected decision if validation passes:

```text
status=BY3A1_provider_or_feedback_blocked
by2_reference_chain=extracted
by3_input_parity=partial_repaired
by3_repaired_inputs_ready=true
by3_go2_priors_materialized=true
by3_raw_doppler_provider=blocked_missing_accepted_BY2_RTKLIB_inputs
by3_same_case_feedback=blocked_until_stage1_solver_eval
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_providers_or_feedback
```

## 19. BY3A2 Decision Lock

BY3A2_HISTORICAL_WSL_PIPELINE_RECOVERY_AND_RUNNER_GATE_REPAIR completed a strict historical BY2 WSL pipeline recovery after BY3A1. It recovered the accepted BY2 Raw Doppler N5A/N5B chain, Go2 N7C6 prior chain, R4J single-baseline handoff, final_v23 external-baseline handoff, and selected-feedback same-case dependency policy.

BY3A2 did not run BY3 solvers, official evaluators, artificial degradation, BY3 degradation matrix, metric figure generation, parameter retuning, trace tuning, final_v23 algorithm mutation, selected-feedback generation, or paper-claim work.

Expected decision if validation passes:

```text
status=BY3A2_selected_feedback_blocked
historical_pipeline_recovered=true
by3_raw_ubx_rebuild=true
by3_raw_doppler_provider=materialized_accepted_N5A_N5B_chain
by3_go2_priors_validated=true
single_baseline_handoff=ready_for_review_not_run
finalv23_handoff=ready_for_review_not_run
by3_same_case_feedback=blocked_until_stage1_solver_eval
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=repair_BY3_stage1_feedback_chain
```

## 20. BY3A3 Decision Lock

BY3A3_SELECTED_FEEDBACK_STAGE1_CHAIN_AND_NORMAL_GENERALIZATION_EXECUTION repaired the BY3 same-case selected-feedback dependency and ran the normal BY3 comparison only. It recovered the accepted BY2 selected-feedback policy, ran a BY3 stage1 `baseline_no_feedback_EKF`, ran official evaluation, materialized BY3 same-case feedback from the stage1 official-eval state/estimate table, ran BY3 `LegSA_full_EKF` stage2 selected-feedback, ran the GNSS1-status single baseline, ran the final_v23 external baseline, and generated official normal metrics, figures, and a case review.

BY3A3 did not run BY3 degradation, artificial degradations, branch ablations, LegSA_9F_FGO_EKF, nonredundant FGO extension, parameter retuning, trace tuning, final_v23 output solver input, BY2 feedback reuse, output substitution, paper claims, PR merge/closure, or tag creation.

Expected decision if validation passes:

```text
status=BY3A3_normal_generalization_completed
by3_same_case_feedback=generated_from_stage1_official_eval_state_estimate_columns_only
legsa_full_stage2=completed
single_baseline=completed
finalv23_external_baseline=completed
official_evaluation=completed
ready_for_BY3_degradation_matrix_planning=superseded_by_BY3A4A_false
ready_for_paper_claims=false
recommended_next_stage=manual_review_dual_antenna_yaw_policy
```

## 21. BY3A4A Decision Lock

BY3A4A_LATERAL_DUAL_ANTENNA_YAW_REPAIR_SEED_EXPLANATION_AND_CONTEXT_MEMORY_LOCK recovered the BY2 lateral dual-antenna yaw policy evidence as partial, encoded that the dual antennas are mounted laterally and perpendicular to the robot forward/head direction, audited physically meaningful +90/-90 and baseline-reversal yaw candidates using existing BY3A3 solver outputs only, recomputed strict common-overlap metrics, regenerated diagnostic comparison figures, generated the seed0-9 explanation files under the BY2 text-summary index, and updated context/Obsidian memory.

BY3A4A did not run BY3 degradation, rerun solvers, retune parameters, use trace/final_v23/single/LegSA outputs as solver inputs, select +90/-90 by RMSE alone, hide the original BY3A3 bad yaw metrics, make paper claims, merge PR #52, close PR #52, or create a tag.

Expected decision if validation passes:

```text
status=BY3A4A_yaw_policy_inconclusive
lateral_dual_antenna_geometry_locked=true
by2_lateral_yaw_policy_recovered=partial
original_BY3A3_yaw_metrics_preserved=true
repaired_yaw_metrics_accepted=false
common_overlap_metrics_ready=true
seed0_9_explanation_created=true
ready_for_BY3_degradation_matrix_planning=false
ready_for_paper_claims=false
recommended_next_stage=manual_review_dual_antenna_yaw_policy
```

## 22. BY3A4C Decision Lock

BY3A4C_GIT_HISTORY_YAW_REFERENCE_RECONSTRUCTION_AND_VISUAL_VALIDATION recovered the historical BY2/N4 yaw-reference repair from git history, tracked docs, source, PR metadata, and runtime evidence. It verified that N4H2D invalidated the old N4H2 roughly 93 deg yaw result as a stale/wrong-reference mapping, selected `official_ref_sign_minus`, and evaluated fresh replay yaw with direct identity against the reconstructed dual official reference.

BY3A4C applied the recovered and diagnostic profiles to existing BY3A3 outputs only. It did not rerun BY3 solvers, run BY3 degradation, modify BY3 inputs or solver outputs, retune parameters, use trace/final_v23/LegSA/single outputs as solver inputs, select policy by RMSE alone, hide original bad yaw metrics, make paper claims, merge PR #52, close PR #52, or create a tag.

Expected decision if validation passes:

```text
status=BY3A4C_yaw_not_evaluable_position_only_generalization_ready
historical_BY2_yaw_fix_recovered=true
selected_reference_sign=official_ref_sign_minus
old_BY2_yaw_around_93_deg_invalidated=true
fresh_BY2_yaw_rmse_about_deg=1.98
BY3_yaw_status=not_evaluable
original_BY3A3_yaw_metrics_preserved=historical_invalid_reference
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=position_up_only
yaw_degradation_claims=false
ready_for_paper_claims=false
recommended_next_stage=BY3B_POSITION_ONLY_DEGRADATION_PLANNING_OR_HUMAN_REVIEW
```
## BY3A5/BY3A5B Dual Yaw Input Source Repair

BY3A5 remains valid only as the wrong-source audit: the old BY3 15-column yaw input used a wrong source, likely GNSS1 status heading or a long-baseline status rel_pos vector. BY3A5's HDT repaired-input policy is diagnostic/rejected/superseded for mainline BY3 generalization and must not be reused as the main solver yaw source.

BY3A5B repairs BY3 mainline dual yaw with A1_dual_diff short-baseline yaw from GNSS1/GNSS2 absolute positions, not status long-baseline `rel_pos_n/e/d` and not HDT. The accepted policy is `gnss2_minus_gnss1`, BY2 sign/lateral conversion equivalent to `baseline_heading+90`, and fixed_1p5 yaw_std. BY3A6 then validated the trace/evaluator/base_time chain and repaired stale first-row initatt for stage1/LegSA. BY3A7 repaired the remaining BY3 Go2 IMU preprocessing issue. BY3A8 found the residual yaw error is limited by A1 observation quality; `ready_for_BY3_degradation_matrix_planning=true` only with `scope=position_up_with_diagnostic_yaw`, and `ready_for_paper_claims=false`.

## 23. BY3A7 Decision Lock

BY3A7_A1_YAW_DYNAMIC_QUALITY_IMU_SIGN_AND_GATE_REPAIR accepted BY3A6 trace/evaluator/base_time/initatt findings, audited A1 dual-diff yaw dynamics, audited BY3 Go2 IMU sign/axis/yaw-rate preprocessing, audited yaw gate residuals, and audited yaw update code. It confirmed that the BY3A0/BY3A1 IMU input estimated gyro bias from a moving segment after selected Go2 start; the z bias was about -8.58 deg/s versus about -0.074 deg/s from the pre-motion source segment.

BY3A7 repaired only a BY3A7-local IMU input using pre-motion source gyro bias and the existing FLU-to-FRD conversion. It did not change A1 yaw source, yaw_std, yaw gate thresholds, final_v23 code, solver parameters, trace/evaluator policy, or output values. It then ran BY3 normal only. No BY3 degradation, artificial degradation, trace solver input, HDT solver input, final_v23 solver input, gate relaxation, parameter retuning, paper claims, PR #52 merge/closure, or tag creation was performed.

Expected decision if validation passes:

```text
status=BY3A7_yaw_salvaged_ready_for_full_BY3_degradation
a1_yaw_quality=BY3A7_a1_yaw_quality_acceptable_with_mask
imu_sign_axis=BY3A7_imu_sign_axis_bug_confirmed
yaw_update_code=BY3A7_yaw_update_code_valid
normal_rerun=BY3A7_normal_rerun_completed
LegSA_full_EKF_yaw_rmse_about_deg=5.26
final_v23_dual_antenna_EKF_yaw_rmse_about_deg=4.30
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=full_after_human_review
ready_for_paper_claims=false
recommended_next_stage=BY3B_DEGRADATION_MATRIX_PLANNING_AND_PRECHECK
```

## 24. BY3A8 Decision Lock

BY3A8_YAW_ERROR_BUDGET_AND_SAFE_REPAIR accepted BY3A7's trace/base-time/initatt/A1/IMU findings and audited the residual 4-5 deg dual-yaw normal error. The A1 observation lower-bound audit used the BY3 trace as evaluation-only reference and found A1-vs-trace heading RMSE about 24.06 deg, p95 about 31.78 deg, max about 167.29 deg, circular mean about -15.06 deg, and circular std about 17.17 deg.

BY3A8 found that source-quality-only A1 checks identify 6 objective invalid solver-candidate epochs, but an objective mask is insufficient for the broad observation error. BY3A7 pre-motion IMU bias remains accepted, no metadata-backed time-lag repair exists, yaw gate behavior is acceptable under unchanged thresholds, and feedback worsens yaw relative to stage1 but requires a separate human-approved review. BY3A8 did not run BY3 normal solvers, official evaluators, degradation, artificial degradation, trace solver input, HDT/long-relpos fallback, gate relaxation, parameter retuning, paper claims, PR #52 merge/closure, or tag creation.

Expected decision if validation passes:

```text
status=BY3A8_yaw_limited_but_position_up_ready
a1_observation_lower_bound=BY3A8_a1_observation_quality_poor
safe_repair_plan=BY3A8_no_safe_repair_accept_yaw_limit
normal_rerun=BY3A8_normal_rerun_not_run_no_safe_repair
ready_for_BY3_degradation_matrix_planning=true
ready_for_BY3_degradation_matrix_planning_scope=position_up_with_diagnostic_yaw
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=BY3B_POSITION_UP_WITH_DIAGNOSTIC_YAW_PLANNING
```

## 25. BY3B Decision Lock

BY3B_POSITION_UP_WITH_DIAGNOSTIC_YAW_PLANNING imported the BY3A8 decision, locked the BY3A7 repaired IMU and BY3A5B/BY3A7 A1_dual_diff 15-column GNSS yaw input for future BY3 degradation execution, and planned position/up degradation with yaw retained only as diagnostic evidence.

BY3B created planning/precheck artifacts only: family scope, 118-unit case matrix, seed plan, provider/feedback dependency plan, dry-run command template plan, evaluator/metric policy plan, figure/case-review plan, batch execution plan, context update, and Obsidian sync. BY3B did not execute BY3 degradation, generate degraded inputs, generate random arrays, run solvers, run evaluators, generate figures, retune parameters, relax yaw gates, use trace/final_v23/single/LegSA output as solver input, use HDT or long-baseline rel_pos yaw, reuse BY2 feedback, reuse BY3 normal feedback for degraded cases, make paper claims, merge PR #52, close PR #52, or create a tag.

Expected decision if validation passes:

```text
status=BY3B_position_up_diagnostic_yaw_plan_complete
case_seed_units_total=118
position_up_primary_units=75
diagnostic_yaw_units=43
solver_rows_planned=311
command_templates_execute_now=false
random_arrays_generated=false
degraded_inputs_generated=false
solvers_run=false
evaluators_run=false
ready_for_BY3C_position_up_degradation_execution=true
human_final_decision_required_before_execution=true
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=BY3C_POSITION_UP_DEGRADATION_EXECUTION_BATCH0_TO_BATCH3_LONG_PIPELINE
```

## 26. BY3C Decision Lock

BY3C_POSITION_UP_DEGRADATION_EXECUTION_BATCH0_TO_BATCH3_LONG_PIPELINE executed only the human-approved BY3 position/up-primary subset after BY3B. It locked BY3A7 repaired IMU, BY3A5B/BY3A7 A1_dual_diff yaw, BY3A2 Raw Doppler, BY3 Go2 priors, trace as evaluation-only reference, and same-case degraded feedback policy.

BY3C completed Batch 0 normal parity, Batch 1 deterministic A/B/E_position_std, Batch 2 C_position_noise seeds 0..9, and Batch 3 D_position_spike seeds 0..9. It generated degraded inputs, Batch 2/3 random arrays with structured hashes, stage1 and final solver outputs, official evaluations, same-case feedback, figures, case reviews, consolidated metrics, context updates, and Obsidian notes. It did not run H_dual_yaw_noise, E_yaw_std_inflation, mixed cases, module-disable cases, `LegSA_9F_FGO_EKF`, nonredundant FGO extension, or a full monolithic BY3 matrix.

Expected decision if validation passes:

```text
status=BY3C_batch0_to_batch3_position_up_degradation_complete
case_units_executed=71
final_metric_rows=213
ready_for_BY3D_diagnostic_yaw_or_mixed_planning=true_after_human_review
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=human_review_BY3C_then_BY3D_DIAGNOSTIC_YAW_OR_MIXED_PLANNING
```

## 27. BY3C1/BY3Y1 Review And Yaw Diagnostic Lock

BY3C1_TO_BY3Y1_POSITION_UP_GENERALIZATION_REVIEW_AND_YAW_DIAGNOSTIC_EXPLANATION is complete as a reporting/review-only stage. It read existing BY3C Batch0-Batch3 metrics, existing BY3A8 yaw-error-budget evidence, and existing BY2 N9C0D/N9C2B comparison material. It did not run solvers, evaluators, degraded-input generation, random generation, parameter retuning, or paper-claim work.

BY3C1 result integrity passed with 71 BY3 case units and 213 final metric rows. BY3 three-scheme position/up review found family-dependent behavior: B downsample generalizes consistently across BY2/BY3 for position/up, while normal, A outage, E position std, C position noise, and D position spike remain same-order or mixed, not paper-ready advantage claims. BY3 yaw remains diagnostic-only; BY3Y1 explains the yaw limitation through the repaired source chain and the BY3A8 A1 observation lower bound.

Current decision:

```text
status=BY3C1_position_up_review_and_yaw_diagnostic_complete
ready_for_BY3D_or_other_dataset_planning=true_after_human_review
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=human_review_BY3C1_then_BY3D_mixed_position_up_or_other_dataset_planning
```

## 28. GEN1 BY2-BY3 Generalization Report And BY3 Figure Organization Lock

GEN1_BY2_BY3_GENERALIZATION_REPORT_AND_BY3_FIGURE_ORGANIZATION is complete as a reporting, review, and copy-only organization stage. It read existing BY2 N9C0D/N9B2R3/N9C2B metrics, existing BY3C metrics, existing BY3C1/BY3Y1 summaries, and existing BY3 figures. It did not run solvers, evaluators, degraded-input generation, random generation, parameter retuning, or paper-claim work.

GEN1 metric inventory passed with 213 BY2 rows and 213 BY3 rows across 71 comparable case units for `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, and `final_v23_dual_antenna_EKF`. GEN1 generated cross-dataset tables and metric figures from existing metrics only. BY3 figure inventory found existing normal and degradation figures; GEN1 copied 874 unique nonempty figure files into `<BY3_FIGURE_SUMMARY_ROOT>` as an organized view without moving or deleting originals.

Current decision:

```text
status=GEN1_cross_dataset_report_and_BY3_figure_organization_complete
ready_for_next_stage=true_after_human_review
yaw_claim_scope=diagnostic_only
ready_for_paper_claims=false
recommended_next_stage=human_review_GEN1_then_decide_BY3D_or_other_dataset
```

## 29. XB1 Poor-GNSS Generalization Bootstrap Lock

XB1A0_TO_XB1E_POOR_GNSS_GENERALIZATION_CONTEXT_QUALITY_AUDIT_ALIGNMENT_AND_NORMAL_RUN is complete as the first poor-GNSS repeated-experiment bootstrap for XB1 / PG1_20260105_122513. It created context, literature-backed GNSS quality criteria, data inventory, GNSS quality profile, kick-event alignment, input/provider reports, quality figures, case review, Obsidian notes, and export-clean material under `<XB1_STAGE_ROOT>` and `<XB1_EXPORT_CLEAN_ROOT>`.

XB1 uses `<XB1_BODY_SOURCE>` as the robot body/high-level/body-IMU source. Receiver `imu-data.csv` is diagnostic-only. Trace is evaluation-only. A1 dual-diff yaw must come from GNSS1/GNSS2 short-baseline absolute positions with lateral antenna conversion and fixed_1p5 yaw std; status long-baseline `rel_pos_n/e/d` and HDT are forbidden as mainline yaw sources. Initatt yaw must be starttime-aligned. IMU preprocessing must use a pre-motion stationary bias, not a moving segment.

XB1 GNSS quality was classified `severe`: both receivers show PDOP p95 at the 99.99 sentinel, sol_num_sat p05 of 0, large position-accuracy tails, and invalid A1 short-baseline geometry. The A1 short-baseline median length was about 9.14 m with p95 about 51.68 m, while status long-baseline `rel_pos_n/e/d` had median length about 2925.69 m and was rejected. Kick-event alignment passed without trace tuning, with recommended algorithm start about 16.646 s and end about 390.640 s relative to the body-source time zero.

XB1A0-E input/provider generation was partial. The repaired body IMU was generated from `<XB1_BODY_SOURCE>` using pre-motion stationary gyro bias. Go2 attitude, horizontal velocity, and joint priors were materialized. Raw Doppler provider materialization attempted the accepted N5A/N5B-style RTKLIB/RINEX/helper path but failed because the RTKLIB Doppler helper compile tool was unavailable in that Windows runtime. Normal solvers and official evaluators were not run in XB1A0-E because `inputs_not_ready_for_normal`, `A1_short_baseline_yaw_gate_blocked`, and `providers_not_ready_for_LegSA_full` gates blocked execution.

XB1A0-E decision:

```text
status=XB1_severe_GNSS_quality_mainline_limited
normal_run_status=XB1F_failed_before_solver
ready_for_quality_aware_branch_planning=true_after_human_review
ready_for_PG2_or_XB1_degradation_planning=false
ready_for_paper_claims=false
recommended_next_stage=human_review_XB1_then_repair_provider_or_plan_quality_aware_branch
```

## 30. XB1A1 Blocker Triage And Normal-Gate Lock

XB1A1_BLOCKER_TRIAGE_RAW_DOPPLER_A1_YAW_AND_MAINLINE_NORMAL_GATE is complete as a blocker-triage and safe normal-gate repair stage after XB1A0-E. It created blocker-ledger, Raw Doppler toolchain/provider, A1 yaw gate, dual-yaw applicability, normal-gate, quality-aware branch planning, figure, case-review, validation, and decision artifacts under `<XB1A1_STAGE_ROOT>` and `<XB1A1_NORMAL_GATE_ROOT>`.

Raw Doppler provider materialization is repaired for XB1 through the accepted RTKLIB/RINEX/helper path. The helper compile issue was environmental: native Windows gcc was unavailable, but the stage uses a WSL gcc/helper bridge without substituting GNSS receiver velocity, NAV-PVT velocity, trace, final_v23 output, or LegSA output. The XB1 Raw Doppler factor provider is schema-valid with 1809 rows and is ready as source-backed provider evidence.

The A1 short-baseline yaw gate remains blocked. GNSS1/GNSS2 absolute-position overlap exists, but objective valid A1 epochs are about 1.95 percent and the short-baseline length is nonphysical for the robot antennas: median about 9.14 m, p95 about 51.68 m, and max about 120.50 m. Status long-baseline `rel_pos_n/e/d` and HDT remain rejected as mainline yaw sources.

Algorithm applicability is therefore partial. `LegSA_full_EKF` is blocked because forcing it without valid A1 dual yaw would change the current algorithm identity. `final_v23_dual_antenna_EKF` is not applicable because dual-yaw input is invalid. `single_antenna_gnss1_status_KF_GINS` is allowed and completed normal official evaluation as a diagnostic baseline only.

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

## 31. PG_QA0 Quality-Aware Fallback Design Lock

PG_QA0_QUALITY_AWARE_FALLBACK_DESIGN_AND_PAPER_MAINLINE_DECISION is complete as a design-only stage after PG_MULTI_A0 and XB1A2. It imported BY2, BY3, and PG1-PG4 evidence; defined `LegSA_QA_Fallback_EKF` as a separate future candidate; designed the quality-state machine, measurement ownership, R-scale threshold sources, Raw Doppler retention policy, IMU+Go2 bridge policy, logging schema, implementation roadmap, validation protocol, risk register, and paper-mainline decision matrix.

`LegSA_full_EKF` remains the frozen verified mainline for normal/moderate GNSS and the BY2/BY3 position-up evidence route. `LegSA_QA_Fallback_EKF` is a supervisory quality manager and fallback policy over the existing EKF update core; it may share code in a later implementation but must have a separate `algorithm_id`, logs, and validation package. It is not final_v23 and does not relabel `LegSA_full_EKF`.

Current PG_QA0 decision:

```text
status=PG_QA0_design_complete_human_review_before_QA1
paper_mainline_recommendation=Option_B_design_extension_now
optional_high_tier_route=Option_C_after_QA1_QA2_QA3
legsa_full_ekf_status=frozen_verified_mainline
legsa_qa_fallback_ekf_status=design_only_not_implemented_not_validated
ready_for_QA1=false
ready_for_paper_claims=false
recommended_next_stage=human_review_PG_QA0_then_keep_future_work_or_approve_PG_QA1
```

PG_QA0 does not authorize implementation, solver execution, evaluator execution, degraded-input generation, random-array generation, parameter retuning, quality-aware execution, trace-tuned thresholds, poor-GNSS robustness claims, paper performance claims, PR #52 merge/closure/tag, or any relabeling of `LegSA_full_EKF`.

## 32. PAPER0 Mainline Evidence Package Lock

PAPER0_MAINLINE_EVIDENCE_PACKAGE_AND_CLAIM_BOUNDARY_REVIEW is complete as a paper-facing evidence organization and claim-boundary review stage after PG_QA0. It uses existing evidence only: BY2 full-metric main evidence, BY3 independent position/up generalization with diagnostic-only yaw, PG1-PG4 severe-GNSS boundary/motivation evidence, and PG_QA0 design-extension evidence.

Current PAPER0 decision:

```text
status=PAPER0_evidence_package_complete_ready_for_manuscript_drafting
paper_mainline=LegSA_full_EKF_with_BY2_BY3_evidence
qa_role=design_extension_or_future_work
ready_for_manuscript_drafting=true
ready_for_QA1=false
ready_for_paper_claims=false
recommended_next_stage=PAPER1_MANUSCRIPT_EXPERIMENT_SECTION_DRAFT
```

PAPER0 does not authorize solver execution, evaluator execution, degraded-input generation, random-array generation, QA1 implementation, parameter retuning, metric alteration, final paper figures, final paper claims, PR #52 merge/closure/tag, staging runtime outputs, or staging Obsidian notes.

## 33. PAPER10X Git Context Cleanup And Next Experiment Direction Freeze

`PAPER10X_GIT_CONTEXT_CLEANUP_AND_COMMIT` is the active Git/context cleanup stage after PAPER10A, PAPER10A_R1, PAPER10B, PAPER10B_R1, PAPER10B_R2B, and PAPER10B_R2C. It is a documentation, Git hygiene, claim-boundary, Obsidian sync, and next-experiment planning stage only.

PAPER10X must not run solvers, evaluators, DA, LC, GINav, MATLAB, RTKLIB, contact-aided variants, complete FGO, random generation, degraded-input generation, or any continuation of PAPER10B_R2. It must not modify receiver CSV, Go2 body text, trace, raw data, or existing runtime outputs.

PAPER10X Git handling rules:

- classify every tracked and untracked dirty item before staging;
- keep `.legsa_runtime/` and `qa_fallback_review/` untracked or ignored;
- stage only safe context docs, lightweight reports, `.gitignore`, and alias-safe summaries;
- never stage raw/RINEX/UBX/RTCM/bag/NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, archives, conda installers, core dumps, or files over 50 MB;
- never write local absolute paths into tracked docs;
- do not reset, clean, stash, push, merge, tag, close PRs, or delete branches.

Current PAPER10X evidence summary:

- `LegSA_full_EKF` remains the verified main algorithm identity.
- `final_v23_dual_antenna_EKF` remains a strong Dual-Antenna GNSS/INS EKF baseline and external reference, not solver input.
- Raw Doppler velocity update and source-aware LSIM/OIM R scaling are accepted mainline modules.
- BY2 is the main full-metric dataset; PAPER10B_R1 closed BY2 120 x 5 source-aware full ablation.
- BY3 is position/up generalization plus poor-heading stress; PAPER10B_R2B closed BY3 120 x 5 source-aware rows, but BY3 yaw remains diagnostic-only.
- PAPER10B_R2C repaired default `python3` and reinstalled conda without creating a new default env.

PAPER10X next-stage decision:

```text
steady_submission_route=PAPER10C -> PAPER10E -> PAPER10F
strong_innovation_route=PAPER10C -> PAPER10B2 -> optional PAPER10D -> PAPER10E -> PAPER10F
ready_for_paper_claims=false_until_final_method_matrix_and_claim_review
```

PAPER10X keeps these claim boundaries: source-aware can be a bounded main innovation supported by BY2 and stress-tested by BY3, but it must not be written as universal superiority; BY3 must not be written as ordinary yaw generalization; `LegSA_QA_Fallback_EKF`, complete nine-factor FGO, and full contact-aided InEKF remain future or unsupported claims unless later reviewed evidence closes them.

## 34. PAPER4A Write-Ready Evidence Package Lock

`PAPER4A_WRITE_READY_EVIDENCE_PACKAGE_AND_CONTEXT_SYNC` consolidates completed evidence from PAPER1F, PAPER2A, PAPER2B, PAPER3A-R1, PAPER3B, PAPER3D-R2, PAPER3E, PAPER3F, PAPER3G, PAPER3H, and PAPER3I into a writing-ready evidence package. It is a consolidation/context-sync stage only.

PAPER4A consolidates completed evidence; it does not close body-yaw, exact reproduction, or same-evaluator superiority.

PAPER4A allowed work:

- classify evidence as `MAIN_TEXT_ALLOWED`, `APPENDIX_ALLOWED`, `DIAGNOSTIC_ONLY`, `BLOCKED_WITH_PROOF`, or `FORBIDDEN_CLAIM`;
- create lightweight evidence ledgers, writing scaffold, figure/table plan, claim-boundary tables, reviewer/supervisor reports, and context updates under `<PAPER4A_STAGE_ROOT>`;
- use PAPER2B as secondary proof for PAPER1F if direct PAPER1F files are not found;
- use PAPER3I as the latest provider/backend evidence while preserving PAPER3G/PAPER3H lineage.

PAPER4A forbidden work:

- no solver, evaluator, degraded-input generation, random generation, figure rendering, algorithm execution, parameter retuning, RTKLIB source modification, RINEX/UBX/RTCM/raw/runtime mutation, external-code modification, or push;
- no runtime/raw/RINEX/UBX/RTCM/external-code artifact may be staged;
- no body-yaw RMSE, yaw superiority, exact/full faithful reproduction, five faithful external dual-antenna algorithms, same-evaluator superiority, BY3 yaw generalization, XB severe-GNSS high-precision proof, trace-online, receiver-IMU-as-Go2-body-IMU, or full contact/joint-foot kinematic claim may be introduced.

PAPER4A paper-use decision:

```text
status=PAPER4A_write_ready_evidence_package_context_sync
main_text_allowed=dataset_protocol_BY2_BY3_XB_roles; BY2_120_case_design; PAPER2A_QA_behavior_and_coverage; RTKLIB_RINEX_DDLOS_provider_chain; provider_v4_GPS_BDS_residual_ready; evidence_classification_matrix; forbidden_claim_boundary_table
appendix_allowed=PAPER2A_row_level_QA; PAPER3E_to_PAPER3I_native_proxy_backend_level_literature_module_diagnostics; LAMBDA_MLAMBDA_helper_evidence; provider_v4_system_frequency_blockers; internal_baseline_error_series_coverage
diagnostic_only=PAPER1F_adapters; yaw_frame_sensitivity; RTKLIB_movingbase; BY3_yaw; XB_PG_severe_GNSS; Pavlasek_IEKF_and_Wu_EQKF_diagnostics
ready_for_manuscript_drafting=true_bounded_by_claim_boundary
ready_for_paper_claims=false
```

## 35. PAPER4B_R2 Physical Frame Close And Offline Yaw Reevaluation Lock

`PAPER4B_R2_PHYSICAL_FRAME_CLOSE_AND_YAW_REEVALUATION` records the user-confirmed Fixposition/Go2 antenna installation evidence and accepts the physical frame policy for the BY2 dual-antenna baseline. This stage closes the physical antenna-to-body geometry only; it does not close exact reproduction, full faithful external algorithms, same-evaluator superiority, BY3 yaw generalization, or XB severe-GNSS high-precision proof.

PAPER4B_R2 accepted physical facts:

- Fixposition receiver front faces the Go2 forward direction.
- Official GNSS extrinsics are used.
- GNSS1 has negative y and is the robot-right antenna.
- GNSS2 has positive y and is the robot-left antenna.
- Under Go2 FLU, GNSS1->GNSS2 is body `+Y_left`.
- The fixed physical transform is `body_yaw_NED_deg = wrap360(baseline_heading_NED_deg + 90 deg)`.

PAPER4B_R2 allowed evidence:

- `FRAME_POLICY_ACCEPTED.yaml` under `<PAPER4B_R2_STAGE_ROOT>`;
- user-confirmed physical-frame statement, photo/PDF/STEP/STL evidence indices, trace-generation audit, and mount geometry reports;
- derived offline yaw reevaluation for PAPER3F/PAPER3G/PAPER3H rows whose native baseline heading semantics are explicit `atan2(E,N)` and whose baseline direction is GNSS1->GNSS2;
- lightweight summary tables, render-QA reports, and figure/table indices under `<PAPER4B_R2_STAGE_ROOT>` and `<PAPER4B_R2_EXPORT_ROOT>`.

PAPER4B_R2 diagnostic/blocked evidence:

- PAPER3I Wu EQKF DD/LOS row headings remain diagnostic and are not case-level baseline-state body-yaw outputs.
- PAPER3I Pavlasek IEKF remains innovation/provider diagnostic without a baseline-heading epoch output for body-yaw reevaluation.
- PDF machine text extraction may be unavailable; official extrinsics values are recorded from the user-provided official tutorial excerpt and the present PDF asset path.

PAPER4B_R2 hard prohibitions:

- no modification of historical `epoch_output.csv`;
- no per-case offset, no RMSE-selected transform, and no method-specific trace tuning;
- no trace online use;
- no receiver `imu-data.csv` as Go2 body IMU;
- no exact/full faithful external reproduction claim;
- no final_v23, LegSA_QA, LegSA_full, or universal superiority claim;
- no raw/RINEX/UBX/RTCM/runtime payload or external-code staging;
- no push.

## 38. PAPER10C_R1A Interrupted Go2 BY3 Matrix Resume

`PAPER10C_R1A_RESUME_INTERRUPTED_GO2_BY3_MATRIX_AND_COMPLETE_STAGE` is closed as a conditional resume-manifest package, not a completed matrix package.

PAPER10C_R1A recovered facts:

- BY3 Go2 source `by3.txt` exists and matches the R1 provider QA hash.
- BY3 roll/pitch, horizontal velocity, and readiness/motion-state providers exist and are generated from BY3, not BY2.
- BY2 Go2 120x6 is closed at 720/720 completed-evaluable rows.
- BY3 Go2 120x6 is partial: 543/720 completed-evaluable rows, 169 missing rows, and 8 partial/corrupted rows.
- A resume manifest and missing-only wrapper exist; the wrapper must not run `SKIP_ALREADY_COMPLETED` rows.
- Runner execution was not performed in R1A because the Windows E free-space gate failed.

PAPER10C_R1A claim boundary:

- Go2 high-level motion-state data may be described only as bounded weak-prior and LSIM metadata support under verified source roles.
- Readiness/motion-state is first-class LSIM metadata in completed G03/G05 runtime rows, but BY3 readiness modes are not globally closed until the missing/partial BY3 rows are resumed and validated.
- BY3 yaw remains diagnostic-only.
- Do not claim full BY2/BY3 Go2 matrix closure, full contact-aided InEKF, full leg odometry, Go2 position/yaw truth, universal superiority, complete nine-factor FGO, or completed PAPER10B2 multi-state quality management from R1A.
- Next safe route is either a space-gated `PAPER10C_R1B` missing-only resume, or a human-approved PAPER10B2 design/validation stage if the paper keeps multi-state quality management as a contribution.

## 39. PAPER10C_R1B Low-Space BY3 Missing-Only Resume

`PAPER10C_R1B_LOW_SPACE_BY3_MISSING_ONLY_RESUME` closes the R1A low-space blocker with a human-approved lower Windows E hard-stop.

PAPER10C_R1B recovered facts:

- User-approved runner gate: Windows E hard-stop 5 GB and WSL root hard-stop 20 GB.
- R1B imported the R1A resume manifest and selected only BY3 rows marked missing/partial/corrupted.
- R1B quarantined the 8 partial/corrupted BY3 rows before rerun.
- R1B reran 177/177 selected BY3 rows with jobs=8 and zero runtime failures.
- BY2 Go2 120x6 remains closed at 720/720 completed-evaluable rows and was not rerun.
- BY3 Go2 120x6 is now closed at 720/720 completed-evaluable rows.
- BY3 provider evidence remains `by3.txt`-derived; BY2 providers were not reused as BY3.
- Readiness/motion-state metadata is first-class LSIM metadata for G03/G05 runtime rows.
- Completed rows were not overwritten; trace online, per-case tuning, final_v23/LegSA solver input, and Go2 position/yaw truth remain false.

PAPER10C_R1B claim boundary:

- Go2 high-level roll/pitch, horizontal velocity, and readiness/motion-state metadata may be described as a bounded source-aware auxiliary-prior/LSIM metadata mechanism.
- BY3 yaw remains diagnostic-only.
- Performance is mixed, so Go2 is a supporting/secondary innovation candidate, not a universal superiority or standalone main-performance claim.
- PAPER10B2 multi-state quality management is motivated by R1B but remains future work unless separately executed.
- Do not claim full contact-aided InEKF, full leg odometry, complete nine-factor FGO, Go2 position/yaw truth, trace online use, per-case tuning, or BY3 ordinary yaw generalization from R1B.

## 40. PAPER10Y Post-R1B Git Archive And WSL Space Cleanup

`PAPER10Y_POST_R1B_GIT_ARCHIVE_AND_WSL_SPACE_CLEANUP` is a maintenance-only closeout after PAPER10C_R1B. It is not a new experiment stage.

PAPER10Y recovered facts:

- PAPER10C_R1B evidence remains accepted: BY2 Go2 120x6 and BY3 Go2 120x6 are both closed at 720/720.
- Selected completed WSL runtime/worktree material was archived under `<PAPER10Y_ARCHIVE_ROOT>` using tar.xz fallback archives.
- Archive SHA256 recording and integrity verification passed for all selected packages.
- Only verified WSL source directories or clean verified worktrees were deleted; about 67.1 GB of WSL internal space was released.
- `fstrim` was attempted but sudo required a password.
- A Windows Administrator PowerShell compact script was generated; VHDX compact remains manual and pending.

PAPER10Y boundaries:

- No solver/evaluator, DA, LC, GINav, MATLAB, RTKLIB, contact-aided reproduction, complete FGO, PAPER10B2, or PAPER10E execution was run.
- No raw data, by2.txt, by3.txt, trace, main repo, C/G project data, C export, or Obsidian vault was deleted.
- PAPER10Y supports the next-route recommendation `PAPER10B2_MULTI_STATE_QUALITY_MANAGEMENT_CLOSURE`, but it does not complete PAPER10B2.
- Do not treat archive/cleanup success as algorithm-performance evidence.

## 36. PAPER4G Yaw Boundary Freeze And Native Metrics Route

`PAPER4G_YAW_BOUNDARY_FREEZE_NATIVE_METRICS_WRITE_PACKAGE` freezes the external-method body-yaw claim boundary after PAPER4F_R2. PAPER4F_R2 applied the user-declared BY2 minimal-export yaw policy `trace_body_yaw_NED_deg = wrap360(trace_yaw_deg + 90 deg)` to 2160/2160 PAPER3F/PAPER3G/PAPER3H vector-closed method-case rows, but the systematic yaw discrepancy remained: median previous-policy RMSE was about 94.65 deg, median user-policy RMSE was about 106.09 deg, and the 90-degree-like systematic case ratio was about 0.9875.

PAPER4G frozen decisions:

- physical GNSS1-right/GNSS2-left baseline frame remains closed from PAPER4B_R2;
- trace yaw source remains closed to `user_io-out-poi_geodetic.csv:ypr.vector3.x`;
- status `rel_pos` and LLH position-diff remain invalid as physical short-baseline truth;
- final body-yaw RMSE and yaw-superiority claims for external literature methods remain diagnostic-only;
- external literature method comparison must use native DD/LOS baseline, residual, ambiguity, provider-readiness, ratio/ADOP, and fix-rate-proxy evidence.

PAPER4G allowed evidence:

- `PAPER4G_YAW_CLAIM_BOUNDARY_FREEZE.md`;
- `PAPER4G_YAW_DECISION_TABLE.csv`;
- `PAPER4G_NATIVE_DDLOS_METRICS_LEDGER.csv`;
- `PAPER4G_EXTERNAL_LITERATURE_METHOD_STATUS.csv`;
- writing package files that route external method discussion to native metrics only.

PAPER4G hard prohibitions:

- no body-yaw RMSE claim;
- no external-method yaw superiority claim;
- no exact/full faithful external reproduction claim;
- no RTKLIB-as-Teunissen/Yang/Liu/Wu exact reproduction claim;
- no final_v23, LegSA_QA, LegSA_full, BY3 yaw generalization, or XB severe-GNSS high-precision claim;
- no trace online use;
- no receiver `imu-data.csv` as Go2 body IMU;
- no raw/RINEX/UBX/RTCM/runtime payload or external-code staging;
- no push.

## 37. PAPER10C Go2 High-Level Prior Evidence Freeze

`PAPER10C_GO2_HIGH_LEVEL_PRIOR_EVIDENCE_FREEZE` is closed as a conditional Go2 auxiliary-prior freeze. It imports the PAPER10X route decision, PAPER10A Go2/source-aware code evidence, PAPER10B_R1/BY2 source-aware policy, PAPER10B_R2B/BY3 source-aware closure, and N7C6 Go2 prior provider evidence.

PAPER10C proven code/runtime facts:

- Go2 roll/pitch weak prior is code-present and enters `EKFUpdate` through the source-aware `go2_attitude_roll_pitch` source when enabled.
- Go2 horizontal velocity weak prior is code-present and enters `EKFUpdate` through the source-aware `go2_horizontal_velocity` source when controlled horizontal mode is enabled.
- Go2 vertical velocity is disabled or diagnostic-only; Go2 position and Go2 yaw are not truth inputs.
- BY2 Go2 ablation used fixed `SA04_N6B_POLICY` and completed 480 evaluable rows for G00/G01/G02/G04; G03/G05 readiness metadata rows are blocked with proof because readiness/motion-state is not first-class LSIM metadata.
- BY3 Go2 ablation was not launched because the current workspace did not contain the required BY3 Go2 prior provider CSVs; BY3 yaw remains diagnostic-only.

PAPER10C claim boundary:

- Go2 can be described as a BY2-supported bounded auxiliary weak-prior module.
- Do not write Go2 as full contact-aided InEKF, full leg odometry, support-foot FK, Go2-yaw truth, or Go2-position truth.
- Do not write universal improvement, comprehensive final_v23 outperformance, BY3 ordinary yaw generalization, trace online use, final_v23/LegSA output solver input, or per-case tuning.
- PAPER10B2 is required only if the paper keeps a multi-state quality-management claim; otherwise PAPER10E may use Go2 as a bounded auxiliary prior while leaving readiness metadata and BY3 Go2 provider generation as future work.

## 41. PAPER10B2 Multi-State Quality Management Closure

`PAPER10B2_MULTI_STATE_QUALITY_MANAGEMENT_CLOSURE` first closed as a conditional hard-stop stage: it implemented the source-level multi-state QM mechanism and closed BY2, but BY3 stopped at the user-defined E drive hard-stop. `PAPER10B2_R1_MISSING_ONLY_RESUME_AND_FINAL_QM_CLOSURE` then resumed only the BY3 missing-only manifest and closed the full BY3 matrix.

PAPER10B2 proven facts:

- Multi-state QM is implemented as a deterministic source-level state/action/recovery layer above source-aware `SA04_N6B` LSIM/OIM and Go2 `G05_FULL_AUX` readiness/motion-state metadata.
- Fixed states are `NORMAL`, `DOWNWEIGHT`, `REJECT`, `HOLD`, `RECOVERY`, and `FALLBACK`; each source keeps independent state and counters.
- Managed sources are `receiver_position`, `receiver_velocity`, `dual_antenna_yaw`, `raw_doppler_velocity`, `go2_attitude_roll_pitch`, and `go2_horizontal_velocity`.
- QM is default-off through `enable_multi_state_qm=false` / `QM00_OFF`, and `QM_STATE_ACTION_TRACE.csv` records source/action/recovery evidence when enabled.
- Targeted unit/integration tests and `legsa_v23_port_core_demo` build passed.
- BY2 QM matrix completed 600/600 rows with state/action trace evidence.
- BY3 QM matrix completed 579/600 rows before `E_DRIVE_HARD_STOP`; R1 processed only the 21 missing-manifest rows, harvested 7 complete-but-unindexed artifacts, executed 14 missing-only rows, and closed BY3 at 600/600.
- BY3 yaw remains diagnostic-only. Trace online, final_v23/LegSA output solver input, Go2 position/yaw truth, per-case tuning, and external DA/LC/GINav/MATLAB/RTKLIB/contact-aided/complete FGO remained false.

PAPER10B2 decision:

- R1 final status is `CONDITIONAL_PASS_QM_FULL_MATRIX_COMPLETED_PERFORMANCE_MIXED`.
- Current QM evidence enum is `QM_MAIN_MECHANISM_READY_AS_BOUNDED_METHOD_NOT_UNIVERSAL_PERFORMANCE_CLAIM`.
- QM may be treated as a bounded deterministic mechanism contribution after human wording review, but not as universal superiority or final_v23 outperformance.
- The next safe action is human review of the mixed-performance boundary before PAPER10E.

PAPER10B2 boundaries:

- BY3 full QM matrix completion may now be claimed only as 600/600 runtime closure, not as yaw generalization or universal performance improvement.
- Do not write universal superiority, final_v23 outperformance, BY3 ordinary yaw generalization, trace online use, final_v23/LegSA output solver input, Go2 pose/yaw truth, output substitution, per-case tuning, complete nine-factor FGO, or full contact-aided InEKF.
- Do not treat fallback as output substitution or source-aware LSIM/OIM alone as the complete multi-state QM mechanism.

## 42. PAPER10G Legged State Estimation Observability Diagnostic

`PAPER10G_LEGGED_STATE_ESTIMATION_OBSERVABILITY_DIAGNOSTIC` is a theory/diagnostic and paper-packaging stage. It imports PAPER10B/PAPER10C/PAPER10B2/PAPER10Y evidence, audits Go2/source-aware/QM/dual-yaw code contracts, reviews primary legged-observability literature, reads BY2/BY3 Go2 high-level logs in read-only mode, runs lightweight yaw-rate and symmetry/gauge diagnostics, and generates paper-facing tables, figures, claim boundaries, C export, and Obsidian notes.

PAPER10G proven facts:

- IMU plus legged proprioceptive/contact/high-level sensing alone leaves global translation and gravity-axis yaw unobservable without an external/global reference.
- Gravity can constrain roll/pitch but cannot define absolute heading.
- Go2 roll/pitch is a weak attitude prior, Go2 horizontal velocity is a weak or diagnostic motion constraint, and Go2 readiness/motion-state is LSIM/QM metadata.
- Go2 yaw and Go2 position are not truth and are not absolute global-reference measurements.
- Short lateral dual-antenna GNSS yaw remains the absolute heading source, with body-yaw semantic conversion and source-quality management required.
- Source-aware weighting and multi-state QM are motivated by heterogeneous source observability and reliability.
- BY3 yaw remains diagnostic-only.

PAPER10G boundaries:

- Do not claim full contact-aided InEKF, full leg odometry, Hartley reproduction, complete nine-factor FGO, DA, LC, GINav, MATLAB, RTKLIB, or large-matrix execution from PAPER10G.
- Do not use trace online, final_v23/LegSA output as solver input, Go2 yaw/position truth, receiver `imu-data.csv` as Go2 body IMU, output substitution, bad-epoch deletion, or per-case tuning.
- Do not write legged-only absolute yaw/global position, BY3 ordinary yaw generalization, universal superiority, or final_v23 outperformance.
- Generated figures are runtime/export artifacts only and must not be staged.

PAPER10G next route:

- `PAPER10H_XB_PG_QM_BOUNDARY_DIAGNOSTIC` is recommended for severe-GNSS XB/PG source-risk and QM state/action/recovery visualization.
- PAPER10H should remain boundary/diagnostic evidence unless the human explicitly approves a broader execution stage.

## 43. PAPER10G_R2 Real Legged State Estimation Literature Reproduction

`PAPER10G_R2_REAL_LEGGED_STATE_ESTIMATION_LITERATURE_REPRODUCTION` is a bounded real-sequence literature-reproduction stage. It locks the user-provided legged-state-estimation PDFs, deduplicates repeated sources, extracts method formulas/input contracts/fidelity boundaries, builds BY2/BY3 Go2 high-level legged providers, and runs independent LSE01-LSE05 backends on real BY2/BY3 sequences.

PAPER10G_R2 proven facts:

- `2104.04238v1` duplicate copies are byte-identical; `1805.10410v1` and `1904.09251v2` are the original/extended Hartley InEKF method family and are not counted as two independent methods.
- LSE01 is Hartley contact-aided InEKF; LSE02 is QEKF/kinematic contact EKF; LSE03 is Rotella point-foot subset with humanoid flat-foot branch not applicable to Go2; LSE04 is FK plus preintegrated contact factor graph; LSE05 is Teng slippery InEKF velocity-update camera-off subset.
- BY2 and BY3 Go2 legged providers are built from read-only `sportmodestate` logs using IMUState, `foot_force`, `foot_position_body`, `foot_speed_body`, velocity, mode/gait, and body-height fields.
- `foot_position_body` is a high-level FK-like proxy, not raw joint encoder FK.
- No Go2 yaw/position truth, GNSS dual-yaw input, trace online input, final_v23/LegSA solver input, DA, LC, GINav, MATLAB, RTKLIB, complete FGO, LegSA final matrix, degradation matrix, or per-case tuning was used.
- BY2/BY3 LSE comparison is valid only as formula-level/proxy-bounded local proprioceptive odometry evidence.
- Absolute yaw RMSE remains `NOT_APPLICABLE_WITH_PROOF`; relative yaw drift after initial alignment is diagnostic only.

PAPER10G_R2 decision:

- Final status is `CONDITIONAL_PASS_REAL_LSE_COMPLETED_WITH_PROXY_BOUNDARIES`.
- LSE methods support the Go2 weak-prior/QM context and local odometry discussion, but they do not replace short lateral dual-antenna GNSS absolute yaw or LegSA-GINS global PNT.
- The next recommended stage remains `PAPER10H_XB_PG_QM_BOUNDARY_DIAGNOSTIC`.

PAPER10G_R2 boundaries:

- Do not claim author-official exact reproduction, raw-joint-FK reproduction, full contact-aided exact reproduction, or tracking-camera branch execution from PAPER10G_R2.
- Do not claim legged-only absolute yaw, Go2 yaw/position truth, BY3 ordinary yaw generalization, universal superiority, final_v23 outperformance, trace online use, output substitution, or per-case tuning.
- Runtime provider CSVs over 50 MB stay runtime-only and must not be committed or included in lightweight C export.

## 44. PAPER10G_R2A LSE Method Distinctness Audit And Recompute Gate

`PAPER10G_R2A_LSE_METHOD_DISTINCTNESS_AUDIT_AND_REAL_RECOMPUTE_GATE` is the mandatory audit and repair stage for PAPER10G_R2 method-distinctness claims. It treats PAPER10G_R2 as untrusted evidence, audits backend code, output provenance, metric sources, perturbation sensitivity, and short-segment reruns, then triggers recomputation because the initial R2 implementation used a single dispatch backend.

PAPER10G_R2A proven facts:

- The user suspicion was partially correct: the initial PAPER10G_R2 script used one `run_backend(provider, method)` dispatcher with method branches, so R2 alone cannot support the phrase "one independent backend per literature method".
- R2 roll/pitch metrics were not method-specific because they directly reused Go2 provider roll/pitch fields; those R2 roll/pitch metrics are superseded.
- R2A executed a full repaired recompute for BY2/BY3 and LSE01-LSE05 using separate top-level backend functions, separate backend hashes, separate output files, update-count summaries, output-provenance hashes, perturbation tests, and short-segment validation.
- Repaired LSE01 is a Hartley/RIEKF-style contact velocity proxy; LSE02 is a standard QEKF/kinematic-contact proxy; LSE03 is a Rotella point-foot subset with flat-foot branch not applicable; LSE04 is a fixed-window contact-factor smoothing proxy; LSE05 is a Teng camera-off velocity-update subset.
- All repaired key metrics are finite, output pairs are method-distinct, LSE05 velocity-disable perturbation changes output, and contact/foot-position perturbation gates pass for the methods expected to consume those fields.
- R2A final status is `PASS_LSE_METHOD_DISTINCTNESS_REPAIRED_AND_RECOMPUTED`.

PAPER10G_R2A decision:

- PAPER10G_R2 initial method-distinctness evidence is superseded by PAPER10G_R2A.
- Use only R2A repaired/recomputed metrics for LSE method-distinct comparison.
- The fidelity ceiling remains formula-level/proxy-bounded; no author-official exact, raw joint FK, full GTSAM/iSAM2 factor graph, full contact-aided exact reproduction, or Teng tracking-camera branch is claimed.

PAPER10G_R2A boundaries:

- Absolute yaw RMSE remains `NOT_APPLICABLE_WITH_PROOF`; LSE methods provide local proprioceptive odometry/attitude/velocity context and cannot replace short lateral dual-antenna GNSS yaw.
- No Go2 yaw/position truth, GNSS dual-yaw input to LSE, trace online use, final_v23/LegSA output solver input, DA, LC, GINav, MATLAB, RTKLIB, LegSA final matrix, degradation matrix, complete FGO, per-case tuning, output substitution, or bad-epoch deletion was used.
- Generated figures and full recompute result CSVs remain runtime/C-export artifacts only and must not be staged.

## 45. PAPER10G_R3 LSE Fidelity Upgrade Raw FK Official Adapters

`PAPER10G_R3_LSE_FIDELITY_UPGRADE_RAW_FK_OFFICIAL_ADAPTERS` is a fidelity-upgrade audit after PAPER10G_R2A. It uses the user-provided Go2 URDF zip as read-only runtime material, locks the URDF identity and Go2 leg FK chains, scans for raw lowstate joint `q/dq`, checks official-code/GTSAM/Teng tracking-camera feasibility, and repairs C1-C9 claim boundaries.

PAPER10G_R3 proven facts:

- The Go2 URDF zip is hash-locked and extracted runtime-only; the primary URDF parses successfully.
- The URDF contains four base-to-foot Go2 leg chains with hip, thigh, and calf joints for FL/FR/RL/RR.
- Lowstate motor order remains unconfirmed because BY2/BY3 timestamped raw `motor_state.q/dq` streams were not found.
- Raw FK provider generation is `BLOCKED_WITH_PROOF`; `sportmodestate.foot_position_body` remains a high-level proxy, not raw joint FK.
- Hartley author-official exact reproduction is not closed; MATLAB/Simulink official example availability does not equal a Go2 official adapter run.
- LSE04 remains below full GTSAM/iSAM2 closure because local GTSAM was not available and raw FK is blocked.
- Teng tracking-camera branch remains blocked because no synchronized tracking-camera/VIO velocity source was proven.
- Absolute yaw remains `NOT_APPLICABLE_WITH_PROOF`; Go2 yaw/position remain forbidden as truth; BY3 yaw remains diagnostic-only.

PAPER10G_R3 boundaries:

- Do not claim author-official exact reproduction, raw joint FK, full Hartley InEKF official adapter, full GTSAM/iSAM2 factor graph, or Teng tracking-camera branch execution from R3.
- Do not relabel high-level `foot_position_body` / `foot_speed_body` as raw FK or raw joint encoder output.
- Do not write LSE absolute yaw/global position, LegSA-GINS universal superiority over LSE, BY3 ordinary yaw generalization, Go2 yaw/position truth, trace online use, GNSS dual-yaw as LSE input, final_v23/LegSA output as solver input, DA, LC, GINav, MATLAB, RTKLIB, LegSA final matrix, degradation matrix, complete FGO, per-case tuning, or output substitution.
- URDF zip, extracted URDF trees, raw data, by2/by3 files, images/PDFs, and runtime-heavy outputs must remain untracked.

## 46. PAPER10X_R2 Git Remote Branch PR Merge And Bundle Freeze

`PAPER10X_R2_GIT_REMOTE_BRANCH_PR_MERGE_AND_BUNDLE_FREEZE` is a Git-only safety-freeze stage before new-drive migration. It audits local branches, remote branches, worktrees, tags, unpushed commits, GitHub PRs, merge decisions, stage-to-commit maps, and bundle/restore policy. It does not run experiments or modify raw/project data.

PAPER10X_R2 proven facts:

- Full local/remote ref audit is required; current evidence must not rely on a spot check of the active branch only.
- Existing open PRs are audited but not merged, closed, or force-updated automatically.
- Branches are classified for human-reviewed merge, evidence-only retention, or bundle-only retention; no blind merge of experimental/runtime branches is allowed.
- The current Git freeze branch remains local unless the human explicitly authorizes a push or draft PR.
- `git bundle --all` is the migration safety artifact; the bundle binary and checksum/verify output are runtime/C-export/archive artifacts, not tracked Git files.
- `AGENTS.md`, `PLANS.md`, `CLAIM_BOUNDARY.md`, and `PHASE_LOG.md` remain authoritative only in the active repository root on the new drive.

PAPER10X_R2 boundaries:

- Do not run solver/evaluator, DA, LC, GINav, MATLAB, RTKLIB, contact-aided reproduction, complete FGO, random/degraded-input generation, or any experiment.
- Do not delete branches, tags, worktrees, old directories, raw data, archives, or migration sources.
- Do not use `git reset`, `git clean`, `git stash`, force-push, or rebase.
- Do not push main or merge PRs without explicit human approval and a safety scan.
- Do not stage raw/RINEX/UBX/RTCM/bag/NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, archives, bundles, files over 50 MB, or local absolute path content.

## 47. PAPER10E0 Basic Dual-Yaw EKF Baseline Freeze

`PAPER10E0_BASIC_DUAL_YAW_EKF_BASELINE_FREEZE` freezes a minimal Basic Dual-Yaw EKF baseline for later PAPER10E/PAPER10H comparison. The active codebase is `paper10e0/basic-dual-yaw-ekf-baseline-freeze` using `cpp/legsa_v23_port_core` from the PAPER10X_R2 base commit. This stage does not merge other branches.

PAPER10E0 proven facts:

- The KF-GINS source parse PDF was read and indexed. The reused backbone is the original loose-coupled GNSS/INS flow: IMU mechanization/propagation, GNSS position update, generic `EKFUpdate`, and `stateFeedback`.
- final_v23 `process_data.py`, `run_final_mainline.py`, and config docs were audited read-only. `process_data.py` contains semi-physical yaw noise/outlier/outage logic and no dedicated PAPER10E0 normal-only gate, so PAPER10E0 did not call it for smoke input assembly.
- Basic Dual-Yaw EKF is formally defined as KF-GINS original propagation plus original 3D GNSS position update plus one optional 1D dual-antenna body-yaw update. The state dimension, INS propagation, and state feedback are unchanged.
- `applyBasicDualYawUpdate` uses `dz = wrap(yaw_INS - yaw_dual)`, `H(0, PHI_ID + 2) = -1`, and fixed `R_yaw = (1.5 deg)^2` in radians squared through the existing `EKFUpdate`.
- source-aware, Go2, QM, Raw Doppler, FGO feedback, QA fallback, and final_v23 robust yaw gate/downweight/reject/hold/fallback are hard-disabled under `enable_basic_dual_yaw_baseline=true`.
- The yaw Jacobian sign test passed, Basic-specific unit tests passed, and the C++ `legsa_v23_port_core_demo` target built successfully.
- BY2 normal smoke completed for B00 position-only and B01 Basic Dual-Yaw; B01 applied 274 yaw updates with 0 reject and 0 downweight.
- BY3 normal smoke completed for B00 and B01 as diagnostic-only; B01 applied 286 yaw updates with 0 reject and 0 downweight. BY3 yaw remains poor-heading diagnostic-only and is not ordinary yaw generalization.

PAPER10E0 boundaries:

- This stage is smoke-only and does not authorize paper performance claims, final method claims, final_v23 outperformance, or BY3 ordinary yaw generalization.
- No BY2/BY3 120 degradation matrix, source-aware LSIM/OIM, Go2 weak prior/readiness, QM, Raw Doppler, selected feedback, complete FGO, DA, LC, GINav, MATLAB, RTKLIB, trace online, per-case tuning, or output substitution was run.
- Official trace RMSE was not run in PAPER10E0; smoke evidence is runtime closure, update counts, disabled-module manifests, and diagnostic yaw residual QA only.
- Runtime outputs under `<PAPER10E0_STAGE_ROOT>`, C export material under `<PAPER10E0_C_EXPORT_ROOT>`, and Obsidian notes under `<PAPER10E0_OBSIDIAN_SYNC_ROOT>` are not solver inputs and must not be confused with tracked algorithm sources.
- Do not stage NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, raw/by2/by3/trace data, archives, files over 50 MB, or local absolute paths.
## PAPER10Z3 Migration And Dual-Root Policy

PAPER10Z3 establishes a dual-root operating model:

- `<LEGSA_CODE_ROOT>` is the active WSL/ext4 code root.
- `<LEGSA_PROJECT_ROOT>` is the exFAT project asset root.
- `<LEGSA_OBSIDIAN_ROOT>` is the Obsidian vault inside the project asset root.

The project asset root is not an active Git checkout, C++ build root, or high-frequency experiment workspace. Raw datasets copied into `<LEGSA_PROJECT_ROOT>/data/raw` are immutable by policy and their original source directories remain retained until explicit human approval. Runtime outputs, generated figures, archives, bundles, raw data, NAV/STD/EVAL_NAV/RUN_MANIFEST files, and local absolute paths remain forbidden in Git.

PAPER10Z3 is a reconciliation, migration, archive, and cleanup stage only. It does not authorize algorithm-math changes, solver/evaluator runs, BY2/BY3 matrices, XB/PG execution, MATLAB, RTKLIB/Ginav solver use, PR merge, force push, or push.

## 48. PAPER10M1R2A V2 BY2 Degradation Matrix Spec Lock

`PAPER10M1R2A_V2_BY2_DEGRADATION_MATRIX_SPEC_LOCK_60TYPES_9SEEDS` locks the canonical BY2 controlled-degradation matrix specification. Codex must not invent, trim, merge, or re-plan the degradation matrix in this stage or in downstream provider-generation stages unless the human explicitly replaces the locked spec.

PAPER10M1R2A V2 fixed rules:

- A BY2 degradation case is defined only by `degradation_type_id`, fixed `seed_index` / `seed_value`, canonical anchor policy, and the matching effect-validation rule.
- V2 is fixed as 60 degradation types x 9 seeds plus one clean case: 540 degraded cases, 1 clean case, 541 total cases.
- Mixed cases must have an explicit component list in `degradation_parameters_json`; placeholder mixed cases are forbidden.
- `module-disable` is not a case axis. Module-disable style comparisons belong to internal ablation method queues, not degradation case definitions.
- Trace remains evaluation-only and must not be used for degradation parameter choice, anchor choice, provider generation, solver input, tuning, or feedback.
- Go2 position, yaw, velocity, contact, and metadata remain weak-prior or diagnostic sources only, never truth.
- Raw Doppler and receiver velocity are separate source channels and must not be collapsed into one axis.
- Degraded providers must be generated only in approved runtime/provider roots and must never overwrite raw data.
- M1R2A is no-run: no solver, evaluator, full matrix, provider generation, internal ablation, horizontal benchmark, random provider payload, figure generation, raw modification, or raw copy is authorized.

Downstream route:

- `PAPER10M1R2B` may generate degraded providers only after human approval and must validate each provider against the locked effect-validation rule.
- `PAPER10M1R2C` may run the four frozen method modes only after M1R2B passes.
- `PAPER10M1R2D` may run internal ablations only after M1R2C review.
- PAPER10H remains blocked and separate.

## 49. PAPER10M1R2B V2 BY2 Degraded Provider Generation

`PAPER10M1R2B_V2_BY2_DEGRADED_PROVIDER_GENERATION_AND_EFFECT_VALIDATION_541CASES` must follow the M1R2A frozen 541-case manifest exactly. Codex must not redesign degradation types, seeds, anchors, case counts, or claim boundaries during provider generation.

PAPER10M1R2B fixed rules:

- Every degraded provider package must be defined by the M1R2A `case_id`, `degradation_type_id`, seed replay, anchor realization, and effect-validation rule.
- Every provider package must include seed replay, input source SHA256 manifest, generated provider SHA256 manifest, case spec dump, provider generation log, and effect-validation summary.
- Trace remains evaluation-only and must not enter provider generation, anchor realization, solver input, tuning, or feedback.
- final_v23 and LegSA outputs must not be used for provider generation, anchor realization, or effect adjustment.
- Raw Doppler and receiver velocity remain separate provider channels; receiver velocity must not be substituted for Raw Doppler.
- Go2 high-level/body-state data remain weak-prior or metadata sources only, never truth.
- Degraded providers must never overwrite raw data and must remain runtime artifacts outside tracked Git.
- Provider runtime directories, degraded provider CSV payloads, raw/by2 source files, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, and export-clean zips must not be committed.

PAPER10M1R2B boundaries:

- This stage may generate provider runtime packages and effect-validation reports only.
- It does not authorize solver runs, evaluator runs, full algorithm matrices, internal ablations, horizontal benchmark matrices, PAPER10H, BY3/XB/PG execution, performance claims, final paper claims, or universal-superiority wording.

## 50. PAPER10M1R2C V2 BY2 Full Algorithm Matrix

`PAPER10M1R2C_V2_BY2_FULL_ALGORITHM_MATRIX_EXECUTION_2164ROWS` is the approved BY2 controlled-degradation full-algorithm execution stage after M1R2B provider generation/effect validation passed. It must consume only the M1R2B provider-ready manifest and provider packages.

PAPER10M1R2C fixed rules:

- The executable queue is fixed as four PAPER10L frozen method modes x 541 M1R2B provider-ready cases = 2164 rows.
- The only allowed method modes are `basic_dual_baseline`, `strong_dual_yaw_baseline`, `legsa_without_qm`, and `legsa_full_candidate_with_qm`.
- The queue must be locked locally for M1R2C; M1R2B queue drafts remain unchanged and have `run_allowed_now=false`.
- M1R2C must not redesign the degradation matrix, regenerate providers, or modify M1R2B provider packages.
- Every row must write RUN_MANIFEST, feature flag dump, dataset role dump, method mode dump, case spec dump, provider-ready reference, config hash, forbidden-input audit, and evaluator summary.
- Trace remains evaluation-only and must never enter solver input, tuning, provider selection, method selection, or feedback.
- final_v23, LegSA, benchmark, and external-method outputs must not enter solver input.
- Go2 high-level/body-state providers remain weak-prior or metadata sources only, never truth.
- Receiver IMU must not be treated as Go2 body IMU.
- QA fallback must remain disabled as a final method.
- Runtime NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, provider payloads, and export-clean zip files remain outside tracked Git.

PAPER10M1R2C boundaries:

- This stage authorizes BY2 full-algorithm matrix execution only.
- It does not authorize M1R2D internal ablation, horizontal benchmark comparison, PAPER10H, BY3/XB/PG execution, performance-claim finalization, final paper readiness, universal superiority, final_v23 comprehensive superiority, or complete 9F FGO validation.

## 51. PAPER10M1R2C1 Clean Yaw And QM Semantic Audit

`PAPER10M1R2C1_CLEAN_YAW_QM_SEMANTIC_AUDIT_AND_METRIC_REPAIR` is a mandatory semantic gate inserted after M1R2C and before any M1R2D internal ablation. It exists because M1R2C completed the 2164-row BY2 full algorithm matrix but the clean case yaw metrics and QM counters showed semantic anomalies that cannot be ignored.

PAPER10M1R2C1 fixed rules:

- M1R2C row completion remains an execution-completion fact only; it is not enough for yaw performance claims or ablation authorization.
- The BY2 clean yaw RMSE anomaly must be explained before M1R2D starts.
- Corrected evaluator-only metric tables, if generated, must be explicitly labeled `corrected_evaluator_only` and must never be presented as original solver output.
- QM counters must not be used for claims until their field semantics are audited and separated into required, present, not-required, state-action, and diagnostic meanings.
- `bad_a1_consumed_count` must distinguish accepted, downweighted, rejected, and diagnostic A1 counts before it is used for any paper or algorithm claim.
- Trace remains evaluation-only and may be used to audit evaluator semantics, not solver input, method selection, provider tuning, or output correction.
- No solver rerun, provider regeneration, raw-data modification, per-case tuning, output-only correction, or epoch deletion is authorized in M1R2C1.

PAPER10M1R2C1 current decision:

- M1R2D remains blocked after M1R2C1 because clean yaw semantics did not resolve as a pure evaluator-convention repair.
- The current gate status is `BLOCKED_SOLVER_PROVIDER_YAW_SEMANTIC_FAILURE`.
- PAPER10H remains blocked and separate.

## 52. PAPER10M1R2C2 Yaw Provider And Clean Sentinel Repair

`PAPER10M1R2C2_YAW_PROVIDER_METHOD_MODE_REPAIR_AND_CLEAN_SENTINEL_RERUN` is the repair stage after M1R2C1. It fixes yaw provider lineage and method-mode yaw input semantics before any full rerun or internal ablation.

PAPER10M1R2C2 fixed rules:

- M1R2C clean yaw semantic gate continues to block M1R2D until a clean sentinel passes and the full matrix is rerun from repaired providers.
- Yaw provider repair must be geometry/source-lineage based, not trace-tuned.
- The accepted BY2 yaw provider convention is A1 dual-diff status yaw with GNSS2-GNSS1, GNSS2 interpolation to the GNSS1-time source chain, lateral body-heading conversion, fixed 1.5 deg yaw std, and provider-axis interpolation.
- Clean sentinel must pass before any full rerun or internal ablation.
- `bad_a1_consumed_count` is deprecated unless split into claim-valid accepted/downweighted/rejected counters.
- Corrected evaluator-only tables must be labeled; if the issue is not evaluator-only, no corrected metric table may replace original solver output.
- The original M1R2B provider packages and M1R2C 2164-row results remain historical/invalidated for yaw interpretation; they must not be silently reused for claims.

PAPER10M1R2C2 current decision:

- Clean sentinel passed after provider repair.
- Full 541-provider regeneration is required in M1R2B2.
- M1R2C full algorithm matrix rerun is required after M1R2B2.
- M1R2D and PAPER10H remain blocked until the repaired rerun passes review.

## 53. PAPER10M1R2B2 BY2 Yaw Provider Regeneration

`PAPER10M1R2B2_V2_BY2_YAW_PROVIDER_REGENERATION_AND_EFFECT_REVALIDATION_541CASES` supersedes the old M1R2B provider packages because M1R2C2 proved the original yaw provider lineage was wrong.

PAPER10M1R2B2 fixed rules:

- BY2 yaw provider generation must use source-lineage A1 dual-diff status yaw with GNSS2-GNSS1 and lateral body-heading conversion.
- Baseline heading must not be directly written as solver-visible body yaw.
- Yaw sign and lateral +/-90 deg convention must not be selected by trace RMSE.
- Yaw residual/effect validation must be wrap-safe.
- D30-D41 yaw degradation and D58-D60 mixed yaw components must start from the corrected body-yaw provider.
- M1R2B2 provider packages supersede old M1R2B provider packages for any future M1R2C_R1/M1R2D_R1 run.
- Trace remains evaluation-only and must not enter provider generation, sign selection, tuning, solver input, or feedback.

PAPER10M1R2B2 boundaries:

- This stage regenerates providers, validates effects, locks provider-ready manifests, and drafts M1R2C_R1/M1R2D_R1 queues only.
- It does not authorize solvers, evaluators, full matrix execution, internal ablation, horizontal comparison, PAPER10H, BY3/XB/PG execution, raw-data modification, paper performance claims, final paper readiness, or universal-superiority wording.

## 54. PAPER10M1R2C_R1 Yaw-Corrected Full Algorithm Matrix Rerun

`PAPER10M1R2C_R1_V2_BY2_FULL_ALGORITHM_MATRIX_RERUN_WITH_YAW_CORRECTED_PROVIDERS` is the only approved rerun stage for the BY2 full algorithm matrix after M1R2B2. It must consume the M1R2B2 yaw-corrected provider-ready manifest and provider packages only.

PAPER10M1R2C_R1 fixed rules:

- The executable queue is fixed as four PAPER10L frozen method modes x 541 M1R2B2 provider-ready cases = 2164 rows.
- Old M1R2B provider packages are forbidden.
- Old M1R2C results are forbidden as new results and remain execution proof only.
- The degradation matrix must not be redesigned and providers must not be regenerated in this stage.
- The four method modes must come from PAPER10L frozen config: `basic_dual_baseline`, `strong_dual_yaw_baseline`, `legsa_without_qm`, and `legsa_full_candidate_with_qm`.
- Every row must have RUN_MANIFEST, feature flag dump, dataset role dump, method mode dump, case spec dump, provider-ready reference, yaw provider lineage reference, config hash, forbidden-input audit, and evaluator summary.
- Trace remains evaluation-only and must never enter solver input, tuning, provider selection, method selection, or feedback.
- final_v23, LegSA, benchmark, and external-method outputs must not enter solver input.
- Go2 high-level/body-state providers remain weak-prior or metadata sources only, never truth.
- Runtime NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figures, provider payloads, and export-clean zip files remain outside tracked Git.

PAPER10M1R2C_R1 boundaries:

- This stage authorizes only the BY2 yaw-corrected full-algorithm matrix rerun.
- It does not authorize M1R2D_R1 internal ablation, horizontal benchmark comparison, PAPER10H, BY3/XB/PG execution, performance-claim finalization, final paper readiness, universal superiority, final_v23 comprehensive superiority, or complete 9F FGO validation.

## 55. PAPER10M1R2E BY2 Result Review And Claim Freeze

`PAPER10M1R2E_BY2_RESULT_REVIEW_FIGURE_PACKAGE_AND_CLAIM_BOUNDARY_FREEZE` is the review-only stage after M1R2C_R1 and M1R2D_R1.

PAPER10M1R2E fixed rules:

- M1R2E must not run solvers, evaluators, provider generation, degraded-input generation, random generation, BY3, XB/PG, PAPER10H, or horizontal algorithm comparison.
- M1R2C_R1 and M1R2D_R1 are the current valid BY2 evidence sources for full-algorithm and internal-ablation review.
- Old M1R2C yaw-invalid metrics are forbidden for active claims.
- M1R2C_R1 rows must not substitute for M1R2D_R1 rows, and M1R2D_R1 rows must not substitute for M1R2C_R1 full-algorithm evidence.
- Module contribution claims require M1R2E classification labels and caveats.
- Weak, no-effect, alias, or diagnostic modules must not be inflated into effective module claims.
- Go2 remains an observation / weak-prior source and never truth.
- Trace remains evaluation-only and never solver input.
- Runtime outputs, generated figures, NAV/STD/EVAL_NAV/RUN_MANIFEST, provider payloads, and export-clean zip files remain outside tracked Git.

PAPER10M1R2E current interpretation boundaries:

- Raw Doppler may be described only as a small bounded auxiliary contribution under the frozen BY2 protocol.
- Source-aware weighting may be described as stable bounded evidence with small deltas and tradeoffs.
- Multi-state QM may be described as interpretable state/action evidence with metric tradeoffs, not universal improvement.
- Go2 horizontal velocity may be described only as a weak auxiliary prior with limited measured contribution.
- Go2 roll/pitch is not a main-text strong contribution under current evidence.
- Go2 joint/proprioceptive factor is no-effect/diagnostic in the current matrix if its delta remains zero.
- FGO feedback / EKF-only relation is alias/no-effect/diagnostic in the current matrix if its delta remains zero.
- Dual-antenna yaw is a source-backed BY2 backbone and system foundation, not proof of BY3 yaw generalization.

PAPER10M1R2E boundaries:

- This stage may generate review tables, figure-candidate indexes, Chinese experimental summaries, claim-boundary tables, innovation-positioning notes, next-stage decision notes, AI-context snippets, and export-clean packages.
- This stage does not authorize final paper claim readiness, universal superiority, final_v23 comprehensive superiority, BY3 yaw generalization, XB/PG severe-GNSS high-precision proof, exact external reproduction, complete 9F FGO validation, output-only correction, per-case tuning, or deletion of bad epochs.
- The recommended next stage is M1R2F final figure/table replot from existing summaries only, unless the human chooses M1R2G module repair or a separately authorized BY3/XB/PAPER10H/horizontal route.

## 56. PAPER10Q1 QM Degraded-Action Evidence Package

`PAPER10Q1_QM_DEGRADED_ACTION_EVIDENCE_AND_FIGURE_PACKAGE` is a review/plot-only follow-up focused on multi-state QM and source-aware evidence.

PAPER10Q1 fixed rules:

- Q1 must not run solvers, evaluators, provider generation, degraded-input generation, random generation, BY3, XB/PG, PAPER10H, or horizontal algorithm comparison.
- Q1 may read only frozen M1R2C_R1/M1R2D_R1 result tables, QM/source-aware summaries, and existing trace files for review and plotting.
- Q1-generated PNG/PDF figures are review artifacts under `<PAPER10Q1_FIGURE_ROOT>` and must not be committed to Git.
- Q1 export-clean material must exclude raw data, providers, NAV/STD/EVAL_NAV/RUN_MANIFEST, generated figure binaries, old zips, local absolute paths, and secrets.
- Legacy `bad_a1_consumed_count` is deprecated and must not be used as a claim field.
- QM/source-aware claims must be family-specific and caveated; Q1 does not authorize universal improvement wording.
- BY3, XB/PG, PAPER10H, and horizontal comparison were not run in Q1 and remain separate human-authorized stages only.

PAPER10Q1 current interpretation boundaries:

- Final QM judgment is `QM_supported_only_as_interpretability_and_protection`.
- Source-aware weighting has bounded positive evidence with small deltas and metric tradeoffs.
- Multi-state QM provides interpretable state/action/recovery evidence but has RMSE tradeoffs and must not be written as all-metric precision improvement.
- Full-QM versus no-QM must be presented with no-QM-better and tradeoff caveats.
- Diagnostic figures, legacy counters, and cases where QM hurts or is neutral must not be promoted to main claims.
