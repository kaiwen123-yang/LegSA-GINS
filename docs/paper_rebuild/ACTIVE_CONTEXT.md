# LegSA-GINS Clean Rebuild Active Context

## Identity

- Active program: `STAGE_ID=CLEAN1R2_FINAL_V23_ARCHIVE_PARITY_AND_FOUR_METHOD_REEXECUTION`.
- Parent program: `PARENT_STAGE=CLEAN1_BY2_CLEAN_FOUR_METHOD_EXECUTION`.
- Active case: `CASE_ID=CLEAN1_BY2_CLEAN_NORMAL`.
- Active protocol: recovered exact final_v23 archive parity contract; terminal decision `BLOCKED_CLEAN1R2_EVIDENCE_CONTAMINATION`.
- Retained predecessor protocol: `CLEAN1_BY2_CLEAN_NORMAL_V2_KICK_ALIGNED`; review disposition `SUPERSEDED_FOR_FINAL_V23_PARITY_REVIEW`; `superseded_by=CLEAN1R2_FINAL_V23_PARITY`.
- Frozen base commit: `4e6b3f3fa9f50ed91b6c4e250f3d1f75d6725cc6`.
- Active Git line: `stage/clean1-by2-clean-four-method`.
- Active worktree: existing `worktree://clean1-by2-clean-four-method`, unchanged.
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

The human authorized the bounded CLEAN1R2 chain in this exact fail-closed order:

1. recover the unique exact final_v23 static source, actual runtime configuration, input-generation contract, and evaluator identity from the authorized archive;
2. generate exact final_v23 input freshly from the current hash-locked BY2 raw sources;
3. run one exact archived final_v23 parity anchor with every additional paper module disabled;
4. make the active paper-rebuild port pass the same final_v23 parity contract;
5. complete tests/build/review and freeze the parity-restored code commit;
6. regenerate the provider at that code freeze and run the four methods under one common recovered contract, in order: `single_antenna_EKF`, `basic_dual_yaw_EKF`, `strong_dual_yaw_EKF`, and `LegSA_Paper_V1`;
7. open trace only for offline evaluation after all four fresh outputs are sealed and hashed.

The four-method execution is forbidden until both the exact archived fresh-run parity and active-port parity gates pass. Historical archive inputs and outputs are parity-reference material only and can never become current solver input or current performance evidence. Raw 22/22 integrity, fresh provider lineage, forbidden-input flags, method-effective counters, and evaluator identity remain fail-closed gates.

Archive recovery closed the static tag source, same-run runtime configuration,
input-builder behavior, and evaluator identity.  It also proved that the linked
E001 `nominal_none` input is semisynthetic: a separate command argument injects
1.5 degree Gaussian yaw noise with seed 42, and the input builder reads trace
during provider generation.  This conflicts with the clean real-data contract.
Therefore no fresh CLEAN1R2 provider, exact solver run, active-port parity run,
four-method run, or current trace evaluation was started.

Continuation requires an explicit human choice between a semisynthetic
diagnostic historical reproduction, which cannot be clean real-data evidence,
and a clean no-injection/no-online-trace execution, which cannot claim strict
archived E001 input parity.  Until that choice, the parity and four-method gates
remain closed.

No start/end window, initialization, receiver-velocity policy, yaw standard-deviation interpretation, scheme-C setting, or evaluator behavior is frozen by this governance update. Each value must be recovered from the archive under the stated source-priority rules; current CLEAN1R1C values must not fill an archive evidence gap.

CLEAN1R2 does not authorize figures, classic-18, D01-D60, the 60x9 matrix, DA03, DA05, BY3, XB, PG, selected FGO feedback, active/complete nine-factor FGO, QM, QA, contact/FK factors, a merge, a tag, or any next stage.
