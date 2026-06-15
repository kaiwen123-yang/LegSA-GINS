# PAPER10C_R1A Next Stage Instructions

Recommended next stage: `PAPER10C_R1B_CLEAR_SPACE_AND_RUN_MISSING_ONLY_GO2_BY3_ROWS`, or move directly to `PAPER10B2_MULTI_STATE_QUALITY_MANAGEMENT_CLOSURE` only if the human accepts the incomplete BY3 Go2 matrix as sufficient for planning.

Before any runner:

1. Free Windows E so `E free >= 50GB`; do not use G for new outputs.
2. Re-run process and space gates.
3. Quarantine the 8 partial/corrupted rows listed in `PAPER10C_R1A_QUARANTINE_INDEX.csv`.
4. Run only rows marked `RERUN_MISSING_ONLY`, `RERUN_PARTIAL_OR_CORRUPTED`, or `RERUN_FAILED_WITH_PROOF` using the R1A wrapper.
5. Do not call the original `by3-full` command directly.
6. Do not push.
