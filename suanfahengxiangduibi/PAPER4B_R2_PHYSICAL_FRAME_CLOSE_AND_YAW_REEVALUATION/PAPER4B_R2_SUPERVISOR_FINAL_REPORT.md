# PAPER4B_R2 Supervisor Final Report

Final status: `CONDITIONAL_PASS_PHYSICAL_FRAME_CLOSED_METHOD_YAW_PARTIAL`

## 1. Input Evidence Paths

- Installation photo found: `True`
- Fixposition tutorial PDF found: `True`
- STL/STEP mount files found: `True`
- BY2 trace reference found: `True`
- PAPER3F/G/H row-level epoch outputs found and processed: `2160` completed rows.
- PAPER3I diagnostic inputs found but not promoted to case-level body-yaw metrics.

## 2. User Confirmation Intake

The user-confirmed physical facts were recorded verbatim in `01_asset_and_physical_evidence_intake/user_confirmed_physical_frame_statement.md`.

## 3. Official Fixposition Extrinsics

Recorded official Step 5 values:

- GNSS1: x=0.0200, y=-0.1750, z=-0.0200
- GNSS2: x=0.0200, y=+0.1750, z=-0.0200

Machine text extraction from the PDF was not available in this WSL environment; binary probes and the input PDF presence are recorded. The official values are recorded from the user-provided PAPER4B_R2 prompt excerpt.

## 4. STEP/STL Geometry Evidence

STL/STEP files were parsed for lightweight bounding boxes. They support a transverse mounting structure but do not replace the user cable/port confirmation.

## 5. Trace Script Audit

Trace is used only as offline evaluator reference. PAPER4B_R2 uses raw numeric `time` and `yaw`; it does not use `processed_lat`/`processed_lon`, trace online input, or receiver IMU as Go2 body IMU.

## 6. FRAME_POLICY_ACCEPTED

Generated: `05_frame_policy_decision/FRAME_POLICY_ACCEPTED.yaml`.

Physical conclusion:

- GNSS1 is the robot-right antenna.
- GNSS2 is the robot-left antenna.
- GNSS1->GNSS2 points to body +Y_left under Go2 FLU.
- Fixed transform: `body_yaw_NED_deg = wrap360(baseline_heading_NED_deg + 90 deg)`.

## 7. Method Yaw Semantics

PAPER3F/PAPER3G/PAPER3H methods with explicit NED `atan2(E,N)` heading columns were accepted for offline body-yaw reevaluation. PAPER3I Wu/Pavlasek diagnostics remain blocked for case-level body-yaw metrics because they are DD/LOS row diagnostics or summary innovation diagnostics, not baseline-state epoch outputs.

## 8. BY2 Yaw Reevaluation Summary

Completed row-level reevaluations: `2160`.
Blocked/diagnostic rows: `2`.

Top method summaries:

- PAPER3F `P3F_DD06_RTKLIB_MOVING_BASELINE_EXTERNAL_DIAGNOSTIC`: cases=120, mean RMSE=88.117 deg, mean coverage=0.177
- PAPER3G `G01_TEUNISSEN_STANDARD_LAMBDA_FLOAT_FIXED`: cases=120, mean RMSE=95.163 deg, mean coverage=0.095
- PAPER3G `G02_TEUNISSEN_CLAMBDA_QCILS_BACKEND`: cases=120, mean RMSE=95.163 deg, mean coverage=0.095
- PAPER3H `H03_LIU_CWLS_REFINED_SEARCH`: cases=120, mean RMSE=95.163 deg, mean coverage=0.095
- PAPER3H `H01_TEUNISSEN_STANDARD_LAMBDA_HELPER`: cases=120, mean RMSE=95.163 deg, mean coverage=0.095
- PAPER3G `G06_PAVLASEK_TWO_RECEIVER_IEKF_MEASUREMENT_READY`: cases=120, mean RMSE=95.163 deg, mean coverage=0.095
- PAPER3G `G05_WU_PAR_ADOP_CONSTRAINED_AMBIGUITY_MODULE`: cases=120, mean RMSE=95.163 deg, mean coverage=0.095
- PAPER3G `G03_LIU_CWLS_FULLER_WRAPPED_SEARCH`: cases=120, mean RMSE=95.163 deg, mean coverage=0.095

## 9. Figure Render QA

Render QA passed: `True`.
Figures generated in `08_joined_tables_and_figures/` include RMSE bar, family heatmap, case boxplot, frame policy dashboard, and coverage dashboard.

## 10. Export Path

C export root: `<PAPER4B_R2_C_EXPORT_ROOT>`
Repo lightweight export root: `<REPO_ROOT>/suanfahengxiangduibi/PAPER4B_R2_PHYSICAL_FRAME_CLOSE_AND_YAW_REEVALUATION`
WSL runtime root: `<PAPER4B_R2_WSL_RUNTIME_ROOT>`

## 11. Git Status

Commit status is determined after context sync and reviewer check. No push is performed by this stage.

## 12. Claims

Newly allowed claims are listed in `09_claim_boundary_update/allowed_claims_after_R2.md`. Still-forbidden claims are listed in `09_claim_boundary_update/still_forbidden_claims_after_R2.md`.

This stage does not introduce exact reproduction, full faithful external algorithm, universal superiority, final_v23/LegSA_QA superiority, BY3 yaw generalization, or XB severe-GNSS high-precision proof claims.
