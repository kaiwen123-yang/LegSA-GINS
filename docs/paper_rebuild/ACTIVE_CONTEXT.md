# LegSA-GINS Clean Rebuild Active Context

## Identity

- Active program: `CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION`.
- Active case/protocol: `CLEAN1_BY2_CLEAN_NORMAL` / `CLEAN1_BY2_CLEAN_NORMAL_V1`.
- Frozen base commit: `4e6b3f3fa9f50ed91b6c4e250f3d1f75d6725cc6`.
- Active Git line: `stage/clean1-by2-clean-four-method`.
- Active implementation namespace: `src/legsa_gins/paper_rebuild/`.
- Active runner entrypoints: `scripts/paper_rebuild/` only.
- Active raw source: `<RAW_ROOT>`; raw files are immutable.
- Active generated-asset root: `<CLEAN_ROOT>`.
- Historical freeze root: `<LEGACY_FREEZE_ROOT>`; it is provenance/reference material, not active performance evidence.

## Mandatory Reading Order

1. This file.
2. `DATA_ROLES.md`.
3. `METHOD_SCOPE.md`.
4. `EXPERIMENT_PROTOCOL.md`.
5. `LEGACY_DENYLIST.md`.
6. `CLAIM_BOUNDARY.md`.
7. `NEXT_ACTIONS.md`.

## Clean Active Allowlist

Tracked protocol and implementation material may come only from:

- `docs/paper_rebuild/`;
- `configs/paper_rebuild/`, excluding the ignored local path file from Git;
- `scripts/paper_rebuild/`;
- `tests/paper_rebuild/`;
- `src/legsa_gins/paper_rebuild/`;
- maintained shared source explicitly imported by the paper-rebuild runner and recorded by commit SHA.

Active runtime evidence may come only from `<CLEAN_ROOT>` and only when its manifest passes the clean dependency audit. Raw data under `<RAW_ROOT>` are inputs, not algorithm results. Selected specifications and lessons under `<LEGACY_FREEZE_ROOT>` may explain provenance, but no legacy metric, row result, provider payload, NAV, STD, EVAL_NAV, figure, aggregate, or reconstructed summary is active evidence.

## Hard Rules

- Every formal result starts from hash-locked raw data and freshly generated providers.
- Trace is evaluation-only; it cannot select sign, offset, provider, method, threshold, or tuning.
- The lateral antenna vector is GNSS2 minus GNSS1. Baseline heading is not body yaw; the fixed physical transform is applied before wrap-safe residual evaluation.
- Receiver IMU is not Go2 body IMU.
- Go2 position, velocity, yaw, contact, and metadata are not truth. Approved Go2 inputs are weak priors or diagnostic metadata only.
- final_v23 and LegSA outputs are never solver inputs.
- No per-case tuning, output-only correction, or metric-driven epoch deletion is allowed.
- Synthetic and semi-synthetic results must never enter a real-data result table.
- Every runtime manifest records source hashes, provider hashes, provider-generator commit/config hash, data mode, synthetic flags, forbidden-input flags, clean code commit, clean-worktree state, and runtime config hash.
- Old runners may remain for historical reproducibility, but the clean rebuild must not call them.
- There is no active complete nine-factor FGO claim.

## Current Gate

The human explicitly authorized only the CLEAN1 BY2 clean-normal four-method chain. The exact method order is `single_antenna_EKF`, `basic_dual_yaw_EKF`, `strong_dual_yaw_EKF`, and `LegSA_Paper_V1`. Provider generation, solver execution, and offline evaluation are separate read domains.

Formal execution remains fail-closed unless the fresh Raw Doppler lineage, full common window, common 21-state initialization, method-effective flags, and evaluator contracts all pass. The active trace does not itself prove its yaw-frame semantics or a unique identity/transform between its reference point and the solver propagation-IMU state point. No fit, alignment, output inspection, or legacy evidence may close those contracts. If they remain unproven, the terminal decision is `BLOCKED_CLEAN1_EVALUATOR_CONTRACT_FAILED` with zero formal runs and no metrics.

CLEAN1 does not authorize figures, classic-18, the 60x9 matrix, DA03, DA05, another dataset, a merge, a tag, or any next stage.
