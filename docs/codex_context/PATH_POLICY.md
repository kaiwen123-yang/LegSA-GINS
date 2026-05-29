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
- `<BY3_FULL_MATRIX_ROOT>`: placeholder BY3 full-matrix root; not authorized for degradation execution in BY3A0_TO_BY3E.
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

## N9B2 Path Lock

N9B2B locked Windows plus WSL aliases and the BY2/N9 runtime alias root. Future BY2/N9 outputs must use `BY2_N9B2_*` aliases in tracked docs and reports.

N9C0 consolidated precheck artifacts are represented in tracked docs as `<N9C0_CONSOLIDATED_PRECHECK_ROOT>`, not as concrete local paths.

Native Ubuntu migration is deferred. The old Chinese output root is read-only historical evidence and must not become the active future output root.

## BY3 Path Lock

BY3A0 locked `<BY3_OUTPUT_ROOT>` for BY3 generalization outputs. BY3A0_TO_BY3E artifacts are represented in tracked docs as `<BY3_STAGE_ROOT>`. BY3A4A artifacts are represented as `<BY3A4A_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3A4A_YAW_REPAIR`. BY3A4C artifacts are represented as `<BY3A4C_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3A4C_YAW_HISTORY_RECONSTRUCTION`. BY3A5B artifacts are represented as `<BY3A5B_STAGE_ROOT>` and `<BY3_FULL_MATRIX_ROOT>/BY3A5B_A1_DUAL_DIFF_REPAIR`. BY3 degradation planning after BY3A5B is position/up-only until a valid BY3 yaw reference mapping is confirmed.

BY3 tracked docs must refer to receiver data through `<BY3_RECEIVER_ROOT>` and Go2 body/high-level data through `<BY3_GO2_BODY_SOURCE>`. The BY3 receiver `imu-data.csv` is diagnostic only and must not be documented as the Go2 body IMU source.

BY2 degradation text summaries and reorganized figures are represented by `<BY2_DEGRADATION_ARCHIVE_ROOT>`. That archive is copy-only runtime evidence and must not be staged by default.

## Local Path File

`docs/codex_context/DATA_PATHS.local.md` may contain real local absolute paths for this machine. It is local-only by default, ignored, and must not be staged or committed unless the user explicitly requests it.

Use `docs/codex_context/DATA_PATHS.template.md` as an alias-only template.
