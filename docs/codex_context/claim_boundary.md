# Claim Boundary

LegSA-GINS claims must track what the audits actually prove.

## Allowed Current Claims

- The project has a source-backed EKF backbone.
- Raw Doppler has been activated as a real factor in EKF and injected into FGO after the N8C3 fix.
- Source-aware weighting is implemented as a conservative R-scaling layer.
- Go2 proprioceptive joint factor covers roll/pitch and horizontal velocity when parseable source fields exist.
- FGO feedback EKF achieved engineering closure on BY2 clean under the selected conservative policy.
- N8K formal ablation plot audit was repaired through N8K2-N8K6 and merged.
- N9A normal clean completed.
- N9B1D4 is the current technical pilot source.
- N9B1E passed with the C yaw caution and is the current pilot visual/go-no-go source.
- N9B2A/N9B2A1 are full-matrix preparation sources.
- N9B2B completed path lock for Windows/WSL and future by2-huitu output aliases.
- N9B2B1 completed context update after path lock.
- N9B staged execution is complete through N9C0 global consolidated precheck.
- N9C0 active final-only metrics table exists with 825 rows.
- Batch 6 selected mixed cases completed.
- final_v23 external baseline completed and is integrated as `external_reference_baseline`.
- N9C1 consolidated figure generation readiness passed.
- N9E logging-blocked review completed and kept `complete_nine_factor_FGO_claim=false`.
- N9F active nine-factor FGO design package completed with `ready_for_implementation_review=true`.
- N9F6A/N9F7 source-code audit and design package completed with `N9F7_substantial_algorithm_design_required`.
- N9F6A may state that robot kinematics/contact/legged modeling exists in provider, diagnostic, offline no-feedback, and candidate factor code, but this is not complete active FGO residual/cost evidence.
- N9F7 must keep `ready_for_implementation_review=false` until a later manual algorithm design review approves implementation.
- N9F7A/N9G0 Git-boundary and manual design review completed; the earlier publish block is historical after N9G0A.
- N9G0 may state that `LegSA_9F_FGO_EKF` has a manual design package, but it remains design-only and separate from `LegSA_full_EKF`.
- N9G0 must keep `complete_nine_factor_FGO_claim=false`, `ready_for_paper_claims=false`, `ready_for_N9B2_execution=false`, and `ready_for_full_N9B_execution=false`.
- N9G0A completed Git boundary resolution and PR #52 head is synced to `9ceba928`.
- N9G1A may state that N9G1 is split into context lock and later Phase 1 provider/factor/logger/normal-smoke only.
- N9G1A may state that `LegSA_full_EKF` remains the current verified EKF/feedback algorithm.
- N9G1A may state that `LegSA_9F_FGO_EKF` is a separate new candidate.
- N9G1A must keep `complete_nine_factor_FGO_claim=false`, `ready_for_paper_claims=false`, `ready_for_N9B2_execution=false`, and `ready_for_full_N9B_execution=false`.
- N9G1B may state that the separate `LegSA_9F_FGO_EKF` candidate ID, config boundary, provider/factor audit helper, logger schemas, and normal-smoke safety gate exist.
- N9G1B may state that normal smoke was not run because provider contracts are blocked, the active nine-factor FGO backend is unavailable, and candidate solver execution is disabled.
- N9G1C-E may state that locked normal source resolution passed and core providers were resolved for the separate `LegSA_9F_FGO_EKF` candidate.
- N9G1C-E may state that provider contracts are partial accepted, with candidate legged providers still candidate-only or aggregate evidence.
- N9G1C-E may state that active backend and solver execution remain blocked and normal smoke was not run.
- Current evidence requires a new active nine-factor FGO algorithm design before representative runs.
- BY3A0_TO_BY3E may state that BY3 context lock, receiver inventory, BY3 `by3.txt` body-IMU audit, BY2 kick-alignment method recovery, BY3 no-trace kick-event alignment, and BY3 candidate input generation were completed.
- BY3A0_TO_BY3E may state that BY3 normal solver/evaluator execution was blocked by provider and runner gates, so no BY3 normal metrics or BY3 generalization success claim exists yet.
- BY3A0_TO_BY3E may state that BY2 three-scheme text summaries and the BY2 degradation figure archive were generated from existing BY2 evidence as reporting/organization work only.
- BY3A1 may state that BY3A0 candidate inputs failed strict BY2 parity in delimiter/header, IMU column count, single-baseline schema, and original time-normalization policy.
- BY3A1 may state that repaired BY3 runtime input files and BY3 Go2 priors were generated from BY3 source data without trace tuning, parameter retuning, or receiver-IMU substitution.
- BY3A1 may state that BY3 Raw Doppler and BY3 same-case selected feedback remain blocked, so solvers/evaluators were not run.
- BY3A2 may state that historical BY2 WSL Raw Doppler, Go2, single-baseline, final_v23, and selected-feedback chains were recovered.
- BY3A2 may state that BY3 Raw Doppler provider files were materialized through the accepted N5A/N5B RTKLIB/RINEX/helper path without GNSS receiver velocity, NAV-PVT velocity, RTKLIB position solution, trace, final_v23 output, or LegSA output substitution.
- BY3A2 may state that BY3 same-case selected feedback remains blocked and no BY3 solver/evaluator/degradation/metric figure run was performed.
- BY3A3 may state that BY3 same-case selected feedback was generated from stage1 official-eval state/estimate columns only.
- BY3A3 may state that BY3 normal-only `LegSA_full_EKF`, `single_antenna_gnss1_status_KF_GINS`, and `final_v23_dual_antenna_EKF` solver/evaluator runs completed if backed by the BY3A3 runtime decision report.
- BY3A3 may state that its normal-only comparison completed, but its degradation-planning readiness is superseded by BY3A4A.
- BY3A4A may state that BY2 lateral dual-antenna yaw policy evidence was recovered as partial and that the physical dual-antenna baseline is lateral/perpendicular to the robot forward/head direction.
- BY3A4A may state that body heading requires a plus/minus 90 degree correction from antenna-baseline heading depending on antenna order and frame convention, and that +90/-90 must not be selected by RMSE alone.
- BY3A4A may state that existing BY3A3 outputs were used to audit yaw candidates, compute common-overlap metrics, regenerate diagnostic figures, generate seed0-9 explanation files, and update context memory.
- BY3A4A may state that repaired yaw metrics were not accepted and BY3 degradation planning is blocked pending manual yaw-policy review.
- BY3A4C may state that the historical BY2/N4 yaw-reference repair was recovered from git history, tracked docs/source, PR metadata, and runtime evidence.
- BY3A4C may state that N4H2 old yaw around 93 deg was invalidated by N4H2D, N4H2D selected `official_ref_sign_minus`, and fresh replay yaw was about 1.98 deg under the reconstructed dual official reference.
- BY3A4C may state that recovered and diagnostic profiles were applied to existing BY3A3 outputs only, but no BY3 yaw truth/reference profile was accepted.
- BY3A4C may state that BY3 yaw is `not_evaluable`, BY3A3/BY3A4A yaw metrics are historical invalid-reference evidence, and position/up metrics can support position/up-only planning.
- BY3A4C must keep `yaw_degradation_claims=false` and `ready_for_paper_claims=false`.
- BY3A5B may state that BY3A5 correctly confirmed the old BY3 15-column yaw input was wrong-source, while BY3A5's HDT replacement policy is diagnostic/rejected/superseded for mainline BY3.
- BY3A5B may state that BY3 mainline dual yaw was regenerated from GNSS1/GNSS2 A1_dual_diff short-baseline absolute positions with BY2 sign/lateral conversion and fixed_1p5 yaw_std.
- BY3A5B may state that BY3 normal-only solver/evaluator reruns completed for LegSA_full_EKF, single_antenna_gnss1_status_KF_GINS, and final_v23_dual_antenna_EKF, with no degradation, no HDT solver input, no trace/final_v23/solver-output input, and no parameter retuning.
- BY3A5B may state that A1 input repair completed but yaw remained unresolved before BY3A6.
- BY3A6 may state that the BY3 trace file is the evaluation truth reference, evaluator raw-field/base_time/yaw_truth_mode behavior is valid, and processed trace lat/lon fields are unsafe for blind evaluation.
- BY3A6 may state that stage1 and LegSA_full_EKF had stale first-row initatt before repair and now use starttime-aligned A1 yaw without trace or RMSE tuning.
- BY3A6 may state that BY3 normal-only rerun after initatt repair completed, but yaw still fails and likely needs a separate yaw-gate/A1-dynamics review; `ready_for_BY3_degradation_matrix_planning=false`, `yaw_degradation_claims=false`, and `ready_for_paper_claims=false`.
- BY3A7 may state that A1_dual_diff remains the mainline short-baseline yaw source with dynamic-quality caution and source-quality-only invalid epoch criteria.
- BY3A7 may state that BY3 Go2 IMU preprocessing estimated gyro bias from a moving segment after selected Go2 start and that the BY3A7-local repair uses pre-motion source gyro bias while preserving FLU-to-FRD conversion, A1 yaw source, fixed_1p5 yaw_std, and yaw gate thresholds.
- BY3A7 may state that BY3 normal-only rerun after the IMU preprocessing repair completed and dual-yaw yaw sanity passed: LegSA_full_EKF yaw RMSE is about 5.26 deg and final_v23_dual_antenna_EKF yaw RMSE is about 4.30 deg.
- BY3A7 may set `ready_for_BY3_degradation_matrix_planning=true` only with `scope=full_after_human_review`; `ready_for_paper_claims=false` remains mandatory.

