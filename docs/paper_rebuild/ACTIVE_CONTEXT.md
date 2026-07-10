# LegSA-GINS Clean Rebuild Active Context

## Identity

- Active program: `PAPER10_CLEAN0_REPOSITORY_LEGACY_FREEZE_DEPENDENCY_DECOUPLING_AND_HARD_RESET`.
- Active Git line: `paper-rebuild/202607`.
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

`PAPER10_CLEAN0` established the new context, raw hash lock, independent runner, reproducible BY2 clean smoke, guarded legacy deletion, and GPT context export. `CLEAN1` must not start without explicit human approval. No performance or paper claim is authorized by bootstrap completion alone.
