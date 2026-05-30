# PATH_POLICY.md

Tracked docs must use aliases instead of local absolute paths.

## Core Aliases

- `<WINDOWS_AUDIT_ROOT>`: Windows audit workspace.
- `<WSL_AUDIT_ROOT>`: WSL path to the Windows audit workspace.
- `<WSL_ALGO_REPO>`: WSL algorithm source repository.
- `<BY2_N9B2_WINDOWS_ROOT>`: locked Windows root for future BY2/N9B2 outputs and audit reports.
- `<BY2_N9B2_WSL_ROOT>`: locked WSL view of the BY2/N9B2 output root.
- `<BY2_N9B2_FULL_MATRIX_ROOT>`: locked full-matrix output root alias.
- `<BY2_N9B2_DEFERRED_EXT4_ROOT>`: deferred native Ubuntu/ext4 output root alias.
- `<N9C0_CONSOLIDATED_PRECHECK_ROOT>`: N9C0 consolidated precheck root under `<BY2_N9B2_FULL_MATRIX_ROOT>`.
- `<FINALV23_EXTERNAL_BASELINE_ROOT>`: final_v23 external baseline runtime root under `<BY2_N9B2_FULL_MATRIX_ROOT>`.
- `<BY3_OUTPUT_ROOT>`: locked Windows root for BY3 generalization outputs.
- `<BY3_STAGE_ROOT>`: BY3A0_TO_BY3E stage output root under `<BY3_OUTPUT_ROOT>`.
- `<BY3A4A_STAGE_ROOT>`: BY3A4A lateral yaw repair and context-memory-lock output root under `<BY3_OUTPUT_ROOT>`.
- `<BY3A4C_STAGE_ROOT>`: BY3A4C git-history yaw-reference reconstruction and visual-validation output root under `<BY3_OUTPUT_ROOT>`.
- `<BY3A5B_STAGE_ROOT>`: BY3A5B A1 dual-diff yaw-input repair output root under `<BY3_OUTPUT_ROOT>`.
- `<BY3A6_STAGE_ROOT>`: BY3A6 trace-truth/initatt/gate forensic output root under `<BY3_OUTPUT_ROOT>`.
- `<BY3A7_STAGE_ROOT>`: BY3A7 A1 yaw dynamic-quality, IMU sign-axis, and yaw-gate repair output root under `<BY3_OUTPUT_ROOT>`.
- `<BY3A8_STAGE_ROOT>`: BY3A8 yaw error-budget and safe-repair output root under `<BY3_OUTPUT_ROOT>`.
- `<BY3B_STAGE_ROOT>`: BY3B position/up degradation planning with diagnostic yaw output root under `<BY3_OUTPUT_ROOT>`.
- `<BY3C_STAGE_ROOT>`: BY3C approved Batch0-Batch3 position/up degradation execution output root under `<BY3_OUTPUT_ROOT>`.
- `<BY3_FULL_MATRIX_ROOT>`: BY3 full-matrix runtime root; after BY3C it contains approved Batch0-Batch3 execution artifacts under `BY3C_POSITION_UP_DEGRADATION_EXECUTION`, not a full monolithic BY3 matrix.
- `<BY3C1_STAGE_ROOT>`: BY3C1/BY3Y1 position/up generalization review and yaw diagnostic explanation root under `<BY3_OUTPUT_ROOT>`.
- `<BY3C1_REVIEW_PACKAGE_ROOT>`: BY3C1 review package root under `<BY3_FULL_MATRIX_ROOT>`.
- `<BY3Y1_STAGE_ROOT>`: BY3Y1 yaw diagnostic package root under `<BY3_FULL_MATRIX_ROOT>`.
- `<BY3C1_EXPORT_CLEAN_ROOT>`: BY3C1 export-clean generalization package root under `<BY3_OUTPUT_ROOT>`.
- `<GEN1_STAGE_ROOT>`: GEN1 BY2-BY3 generalization report and BY3 figure-organization root under `<BY3_OUTPUT_ROOT>`.
- `<BY3_FIGURE_SUMMARY_ROOT>`: copy-only organized BY3 figure summary root under `<BY3_OUTPUT_ROOT>`.
- `<GEN1_EXPORT_CLEAN_ROOT>`: GEN1 export-clean BY2-BY3 generalization package root under `<BY3_OUTPUT_ROOT>`.
- `<XB1_OUTPUT_ROOT>`: locked Windows root for XB1 / PG1 poor-GNSS generalization outputs.
- `<XB1_STAGE_ROOT>`: XB1A0_TO_XB1E poor-GNSS stage output root under `<XB1_OUTPUT_ROOT>`.
- `<XB1A1_STAGE_ROOT>`: XB1A1 blocker-triage and normal-gate repair stage output root under `<XB1_OUTPUT_ROOT>`.
- `<XB1A2_STAGE_ROOT>`: XB1A2 A1 relpos-difference re-audit stage output root under `<XB1_OUTPUT_ROOT>`.
- `<XB1_FULL_MATRIX_ROOT>`: XB1 normal-bootstrap runtime root family; current stage used only `XB1A_NORMAL_BOOTSTRAP`, not a degradation matrix.
- `<XB1A1_NORMAL_GATE_ROOT>`: XB1A1 normal-gate runtime material under `<XB1_FULL_MATRIX_ROOT>`.
- `<XB1A2_RELPOS_DIFF_REPAIR_ROOT>`: XB1A2 relpos-difference repair runtime material under `<XB1_FULL_MATRIX_ROOT>`.
- `<XB1_EXPORT_CLEAN_ROOT>`: XB1 export-clean package root under `<XB1_OUTPUT_ROOT>`.
- `<PG_MULTI_REVIEW_ROOT>`: locked Windows root for PG multi-repeat poor-GNSS review outputs.
- `<PG_MULTI_A0_STAGE_ROOT>`: PG_MULTI_A0 review-only stage output root under `<PG_MULTI_REVIEW_ROOT>`.
- `<PG_QA0_STAGE_ROOT>`: PG_QA0 quality-aware fallback design package root under `<PG_MULTI_REVIEW_ROOT>`.
- `<BY2_DEGRADATION_ARCHIVE_ROOT>`: copy-only BY2 degradation figure/text archive root.
- `<BY2_DEGRADATION_TEXT_SUMMARY_ROOT>`: BY2 degradation text-summary root containing the seed0-9 explanation index.