## Not Allowed Current Claims

- Do not claim additional N9B2 execution is approved unless a later human-defined follow-up authorizes it.
- Do not claim full monolithic N9B2 was run.
- Do not claim paper-level performance improvement.
- Do not claim outperforming final_v23.
- Do not claim Go2 position, velocity, contact, or yaw as truth.
- Do not claim FGO replaces EKF.
- Do not claim trace/final_v23 tuning.
- Do not claim source observations are algorithm estimates.
- Do not claim placeholder plots are real figures.
- Do not claim clean feedback can be reused for degraded cases.
- Do not claim `B_gnss_downsample_2Hz` is valid.
- Do not use superseded rows for active conclusions.
- Do not use `historical_nominal_none` for current claims.
- Do not treat N9C0 readiness for N9C1 as paper-claim authorization.
- Do not authorize PR #52 merge/tag without explicit human approval.
- Do not relabel `LegSA_full_EKF` as active nine-factor FGO.
- Do not claim provider/update counts or historical candidate no-feedback rows are current active nine-factor FGO residual/cost evidence.
- Do not run representative active-nine-factor FGO before human-approved implementation review.
- Do not run representative degradation or full-matrix validation during N9G1B.
- Do not claim N9G1B produced active nine-factor FGO residual/Jacobian/cost rows.
- Do not claim N9G1C-E produced active nine-factor FGO residual/Jacobian/cost rows.
- Do not claim N9G1E normal smoke passed.
- Do not start N9G2 until provider/factor model and active backend gaps are fixed and reviewed.
- Do not treat PR #52 head sync as merge, closure, tag, or paper-claim authorization.
- Do not claim BY3 paper-ready generalization, final_v23 outperformance, or degradation/full-matrix completion from BY3A3 normal-only metrics.
- Do not claim BY3A4A repaired BY3 yaw metrics, BY3 degradation readiness, paper-ready BY3 generalization, or final_v23 outperformance.
- Do not choose or describe BY3/BY2 lateral +90/-90 dual-antenna yaw conversion by yaw RMSE minimization alone.
- Do not claim BY3A4C repaired BY3 yaw metrics or authorized yaw degradation planning.
- Do not treat BY3A4C position/up-only planning readiness as yaw generalization or paper-ready BY3 evidence.
- Do not use BY3A4C diagnostic yaw-source figures as a substitute for a confirmed BY3 yaw truth/reference mapping.
- Do not treat BY3A5 HDT as mainline BY3 solver yaw input.
- Do not use GNSS status long-baseline `rel_pos_n/e/d` as BY3 dual-antenna yaw.
- Do not treat BY3A5B A1 input repair as repaired official BY3 yaw-reference metrics, BY3 yaw degradation readiness, or paper-ready evidence.
- Do not treat BY3A6 initatt repair as repaired BY3 yaw, BY3 degradation readiness, or paper-ready evidence.
- Do not treat BY3A7 normal-only yaw sanity as paper-ready evidence, final_v23 outperformance, completed BY3 degradation/full-matrix execution, or PR #52 merge/tag/closure authorization.
- Do not turn BY3A7 A1 quality masks into RMSE-selected bad-epoch deletion.
- Do not claim BY3 degradation execution until a later explicitly approved BY3 degradation stage runs.
- Do not treat BY3 receiver `imu-data.csv` as Go2 body IMU.
- Do not treat BY3 candidate input files as solver success, evaluation evidence, or paper evidence.
- Do not treat BY3A1 repaired input files or materialized Go2 prior files as BY3 normal solver/evaluator success, metric evidence, or paper evidence.
- Do not treat BY3A2 Raw Doppler provider materialization or baseline handoff configs as BY3 normal solver/evaluator success, metric evidence, or paper evidence.
- Do not treat BY3A3 normal-only runtime evidence as complete nine-factor FGO evidence, LegSA_9F_FGO_EKF evidence, or paper performance evidence.
- Do not treat BY2 text-summary/archive reorganization as new BY2 execution or new performance evidence.

## Paper Boundary

Paper-grade claims require source lineage, frame/time alignment, metric sanity, semantic sanity, same-case feedback validation for feedback cases, N9C visual review, N9D claim-boundary review, and explicit human approval. N9F design readiness is not paper-claim authorization.
