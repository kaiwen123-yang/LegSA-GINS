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

## Data Aliases

- `<BY2_FIXPOSITION_ROOT>`: BY2 Fixposition / GNSS receiver data root.
- `<GNSS1_RAW>`, `<GNSS2_RAW>`: dual antenna raw GNSS files.
- `<GNSS1_STATUS>`, `<GNSS2_STATUS>`: GNSS status files.
- `<TRACE_TRUTH>`: trace reference, evaluation-only.
- `<FIXPOSITION_IMU_DATA>`, `<FIXPOSITION_IMU_BIASES>`, `<FIXPOSITION_IMU_TEMP>`: receiver IMU diagnostics.
- `<GO2_BODY_IMU_HIGHLEVEL>`: fused Go2 body IMU / high-level source.

## N9B2 Path Lock

N9B2B locked Windows plus WSL aliases and the BY2/N9 runtime alias root. Future BY2/N9 outputs must use `BY2_N9B2_*` aliases in tracked docs and reports.

N9C0 consolidated precheck artifacts are represented in tracked docs as `<N9C0_CONSOLIDATED_PRECHECK_ROOT>`, not as concrete local paths.

Native Ubuntu migration is deferred. The old Chinese output root is read-only historical evidence and must not become the active future output root.

## Local Path File

`docs/codex_context/DATA_PATHS.local.md` may contain real local absolute paths for this machine. It is local-only by default, ignored, and must not be staged or committed unless the user explicitly requests it.

Use `docs/codex_context/DATA_PATHS.template.md` as an alias-only template.