## Data Aliases

- `<BY2_FIXPOSITION_ROOT>`: BY2 Fixposition / GNSS receiver data root.
- `<GNSS1_RAW>`, `<GNSS2_RAW>`: dual antenna raw GNSS files.
- `<GNSS1_STATUS>`, `<GNSS2_STATUS>`: GNSS status files.
- `<TRACE_TRUTH>`: trace reference, evaluation-only.
- `<FIXPOSITION_IMU_DATA>`, `<FIXPOSITION_IMU_BIASES>`, `<FIXPOSITION_IMU_TEMP>`: receiver IMU diagnostics.
- `<GO2_BODY_IMU_HIGHLEVEL>`: fused Go2 body IMU / high-level source.
- `<BY3_RECEIVER_ROOT>`: BY3 Fixposition receiver source root.
- `<BY3_GO2_BODY_SOURCE>`: BY3 Go2 body/high-level `by3.txt` source.
- `<BY3_TRACE_TRUTH>`: BY3 trace reference, evaluation-only.
- `<BY3_FIXPOSITION_IMU_DATA>`: BY3 receiver IMU diagnostics only, not Go2 body IMU.
- `<XB1_RECEIVER_ROOT>`: XB1 Fixposition receiver source root.
- `<XB1_BODY_SOURCE>`: XB1 robot body/high-level `xb1.txt` source and body-IMU source.
- `<XB1_TRACE_TRUTH>`: XB1 trace reference, evaluation-only.
- `<XB1_FIXPOSITION_IMU_DATA>`: XB1 receiver IMU diagnostics only, not body IMU.
- `<PG2_XB2_RECEIVER_ROOT>`, `<PG3_XB3_RECEIVER_ROOT>`, `<PG4_XB4_RECEIVER_ROOT>`: PG2/PG3/PG4 poor-GNSS Fixposition receiver roots.
- `<PG2_XB2_BODY_SOURCE>`, `<PG3_XB3_BODY_SOURCE>`, `<PG4_XB4_BODY_SOURCE>`: user-locked PG2/PG3/PG4 body/high-level sources and body-IMU sources.

## N9B2 Path Lock

N9B2B locked Windows plus WSL aliases and the BY2/N9 runtime alias root. Future BY2/N9 outputs must use `BY2_N9B2_*` aliases in tracked docs and reports.

N9C0 consolidated precheck artifacts are represented in tracked docs as `<N9C0_CONSOLIDATED_PRECHECK_ROOT>`, not as concrete local paths.

Native Ubuntu migration is deferred. The old Chinese output root is read-only historical evidence and must not become the active future output root.

## BY3 Path Lock

