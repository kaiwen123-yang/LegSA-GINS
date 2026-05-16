# PATH_POLICY.md

Tracked docs should use aliases instead of local absolute paths.

## Core Aliases

- `<WINDOWS_AUDIT_ROOT>`: Windows output audit workspace.
- `<WSL_AUDIT_ROOT>`: WSL path to the Windows audit workspace.
- `<WSL_ALGO_REPO>`: WSL algorithm source repository.
- `<BY2_PLOT_AUDIT_ROOT>`: BY2 plot audit area under the audit workspace.

## Data Aliases

- `<BY2_FIXPOSITION_ROOT>`: BY2 Fixposition / GNSS receiver data root.
- `<GNSS1_RAW>`, `<GNSS2_RAW>`: dual antenna raw GNSS files.
- `<GNSS1_STATUS>`, `<GNSS2_STATUS>`: GNSS status files.
- `<TRACE_TRUTH>`: trace reference, evaluation-only.
- `<FIXPOSITION_IMU_DATA>`, `<FIXPOSITION_IMU_BIASES>`, `<FIXPOSITION_IMU_TEMP>`: receiver IMU diagnostics.
- `<GO2_BODY_IMU_HIGHLEVEL>`: fused Go2 body IMU / high-level source.

## Local Path File

`docs/codex_context/DATA_PATHS.local.md` may contain real local absolute paths for this machine. It is local-only by default and must not be staged or committed unless the user explicitly requests it.

Use `docs/codex_context/DATA_PATHS.template.md` as an alias-only template.
