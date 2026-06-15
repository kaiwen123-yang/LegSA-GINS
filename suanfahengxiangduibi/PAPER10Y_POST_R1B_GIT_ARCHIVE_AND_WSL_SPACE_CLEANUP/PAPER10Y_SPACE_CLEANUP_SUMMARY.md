# PAPER10Y Archive And Space Cleanup Summary

## Archive Packages

| Package | Source GiB | Archive GiB | SHA256 | Verified |
|---|---:|---:|---|---|
| `PAPER10C_R1_completed_runtime_archive.tar.xz` | 39.18 | 10.33 | `523753b06ecae59e7e5eb5c0792e68aaf07a84f28af36018ba2c03ea046ffa92` | PASS |
| `PAPER10C_go2_evidence_runtime_archive.tar.xz` | 23.17 | 6.43 | `cdde8e82cfab0ac4c52a609ed907cbd57a42f5c032ec19253cb197674d7f2352` | PASS |
| `PAPER10C_R1B_final_runtime_snapshot.tar.xz` | 0.06 | 0.01 | `862edb728b21945028f143e5d7e1a9ddfb9daad6de38fc1782c434183f827637` | PASS |
| `PAPER10_recent_maintenance_runtime_archive.tar.xz` | 0.01 | 0.00 | `97b26d419f737d144c1a5c0c8837305c0a0a30a057fa77fcff4bf248404f64ca` | PASS |
| `PAPER10_completed_worktrees_recent.tar.xz` | 0.02 | 0.00 | `68daa27e6cf2ccceea966c293ece35e1c901d2d596c5a5f463694d99f7b45162` | PASS |

## Deleted Verified WSL Sources

- `<WSL_PREFLIGHT_ROOT>/PAPER10C_R1_BY3_GO2_PROVIDER_AND_READINESS_LSIM_CLOSURE` via `rm -rf verified runtime dir`.
- `<WSL_PREFLIGHT_ROOT>/PAPER10C_GO2_HIGH_LEVEL_PRIOR_EVIDENCE_FREEZE` via `rm -rf verified runtime dir`.
- `<PAPER10C_R1B_STAGE_ROOT>` via `rm -rf verified runtime dir`.
- `<WSL_PREFLIGHT_ROOT>/PAPER10B_R2B_ENV_REPAIR_RESUME_RUNNER_PATCH_AND_GIT_HYGIENE` via `rm -rf verified runtime dir`.
- `<WSL_PREFLIGHT_ROOT>/PAPER10B_R2C_REPAIR_EXISTING_DEFAULT_PYTHON3_AND_REINSTALL_CONDA_ONLY` via `rm -rf verified runtime dir`.
- `<WSL_PREFLIGHT_ROOT>/PAPER10X_GIT_CONTEXT_CLEANUP_AND_COMMIT` via `rm -rf verified runtime dir`.
- `<WSL_PREFLIGHT_ROOT>/PAPER10C_R1A_RESUME_INTERRUPTED_GO2_BY3_MATRIX_AND_COMPLETE_STAGE` via `rm -rf verified runtime dir`.
- `<LEGSA_WORKTREE_ROOT>/PAPER10B_R2B_ENV_REPAIR_RESUME_RUNNER_PATCH_AND_GIT_HYGIENE` via `git worktree remove verified clean worktree`.
- `<LEGSA_WORKTREE_ROOT>/PAPER10B_R2C_REPAIR_EXISTING_DEFAULT_PYTHON3_AND_REINSTALL_CONDA_ONLY` via `git worktree remove verified clean worktree`.

## Skipped Sources

Skipped entries are recorded in `07_safe_delete/PAPER10Y_DELETE_SKIPPED_WITH_REASON.csv`. They were not deleted because they were archive-only keep-source, active/current, too small, or unknown/not selected in this low-risk pass.

## Space Result

- Released: 67121369088 bytes (62.51 GiB).
- Current WSL root: `/dev/sdd` about 820G available after cleanup.
- Current Windows C/E/G free from PowerShell is recorded in `00_status_check` and this report's final status block.
