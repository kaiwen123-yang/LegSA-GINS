# LegSA-GINS Clean Rebuild Active Context

## Identity

- Active program: `STAGE_ID=CLEAN3R2_MATH_REPAIR_COUNTER_CONTRACT_ROUTING_REPAIR_AND_S3_RESUME`.
- Base main commit: `9f9727b74f5195141523ab570380cc35006f3d18`.
- Active Git branch: `stage/clean3-math-repair`.
- Reviewed S2 math-repair commit: `0d8cc2bdccfd89b236ab4badeef9db5344dcf4d3`.
- Reviewed S2 math-repair `cpp/` tree identity at that commit: `a3716d22acf95fb1e6028ae82acb2ae73e138bfc`. This is S2 math-tree provenance, not the final S3 execution `cpp/` tree.
- CLEAN3R2 code freeze: `8dd620ea6d9645b946a503275ddbf04d66c3baa2`.
- CLEAN3R2 runner freeze: `5209b6afeeb2b2a0ad99e640ffe50f8dd3b0c909`.
- CLEAN3R2 authorization document SHA-256: `eb267045d32af7ae407129b8b53fb6f4c8ed8a6dd75b7889a5a0fb53c3223237`.
- Active implementation namespace: `src/legsa_gins/paper_rebuild/`, invoked only through `scripts/paper_rebuild/`.
- Active raw source: `<RAW_ROOT>`; raw files are immutable.
- Active generated-asset root: `<CLEAN_ROOT>`.
- Historical freeze root: `<LEGACY_FREEZE_ROOT>`; it is provenance/reference material, never active performance evidence.
- `ready_for_paper_claims=false`.

## Mandatory Reading Order

1. This file.
2. `DATA_ROLES.md`.
3. `METHOD_SCOPE.md`.
4. `EXPERIMENT_PROTOCOL.md`.
5. `LEGACY_DENYLIST.md`.
6. `CLAIM_BOUNDARY.md`.
7. `NEXT_ACTIONS.md`.

## Current Gate

- S1 read-only inventory and human scope approval: complete.
- S2 repairs A/B/E1, focused tests, Release build, full `tests/paper_rebuild`, and read-only reviewer recheck: complete and reviewer-approved.
- Final S2/C1b verified test result: `253 passed, 3 skipped`.
- The old CLEAN3 supervisor terminal remains `FAILED_TECHNICAL_S3_AB0000_FORMAL_COUNTER_CONTRACT_UNROUTED`; its original S3 attempt terminal is `FAILED_TECHNICAL_SOLVER_EXECUTION` and its byte parity is `NOT_EVALUATED`.
- Human authorization approved the non-overwriting CLEAN3R2 attempt. The exact counter-routing repair, guarded stage transport, T1–T4, loader bypass regression, Release build, and full `tests/paper_rebuild` validation are reviewer-approved at the new code/runner freeze.
- CLEAN3R2 consumed its sole authorized S3 attempt and terminated `FAILED_TECHNICAL_SOLVER_MANIFEST_CONTRACT`; formal byte parity is `NOT_EVALUATED` and `retry_count=0`.
- The loader assigned `clean3_s3_ab0000_parity_solver`, but `PortRuntime::runFromConfig` overwrote the role for the formal non-CLEAN2R2A stage with `clean1_formal_four_method_solver`; the runner correctly rejected the persisted manifest role.
- `ready_for_S4=false`; `ready_for_paper_claims=false`; evaluator, evaluation trace, performance metrics, S4, provider regeneration, retry, rebind, and Canonical-541 remain unauthorized.

The old S3 execution used C1b `e28899156b03b32d3840476bf57ac01807494086`, C2b/execution HEAD `3110131cbbb64caff71a4e493a0b64365e6fb936`, and final `cpp/` tree `40baa12045d6100e3342fd92a01079d253705a45`. Configure/build succeeded, but the solver failed before `writeAll`: the runtime config correctly selected CLEAN3/AB0000 while `port_runtime.cpp::validateFormalRuntimeCounters` routed its AB counter contract only for CLEAN2R2A, so `counters_match` became false unconditionally. This was a technical routing failure, not an observed mathematical parity mismatch. No NAV, STD, run manifest, outer manifest, output seal, or byte comparison exists; old-attempt parity therefore remains `NOT_EVALUATED`. CLEAN3R2 preserves that attempt and uses a new stage root.

The CLEAN3R2 solver completed with the valid AB0000 counter pattern, but the provenance-role mismatch stopped the runner before formal ledger persistence, manifest post-validation, sealing, and stream comparison. The unsealed NAV/STD hashes equal the locked anchors; they cannot be promoted to parity evidence. The formal ledger, seal, and outer manifest are absent, all 34 immutable roles were unchanged, and no evaluator or reference trace was used. Any repair or new attempt requires separate human approval, a new non-overwriting identity, and a new freeze/authorization chain.