BY3A0 locked `<BY3_OUTPUT_ROOT>` for BY3 generalization outputs. BY3A0_TO_BY3E artifacts are represented in tracked docs as `<BY3_STAGE_ROOT>`. BY3A4A artifacts are represented as `<BY3A4A_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3A4A_YAW_REPAIR`. BY3A4C artifacts are represented as `<BY3A4C_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3A4C_YAW_HISTORY_RECONSTRUCTION`. BY3A5B artifacts are represented as `<BY3A5B_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3A5B_A1_DUAL_DIFF_REPAIR`. BY3A6 artifacts are represented as `<BY3A6_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3A6_TRACE_TRUTH_INITATT_GATE_FORENSIC`. BY3A7 artifacts are represented as `<BY3A7_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3A7_YAW_DYNAMIC_GATE_REPAIR`. BY3A8 artifacts are represented as `<BY3A8_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3A8_YAW_ERROR_BUDGET_REPAIR`. BY3B artifacts are represented as `<BY3B_STAGE_ROOT>` and planning under `<BY3_FULL_MATRIX_ROOT>/BY3B_POSITION_UP_DEGRADATION_MATRIX`. BY3C artifacts are represented as `<BY3C_STAGE_ROOT>` and approved Batch0-Batch3 execution under `<BY3_FULL_MATRIX_ROOT>/BY3C_POSITION_UP_DEGRADATION_EXECUTION`. BY3C1/BY3Y1 artifacts are represented as `<BY3C1_STAGE_ROOT>`, `<BY3C1_REVIEW_PACKAGE_ROOT>`, `<BY3Y1_STAGE_ROOT>`, and `<BY3C1_EXPORT_CLEAN_ROOT>`. GEN1 artifacts are represented as `<GEN1_STAGE_ROOT>`, `<BY3_FIGURE_SUMMARY_ROOT>`, and `<GEN1_EXPORT_CLEAN_ROOT>`. BY3 work after GEN1 remains position/up primary with diagnostic yaw unless a later human review explicitly broadens yaw scope.

BY3 tracked docs must refer to receiver data through `<BY3_RECEIVER_ROOT>` and Go2 body/high-level data through `<BY3_GO2_BODY_SOURCE>`. The BY3 receiver `imu-data.csv` is diagnostic only and must not be documented as the Go2 body IMU source.

BY2 degradation text summaries and reorganized figures are represented by `<BY2_DEGRADATION_ARCHIVE_ROOT>`. That archive is copy-only runtime evidence and must not be staged by default.

## XB1 Path Lock

XB1A0_TO_XB1E locked XB1 / PG1 poor-GNSS outputs under `<XB1_OUTPUT_ROOT>`. Runtime reports and quality figures are represented by `<XB1_STAGE_ROOT>`, normal-bootstrap runtime material by `<XB1_FULL_MATRIX_ROOT>/XB1A_NORMAL_BOOTSTRAP`, and export-clean material by `<XB1_EXPORT_CLEAN_ROOT>`. XB1A1 blocker-triage and normal-gate repair outputs are represented by `<XB1A1_STAGE_ROOT>` and `<XB1A1_NORMAL_GATE_ROOT>`. XB1A2 A1 relpos-difference re-audit outputs are represented by `<XB1A2_STAGE_ROOT>` and `<XB1A2_RELPOS_DIFF_REPAIR_ROOT>`.

XB1 tracked docs must refer to receiver data through `<XB1_RECEIVER_ROOT>` and body/high-level data through `<XB1_BODY_SOURCE>`. The XB1 receiver `imu-data.csv` is diagnostic only and must not be documented as the robot body IMU source. After XB1A2, Raw Doppler provider materialization is repaired, but dual-yaw normal solvers remain blocked/not applicable because both the BY2 status relpos-difference candidate and the BY3A5B absolute-position candidate are nonphysical for XB1. A valid A1 source or a later human-approved separate branch is required before dual-yaw runs.

## PG Multi-Repeat Poor-GNSS Path Lock

PG_MULTI_A0 outputs are represented in tracked docs by `<PG_MULTI_A0_STAGE_ROOT>` under `<PG_MULTI_REVIEW_ROOT>`. PG_QA0 design outputs are represented by `<PG_QA0_STAGE_ROOT>` under `<PG_MULTI_REVIEW_ROOT>`. PG2/PG3/PG4 tracked docs must refer to receiver data and body/high-level data only through the `PG*_XB*` aliases. The PG2/PG3/PG4 receiver `imu-data.csv` files are diagnostic only and must not be documented as body IMU sources.

PG_MULTI_A0 classified PG1-PG4 as quality-aware branch candidates because all available relpos-diff A1 audits are invalid/nonphysical. This path lock does not authorize solver/evaluator execution, frozen dual-yaw mainline normal runs, quality-aware execution, degradation, retuning, or paper claims.

PG_QA0 is design-only. It does not authorize implementation, solver/evaluator execution, degraded-input generation, random-array generation, retuning, or paper claims. Export-clean QA0 material must use aliases only and must not contain local absolute paths.

## Local Path File

`docs/codex_context/DATA_PATHS.local.md` may contain real local absolute paths for this machine. It is local-only by default, ignored, and must not be staged or committed unless the user explicitly requests it.

Use `docs/codex_context/DATA_PATHS.template.md` as an alias-only template.