## Inherited Locked Identities

- Full `RAW_FILE_HASH_LOCK.csv` SHA-256: `f6e5d7965d17857e5b4a846501883f4675f2331a1164fab3de9e5ba9470f1ad7`.
- BY2 22-row subset `BY2_HASH_LOCK.csv` SHA-256: `7103880ff53eb195c7d9acdbb87292a7be20e4a58b764da29f848e80a84ecb6c`; all 22 BY2 files were previously verified without mutation.
- IMU provider SHA-256: `a46fe2b50a5a99d550392f42e3952c871a7562c6d5625ea1b377691009ab643b`.
- GNSS provider SHA-256: `f4070ba795825cc243402e4acb551c62c6aad109e7040582bf57781226420e22`.
- Raw Doppler provider full-file SHA-256: `847d6c0ed6c28c59c661b07d59707faf76c3a5adb2b45fac9802a190b8b00fc4`.
- Go2 roll/pitch provider SHA-256: `2329770b8e9bc61c02fbf943e2e5fd9ea233d6fd8a3550f7a22410a536155c7a`.
- Go2 horizontal-velocity provider SHA-256: `f390c8e51f1bec1162c0f6c628ebbcd0449923cfbf9211bebb36004dc2b2aab0`.
- Offline evaluator identity SHA-256: `aa0492482b6467cdd701bc8882aca11c4170bbe2e7c6bb5f932679dc204978da`.
- Raw Doppler provider semantics: GNSS1 RAWX/SFRBX observation-derived velocity; GNSS2 and body-center velocity are not the provider source.

These are inherited identities, not authorization to regenerate providers or execute the evaluator. Before any later authorized evaluation, the evaluator file must be resolved and verified against its locked hash. Any hash or lineage mismatch is fail-closed.

## Clean Active Allowlist

Tracked active material may come only from:

- `docs/paper_rebuild/`;
- `configs/paper_rebuild/`, excluding ignored local path configuration from Git;
- `scripts/paper_rebuild/`;
- `tests/paper_rebuild/`;
- `src/legsa_gins/paper_rebuild/`;
- maintained shared source explicitly imported by the clean runner and recorded by commit SHA;
- the exact C++ repair and manifest-transport paths approved for CLEAN3.

Active runtime evidence may come only from `<CLEAN_ROOT>` and only when its manifest and dependency audit pass. Raw inputs under `<RAW_ROOT>` are not algorithm results. No legacy metric, row result, provider payload, NAV, STD, EVAL_NAV, figure, aggregate, or reconstructed summary may become active CLEAN3 evidence.

## Hard Rules

- Every formal result starts from hash-locked raw data and approved, hash-locked fresh providers.
- Trace is evaluation-only; it cannot select sign, offset, provider, method, threshold, tuning, feedback, or correction.
- GNSS2 minus GNSS1 is the locked lateral antenna vector. Baseline heading is not body yaw; the fixed physical transform and wrap-safe residual are mandatory.
- Receiver IMU is not Go2 body IMU.
- Go2 position, velocity, yaw, contact, foot, mode, gait, and metadata are weak-prior or diagnostic sources only, never truth.
- Raw Doppler is an observation, not an algorithm estimate or truth.
- final_v23 and LegSA outputs are never solver inputs.
- Per-case tuning, output substitution, direct NAV overwrite, output-only correction, and metric-driven epoch deletion are forbidden.
- Synthetic or semi-synthetic results must never enter a real-data result table.
- Every clean manifest must record data mode, raw/provider hashes, synthetic flags, forbidden-input flags, code commit, and config hash. Forbidden booleans must be false and `old_runtime_input_count` must be zero for a clean raw run.
- Old runners may remain for historical reproducibility, but the clean rebuild must not call them. `src/legsa_gins/reporting/by2_algorithm_runner.py` remains explicitly legacy and forbidden to CLEAN3.
- Raw data, frozen assets, historical results, and existing outputs must not be overwritten, moved, or deleted.
- There is no active complete nine-factor FGO claim.

## Current Claim and Execution Boundary

All CLEAN2R2A1 full-minus-strong and RD/SA/RP/HV module-effect numbers are `SUPERSEDED_BY_CLEAN3_PENDING_RERUN`. They may be retained as history but cannot support an active claim, threshold adjustment, or tuning decision.

CLEAN3R2 does not authorize Canonical-541 solving, D01-D60, BY3/XB/PG, DA studies, QM/QA/FGO, kernel comparisons, trace-online use, per-case tuning, paper figures, performance claims, merge, or release tagging. Canonical-541 restart is `NOT_AUTHORIZED`.
